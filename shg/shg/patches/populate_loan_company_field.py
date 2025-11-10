import frappe

def execute():
    """Populate company field for existing SHG Loan records."""
    # Get default company from SHG Settings
    default_company = frappe.db.get_single_value("SHG Settings", "company")
    
    if not default_company:
        frappe.msgprint("No default company found in SHG Settings. Skipping company field population.")
        return
    
    # Update SHG Loan records where company is not set
    frappe.db.sql("""
        UPDATE `tabSHG Loan`
        SET company = %s
        WHERE company IS NULL OR company = ''
    """, (default_company,))
    
    # Update SHG Loan Repayment records where company is not set
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment`
        SET company = %s
        WHERE company IS NULL OR company = ''
    """, (default_company,))
    
    frappe.db.commit()
    frappe.msgprint(f"✅ Populated company field for existing SHG Loan and Loan Repayment records with {default_company}")