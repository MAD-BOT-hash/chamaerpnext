import frappe

def execute():
    """Clean up broken Payment Entry links in SHG Loan Repayment"""
    # Update loan repayments where payment_entry references non-existent Payment Entries
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment`
        SET payment_entry=NULL
        WHERE payment_entry IS NOT NULL
          AND payment_entry NOT IN (
            SELECT name FROM `tabSHG Payment Entry`
            UNION
            SELECT name FROM `tabPayment Entry`
          )
    """)
    frappe.db.commit()
    
    frappe.msgprint("✅ Cleaned up broken Payment Entry links in SHG Loan Repayment")