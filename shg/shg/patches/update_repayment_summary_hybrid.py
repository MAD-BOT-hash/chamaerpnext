import frappe
from frappe.utils import flt, today, getdate
from typing import Optional

# ---------------------------
# Helpers to create artifacts
# ---------------------------

def _ensure_server_script(name: str, script_type: str, reference_doctype: Optional[str], event: Optional[str], script: str):
    """
    Create/update a Server Script (DocType Event or API).
    Valid script_type: "DocType Event", "API"
    """
    existing = frappe.db.get_value("Server Script", {"name": name}, "name")
    data = {
        "doctype": "Server Script",
        "name": name,
        "script_type": script_type,
        "script": script,
        "disabled": 0,
    }
    if script_type == "DocType Event":
        data["reference_doctype"] = reference_doctype
        data["event"] = event

    if existing:
        doc = frappe.get_doc("Server Script", existing)
        doc.update(data)
        doc.save()
    else:
        frappe.get_doc(data).insert()
    frappe.db.commit()


def _ensure_client_script(name: str, reference_doctype: str, script: str):
    """
    Create/update a Client Script (this must use the Client Script doctype, not Server Script).
    """
    existing = frappe.db.get_value("Client Script", {"name": name}, "name")
    data = {
        "doctype": "Client Script",
        "name": name,
        "dt": reference_doctype,
        "script": script,
        "view": "Form",
        "enabled": 1,
    }
    if existing:
        doc = frappe.get_doc("Client Script", existing)
        doc.update(data)
        doc.save()
    else:
        frappe.get_doc(data).insert()
    frappe.db.commit()


def _allow_update_after_submit_fields():
    """
    Allow summary fields to be updated on submitted loans via Property Setter.
    Idempotent.
    """
    fields = [
        "repayment_start_date",
        "monthly_installment",
        "total_payable",
        "balance_amount",
        "total_repaid",
        "overdue_amount",
        "last_repayment_date",
        "next_due_date",
    ]
    for fieldname in fields:
        if not frappe.db.exists(
            "Property Setter",
            {"doc_type": "SHG Loan", "field_name": fieldname, "property": "allow_on_submit"},
        ):
            frappe.get_doc({
                "doctype": "Property Setter",
                "doc_type": "SHG Loan",
                "doctype_or_field": "DocField",
                "field_name": fieldname,
                "property": "allow_on_submit",
                "value": "1",
                "property_type": "Check",
            }).insert()
    frappe.db.commit()


# ----------------------------------------
# Pure function: compute summary for a loan
# ----------------------------------------

