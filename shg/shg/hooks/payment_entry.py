import frappe
from frappe import _
from frappe.utils.data import flt
from shg.shg.utils.member_account_mapping import set_member_credit_account as map_member_account


def get_invoice_total(invoice) -> float:
    """
    Production-safe helper to get the total amount from any invoice document.
    Handles SHG Contribution Invoice (amount), Sales Invoice (grand_total), etc.
    """
    if hasattr(invoice, 'grand_total') and invoice.grand_total:
        return flt(invoice.grand_total)
    elif hasattr(invoice, 'expected_amount') and invoice.expected_amount:
        return flt(invoice.expected_amount)
    elif hasattr(invoice, 'total_amount') and invoice.total_amount:
        return flt(invoice.total_amount)
    elif hasattr(invoice, 'amount') and invoice.amount:
        return flt(invoice.amount)
    else:
        frappe.log_error(
            f"No total field found for {getattr(invoice, 'doctype', 'unknown')} "
            f"{getattr(invoice, 'name', '')}",
            "Invoice Total Field Missing"
        )
        return 0.0

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


def validate(doc, method):
    """
    Hook function called during Payment Entry validation.
    Performs comprehensive validation for SHG-related Payment Entries.
    """
    try:
        # Perform basic payment entry validation
        _validate_payment_entry(doc)
        
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
        
        # Automatically set reference fields for bank transactions if missing
        _set_bank_transaction_reference_fields(doc)
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"SHG Payment Entry Validation Error - {doc.name}")
        # Don't raise the exception to avoid blocking submission, just log it


def on_submit(doc, method):
    """
    Hook function called when Payment Entry is submitted.
    Processes comprehensive payment updates for SHG-related documents.
    """
    try:
        # Process all references in the Payment Entry
        for reference in doc.references:
            if reference.reference_doctype and reference.reference_name:
                # Process based on reference type
                if reference.reference_doctype == "Sales Invoice":
                    # Update the SHG Contribution Invoice status
                    update_shg_contribution_invoice_status(reference.reference_name)
                    
                    # Update the related SHG Contribution status
                    update_shg_contribution_status(reference.reference_name)
                    
                elif reference.reference_doctype == "SHG Contribution Invoice":
                    # Direct contribution invoice reference
                    update_shg_contribution_invoice_status_direct(reference.reference_name, doc.name)
                    
                elif reference.reference_doctype == "SHG Contribution":
                    # Direct contribution reference
                    update_shg_contribution_status_direct(reference.reference_name, doc.name, reference.allocated_amount)
                    
                elif reference.reference_doctype == "SHG Meeting Fine":
                    # Direct meeting fine reference
                    update_shg_meeting_fine_status_direct(reference.reference_name, doc.name)
                    
                elif reference.reference_doctype == "SHG Loan Repayment":
                    # Direct loan repayment reference
                    update_shg_loan_repayment_status_direct(reference.reference_name, doc.name)
        
        # Update member financial summaries for all affected members
        _update_member_financial_summaries(doc)
        
        # Update related invoice statuses
        _update_related_invoice_statuses(doc)
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"SHG Payment Entry On Submit Error - {doc.name}")
        # Don't raise the exception to avoid blocking submission, just log it


def _validate_payment_entry(doc):
    """
    Performs comprehensive validation on the payment entry.
    """
    # Validate reference doctype and name
    for reference in doc.references:
        if reference.reference_doctype and reference.reference_name:
            # Check reference exists
            if not frappe.db.exists(reference.reference_doctype, reference.reference_name):
                frappe.throw(_("Reference {0} {1} does not exist").format(
                    reference.reference_doctype, reference.reference_name))
            
            # Ensure payment amount > 0
            if flt(reference.allocated_amount) <= 0:
                frappe.throw(_("Allocated amount must be greater than zero for {0}").format(
                    reference.reference_name))
            
            # Verify outstanding amount is valid
            outstanding = _get_outstanding_amount(reference.reference_doctype, reference.reference_name)
            if outstanding < 0:
                frappe.throw(_("Outstanding amount cannot be negative for {0}").format(
                    reference.reference_name))
            
            # Prevent payment amount from exceeding outstanding amount
            if flt(reference.allocated_amount) > outstanding:
                frappe.throw(_("Payment amount {0} exceeds outstanding amount {1} for {2}").format(
                    reference.allocated_amount, outstanding, reference.reference_name))


