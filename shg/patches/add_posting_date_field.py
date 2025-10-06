import frappe

def execute():
    """Add posting_date field to transactional doctypes for ERPNext compatibility"""
    
    # List of doctypes that need posting_date field
    doctypes = ["SHG Loan", "SHG Contribution", "SHG Loan Repayment"]
    
    for doctype in doctypes:
        # Check if posting_date field already exists
        if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": "posting_date"}):
            # Create the posting_date custom field
            custom_field = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": doctype,
                "label": "Posting Date",
                "fieldname": "posting_date",
                "fieldtype": "Date",
                "insert_after": "member",
                "reqd": 1,
                "default": "Today",
                "description": "Date when the transaction was posted"
            })
            custom_field.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"Added posting_date field to {doctype}")
        else:
            print(f"posting_date field already exists in {doctype}")