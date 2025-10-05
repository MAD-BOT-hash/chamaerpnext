import frappe
from frappe import _
from frappe.utils import flt, today


def create_loan_disbursement_payment_entry(loan_doc):
    """
    Create a Payment Entry for loan disbursement.
    
    Args:
        loan_doc: SHG Loan document
        
    Returns:
        Payment Entry document
    """
    try:
        frappe.msgprint(f"💸 Disbursing SHG Loan {loan_doc.name} via Payment Entry...")
        
        # Get company
        company = frappe.get_value("Global Defaults", None, "default_company")
        if not company:
            company = loan_doc.company
        
        # Get accounts
        from shg.shg.utils.account_utils import get_or_create_member_account, get_or_create_shg_loans_account
        member_account = get_or_create_member_account(
            frappe.get_doc("SHG Member", loan_doc.member), company)
        
        # Get bank/cash account from settings
        settings = frappe.get_single("SHG Settings")
        bank_account = settings.default_bank_account or settings.default_cash_account
        
        if not bank_account:
            # Try to find a default bank account
            bank_accounts = frappe.get_all("Account", filters={
                "company": company,
                "account_type": ["in", ["Bank", "Cash"]],
                "is_group": 0
            }, limit=1)
            if bank_accounts:
                bank_account = bank_accounts[0].name
            else:
                frappe.throw(_("Please configure default bank or cash account in SHG Settings"))
        
        # Create Payment Entry
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Pay"
        pe.posting_date = loan_doc.disbursement_date or today()
        pe.company = company
        pe.party_type = "Customer"
        pe.party = loan_doc.get_member_customer()
        pe.paid_from = bank_account
        pe.paid_to = member_account
        pe.paid_amount = flt(loan_doc.loan_amount)
        pe.received_amount = flt(loan_doc.loan_amount)
        
        # Set reference fields (required for Bank Entry)
        pe.reference_no = loan_doc.name
        pe.reference_date = loan_doc.disbursement_date or loan_doc.posting_date or today()
        
        # Set remarks
        pe.remarks = f"Loan Disbursement for {loan_doc.member} (Loan {loan_doc.name})"
        
        # Set mode of payment based on account type
        account_type = frappe.db.get_value("Account", bank_account, "account_type")
        if account_type == "Bank":
            pe.mode_of_payment = "Bank"
        elif account_type == "Cash":
            pe.mode_of_payment = "Cash"
        
        # Set voucher type
        pe.voucher_type = "Bank Entry"
        
        # Add reference to ERPNext Loan
        pe.append("references", {
            "reference_doctype": "Loan",
            "reference_name": loan_doc.erpnext_loan_ref or loan_doc.name,
            "allocated_amount": flt(loan_doc.loan_amount)
        })
        
        # Insert and submit
        pe.insert(ignore_permissions=True)
        pe.submit()
        
        frappe.msgprint(f"✅ Disbursement linked successfully to ERPNext Loan {loan_doc.erpnext_loan_ref or loan_doc.name}")
        
        return pe
    except Exception as e:
        frappe.log_error(f"Error creating Payment Entry for loan {loan_doc.name}: {str(e)}")
        frappe.throw(f"Failed to create Payment Entry for loan disbursement: {str(e)}")



def create_contribution_journal_entry(contribution_doc):
    """
    Create a Journal Entry for contribution.
    
    Args:
        contribution_doc: SHG Contribution document
        
    Returns:
        Journal Entry document
    """
    # Get company
    company = frappe.get_value("Global Defaults", None, "default_company")
    if not company:
        company = contribution_doc.company
    
    # Get accounts
    from shg.shg.utils.account_utils import (
        get_or_create_shg_contributions_account,
        get_or_create_member_account
    )
    
    # Get bank/cash account from settings
    settings = frappe.get_single("SHG Settings")
    bank_account = settings.default_bank_account or settings.default_cash_account
    
    if not bank_account:
        # Try to find a default bank/cash account
        bank_accounts = frappe.get_all("Account", filters={
            "company": company,
            "account_type": ["in", ["Bank", "Cash"]],
            "is_group": 0
        }, limit=1)
        if bank_accounts:
            bank_account = bank_accounts[0].name
        else:
            frappe.throw(_("Please configure default bank or cash account in SHG Settings"))
    
    # Get member account
    member_account = get_or_create_member_account(
        frappe.get_doc("SHG Member", contribution_doc.member), company)
    
    # Get contributions income account
    contributions_account = get_or_create_shg_contributions_account(company)
    
    # Create Journal Entry
    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.posting_date = contribution_doc.contribution_date or today()
    je.company = company
    je.user_remark = f"Contribution by {contribution_doc.member}"
    
    # Debit: Company Bank/Cash Account
    je.append("accounts", {
        "account": bank_account,
        "debit_in_account_currency": flt(contribution_doc.amount)
    })
    
    # Credit: Member Liability Account
    je.append("accounts", {
        "account": member_account,
        "credit_in_account_currency": flt(contribution_doc.amount),
        "party_type": "SHG Member",
        "party": contribution_doc.member
    })
    
    # Set custom field for traceability
    je.set("custom_shg_contribution", contribution_doc.name)
    
    # Insert and submit
    je.insert(ignore_permissions=True)
    je.submit()
    
    return je

