import frappe
from frappe.utils import flt, getdate

def execute():
    """
    Patch to update existing SHG Loan Repayment records to properly link to repayment schedule.
    This ensures that when repayments are cancelled, the system can properly reverse the updates.
    """
    frappe.msgprint("🔄 Updating SHG Loan Repayment Schedule Links...")
    
    # Get all submitted loan repayments
    repayments = frappe.get_all("SHG Loan Repayment", 
                               filters={"docstatus": 1},
                               fields=["name", "loan"])
    
    updated_count = 0
    
    for repayment in repayments:
        try:
            repayment_doc = frappe.get_doc("SHG Loan Repayment", repayment.name)
            loan_doc = frappe.get_doc("SHG Loan", repayment_doc.loan)
            
            if loan_doc.get("repayment_schedule"):
                # Update the repayment schedule rows to link to this repayment
                total_paid = flt(repayment_doc.total_paid)
                remaining_amount = total_paid
                
                # Sort schedule rows by due date (oldest first)
                schedule_rows = sorted(loan_doc.get("repayment_schedule"), key=lambda x: getdate(x.due_date))
                
                for row in schedule_rows:
                    if remaining_amount <= 0:
                        break
                        
                    if flt(row.unpaid_balance) > 0:
                        # Check if this row has already been paid (avoid double linking)
                        if not row.payment_entry:
                            # Allocate amount to this row
                            alloc = min(flt(row.unpaid_balance), remaining_amount)
                            
                            # Link this repayment to the schedule row
                            row.payment_entry = repayment_doc.name
                            row.db_update()
                            remaining_amount -= alloc
                
                updated_count += 1
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to update repayment schedule link for {repayment.name}")
    
    frappe.msgprint(f"✅ Updated {updated_count} loan repayments with repayment schedule links.")
    
    # Also create a patch to backfill loan summaries
    backfill_loan_summaries()

def backfill_loan_summaries():
    """
    Backfill loan summaries for all loans to ensure data consistency.
    """
    frappe.msgprint("🔄 Backfilling loan summaries...")
    
    # Get all loans with repayment schedules
    loans = frappe.get_all("SHG Loan",
                          filters={"docstatus": ["<=", 1]},
                          fields=["name"])
    
    updated_count = 0
    
    for loan in loans:
        try:
            # Use our new API method to refresh the repayment summary
            try:
                from shg.shg.api.repayment_refresh import refresh_repayment_summary
                result = refresh_repayment_summary(loan.name)
                updated_count += 1
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Failed to refresh summary for loan {loan.name}")
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to backfill loan summary for {loan.name}")
    
    frappe.msgprint(f"✅ Backfilled {updated_count} loan summaries.")