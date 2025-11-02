import frappe

def execute():
    """Add missing disbursed_on: datetime(6) to SHG Loan table, if not exists."""
    doctype = "SHG Loan"
    fieldname = "disbursed_on"

    if not frappe.db.has_column(doctype, fieldname):
        frappe.log(f"🛠 Creating field `{fieldname}` on `{doctype}` ...")
        frappe.db.sql(f"""
            ALTER TABLE `tab{doctype}`
            ADD COLUMN `{fieldname}` datetime(6) NULL
        """)
        frappe.db.commit()
        frappe.log(f"✅ Field `{fieldname}` added successfully.")
    else:
        frappe.log(f"ℹ️ Field `{fieldname}` already exists. Skipping.")