import frappe

def execute():
    """Fix loan schedule permissions to allow updates after submission."""
    
    # Enable allow_on_submit for repayment_schedule field
    update_repayment_schedule_field()
    
    frappe.msgprint("✅ Loan schedule permissions updated")

def update_repayment_schedule_field():
    """Enable allow_on_submit for repayment_schedule field in SHG Loan doctype."""
    # Check if it's a standard field
    standard_field = frappe.db.get_value("DocField", 
        {"parent": "SHG Loan", "fieldname": "repayment_schedule"}, "name")
    if standard_field:
        frappe.db.set_value("DocField", standard_field, "allow_on_submit", 1)
    else:
        # Check if it's a custom field
        custom_field = frappe.db.exists("Custom Field", 
            {"dt": "SHG Loan", "fieldname": "repayment_schedule"})
        if custom_field:
            frappe.db.set_value("Custom Field", custom_field, "allow_on_submit", 1)