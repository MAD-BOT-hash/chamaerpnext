import frappe

def execute():
    """
    Create default SHG Contribution Types if they don't exist.
    """
    # List of default contribution types to create
    default_types = [
        {
            "doctype": "SHG Contribution Type",
            "contribution_type_name": "Regular Weekly",
            "description": "Regular weekly contribution from members",
            "default_amount": 500,
            "frequency": "Weekly",
            "enabled": 1
        },
        {
            "doctype": "SHG Contribution Type",
            "contribution_type_name": "Regular Monthly",
            "description": "Regular monthly contribution from members",
            "default_amount": 2000,
            "frequency": "Monthly",
            "enabled": 1
        },
        {
            "doctype": "SHG Contribution Type",
            "contribution_type_name": "Special Assessment",
            "description": "Special assessment for specific needs",
            "frequency": "Monthly",
            "enabled": 1
        },
        {
            "doctype": "SHG Contribution Type",
            "contribution_type_name": "Fines",
            "description": "Fines collected during meetings",
            "frequency": "Monthly",
            "enabled": 1
        }
    ]
    
    for type_data in default_types:
        # Check if the contribution type already exists
        if not frappe.db.exists("SHG Contribution Type", type_data["contribution_type_name"]):
            try:
                # Create the contribution type
                doc = frappe.get_doc(type_data)
                doc.insert(ignore_permissions=True)
                frappe.msgprint(f"Created default contribution type: {type_data['contribution_type_name']}")
            except Exception as e:
                frappe.log_error(f"Failed to create contribution type {type_data['contribution_type_name']}: {str(e)}")
        else:
            frappe.msgprint(f"Contribution type already exists: {type_data['contribution_type_name']}")
    
    frappe.db.commit()