def create_loan_repayment_payment_entry(repayment_doc):
    """
    Create a Payment Entry for loan repayment.
    
    Args:
        repayment_doc: SHG Loan Repayment document
        
    Returns:
        Payment Entry document
    """
    # Get company
    company = frappe.get_value("Global Defaults", None, "default_company")
    if not company:
        company = repayment_doc.company
    
    # Get accounts
    from shg.shg.utils.account_utils import get_or_create_member_account
    
    # Get member account
    member_account = get_or_create_member_account(
        frappe.get_doc("SHG Member", repayment_doc.member), company)
    
    # Get bank/cash account from settings
    settings = frappe.get_single("SHG Settings")
    bank_account = settings.default_bank_account or settings.default_cash_account
    
    if not bank_account:
        # Try to find a default bank account
        bank_accounts = frappe.get_all("Account", filters={
            "company": company,
            "account_type": ["in", ["Bank", "Cash"]],
            "is_group": 0
        }, limit=1)
        if bank_accounts:
            bank_account = bank_accounts[0].name
        else:
            frappe.throw(_("Please configure default bank or cash account in SHG Settings"))
    
    # Create Payment Entry
    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.posting_date = repayment_doc.repayment_date or today()
    pe.company = company
    pe.party_type = "SHG Member"
    pe.party = repayment_doc.member
    pe.paid_from = member_account
    pe.paid_to = bank_account
    pe.paid_amount = flt(repayment_doc.total_paid)
    pe.received_amount = flt(repayment_doc.total_paid)
    
    # Set reference fields (required for Bank Entry)
    pe.reference_no = repayment_doc.name
    pe.reference_date = repayment_doc.repayment_date or repayment_doc.posting_date or today()
    
    # Set remarks
    pe.remarks = f"Loan Repayment (Loan {repayment_doc.loan}) by {repayment_doc.member}"
    
    # Set mode of payment based on account type
    account_type = frappe.db.get_value("Account", bank_account, "account_type")
    if account_type == "Bank":
        pe.mode_of_payment = "Bank"
    elif account_type == "Cash":
        pe.mode_of_payment = "Cash"
    
    # Set voucher type
    pe.voucher_type = "Bank Entry"
    
    # Set custom field for traceability
    pe.set("custom_shg_loan_repayment", repayment_doc.name)
    
    # Add allocations for principal, interest, and penalty
    if repayment_doc.principal_amount > 0:
        pe.append("references", {
            "reference_doctype": "Loan",
            "reference_name": repayment_doc.loan,
            "allocated_amount": flt(repayment_doc.principal_amount)
        })
    
    # Insert and submit
    pe.insert(ignore_permissions=True)
    pe.submit()
    
    return pe

def create_meeting_fine_payment_entry(fine_doc):
    """
    Create a Payment Entry for meeting fine.
    
    Args:
        fine_doc: SHG Meeting Fine document
        
    Returns:
        Payment Entry document
    """
    # Get company
    company = frappe.get_value("Global Defaults", None, "default_company")
    if not company:
        company = fine_doc.company
    
    # Get accounts
    from shg.shg.utils.account_utils import (
        get_or_create_member_account,
        get_or_create_shg_penalty_income_account
    )
    
    # Get member account
    member_account = get_or_create_member_account(
        frappe.get_doc("SHG Member", fine_doc.member), company)
    
    # Get bank/cash account from settings
    settings = frappe.get_single("SHG Settings")
    bank_account = settings.default_bank_account or settings.default_cash_account
    
    if not bank_account:
        # Try to find a default bank account
        bank_accounts = frappe.get_all("Account", filters={
            "company": company,
            "account_type": ["in", ["Bank", "Cash"]],
            "is_group": 0
        }, limit=1)
        if bank_accounts:
            bank_account = bank_accounts[0].name
        else:
            frappe.throw(_("Please configure default bank or cash account in SHG Settings"))
    
    # Get penalty income account
    penalty_account = get_or_create_shg_penalty_income_account(company)
    
    # Create Payment Entry
    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.posting_date = fine_doc.fine_date or today()
    pe.company = company
    pe.party_type = "SHG Member"
    pe.party = fine_doc.member
    pe.paid_from = member_account
    pe.paid_to = bank_account
    pe.paid_amount = flt(fine_doc.fine_amount)
    pe.received_amount = flt(fine_doc.fine_amount)
    
    # Set reference fields (required for Bank Entry)
    pe.reference_no = fine_doc.name
    pe.reference_date = fine_doc.fine_date or fine_doc.posting_date or today()
    
    # Set remarks
    pe.remarks = f"Meeting Fine for {fine_doc.member}"
    
    # Set mode of payment based on account type
    account_type = frappe.db.get_value("Account", bank_account, "account_type")
    if account_type == "Bank":
        pe.mode_of_payment = "Bank"
    elif account_type == "Cash":
        pe.mode_of_payment = "Cash"
    
    # Set voucher type
    pe.voucher_type = "Bank Entry"
    
    # Set custom field for traceability
    pe.set("custom_shg_meeting_fine", fine_doc.name)
    
    # Handle fine through deductions table if needed
    # This is for cases where we want to post the fine to a specific income account
    # pe.append("deductions", {
    #     "account": penalty_account,
    #     "amount": flt(fine_doc.fine_amount)
    # })
    
    # Insert and submit
    pe.insert(ignore_permissions=True)
    pe.submit()
    
    return pe





def update_document_with_payment_entry(doc, payment_entry, entry_field="payment_entry"):
    """
    Update document with payment entry reference.
    
    Args:
        doc: SHG document
        payment_entry: Payment Entry document
        entry_field: Field name to update (default: "payment_entry")
    """
    doc.db_set({
        entry_field: payment_entry.name,
        "posted_to_gl": 1,
        "posted_on": frappe.utils.now()
    }, update_modified=False)


def update_document_with_journal_entry(doc, journal_entry):
    """
    Update document with journal entry reference.
    
    Args:
        doc: SHG document
        journal_entry: Journal Entry document
    """
    doc.db_set({
        "journal_entry": journal_entry.name,
        "posted_to_gl": 1,
        "posted_on": frappe.utils.now()
    }, update_modified=False)





