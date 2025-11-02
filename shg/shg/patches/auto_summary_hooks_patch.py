import frappe

def _ensure_server_script(name: str, script_type: str, reference_doctype: str | None, script: str, event: str | None = None):
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

def execute():
    """Install doc event + API server scripts that keep Repayment Details in sync without touching your Python modules."""
    # --- 1) SHG Loan — Before Save: compute EMI + totals (if method exists)
    _ensure_server_script(
        name="SHG Loan | before_save | compute details",
        script_type="DocType Event",
        reference_doctype="SHG Loan",
        event="Before Save",
        script="""
# Compute monthly_installment/total_payable if the controller provides it.
if hasattr(doc, "calculate_repayment_details"):
    try:
        result = doc.calculate_repayment_details()
        if isinstance(result, dict):
            if result.get("monthly_installment") is not None:
                doc.monthly_installment = result.get("monthly_installment")
            if result.get("total_payable") is not None:
                doc.total_payable = result.get("total_payable")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Loan before_save calc error")
"""
    )

    # --- 2) SHG Loan — After Insert: build schedule + refresh summary
    _ensure_server_script(
        name="SHG Loan | after_insert | schedule + summary",
        script_type="DocType Event",
        reference_doctype="SHG Loan",
        event="After Insert",
        script="""
# Create schedule once and refresh summary.
try:
    if hasattr(doc, "create_repayment_schedule_if_needed"):
        doc.create_repayment_schedule_if_needed()
    if hasattr(doc, "update_repayment_summary"):
        doc.update_repayment_summary()
except Exception:
    frappe.log_error(frappe.get_traceback(), "SHG Loan after_insert error")
"""
    )

    # --- 3) SHG Loan — On Submit: ensure summary is up to date
    _ensure_server_script(
        name="SHG Loan | on_submit | summary",
        script_type="DocType Event",
        reference_doctype="SHG Loan",
        event="on_submit",
        script="""
try:
    if hasattr(doc, "update_repayment_summary"):
        doc.update_repayment_summary()
except Exception:
    frappe.log_error(frappe.get_traceback(), "SHG Loan on_submit summary error")
"""
    )

    # --- 4) SHG Loan — On Update After Submit: keep summary current
    _ensure_server_script(
        name="SHG Loan | on_update_after_submit | summary",
        script_type="DocType Event",
        reference_doctype="SHG Loan",
        event="on_update_after_submit",
        script="""
try:
    if hasattr(doc, "update_repayment_summary"):
        doc.update_repayment_summary()
except Exception:
    frappe.log_error(frappe.get_traceback(), "SHG Loan on_update_after_submit summary error")
"""
    )

    # --- 5) SHG Loan Repayment — On Submit: update parent loan summary
    _ensure_server_script(
        name="SHG Loan Repayment | on_submit | update loan summary",
        script_type="DocType Event",
        reference_doctype="SHG Loan Repayment",
        event="on_submit",
        script="""
# When a repayment is submitted, refresh the parent loan's summary.
try:
    if doc.loan:
        loan = frappe.get_doc("SHG Loan", doc.loan)
        if hasattr(loan, "update_repayment_summary"):
            loan.update_repayment_summary()
except Exception:
    frappe.log_error(frappe.get_traceback(), "Repayment on_submit summary error")
"""
    )

    # --- 6) SHG Loan Repayment — On Cancel: update parent loan summary
    _ensure_server_script(
        name="SHG Loan Repayment | on_cancel | update loan summary",
        script_type="DocType Event",
        reference_doctype="SHG Loan Repayment",
        event="on_cancel",
        script="""
try:
    if doc.loan:
        loan = frappe.get_doc("SHG Loan", doc.loan)
        if hasattr(loan, "update_repayment_summary"):
            loan.update_repayment_summary()
except Exception:
    frappe.log_error(frappe.get_traceback(), "Repayment on_cancel summary error")
"""
    )

    # --- 7) API endpoint: refresh summary (called from client button)
    _ensure_server_script(
        name="API | shg_loan_refresh_summary",
        script_type="API",
        reference_doctype=None,
        event=None,
        script=r"""
import frappe

@frappe.whitelist()
def shg_loan_refresh_summary(name: str):
    """
    Refresh the repayment summary for a loan and return the updated fields.
    """
    loan = frappe.get_doc("SHG Loan", name)
    if hasattr(loan, "update_repayment_summary"):
        loan.update_repayment_summary()

    # Reload to ensure fresh values
    loan.reload()

    return {
        "monthly_installment": float(loan.monthly_installment or 0),
        "total_payable": float(loan.total_payable or 0),
        "balance_amount": float(loan.balance_amount or 0),
        "total_repaid": float(loan.total_repaid or 0),
        "overdue_amount": float(loan.overdue_amount or 0),
    }
"""
    )
}