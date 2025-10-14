import frappe
from frappe import _
from shg.shg.utils.member_account_mapping import set_member_credit_account as map_member_account

def set_reference_fields(pe, source_doc):
    """
    Helper function to automatically set reference_no and reference_date for Payment Entries
    when they are created from SHG modules.
    
    Args:
        pe: Payment Entry document
        source_doc: Source SHG document (Contribution, Loan, etc.)
    """
    # Auto-fill reference fields for all voucher types
    # Only set reference fields if they're not already set
    if not pe.reference_no or not pe.reference_date:
        # Set reference fields from the source document
        if not pe.reference_no:
            pe.reference_no = source_doc.name
        if not pe.reference_date:
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
                pe.reference_date = source_doc.posting_date or pe.posting_date

def payment_entry_validate(doc, method):
    """
    Hook function called during Payment Entry validation.
    Automatically sets reference fields for SHG-related Payment Entries and maps member accounts.
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
    
    # Map member credit account
    map_member_account(doc, method)

def payment_entry_on_submit(doc, method):
    """
    Hook function called when Payment Entry is submitted.
    Updates the status of related SHG Contribution Invoices.
    """
    # Check if this Payment Entry is allocated to any Sales Invoices
    for reference in doc.references:
        if reference.reference_doctype == "Sales Invoice" and reference.reference_name:
            # Update the SHG Contribution Invoice status
            update_shg_contribution_invoice_status(reference.reference_name)

def update_shg_contribution_invoice_status(sales_invoice_name):
    """
    Update the SHG Contribution Invoice status based on the Sales Invoice status
    
    Args:
        sales_invoice_name (str): Name of the Sales Invoice
    """
    try:
        # Get the SHG Contribution Invoice linked to this Sales Invoice
        shg_invoice_name = frappe.db.get_value("SHG Contribution Invoice", 
                                              {"sales_invoice": sales_invoice_name})
        
        if shg_invoice_name:
            shg_invoice = frappe.get_doc("SHG Contribution Invoice", shg_invoice_name)
            sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
            
            # Update status based on outstanding amount
            if sales_invoice.outstanding_amount <= 0:
                shg_invoice.db_set("status", "Paid")
            elif sales_invoice.outstanding_amount < sales_invoice.grand_total:
                shg_invoice.db_set("status", "Partially Paid")
            else:
                shg_invoice.db_set("status", "Unpaid")
                
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Contribution Invoice Status Update Failed")