import frappe

def execute():
    """Update field permissions for SHG Loan and SHG Loan Repayment Schedule doctypes."""
    
    # Update SHG Loan fields to allow updates after submit
    update_shg_loan_field_permissions()
    
    # Update SHG Loan Repayment Schedule fields to allow updates after submit
    update_shg_loan_repayment_schedule_field_permissions()
    
    frappe.msgprint("Updated field permissions for loan doctypes")

def update_shg_loan_field_permissions():
    """Update SHG Loan fields that need allow_on_submit permission."""
    fields_to_update = [
        "last_repayment_date",
        "next_due_date"
    ]
    
    for fieldname in fields_to_update:
        # Check if it's a standard field
        standard_field = frappe.db.get_value("DocField", 
            {"parent": "SHG Loan", "fieldname": fieldname}, "name")
        if standard_field:
            frappe.db.set_value("DocField", standard_field, "allow_on_submit", 1)
        else:
            # Check if it's a custom field
            custom_field = frappe.db.exists("Custom Field", 
                {"dt": "SHG Loan", "fieldname": fieldname})
            if custom_field:
                frappe.db.set_value("Custom Field", custom_field, "allow_on_submit", 1)

def update_shg_loan_repayment_schedule_field_permissions():
    """Update SHG Loan Repayment Schedule fields that need allow_on_submit permission."""
    fields_to_update = [
        "amount_paid",
        "unpaid_balance",
        "loan_balance",
        "status",
        "payment_entry",
        "actual_payment_date",
        "reversed"
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