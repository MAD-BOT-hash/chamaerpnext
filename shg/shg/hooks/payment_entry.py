import frappe
from frappe import _

def set_reference_fields(pe, source_doc):
    """
    Helper function to automatically set reference_no and reference_date for Payment Entries
    when they are created from SHG modules.
    
    Args:
        pe: Payment Entry document
        source_doc: Source SHG document (Contribution, Loan, etc.)
    """
    # Check if payment entry is for bank transactions
    # For Bank Entries, we need to auto-fill reference fields
    if pe.voucher_type == "Bank Entry":
        # Only set reference fields if they're not already set
        if not pe.reference_no or not pe.reference_date:
            # Set reference fields from the source document
            pe.reference_no = source_doc.name
            if hasattr(source_doc, 'contribution_date'):
                pe.reference_date = source_doc.contribution_date
            elif hasattr(source_doc, 'disbursement_date'):
                pe.reference_date = source_doc.disbursement_date
            elif hasattr(source_doc, 'repayment_date'):
                pe.reference_date = source_doc.repayment_date
            elif hasattr(source_doc, 'fine_date'):
                pe.reference_date = source_doc.fine_date
            else:
                # Fallback to posting date
                pe.reference_date = pe.posting_date

def payment_entry_validate(doc, method):
    """
    Hook function called during Payment Entry validation.
    Automatically sets reference fields for SHG-related Payment Entries.
    """
    # Check if this Payment Entry is related to any SHG module
    shg_contribution = doc.get("custom_shg_contribution")
    shg_loan = doc.get("custom_shg_loan")
    shg_loan_repayment = doc.get("custom_shg_loan_repayment")
    shg_meeting_fine = doc.get("custom_shg_meeting_fine")
    
    source_doc = None
    
    # Determine the source document
    if shg_contribution:
        source_doc = frappe.get_doc("SHG Contribution", shg_contribution)
    elif shg_loan:
        source_doc = frappe.get_doc("SHG Loan", shg_loan)
    elif shg_loan_repayment:
        source_doc = frappe.get_doc("SHG Loan Repayment", shg_loan_repayment)
    elif shg_meeting_fine:
        source_doc = frappe.get_doc("SHG Meeting Fine", shg_meeting_fine)
    
    # If we found a source document, set the reference fields
    if source_doc:
        set_reference_fields(doc, source_doc)