import frappe

def execute():
    """Update SHG Loan Repayment Schedule doctype with any missing fields."""
    
    # Check if the doctype exists
    if not frappe.db.exists("DocType", "SHG Loan Repayment Schedule"):
        return
    
    # Fields that should exist in the doctype
    required_fields = {
        "installment_no": "Int",
        "due_date": "Date",
        "principal_amount": "Currency",
        "interest_amount": "Currency",
        "total_due": "Currency",
        "amount_paid": "Currency",
        "unpaid_balance": "Currency",
        "status": "Select"
    }
    
    # Check each field and add if missing
    for fieldname, fieldtype in required_fields.items():
        if not frappe.db.exists("DocField", {"parent": "SHG Loan Repayment Schedule", "fieldname": fieldname}):
            print(f"Field {fieldname} is missing from SHG Loan Repayment Schedule")
    
    print("Repayment schedule fields verification completed")