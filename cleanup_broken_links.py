import frappe

def execute():
    """Clean up broken Payment Entry links in SHG Loan Repayment"""
    print("🔍 Cleaning up broken Payment Entry links in SHG Loan Repayment...")
    
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
    
    print("✅ Cleaned up broken Payment Entry links in SHG Loan Repayment")
    
    # Also clean up SHG Loan Repayment Schedule
    print("🔍 Cleaning up broken Payment Entry links in SHG Loan Repayment Schedule...")
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment Schedule`
        SET payment_entry=NULL
        WHERE payment_entry IS NOT NULL
          AND payment_entry NOT IN (
            SELECT name FROM `tabSHG Payment Entry`
            UNION
            SELECT name FROM `tabPayment Entry`
          )
    """)
    frappe.db.commit()
    
    print("✅ Cleaned up broken Payment Entry links in SHG Loan Repayment Schedule")

if __name__ == "__main__":
    execute()