def _compute_summary(loan_doc) -> dict:
    """
    Compute totals using whichever schedule the site actually has:
    - Embedded child table: loan_doc.repayment_schedule (common)
    - Standalone rows in 'SHG Loan Repayment Schedule' linked via 'loan' or 'parent'
    Returns a dict with all summary numbers and date hints.
    """
    rows = []

    # 1) Embedded table (if defined on the DocType)
    if hasattr(loan_doc, "repayment_schedule") and loan_doc.get("repayment_schedule"):
        for r in loan_doc.repayment_schedule:
            rows.append({
                "due_date": r.get("due_date"),
                "total_payment": flt(r.get("total_payment")),
                "amount_paid": flt(r.get("amount_paid")),
                "unpaid_balance": flt(r.get("unpaid_balance")),
                "status": r.get("status"),
            })

    # 2) Standalone schedule fallback
    if not rows and frappe.db.table_exists("SHG Loan Repayment Schedule"):
        # Try loan field
        q = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={"loan": loan_doc.name},
            fields=["due_date", "total_payment", "amount_paid", "unpaid_balance", "status"],
            order_by="due_date asc",
        )
        if not q:
            # Try parent linkage (some sites store parent/parenttype)
            q = frappe.get_all(
                "SHG Loan Repayment Schedule",
                filters={"parent": loan_doc.name},
                fields=["due_date", "total_payment", "amount_paid", "unpaid_balance", "status"],
                order_by="due_date asc",
            )
        for r in q or []:
            rows.append({
                "due_date": r.get("due_date"),
                "total_payment": flt(r.get("total_payment")),
                "amount_paid": flt(r.get("amount_paid")),
                "unpaid_balance": flt(r.get("unpaid_balance")),
                "status": r.get("status"),
            })

    # If still nothing, heuristics from header
    total_payable = flt(loan_doc.get("total_payable"))
    monthly = flt(loan_doc.get("monthly_installment"))
    months = int(loan_doc.get("loan_period_months") or 0)
    if not total_payable and monthly and months:
        total_payable = monthly * months

    total_paid = 0.0
    overdue_amt = 0.0
    last_paid_date = None
    next_due = None

    if rows:
        total_payable = sum(flt(r["total_payment"]) for r in rows) or total_payable
        total_paid = sum(flt(r["amount_paid"]) for r in rows)
        # Overdue detection
        today_d = getdate(today())
        for r in rows:
            due = getdate(r["due_date"]) if r["due_date"] else None
            if due and due <= today_d and flt(r["unpaid_balance"]) > 0:
                overdue_amt += flt(r["unpaid_balance"])
        # last & next
        paid_like = [r for r in rows if flt(r["amount_paid"]) > 0]
        if paid_like:
            last_paid_date = max([getdate(rr["due_date"]) for rr in paid_like if rr["due_date"]])
        future_due = [r for r in rows if r["due_date"] and flt(r["unpaid_balance"]) > 0]
        if future_due:
            next_due = min([getdate(rr["due_date"]) for rr in future_due])

    balance = flt(total_payable) - flt(total_paid)
    if balance < 0:
        balance = 0.0

    return {
        "repayment_start_date": loan_doc.get("repayment_start_date"),
        "monthly_installment": monthly or loan_doc.get("monthly_installment"),
        "total_payable": flt(total_payable),
        "total_repaid": flt(total_paid),
        "balance_amount": flt(balance),
        "overdue_amount": flt(overdue_amt),
        "last_repayment_date": last_paid_date,
        "next_due_date": next_due,
    }


# ----------------------------
# API server script (callable)
# ----------------------------

API_SCRIPT = """
import frappe
from frappe.utils import flt, today, getdate

def _compute_summary(loan_doc):
    rows = []
    if hasattr(loan_doc, "repayment_schedule") and loan_doc.get("repayment_schedule"):
        for r in loan_doc.repayment_schedule:
            rows.append({
                "due_date": r.get("due_date"),
                "total_payment": flt(r.get("total_payment")),
                "amount_paid": flt(r.get("amount_paid")),
                "unpaid_balance": flt(r.get("unpaid_balance")),
                "status": r.get("status"),
            })
    if not rows and frappe.db.table_exists("SHG Loan Repayment Schedule"):
        q = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={"loan": loan_doc.name},
            fields=["due_date", "total_payment", "amount_paid", "unpaid_balance", "status"],
            order_by="due_date asc",
        )
        if not q:
            q = frappe.get_all(
                "SHG Loan Repayment Schedule",
                filters={"parent": loan_doc.name},
                fields=["due_date", "total_payment", "amount_paid", "unpaid_balance", "status"],
                order_by="due_date asc",
            )
        for r in q or []:
            rows.append({
                "due_date": r.get("due_date"),
                "total_payment": flt(r.get("total_payment")),
                "amount_paid": flt(r.get("amount_paid")),
                "unpaid_balance": flt(r.get("unpaid_balance")),
                "status": r.get("status"),
            })

    total_payable = flt(loan_doc.get("total_payable"))
    monthly = flt(loan_doc.get("monthly_installment"))
    months = int(loan_doc.get("loan_period_months") or 0)
    if not total_payable and monthly and months:
        total_payable = monthly * months

    total_paid = 0.0
    overdue_amt = 0.0
    last_paid_date = None
    next_due = None

    if rows:
        total_payable = sum(flt(r["total_payment"]) for r in rows) or total_payable
        total_paid = sum(flt(r["amount_paid"]) for r in rows)
        today_d = getdate(today())
        for r in rows:
            due = getdate(r["due_date"]) if r["due_date"] else None
            if due and due <= today_d and flt(r["unpaid_balance"]) > 0:
                overdue_amt += flt(r["unpaid_balance"])
        paid_like = [r for r in rows if flt(r["amount_paid"]) > 0]
        if paid_like:
            last_paid_date = max([getdate(rr["due_date"]) for rr in paid_like if rr["due_date"]])
        future_due = [r for r in rows if r["due_date"] and flt(r["unpaid_balance"]) > 0]
        if future_due:
            next_due = min([getdate(rr["due_date"]) for rr in future_due])

    balance = flt(total_payable) - flt(total_paid)
    if balance < 0: balance = 0.0

    return {
        "monthly_installment": monthly or loan_doc.get("monthly_installment"),
        "total_payable": flt(total_payable),
        "total_repaid": flt(total_paid),
        "balance_amount": flt(balance),
        "overdue_amount": flt(overdue_amt),
        "last_repayment_date": last_paid_date,
        "next_due_date": next_due,
    }

@frappe.whitelist()
def refresh_repayment_summary(loan_name: str):
    loan = frappe.get_doc("SHG Loan", loan_name)
    summary = _compute_summary(loan)
    loan.flags.ignore_validate_update_after_submit = True
    # Persist
    for k, v in summary.items():
        loan.db_set(k, v)
    loan.reload()
    return summary
"""

