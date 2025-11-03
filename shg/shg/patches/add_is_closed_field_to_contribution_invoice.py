import frappe

def execute():
    """Add is_closed field to SHG Contribution Invoice doctype and update existing records."""
    
    # Add is_closed field using Custom Field if it doesn't exist in standard doctype
    add_is_closed_custom_field()
    
    # Update existing invoices that are already paid to be closed
    close_paid_invoices()
    
    frappe.msgprint("✅ Added is_closed field to SHG Contribution Invoice and updated existing records")

def add_is_closed_custom_field():
    """Add is_closed field as a custom field to SHG Contribution Invoice doctype."""
    # Check if custom field already exists
    if not frappe.db.exists("Custom Field", {"dt": "SHG Contribution Invoice", "fieldname": "is_closed"}):
        custom_field = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "SHG Contribution Invoice",
            "fieldname": "is_closed",
            "label": "Is Closed",
            "fieldtype": "Check",
            "default": "0",
            "read_only": 1,
            "insert_after": "posted_to_contribution"
        })
        custom_field.insert(ignore_permissions=True)
        frappe.msgprint("Added is_closed custom field to SHG Contribution Invoice")

def close_paid_invoices():
    """Mark all paid invoices as closed."""
    # Get all paid invoices that are not already closed
    try:
        paid_invoices = frappe.get_all("SHG Contribution Invoice", 
                                      filters={"status": "Paid", "is_closed": 0},
                                      fields=["name"])
        
        for invoice in paid_invoices:
            try:
                frappe.db.set_value("SHG Contribution Invoice", invoice.name, "is_closed", 1)
                frappe.logger().info(f"Marked invoice {invoice.name} as closed")
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Failed to close invoice {invoice.name}")
        
        frappe.db.commit()
    except Exception as e:
        # Handle case where is_closed column doesn't exist yet
        frappe.log_error(frappe.get_traceback(), "Failed to query paid invoices - column may not exist yet")