import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    """Add custom fields to Sales Invoice for SHG integration"""
    
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "shg_contribution_type",
                "fieldtype": "Link",
                "label": "SHG Contribution Type",
                "options": "SHG Contribution Type",
                "insert_after": "customer_name",
                "read_only": 1
            }
        ]
    }
    
    create_custom_fields(custom_fields, update=True)
    
    # Also create the default "SHG Contribution" item if it doesn't exist
    if not frappe.db.exists("Item", "SHG Contribution"):
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": "SHG Contribution",
            "item_name": "SHG Contribution",
            "description": "Self Help Group Contribution",
            "item_group": "Services",  # You may need to adjust this based on your setup
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "include_item_in_manufacturing": 0
        })
        item.insert()