def _set_bank_transaction_reference_fields(doc):
    """
    Automatically set reference fields for bank transactions if missing.
    This resolves the "Reference No and Reference Date is mandatory for Bank transaction" error.
    """
    # Check if this is a bank transaction that requires reference fields
    if doc.payment_type in ["Pay", "Internal Transfer"]:
        # Check if paid_to or paid_from is a bank account
        is_bank_transaction = False
        
        if doc.paid_to:
            paid_to_account_type = frappe.get_cached_value("Account", doc.paid_to, "account_type")
            if paid_to_account_type in ["Bank", "Cash"]:
                is_bank_transaction = True
        
        if doc.paid_from:
            paid_from_account_type = frappe.get_cached_value("Account", doc.paid_from, "account_type")
            if paid_from_account_type in ["Bank", "Cash"]:
                is_bank_transaction = True
        
        # If it's a bank transaction and reference fields are missing, auto-populate them
        if is_bank_transaction and (not doc.reference_no or not doc.reference_date):
            if not doc.reference_no:
                # Use the Payment Entry name as reference number
                doc.reference_no = doc.name
            
            if not doc.reference_date:
                # Use the posting date as reference date
                doc.reference_date = doc.posting_date


def _get_outstanding_amount(doctype, name):
    """
    Get outstanding amount for a document.
    """
    if doctype == "Sales Invoice":
        si = frappe.get_doc("Sales Invoice", name)
        return flt(si.outstanding_amount)
    elif doctype == "SHG Contribution Invoice":
        invoice = frappe.get_doc("SHG Contribution Invoice", name)
        # For contribution invoices, the full amount is typically the outstanding
        return flt(invoice.amount)
    elif doctype == "SHG Contribution":
        contrib = frappe.get_doc("SHG Contribution", name)
        return flt(contrib.unpaid_amount or contrib.expected_amount or contrib.amount)
    elif doctype == "SHG Meeting Fine":
        fine = frappe.get_doc("SHG Meeting Fine", name)
        return flt(fine.fine_amount) if fine.status != "Paid" else 0
    elif doctype == "SHG Loan Repayment":
        repayment = frappe.get_doc("SHG Loan Repayment", name)
        return flt(repayment.principal_amount + repayment.interest_amount - repayment.amount_paid)
    else:
        # Generic fallback
        try:
            outstanding = frappe.db.get_value(doctype, name, "outstanding_amount")
            return flt(outstanding) if outstanding else 0.0
        except Exception:
            try:
                amount = frappe.db.get_value(doctype, name, "amount")
                return flt(amount) if amount else 0.0
            except Exception:
                return 0.0


def _update_member_financial_summaries(doc):
    """
    Update financial summaries for all members affected by this payment entry.
    """
    try:
        members_updated = set()
        
        # Get members from references
        for reference in doc.references:
            if reference.reference_doctype and reference.reference_name:
                member = _get_member_from_reference(reference.reference_doctype, reference.reference_name)
                if member and member not in members_updated:
                    try:
                        member_doc = frappe.get_doc("SHG Member", member)
                        member_doc.update_financial_summary()
                        members_updated.add(member)
                    except Exception as e:
                        frappe.log_error(frappe.get_traceback(), 
                                       f"Failed to update member financial summary for {member}")
        
        # Also get member from party if available
        if doc.party_type == "SHG Member" and doc.party and doc.party not in members_updated:
            try:
                member_doc = frappe.get_doc("SHG Member", doc.party)
                member_doc.update_financial_summary()
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), 
                               f"Failed to update member financial summary for {doc.party}")
                
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Member Financial Summary Update Error")


