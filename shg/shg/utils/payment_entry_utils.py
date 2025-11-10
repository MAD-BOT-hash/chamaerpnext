import frappe

def clean_broken_payment_entry_links():
    """Clean up broken Payment Entry links in SHG Loan Repayment Schedule"""
    # Update schedule rows where payment_entry references non-existent Payment Entries
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment Schedule`
        SET payment_entry=NULL
        WHERE payment_entry IS NOT NULL
          AND payment_entry NOT IN (SELECT name FROM `tabPayment Entry`)
    """)
    frappe.db.commit()
    
    frappe.msgprint("✅ Cleaned up broken Payment Entry links in SHG Loan Repayment Schedule")

def validate_payment_entry_exists(payment_entry_name):
    """Validate that a Payment Entry exists"""
    if payment_entry_name and not frappe.db.exists("Payment Entry", payment_entry_name):
        return False
    return True