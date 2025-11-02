import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _ensure_allow_update_after_submit(doctype, fields):
    """Enable allow_update_after_submit for specific fields in a DocType."""
    meta = frappe.get_meta(doctype)
    for fieldname in fields:
        df = meta.get_field(fieldname)
        if df and not df.allow_on_submit:
            df.allow_on_submit = 1
            df.save()
    frappe.db.commit()


def _ensure_server_script(name, script_type, reference_doctype, script, event=None):
    """Create or update a server script."""
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
    """Patch to allow repayment updates on submitted SHG Loans and add auto-hooks."""

    # 1️⃣ Allow key fields on SHG Loan to be updated after submit
    frappe.msgprint("🔓 Enabling update after submit for SHG Loan fields...")
    _ensure_allow_update_after_submit(
        "SHG Loan",
        [
            "total_repaid",
            "balance_amount",
            "overdue_amount",
            "journal_entry",
            "next_due_date",
        ],
    )

    # 2️⃣ Allow child table fields to update after submit
    frappe.msgprint("🔧 Allowing update after submit for repayment schedule child table...")
    _ensure_allow_update_after_submit(
        "SHG Loan Repayment Schedule",
        ["amount_paid", "balance", "status"],
    )

    # 3️⃣ Create auto-sync Server Script for recalculating repayment summary on Payment Entry submit
    repayment_sync_script = """
loan_name = doc.reference_name
if doc.payment_type in ["Receive", "Pay"] and loan_name:
    loan = frappe.get_doc("SHG Loan", loan_name)
    loan.flags.ignore_validate_update_after_submit = True
    loan.refresh_from_db()
    frappe.call("shg.shg.doctype.shg_loan.shg_loan.refresh_repayment_summary", loan_name=loan_name)
"""
    _ensure_server_script(
        name="Sync SHG Loan on Payment Entry Submit",
        script_type="DocType Event",
        reference_doctype="Payment Entry",
        script=repayment_sync_script,
        event="on_submit",
    )

    # 4️⃣ Add form indicator logic to SHG Loan
    frappe.msgprint("🎨 Adding loan submission indicator logic via Server Script...")
    form_indicator_script = """
if doc.docstatus == 1:
    frappe.show_alert({
        'message': `🔒 Loan Submitted — Updates are restricted except for repayment-related fields.`,
        'indicator': 'orange'
    })
"""
    _ensure_server_script(
        name="SHG Loan Form Indicator",
        script_type="Client",
        reference_doctype="SHG Loan",
        script=form_indicator_script,
    )

    frappe.msgprint("✅ Patch work completed successfully!")