import frappe

def execute():
    doctype = "SHG Contribution Invoice"
    fieldname = "company"

    # Skip if the field already exists
    if frappe.db.exists("Custom Field", f"{doctype}-{fieldname}"):
        print("Company field already exists. Skipping.")
        return

    # Create field
    custom_field = frappe.get_doc({
        "doctype": "Custom Field",
        "dt": doctype,
        "fieldname": fieldname,
        "label": "Company",
        "fieldtype": "Link",
        "options": "Company",
        "insert_after": "member",
        "reqd": 1,
        "bold": 1
    })

    custom_field.insert(ignore_permissions=True)
    frappe.db.commit()
    print("Company field added successfully.")