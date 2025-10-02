import frappe
from frappe import _
from frappe.utils import flt, today

def make_gl_entries(doc, method=None):
    """
    Reusable function to create GL entries for SHG documents.
    Supports both Journal Entry and Payment Entry creation based on settings.
    
    Args:
        doc: SHG document (Contribution, Loan, Loan Repayment, Meeting Fine)
        method: Optional method parameter for hooks
    """
    # Determine document type and get appropriate settings
    doc_type = doc.doctype
    settings = frappe.get_single("SHG Settings")
    
    # Get posting method based on document type
    posting_method = _get_posting_method(doc_type, settings)
    
    # Prepare common data
    company = frappe.get_value("Global Defaults", None, "default_company") or settings.company
    member_customer = None
    if hasattr(doc, 'member'):
        member_customer = frappe.get_value("SHG Member", doc.member, "customer")
    
    # Create appropriate entry based on posting method
    if posting_method == "Payment Entry":
        return _create_payment_entry(doc, doc_type, member_customer, company)
    else:
        return _create_journal_entry(doc, doc_type, member_customer, company)

def _get_posting_method(doc_type, settings):
    """Get posting method based on document type and settings"""
    method_map = {
        "SHG Contribution": "contribution_posting_method",
        "SHG Loan": "loan_disbursement_posting_method",
        "SHG Loan Repayment": "loan_repayment_posting_method",
        "SHG Meeting Fine": "meeting_fine_posting_method"
    }
    
    method_setting = method_map.get(doc_type, "Journal Entry")
    return getattr(settings, method_setting, "Journal Entry")

def _create_journal_entry(doc, doc_type, member_customer, company):
    """Create a Journal Entry for the given document"""
    from shg.shg.utils.account_utils import (
        get_or_create_shg_contributions_account,
        get_or_create_shg_loans_account,
        get_or_create_shg_penalty_income_account,
        get_or_create_shg_interest_income_account,
        get_or_create_member_account
    )
    
    # Get accounts based on document type
    accounts = []
    
    if doc_type == "SHG Contribution":
        # Debit: Bank/Cash, Credit: Contribution Income
        accounts = [
            {
                "account": _get_cash_account(doc, company),
                "debit_in_account_currency": flt(doc.amount)
            },
            {
                "account": get_or_create_shg_contributions_account(company),
                "credit_in_account_currency": flt(doc.amount),
                "party_type": "Customer",
                "party": member_customer
            }
        ]
        je_remark = f"SHG Contribution {doc.name} from {doc.member_name}"
        custom_field = "custom_shg_contribution"
        
    elif doc_type == "SHG Loan" and doc.status == "Disbursed":
        # Debit: Loan Asset, Credit: Bank
        member_account = get_or_create_member_account(
            frappe.get_doc("SHG Member", doc.member), company)
        accounts = [
            {
                "account": get_or_create_shg_loans_account(company),
                "debit_in_account_currency": flt(doc.loan_amount)
            },
            {
                "account": _get_bank_account(doc, company),
                "credit_in_account_currency": flt(doc.loan_amount)
            }
        ]
        je_remark = f"SHG Loan Disbursement {doc.name} to {doc.member_name}"
        custom_field = "custom_shg_loan"
        
    elif doc_type == "SHG Loan Repayment":
        # Debit: Bank/Cash, Credit: Loan Receivable + Interest + Penalty
        cash_account = _get_cash_account(doc, company)
        loan_account = get_or_create_shg_loans_account(company)
        interest_account = get_or_create_shg_interest_income_account(company)
        penalty_account = get_or_create_shg_penalty_income_account(company)
        
        accounts = [
            {
                "account": cash_account,
                "debit_in_account_currency": flt(doc.total_paid)
            }
        ]
        
        if doc.principal_amount > 0:
            accounts.append({
                "account": loan_account,
                "credit_in_account_currency": flt(doc.principal_amount)
            })
            
        if doc.interest_amount > 0:
            accounts.append({
                "account": interest_account,
                "credit_in_account_currency": flt(doc.interest_amount)
            })
            
        if doc.penalty_amount > 0:
            accounts.append({
                "account": penalty_account,
                "credit_in_account_currency": flt(doc.penalty_amount)
            })
            
        je_remark = f"SHG Loan Repayment {doc.name} from {doc.member_name}"
        custom_field = "custom_shg_loan_repayment"
        
    elif doc_type == "SHG Meeting Fine":
        # Debit: Member Account, Credit: Penalty Income
        member_account = get_or_create_member_account(
            frappe.get_doc("SHG Member", doc.member), company)
        accounts = [
            {
                "account": member_account,
                "debit_in_account_currency": flt(doc.fine_amount),
                "party_type": "Customer",
                "party": member_customer
            },
            {
                "account": get_or_create_shg_penalty_income_account(company),
                "credit_in_account_currency": flt(doc.fine_amount)
            }
        ]
        je_remark = f"SHG Meeting Fine {doc.name} from {doc.member_name}"
        custom_field = "custom_shg_meeting_fine"
        
    else:
        frappe.throw(_("Unsupported document type for Journal Entry creation: {0}").format(doc_type))
    
    # Create Journal Entry
    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": getattr(doc, 'voucher_type', 'Journal Entry') or 'Journal Entry',
        "posting_date": _get_posting_date(doc, doc_type),
        "company": company,
        "user_remark": je_remark,
        custom_field: doc.name,
        "accounts": accounts
    })
    
    je.insert(ignore_permissions=True)
    je.submit()
    
    # Update document with journal entry reference
    _update_document_with_entry(doc, "journal_entry", je.name)
    
    return je

