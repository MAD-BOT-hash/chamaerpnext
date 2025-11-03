import frappe
from frappe.model.utils.rename_field import rename_field


def _ensure_server_script(name: str, script_type: str, reference_doctype: str | None, script: str, event: str | None = None):
    """Insert or update a Server Script safely."""
    existing = frappe.db.get_value("Server Script", name, "name")
    data = {
        "doctype": "Server Script",
        "name": name,
        "script_type": script_type,
        "script": script,
        "disabled": 0
    }
    if script_type == "DocType Event":
        if not reference_doctype or not event:
            frappe.throw(f"DocType Event scripts require reference_doctype and event. Missing for {name}")
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
    """Install doc event + API server scripts that keep Repayment Details in sync without touching Python modules."""

    # --- 1) SHG Loan — Before Save: compute EMI + totals
    _ensure_server_script(
        name="SHG Loan | before_save | auto_compute_disbursement_values",
        script_type="DocType Event",
        reference_doctype="SHG Loan",
        event="before_save",
        script="""
frappe.msgprint("Auto-updating EMI, totals...")

# Use a safer approach instead of hasattr for Server Script compatibility
try:
    # Try to get the method - if it doesn't exist, this will raise an AttributeError
    doc.update_repayment_summary
    method_exists = True
except AttributeError:
    method_exists = False

if method_exists and callable(doc.update_repayment_summary):
    doc.update_repayment_summary()
"""
    )

    # --- 2) SHG Loan Repayment — After Submit: update member summaries
    _ensure_server_script(
        name="SHG Loan Repayment | on_submit | update_summary",
        script_type="DocType Event",
        reference_doctype="SHG Loan Repayment",
        event="on_submit",
        script="""
# Call SHG Loan's internal method to refresh totals after repayment
loan_id = doc.loan
if loan_id:
    loan = frappe.get_doc("SHG Loan", loan_id)
    # Use a safer approach instead of hasattr for Server Script compatibility
    try:
        # Try to get the method - if it doesn't exist, this will raise an AttributeError
        loan.update_repayment_summary
        method_exists = True
    except AttributeError:
        method_exists = False
    
    if method_exists:
        loan.update_repayment_summary()
        loan.save()
"""
    )

    # --- 3) SHG Loan — API Script for refresh button — called via Client Script
    _ensure_server_script(
        name="SHG Loan | API | trigger_repayment_refresh",
        script_type="API",
        reference_doctype=None,
        script="""
import frappe

@frappe.whitelist()
def refresh_repayment_summary(loan_id):
    loan = frappe.get_doc("SHG Loan", loan_id)
    # Use a safer approach instead of hasattr for Server Script compatibility
    try:
        # Try to get the method - if it doesn't exist, this will raise an AttributeError
        loan.update_repayment_summary
        method_exists = True
    except AttributeError:
        method_exists = False
    
    if method_exists:
        loan.update_repayment_summary()
        loan.save()
    return {"ok": True}
"""
    )

    frappe.log("✅ Installed/Updated SHG Repayment Hooks Server Scripts")