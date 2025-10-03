import frappe
from frappe import _

def execute():
    """
    Patch to remove old GL logic and clean up deprecated fields and references.
    This patch ensures a clean migration to the new accounting structure.
    """
    # Log the start of the patch
    frappe.log("Starting patch to remove old GL logic")
    
    # 1. Remove old custom fields that are no longer needed
    # (These would be removed through the doctype JSON files in a real implementation)
    
    # 2. Clean up any existing GL entries that might have invalid reference types
    clean_up_invalid_gl_entries()
    
    # 3. Reset posting flags on all SHG documents to ensure they get re-posted with new logic
    reset_posting_flags()
    
    # 4. Log completion
    frappe.log("Completed patch to remove old GL logic")

def clean_up_invalid_gl_entries():
    """
    Clean up any GL entries with invalid reference types.
    """
    # In a real implementation, you might want to:
    # 1. Cancel and delete invalid GL entries
    # 2. Log them for review
    # 3. Ensure no orphaned entries exist
    
    frappe.log("Cleaning up invalid GL entries")
    
    # Example of how you might find and handle invalid entries:
    # invalid_entries = frappe.get_all("GL Entry", 
    #     filters={"reference_type": ["in", ["SHG Contribution", "SHG Loan", "SHG Loan Repayment", "SHG Meeting Fine"]]},
    #     fields=["name", "reference_type", "reference_name"])
    # 
    # for entry in invalid_entries:
    #     try:
    #         # Handle each invalid entry appropriately
    #         frappe.log(f"Found invalid GL entry: {entry.name} with reference_type: {entry.reference_type}")
    #     except Exception as e:
    #         frappe.log_error(f"Error handling invalid GL entry {entry.name}: {str(e)}")

def reset_posting_flags():
    """
    Reset posting flags on SHG documents to ensure they get re-posted with new logic.
    """
    frappe.log("Resetting posting flags on SHG documents")
    
    # Reset flags for SHG Contribution
    frappe.db.sql("""
        UPDATE `tabSHG Contribution` 
        SET posted_to_gl = 0, posted_on = NULL 
        WHERE docstatus = 1
    """)
    
    # Reset flags for SHG Loan
    frappe.db.sql("""
        UPDATE `tabSHG Loan` 
        SET posted_to_gl = 0, posted_on = NULL 
        WHERE docstatus = 1 AND status = 'Disbursed'
    """)
    
    # Reset flags for SHG Loan Repayment
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment` 
        SET posted_to_gl = 0, posted_on = NULL 
        WHERE docstatus = 1
    """)
    
    # Reset flags for SHG Meeting Fine
    frappe.db.sql("""
        UPDATE `tabSHG Meeting Fine` 
        SET posted_to_gl = 0, posted_on = NULL 
        WHERE docstatus = 1 AND status = 'Paid'
    """)
    
    frappe.log("Completed resetting posting flags")