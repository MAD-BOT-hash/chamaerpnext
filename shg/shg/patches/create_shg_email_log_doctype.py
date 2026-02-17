import frappe

def execute():
    """Create SHG Email Log doctype if it doesn't exist"""
    try:
        # Check if the doctype already exists
        if not frappe.db.exists("DocType", "SHG Email Log"):
            # Create the doctype
            doc = frappe.new_doc("DocType")
            doc.update({
                "name": "SHG Email Log",
                "module": "SHG",
                "custom": 0,
                "autoname": "SHG-EMAIL-LOG-.#####",
                "doctype": "DocType",
                "engine": "InnoDB",
                "track_changes": 1,
                "is_submittable": 0,
                "is_tree": 0,
                "istable": 0
            })
            doc.insert()
            print("Created SHG Email Log doctype")
        else:
            print("SHG Email Log doctype already exists")
        
        # Also reload the doctype to make sure it's properly registered
        frappe.reload_doc("shg", "doctype", "shg_email_log")
        print("Reloaded SHG Email Log doctype")
        
    except Exception as e:
        frappe.log_error(f"Error creating SHG Email Log doctype: {str(e)}")
        raise