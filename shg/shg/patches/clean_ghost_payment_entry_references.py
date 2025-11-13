import frappe

def execute():
    """Clean up ghost payment entry references in SHG Loan Repayment Schedule table."""
    
    # Remove all invalid payment_entry values that don't exist in Payment Entry table
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment Schedule`
           SET payment_entry=NULL
         WHERE payment_entry IS NOT NULL
           AND payment_entry NOT IN (
                SELECT name FROM `tabPayment Entry`
           )
    """)
    frappe.db.commit()
    
    # Also clean up any ghost references in SHG Loan Repayment breakdown
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment Breakdown`
           SET payment_entry=NULL
         WHERE payment_entry IS NOT NULL
           AND payment_entry NOT IN (
                SELECT name FROM `tabPayment Entry`
           )
    """)
    frappe.db.commit()
    
    frappe.msgprint("✅ Ghost payment entry references cleaned up successfully.")