# -----------------------------------------------------
# DocType Event: keep in sync on loan update/submit
# -----------------------------------------------------

DOC_EVENT_SCRIPT = """
# Called when SHG Loan is updated (draft or submitted) or on submit.
frappe.call("shg.shg.patches.update_repayment_summary_hybrid.refresh_summary_for_server", {"loan_name": doc.name})
"""

# This function is called by the doc event script above (kept in this patch file).
@frappe.whitelist()
def refresh_summary_for_server(loan_name: str):
    # Delegate to the API server script we installed, so both paths use the same code
    return frappe.get_attr("server_script.refresh_repayment_summary")(loan_name=loan_name)  # type: ignore


# -----------------------------------------------------
# Client Script: Button + Header indicator
# -----------------------------------------------------

CLIENT_SCRIPT = r"""
frappe.ui.form.on('SHG Loan', {
    refresh(frm) {
        // Button
        if (!frm.is_new()) {
            frm.add_custom_button('🔄 Refresh Summary', async () => {
                await frappe.call({
                    method: "server_script.refresh_repayment_summary",
                    args: { loan_name: frm.doc.name },
                    freeze: true,
                    freeze_message: "Recomputing schedule totals...",
                    callback: (r) => {
                        frm.reload_doc();
                        frappe.show_alert({message: "Repayment summary refreshed.", indicator: "green"});
                    }
                });
            });
        }

        // Tiny header indicator
        const outstanding = frm.doc.balance_amount || 0.0;
        const text = `Outstanding: ${format_currency(outstanding, frappe.defaults.get_default("currency") || "KES")}`;
        frm.dashboard.set_headline_alert(text, "blue");
    }
});
"""


# -------------------------
# Backfill for existing data
# -------------------------

def _backfill_existing():
    names = [d.name for d in frappe.get_all("SHG Loan", fields=["name"])]
    for name in names:
        try:
            loan = frappe.get_doc("SHG Loan", name)
            summary = _compute_summary(loan)
            loan.flags.ignore_validate_update_after_submit = True
            for k, v in summary.items():
                loan.db_set(k, v, update_modified=False)
        except Exception:
            frappe.log_error(f"Failed to backfill loan {name}", frappe.get_traceback())
    frappe.db.commit()


def execute():
    """Run all patch steps."""
    _allow_update_after_submit_fields()
    _ensure_server_script(
        name="SHG Loan | API — refresh_repayment_summary",
        script_type="API",
        reference_doctype=None,
        event=None,
        script=API_SCRIPT,
    )
    _ensure_server_script(
        name="SHG Loan | After Save/Submit — refresh_repayment_summary",
        script_type="DocType Event",
        reference_doctype="SHG Loan",
        event="on_update",
        script=DOC_EVENT_SCRIPT,
    )
    _ensure_client_script(
        name="SHG Loan | Refresh Summary Button",
        reference_doctype="SHG Loan",
        script=CLIENT_SCRIPT,
    )
    _backfill_existing()