def _create_payment_entry(doc, doc_type, member_customer, company):
    """Create a Payment Entry for the given document"""
    from shg.shg.utils.account_utils import (
        get_or_create_shg_contributions_account,
        get_or_create_shg_loans_account,
        get_or_create_shg_penalty_income_account,
        get_or_create_shg_interest_income_account,
        get_or_create_member_account
    )
    
    if doc_type == "SHG Contribution":
        # Receive payment for contribution
        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "posting_date": doc.contribution_date or today(),
            "company": company,
            "party_type": "Customer",
            "party": member_customer,
            "paid_from": _get_cash_account(doc, company),
            "paid_to": get_or_create_shg_contributions_account(company),
            "paid_amount": flt(doc.amount),
            "received_amount": flt(doc.amount),
            "reference_no": doc.name,
            "reference_date": doc.contribution_date or today(),
            "custom_shg_contribution": doc.name
        })
        pe.insert(ignore_permissions=True)
        pe.submit()
        _update_document_with_entry(doc, "payment_entry", pe.name)
        return pe
        
    elif doc_type == "SHG Loan Repayment":
        # Receive payment for loan repayment
        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "posting_date": doc.repayment_date or today(),
            "company": company,
            "party_type": "Customer",
            "party": member_customer,
            "paid_from": _get_cash_account(doc, company),
            "paid_to": get_or_create_shg_loans_account(company),
            "paid_amount": flt(doc.total_paid),
            "received_amount": flt(doc.total_paid),
            "reference_no": doc.name,
            "reference_date": doc.repayment_date or today(),
            "custom_shg_loan_repayment": doc.name
        })
        
        # Add allocations for principal, interest, and penalty
        if doc.principal_amount > 0:
            pe.append("references", {
                "reference_doctype": "SHG Loan",
                "reference_name": doc.loan,
                "allocated_amount": flt(doc.principal_amount)
            })
            
        pe.insert(ignore_permissions=True)
        pe.submit()
        _update_document_with_entry(doc, "payment_entry", pe.name)
        return pe
        
    elif doc_type == "SHG Loan" and doc.status == "Disbursed":
        # Pay out loan amount
        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Pay",
            "posting_date": doc.disbursement_date or today(),
            "company": company,
            "party_type": "Customer",
            "party": member_customer,
            "paid_from": get_or_create_shg_loans_account(company),
            "paid_to": _get_bank_account(doc, company),
            "paid_amount": flt(doc.loan_amount),
            "received_amount": flt(doc.loan_amount),
            "reference_no": doc.name,
            "reference_date": doc.disbursement_date or today(),
            "custom_shg_loan": doc.name
        })
        pe.insert(ignore_permissions=True)
        pe.submit()
        _update_document_with_entry(doc, "disbursement_payment_entry", pe.name)
        return pe
        
    else:
        frappe.throw(_("Payment Entry creation not supported for document type: {0}").format(doc_type))

def _get_cash_account(doc, company):
    """Get cash or bank account from settings or defaults"""
    settings = frappe.get_single("SHG Settings")
    if settings.default_bank_account:
        return settings.default_bank_account
    elif settings.default_cash_account:
        return settings.default_cash_account
    else:
        # Try to find a default bank account
        bank_accounts = frappe.get_all("Account", filters={
            "company": company,
            "account_type": "Bank",
            "is_group": 0
        }, limit=1)
        if bank_accounts:
            return bank_accounts[0].name
        else:
            # Try cash account
            cash_accounts = frappe.get_all("Account", filters={
                "company": company,
                "account_type": "Cash",
                "is_group": 0
            }, limit=1)
            if cash_accounts:
                return cash_accounts[0].name
            else:
                frappe.throw(_("Please configure default bank or cash account in SHG Settings"))

def _get_bank_account(doc, company):
    """Get bank account from settings or defaults"""
    settings = frappe.get_single("SHG Settings")
    if settings.default_bank_account:
        return settings.default_bank_account
    else:
        # Try to find a default bank account
        bank_accounts = frappe.get_all("Account", filters={
            "company": company,
            "account_type": "Bank",
            "is_group": 0
        }, limit=1)
        if bank_accounts:
            return bank_accounts[0].name
        else:
            frappe.throw(_("Please configure default bank account in SHG Settings"))

def _get_posting_date(doc, doc_type):
    """Get appropriate posting date based on document type"""
    if doc_type == "SHG Contribution":
        return doc.contribution_date or today()
    elif doc_type == "SHG Loan":
        return doc.disbursement_date or today()
    elif doc_type == "SHG Loan Repayment":
        return doc.repayment_date or today()
    elif doc_type == "SHG Meeting Fine":
        return doc.fine_date or today()
    else:
        return today()

def _update_document_with_entry(doc, entry_field, entry_name):
    """Update document with created entry reference and save"""
    doc.set(entry_field, entry_name)
    doc.posted_to_gl = 1
    doc.posted_on = frappe.utils.now()
    doc.save()