import frappe

def execute():
    doctype = "SHG Contribution Invoice"
    fieldname = "company"

    # 1) Add field if missing
    if not frappe.db.exists("Custom Field", f"{doctype}-{fieldname}"):
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
        print("[SHG] Added Company field to SHG Contribution Invoice.")

    # 2) Pull default company from SHG Settings
    settings_company = frappe.db.get_single_value("SHG Settings", "company")
    if not settings_company:
        frappe.throw("Default Company is not set in SHG Settings.")

    # 3) Update all existing documents missing this field
    frappe.db.sql(f"""
        UPDATE `tab{doctype}`
        SET company = %s
        WHERE (company IS NULL OR company = '')
    """, settings_company)

    frappe.db.commit()
    print(f"[SHG] Updated existing {doctype} records with default company: {settings_company}")