def _get_member_from_reference(doctype, name):
    """
    Get member ID from a reference document.
    """
    try:
        if doctype == "Sales Invoice":
            # Get customer and try to find associated member
            customer = frappe.db.get_value("Sales Invoice", name, "customer")
            # Look for member linked to this customer
            member = frappe.db.get_value("SHG Member", {"customer": customer}, "name")
            return member
        elif doctype == "SHG Contribution Invoice":
            return frappe.db.get_value("SHG Contribution Invoice", name, "member")
        elif doctype == "SHG Contribution":
            return frappe.db.get_value("SHG Contribution", name, "member")
        elif doctype == "SHG Meeting Fine":
            return frappe.db.get_value("SHG Meeting Fine", name, "member")
        elif doctype == "SHG Loan Repayment":
            loan_name = frappe.db.get_value("SHG Loan Repayment", name, "against_loan")
            return frappe.db.get_value("SHG Loan", loan_name, "member") if loan_name else None
        else:
            # Try generic lookup
            try:
                return frappe.db.get_value(doctype, name, "member")
            except Exception:
                return None
    except Exception:
        return None


def _update_related_invoice_statuses(doc):
    """
    Update statuses of related invoices after payment submission.
    """
    try:
        for reference in doc.references:
            if reference.reference_doctype == "Sales Invoice" and reference.reference_name:
                # Update related SHG Contribution Invoice if it exists
                contrib_invoice_name = frappe.db.get_value("SHG Contribution Invoice", 
                                                         {"sales_invoice": reference.reference_name})
                if contrib_invoice_name:
                    contrib_invoice = frappe.get_doc("SHG Contribution Invoice", contrib_invoice_name)
                    sales_invoice = frappe.get_doc("Sales Invoice", reference.reference_name)
                    sales_total = get_invoice_total(sales_invoice)
                    
                    # Update status based on outstanding amount
                    if flt(sales_invoice.outstanding_amount) <= 0:
                        contrib_invoice.db_set("status", "Paid")
                    elif flt(sales_invoice.outstanding_amount) < sales_total:
                        contrib_invoice.db_set("status", "Partially Paid")
                    else:
                        contrib_invoice.db_set("status", "Unpaid")
                        
                    contrib_invoice.db_set("payment_reference", doc.name)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Related Invoice Status Update Error")


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
            sales_total = get_invoice_total(sales_invoice)
            
            # Update status based on outstanding amount
            if flt(sales_invoice.outstanding_amount) <= 0:
                shg_invoice.db_set("status", "Paid")
            elif flt(sales_invoice.outstanding_amount) < sales_total:
                shg_invoice.db_set("status", "Partially Paid")
            else:
                shg_invoice.db_set("status", "Unpaid")
                
            # Record payment entry reference
            shg_invoice.db_set("payment_reference", sales_invoice_name)
                
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Contribution Invoice Status Update Failed")


def update_shg_contribution_invoice_status_direct(contrib_invoice_name, payment_entry_name):
    """
    Update SHG Contribution Invoice status directly from payment reference.
    
    Args:
        contrib_invoice_name (str): Name of the SHG Contribution Invoice
        payment_entry_name (str): Name of the Payment Entry
    """
    try:
        shg_invoice = frappe.get_doc("SHG Contribution Invoice", contrib_invoice_name)
        # For direct payment to contribution invoice, mark as paid
        shg_invoice.db_set("status", "Paid")
        shg_invoice.db_set("payment_reference", payment_entry_name)
        
        # Update related contribution if exists
        contrib_name = frappe.db.get_value("SHG Contribution", 
                                         {"invoice_reference": contrib_invoice_name})
        if contrib_name:
            update_shg_contribution_status_direct(contrib_name, payment_entry_name, shg_invoice.amount)
                
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 
                        f"SHG Contribution Invoice Direct Status Update Failed for {contrib_invoice_name}")


