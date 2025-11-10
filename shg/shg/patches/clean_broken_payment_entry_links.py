import frappe

def execute():
    """Clean up broken SHG Payment Entry links in SHG Loan Repayment Schedule"""
    # Update schedule rows where payment_entry references non-existent SHG Payment Entries
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment Schedule`
        SET payment_entry=NULL
        WHERE payment_entry IS NOT NULL
          AND payment_entry NOT IN (SELECT name FROM `tabSHG Payment Entry`)
    """)
    frappe.db.commit()
    
    frappe.msgprint("✅ Cleaned up broken SHG Payment Entry links in SHG Loan Repayment Schedule")