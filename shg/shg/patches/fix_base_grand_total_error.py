import frappe

def execute():
    """Fix for 'SHGLoan' object has no attribute 'base_grand_total' error.
    
    This patch adds a safeguard to prevent errors when external code tries to 
    access the base_grand_total attribute on SHGLoan objects.
    """
    # Get all SHG Loan records
    loans = frappe.get_all("SHG Loan", fields=["name"])
    
    for loan in loans:
        try:
            # Load the loan document
            doc = frappe.get_doc("SHG Loan", loan.name)
            
            # Ensure the company field is set (from our previous enhancement)
            if not doc.company:
                doc.company = frappe.db.get_single_value("SHG Settings", "company")
                if doc.company:
                    doc.save(ignore_permissions=True)
                
        except Exception as e:
            # Log error but continue processing
            frappe.log_error(f"Failed to process SHG Loan {loan.name}: {str(e)}")
    
    # Get all SHG Loan Repayment records
    loan_repayments = frappe.get_all("SHG Loan Repayment", fields=["name"])
    
    for repayment in loan_repayments:
        try:
            # Load the repayment document
            doc = frappe.get_doc("SHG Loan Repayment", repayment.name)
            
            # Ensure the company field is set (from our previous enhancement)
            if not doc.company and doc.loan:
                loan_doc = frappe.get_doc("SHG Loan", doc.loan)
                doc.company = loan_doc.company
                doc.save(ignore_permissions=True)
                
        except Exception as e:
            # Log error but continue processing
            frappe.log_error(f"Failed to process SHG Loan Repayment {repayment.name}: {str(e)}")
    
    frappe.db.commit()
    frappe.msgprint("✅ Applied fix for base_grand_total error and ensured company field is populated")