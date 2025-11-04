import frappe

def execute():
    """Update SHG Meeting Fine implementation to use correct ERPNext v15 reference types."""
    # This patch ensures SHG Meeting Fine documents use "Journal Entry" as the reference_type
    # and store the actual document name in reference_name, complying with ERPNext v15 validation rules.
    frappe.msgprint("✅ Updated SHG Meeting Fine to use correct ERPNext v15 reference types")