def update_shg_contribution_status(sales_invoice_name):
    """
    Update the SHG Contribution status based on the Sales Invoice status
    
    Args:
        sales_invoice_name (str): Name of the Sales Invoice
    """
    try:
        # Get the SHG Contribution Invoice linked to the Sales Invoice
        shg_invoice_name = frappe.db.get_value("SHG Contribution Invoice", 
                                              {"sales_invoice": sales_invoice_name})
        
        if shg_invoice_name:
            # Get the SHG Contribution linked to this Contribution Invoice
            shg_contribution_name = frappe.db.get_value("SHG Contribution", 
                                                      {"invoice_reference": shg_invoice_name})
            
            if shg_contribution_name:
                shg_contribution = frappe.get_doc("SHG Contribution", shg_contribution_name)
                sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
                
                # Safely handle numeric fields
                outstanding_amount = flt(sales_invoice.outstanding_amount)
                grand_total = get_invoice_total(sales_invoice)
                
                # Update status based on outstanding amount
                if outstanding_amount <= 0:
                    shg_contribution.db_set("status", "Paid")
                    # Update amount paid
                    expected_amount = flt(shg_contribution.expected_amount or shg_contribution.amount)
                    shg_contribution.db_set("amount_paid", expected_amount)
                    shg_contribution.db_set("unpaid_amount", 0)
                elif outstanding_amount < grand_total:
                    shg_contribution.db_set("status", "Partially Paid")
                    # Calculate paid amount
                    paid_amount = flt(grand_total - outstanding_amount)
                    shg_contribution.db_set("amount_paid", paid_amount)
                    shg_contribution.db_set("unpaid_amount", outstanding_amount)
                else:
                    shg_contribution.db_set("status", "Unpaid")
                    
                # Save the contribution to trigger any necessary updates
                shg_contribution.flags.ignore_permissions = True
                shg_contribution.save()
                
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"SHG Contribution Status Update Failed for Sales Invoice {sales_invoice_name}")


def update_shg_contribution_status_direct(contrib_name, payment_entry_name, paid_amount=None):
    """
    Update SHG Contribution status directly from payment reference.
    
    Args:
        contrib_name (str): Name of the SHG Contribution
        payment_entry_name (str): Name of the Payment Entry
        paid_amount (float): Amount paid (optional)
    """
    try:
        shg_contribution = frappe.get_doc("SHG Contribution", contrib_name)
        
        if paid_amount:
            # Calculate new amounts based on payment
            current_paid = flt(shg_contribution.amount_paid or 0)
            new_paid = current_paid + flt(paid_amount)
            expected_amount = flt(shg_contribution.expected_amount or shg_contribution.amount)
            new_unpaid = max(0, expected_amount - new_paid)
            
            shg_contribution.db_set("amount_paid", new_paid)
            shg_contribution.db_set("unpaid_amount", new_unpaid)
            
            # Update status based on payment
            if new_unpaid <= 0:
                shg_contribution.db_set("status", "Paid")
            elif new_paid > 0:
                shg_contribution.db_set("status", "Partially Paid")
            else:
                shg_contribution.db_set("status", "Unpaid")
        else:
            # Just mark as paid without recalculating amounts
            shg_contribution.db_set("status", "Paid")
        
        # Record payment reference
        shg_contribution.db_set("payment_entry", payment_entry_name)
        
        # Save the contribution to trigger any necessary updates
        shg_contribution.flags.ignore_permissions = True
        shg_contribution.save()
                
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 
                        f"SHG Contribution Direct Status Update Failed for {contrib_name}")


def update_shg_meeting_fine_status_direct(fine_name, payment_entry_name):
    """
    Update SHG Meeting Fine status directly from payment reference.
    
    Args:
        fine_name (str): Name of the SHG Meeting Fine
        payment_entry_name (str): Name of the Payment Entry
    """
    try:
        fine = frappe.get_doc("SHG Meeting Fine", fine_name)
        fine.db_set("status", "Paid")
        fine.db_set("payment_entry", payment_entry_name)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 
                        f"SHG Meeting Fine Direct Status Update Failed for {fine_name}")


def update_shg_loan_repayment_status_direct(repayment_name, payment_entry_name):
    """
    Update SHG Loan Repayment status directly from payment reference.
    
    Args:
        repayment_name (str): Name of the SHG Loan Repayment
        payment_entry_name (str): Name of the Payment Entry
    """
    try:
        repayment = frappe.get_doc("SHG Loan Repayment", repayment_name)
        
        # Update payment status
        principal_paid = repayment.principal_amount
        interest_paid = repayment.interest_amount
        repayment.db_set("amount_paid", principal_paid + interest_paid)
        repayment.db_set("status", "Paid")
        repayment.db_set("payment_entry", payment_entry_name)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 
                        f"SHG Loan Repayment Direct Status Update Failed for {repayment_name}")