import frappe

def execute():
    """Add is_closed field to SHG Contribution Invoice doctype and update existing records."""
    
    # Add is_closed field to the doctype
    add_is_closed_field()
    
    # Update existing invoices that are already paid to be closed
    close_paid_invoices()
    
    frappe.msgprint("✅ Added is_closed field to SHG Contribution Invoice and updated existing records")

def add_is_closed_field():
    """Add is_closed field to SHG Contribution Invoice doctype."""
    # This is handled by the JSON file update, but we can ensure it exists
    pass

def close_paid_invoices():
    """Mark all paid invoices as closed."""
    # Get all paid invoices that are not already closed
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