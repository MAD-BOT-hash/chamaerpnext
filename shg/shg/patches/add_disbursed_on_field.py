import frappe
from frappe.database.schema import add_column

def execute():
    """Add missing disbursed_on field to SHG Loan DocType (if not already present)."""
    if not frappe.db.has_column("SHG Loan", "disbursed_on"):
        frappe.log("🛠 Adding missing column `disbursed_on` to SHG Loan...")
        add_column("SHG Loan", "disbursed_on", "datetime")
        frappe.db.commit()
        frappe.log("✅ Field `disbursed_on` added successfully.")
    else:
        frappe.log("ℹ️ Field `disbursed_on` already exists. No action taken.")