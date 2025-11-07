import frappe
from frappe.utils import flt

def create_payment_entry(loan_doc, repayment_doc):
    """Create a Payment Entry for loan repayment."""
    try:
        from shg.shg.utils.account_helpers import get_or_create_member_receivable
        
        # Get member details
        member = frappe.get_doc("SHG Member", loan_doc.member)
        customer = member.customer or loan_doc.member
        
        # Get or create member receivable account
        company = loan_doc.company or frappe.db.get_single_value("SHG Settings", "company")
        member_account = get_or_create_member_receivable(loan_doc.member, company)
        
        # Create Payment Entry
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.company = company
        pe.posting_date = repayment_doc.posting_date
        pe.paid_from = member_account
        pe.paid_from_account_type = "Receivable"
        pe.paid_from_account_currency = frappe.db.get_value("Account", member_account, "account_currency")
        pe.paid_to = frappe.db.get_single_value("SHG Settings", "default_bank_account") or "Cash - " + frappe.db.get_value("Company", company, "abbr")
        pe.paid_to_account_type = "Cash"
        pe.paid_to_account_currency = frappe.db.get_value("Account", pe.paid_to, "account_currency")
        pe.paid_amount = flt(repayment_doc.total_paid)
        pe.received_amount = flt(repayment_doc.total_paid)
        pe.allocate_payment_amount = 1
        pe.party_type = "Customer"
        pe.party = customer
        pe.remarks = f"Loan repayment for {loan_doc.name}"
        
        # Add reference to the loan
        pe.append("references", {
            "reference_doctype": "SHG Loan",
            "reference_name": loan_doc.name,
            "total_amount": flt(loan_doc.balance_amount),
            "outstanding_amount": flt(loan_doc.balance_amount),
            "allocated_amount": flt(repayment_doc.total_paid)
        })
        
        pe.insert(ignore_permissions=True)
        pe.submit()
        
        # Link payment entry to repayment
        repayment_doc.db_set("payment_entry", pe.name)
        
        return pe.name
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to create payment entry for {repayment_doc.name}")
        frappe.throw(f"Failed to create payment entry: {str(e)}")

def create_journal_entry(loan_doc, repayment_doc):
    """Create a Journal Entry for loan repayment."""
    # TODO: Implement journal entry creation
    pass

def get_member_receivable_account(member, company):
    """Get or create member receivable account."""
    from shg.shg.utils.account_helpers import get_or_create_member_receivable
    return get_or_create_member_receivable(member, company)