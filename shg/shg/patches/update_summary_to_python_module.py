import frappe

MODULE_PATH = "shg/shg/doctype/shg_loan/api.py"
MODULE_CONTENT = """
import frappe
from frappe.utils import flt

@frappe.whitelist()
def refresh_repayment_summary(loan_name: str):
    \"\"\"Refresh repayment summary and detail values for SHG Loan specified by loan_name.\"\"\"
    # Validate input
    if not loan_name:
        frappe.throw("Loan name is required", title="Invalid Input")
        
    try:
        loan = frappe.get_doc("SHG Loan", loan_name)
    except frappe.DoesNotExistError:
        frappe.throw(f"Loan '{loan_name}' not found", title="Loan Not Found")

    # Ensure doc is fresh
    loan.reload()

    # If summary method exists in class, use it
    # Use a safer approach instead of hasattr for Server Script compatibility
    try:
        # Try to get the method - if it doesn't exist, this will raise an AttributeError
        loan.update_repayment_summary
        method_exists = True
    except AttributeError:
        method_exists = False
    
    if method_exists:
        loan.update_repayment_summary()
        loan.save(ignore_permissions=True)
        frappe.db.commit()
        return {"status": "success"}

    # Fallback: update summary manually from child repayment table
    total_principal = 0
    total_interest = 0
    total_paid = 0
    overdue_amount = 0

    for row in loan.get("repayment_schedule", []):
        total_principal += flt(row.principal_component)
        total_interest += flt(row.interest_component)
        total_paid += flt(row.amount_paid)

        if row.status and row.status.lower() == "overdue":
            overdue_amount += flt(row.unpaid_balance)

    loan.total_principal = total_principal
    loan.total_interest = total_interest
    loan.total_paid = total_paid
    loan.overdue_amount = overdue_amount
    loan.balance_amount = (total_principal + total_interest) - total_paid

    loan.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {"status": "success"}
"""

CLIENT_SCRIPT_NAME = "SHG Loan | Refresh Summary Button"
CLIENT_SCRIPT_CONTENT = """
frappe.ui.form.on("SHG Loan", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("📊 Recalculate Loan Summary (SHG)", () => {
                frappe.call({
                    method: "shg.shg.doctype.shg_loan.api.refresh_repayment_summary",
                    args: { loan_name: frm.doc.name },
                    callback(r) {
                        if (r.message && r.message.status === "success") {
                            frm.reload_doc();
                            frappe.msgprint("📊 Repayment Summary Refreshed Successfully");
                        }
                    }
                });
            }, "Actions");
            
            // Optional: small header indicator on refresh
            if (frm.doc.balance_amount) {
                frm.dashboard.set_headline(
                    `Outstanding: ${format_currency(frm.doc.balance_amount, "KES")}`
                );
            }
        }
    }
});
"""

OLD_SERVER_SCRIPT_NAME = "SHG Loan | refresh_repayment_summary"


def _write_python_module():
    """Create or overwrite the API module under the SHG Loan DocType folder."""
    import os

    module_path = frappe.get_app_path("shg", MODULE_PATH)
    os.makedirs(os.path.dirname(module_path), exist_ok=True)

    with open(module_path, "w") as f:
        f.write(MODULE_CONTENT.strip())

    frappe.msgprint(f"✅ Python module created at {module_path}")


def _disable_old_server_script():
    """Disable the outdated Server Script version if exists."""
    if frappe.db.exists("Server Script", OLD_SERVER_SCRIPT_NAME):
        doc = frappe.get_doc("Server Script", OLD_SERVER_SCRIPT_NAME)
        doc.disabled = 1
        doc.save(ignore_permissions=True)
        frappe.msgprint(f"⚠️ Disabled old Server Script: {OLD_SERVER_SCRIPT_NAME}")


def _ensure_client_script():
    """Create a new client script for SHG Loan to add refresh button."""
    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        frappe.msgprint("🔃 Client Script already exists — skipping create.")
        return

    client_script = frappe.get_doc({
        "doctype": "Client Script",
        "name": CLIENT_SCRIPT_NAME,
        "dt": "SHG Loan",
        "script": CLIENT_SCRIPT_CONTENT,
        "enabled": 1
    })
    client_script.insert(ignore_permissions=True)
    frappe.msgprint("✅ Installed new Client Script for refresh button.")


def execute():
    """Main migration entrypoint."""
    _write_python_module()
    _disable_old_server_script()
    _ensure_client_script()
    frappe.db.commit()