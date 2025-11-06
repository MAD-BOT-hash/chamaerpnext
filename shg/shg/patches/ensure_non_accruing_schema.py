import frappe
from frappe.database.schema import add_column


def execute():
    """
    Ensure required fields for Non-Accruing contributions exist in doctypes and UI.
    - Adds DB columns if not present
    - Creates DocField entries for UI-level access
    """

    doctypes_to_update = {
        "SHG Contribution Type": [
            {"fieldname": "is_non_accruing", "label": "Is Non-Accruing", "fieldtype": "Check", "default": 0},
        ],
        "SHG Contribution": [
            {"fieldname": "is_non_accruing", "label": "Is Non-Accruing", "fieldtype": "Check", "default": 0},
            {"fieldname": "contributor", "label": "Contributor", "fieldtype": "Link", "options": "SHG Member"},
            {"fieldname": "beneficiary", "label": "Beneficiary", "fieldtype": "Link", "options": "SHG Member"},
        ],
    }

    for doctype, fields in doctypes_to_update.items():
        meta = frappe.get_meta(doctype)

        for field in fields:
            fieldname = field["fieldname"]

            # 1. Ensure column exists in DB
            if not frappe.db.has_column(doctype, fieldname):
                frappe.logger().info(f"Adding DB column '{fieldname}' to '{doctype}'")
                add_column(
                    doctype,
                    fieldname,
                    field["fieldtype"],
                    options=field.get("options"),
                )

            # 2. Ensure field exists in DocType (UI)
            if not meta.get_field(fieldname):
                frappe.logger().info(f"Creating DocField '{fieldname}' in '{doctype}'")
                df = frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": doctype,
                    "fieldname": fieldname,
                    "label": field["label"],
                    "fieldtype": field["fieldtype"],
                    "options": field.get("options"),
                    "default": field.get("default"),
                    "insert_after": "modified_by",  # place after system field
                })
                df.insert(ignore_permissions=True)
                frappe.db.commit()

    frappe.logger().info("Non-accruing fields ensured for SHG Contribution and SHG Contribution Type.")