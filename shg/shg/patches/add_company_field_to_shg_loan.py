import frappe

def execute():
    if not frappe.db.exists("Custom Field", {"dt": "SHG Loan", "fieldname": "company"}):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "SHG Loan",
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "insert_after": "loan_amount",
            "reqd": 1
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        print("✅ Added Company field to SHG Loan DocType")