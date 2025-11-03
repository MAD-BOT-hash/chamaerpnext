import frappe

def execute():
    """Fix loan schedule permissions to allow updates after submission."""
    
    # Enable allow_on_submit for repayment_schedule field
    update_repayment_schedule_field()
    
    # Ensure child table fields have proper permissions
    update_repayment_schedule_child_fields()
    
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

def update_repayment_schedule_child_fields():
    """Ensure child table fields have proper permissions."""
    # Fields that need allow_on_submit in the child table
    fields_to_update = [
        "amount_paid",
        "unpaid_balance",
        "status",
        "actual_payment_date"
    ]
    
    for fieldname in fields_to_update:
        # Check if it's a standard field
        standard_field = frappe.db.get_value("DocField", 
            {"parent": "SHG Loan Repayment Schedule", "fieldname": fieldname}, "name")
        if standard_field:
            frappe.db.set_value("DocField", standard_field, "allow_on_submit", 1)
        else:
            # Check if it's a custom field
            custom_field = frappe.db.exists("Custom Field", 
                {"dt": "SHG Loan Repayment Schedule", "fieldname": fieldname})
            if custom_field:
                frappe.db.set_value("Custom Field", custom_field, "allow_on_submit", 1)