import frappe

def execute():
    """Populate company field for existing SHG Loan Repayment Schedule records."""
    
    # Update SHG Loan Repayment Schedule records where company is not set
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment Schedule` as schedule
        INNER JOIN `tabSHG Loan` as loan ON schedule.parent = loan.name
        SET schedule.company = loan.company
        WHERE (schedule.company IS NULL OR schedule.company = '')
        AND loan.company IS NOT NULL
    """)
    
    frappe.db.commit()
    frappe.msgprint("✅ Populated company field for existing SHG Loan Repayment Schedule records")