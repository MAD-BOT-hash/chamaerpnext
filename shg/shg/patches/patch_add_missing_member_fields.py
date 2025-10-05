import frappe

def execute():
    """
    Add missing loan_eligibility_flag and has_overdue_loans columns to SHG Member table
    """
    print("Adding missing columns to SHG Member table...")
    
    # Check if columns exist, if not add them
    columns = frappe.db.get_table_columns("SHG Member")
    
    if "loan_eligibility_flag" not in columns:
        frappe.db.add_column("SHG Member", "loan_eligibility_flag", "int(1) DEFAULT 1")
        print("Added loan_eligibility_flag column")
    
    if "has_overdue_loans" not in columns:
        frappe.db.add_column("SHG Member", "has_overdue_loans", "int(1) DEFAULT 0")
        print("Added has_overdue_loans column")
        
    print("Completed adding missing columns to SHG Member table")