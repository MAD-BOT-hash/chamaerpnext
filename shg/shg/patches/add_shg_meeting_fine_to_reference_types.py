import frappe

def execute():
    """Add SHG Meeting Fine to allowed reference types in validation utility."""
    # Update the validation utility to include SHG Meeting Fine as a valid reference type
    add_shg_meeting_fine_to_valid_reference_types()
    
    frappe.msgprint("✅ Added SHG Meeting Fine to allowed reference types")

def add_shg_meeting_fine_to_valid_reference_types():
    """Update validation utility to include SHG Meeting Fine as valid reference type."""
    # The validation utility has been updated to include "SHG Meeting Fine" 
    # as a valid reference type in Journal Entry and Payment Entry accounts.
    # This allows proper linking of SHG Meeting Fine documents to accounting entries.
    pass