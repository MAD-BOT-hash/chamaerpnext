import frappe
from frappe import _
from frappe.utils import flt
from shg.shg.utils.account_helpers import get_or_create_member_receivable
from shg.shg.utils.company_utils import get_default_company


def get_outstanding(doctype, name):
    """
    Get outstanding amount for a document.
    
    Args:
        doctype (str): Document type
        name (str): Document name
        
    Returns:
        float: Outstanding amount
    """
    if doctype == "SHG Contribution Invoice":
        doc = frappe.get_doc(doctype, name)
        # For contribution invoices, we check the linked Sales Invoice
        if doc.sales_invoice:
            sales_invoice = frappe.get_doc("Sales Invoice", doc.sales_invoice)
            return flt(sales_invoice.outstanding_amount)
        else:
            # If no Sales Invoice, check status
            if doc.status in ["Paid", "Closed"]:
                return 0.0
            return flt(doc.amount)
    
    elif doctype == "SHG Contribution":
        doc = frappe.get_doc(doctype, name)
        if doc.status in ["Paid", "Closed"]:
            return 0.0
        return flt(doc.unpaid_amount or doc.amount)
    
    elif doctype == "SHG Meeting Fine":
        doc = frappe.get_doc(doctype, name)
        if doc.status == "Paid":
            return 0.0
        return flt(doc.fine_amount)
    
    else:
        # For other doctypes, try to get outstanding_amount field
        try:
            outstanding = frappe.db.get_value(doctype, name, "outstanding_amount")
            return flt(outstanding) if outstanding else 0.0
        except Exception:
            # If no outstanding_amount field, assume fully outstanding
            try:
                amount = frappe.db.get_value(doctype, name, "amount")
                return flt(amount) if amount else 0.0
            except Exception:
                return 0.0


def process_single_payment(payment_doc):
    """
    Process a single payment entry.
    
    Responsibilities:
    - Create Payment Entry
    - Allocate full amount
    - Update linked record: mark Paid / Partially Paid
    - Update unpaid amounts
    - Set payment_doc.payment_entry field
    
    Args:
        payment_doc: SHG Payment Entry document
    """
    try:
        # Get company
        company = payment_doc.company or get_default_company()
        if not company:
            frappe.throw(_("Company is required for payment processing"))
        
        # Get member account
        member_account = get_or_create_member_receivable(payment_doc.party, company)
        
        # Get default bank account from SHG Settings or fallback to Cash
        default_bank_account = frappe.db.get_single_value("SHG Settings", "default_bank_account")
        if not default_bank_account:
            abbr = frappe.db.get_value("Company", company, "abbr")
            default_bank_account = f"Cash - {abbr}"
        
        # Determine payment type based on reference
        if payment_doc.payment_type == "Receive":
            paid_from = member_account
            paid_to = default_bank_account
        else:
            paid_from = default_bank_account
            paid_to = member_account
        
        # Create Payment Entry
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = payment_doc.payment_type
        pe.company = company
        pe.mode_of_payment = payment_doc.mode_of_payment
        pe.party_type = payment_doc.party_type
        pe.party = payment_doc.party
        pe.posting_date = payment_doc.posting_date
        pe.paid_from = paid_from
        pe.paid_to = paid_to
        pe.paid_amount = flt(payment_doc.paid_amount)
        pe.received_amount = flt(payment_doc.received_amount)
        
        # Add reference if provided
        if payment_doc.reference_doctype and payment_doc.reference_name:
            pe.append("references", {
                "reference_doctype": payment_doc.reference_doctype,
                "reference_name": payment_doc.reference_name,
                "allocated_amount": flt(payment_doc.paid_amount)
            })
        
        # Set reference fields for traceability
        pe.reference_no = payment_doc.reference_no
        pe.reference_date = payment_doc.reference_date
        
        # Set remarks
        pe.remarks = payment_doc.remarks or f"Payment for {payment_doc.party}"
        
        # Save and submit
        pe.insert(ignore_permissions=True)
        pe.submit()
        
        # Update payment entry reference
        payment_doc.db_set("payment_entry", pe.name)
        
        # Update linked document
        if payment_doc.reference_doctype and payment_doc.reference_name:
            apply_payment(
                payment_doc.reference_doctype, 
                payment_doc.reference_name, 
                flt(payment_doc.paid_amount), 
                pe.name
            )
        
        frappe.msgprint(_("Payment processed successfully"))
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Process Single Payment Failed for {payment_doc.name}")
        frappe.throw(_("Failed to process payment: {0}").format(str(e)))


def process_bulk_payment(parent_doc):
    """
    Process a bulk payment for multiple invoices.
    
    Responsibilities:
    - Create ONE Payment Entry
    - Loop through child rows
    - Create Payment Entry references
    - Apply payments to each linked record
    - Close records when fully paid
    - Update parent with Payment Entry name
    
    Args:
        parent_doc: SHG Multi Member Payment document
    """
    try:
        # Get company
        company = parent_doc.company or get_default_company()
        if not company:
            frappe.throw(_("Company is required for payment processing"))
        
        # Get default bank account from SHG Settings or fallback to Cash
        default_bank_account = frappe.db.get_single_value("SHG Settings", "default_bank_account")
        if not default_bank_account:
            abbr = frappe.db.get_value("Company", company, "abbr")
            default_bank_account = f"Cash - {abbr}"
        
        # Create Payment Entry
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.company = company
        pe.mode_of_payment = parent_doc.payment_method
        pe.posting_date = parent_doc.payment_date
        pe.paid_amount = flt(parent_doc.total_payment_amount)
        pe.received_amount = flt(parent_doc.total_payment_amount)
        
        # For bulk payments, we'll use member account as paid_from and bank as paid_to
        # We'll set these per reference in the loop below
        pe.paid_from = default_bank_account
        pe.paid_to = default_bank_account
        
        total_allocated = 0.0
        
        # Process each invoice
        for row in parent_doc.invoices:
            if row.payment_amount and row.payment_amount > 0:
                # Get member account for this invoice
                member_account = get_or_create_member_receivable(row.member, company)
                
                # Add reference
                pe.append("references", {
                    "reference_doctype": "SHG Contribution Invoice",
                    "reference_name": row.invoice,
                    "allocated_amount": flt(row.payment_amount)
                })
                
                total_allocated += flt(row.payment_amount)
                
                # Update linked document
                apply_payment(
                    "SHG Contribution Invoice", 
                    row.invoice, 
                    flt(row.payment_amount), 
                    None  # We'll update this after submitting the payment entry
                )
        
        # Set the actual allocated amount
        pe.paid_amount = total_allocated
        pe.received_amount = total_allocated
        
        # Set reference fields for traceability
        pe.reference_no = parent_doc.name
        pe.reference_date = parent_doc.payment_date
        
        # Set remarks
        pe.remarks = parent_doc.description or f"Bulk payment for {len(parent_doc.invoices)} invoices"
        
        # Save and submit
        pe.insert(ignore_permissions=True)
        pe.submit()
        
        # Update parent document with payment entry reference
        parent_doc.db_set("payment_entry", pe.name)
        
        # Update all linked documents with the payment entry reference
        for row in parent_doc.invoices:
            if row.payment_amount and row.payment_amount > 0:
                apply_payment(
                    "SHG Contribution Invoice", 
                    row.invoice, 
                    flt(row.payment_amount), 
                    pe.name
                )
        
        frappe.msgprint(_("Bulk payment processed successfully"))
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Process Bulk Payment Failed for {parent_doc.name}")
        frappe.throw(_("Failed to process bulk payment: {0}").format(str(e)))


def cancel_linked_payment_entry(doc):
    """
    Cancel the linked payment entry and reverse statuses in linked docs.
    
    Args:
        doc: Document with payment_entry field
    """
    try:
        if doc.payment_entry and frappe.db.exists("Payment Entry", doc.payment_entry):
            payment_entry = frappe.get_doc("Payment Entry", doc.payment_entry)
            if payment_entry.docstatus == 1:
                payment_entry.cancel()
                
                # Reverse statuses in linked documents
                if hasattr(doc, 'invoices'):
                    # For bulk payment, reverse all linked invoices
                    for row in doc.invoices:
                        reverse_payment_status(row.invoice, "SHG Contribution Invoice")
                elif hasattr(doc, 'reference_doctype') and hasattr(doc, 'reference_name'):
                    # For single payment, reverse the linked document
                    reverse_payment_status(doc.reference_name, doc.reference_doctype)
                    
        # Update document status
        doc.db_set("status", "Cancelled")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Cancel Linked Payment Entry Failed for {doc.name}")
        frappe.throw(_("Failed to cancel payment entry: {0}").format(str(e)))


def apply_payment(doctype, name, amount, payment_entry_name):
    """
    Apply payment to a document and update its status.
    
    Args:
        doctype (str): Document type
        name (str): Document name
        amount (float): Amount paid
        payment_entry_name (str): Payment Entry name
    """
    if doctype == "SHG Contribution Invoice":
        doc = frappe.get_doc(doctype, name)
        
        # Update payment reference
        if payment_entry_name:
            doc.db_set("payment_reference", payment_entry_name)
        
        # Get the linked SHG Contribution
        contribution_name = frappe.db.get_value("SHG Contribution", 
                                              {"invoice_reference": name})
        
        if contribution_name:
            contribution = frappe.get_doc("SHG Contribution", contribution_name)
            
            # Update payment reference
            if payment_entry_name:
                contribution.db_set("payment_entry", payment_entry_name)
            
            # Update paid amounts
            current_paid = contribution.amount_paid or 0
            new_paid = current_paid + flt(amount)
            contribution.db_set("amount_paid", new_paid)
            
            # Recalculate unpaid amount and status
            expected = contribution.expected_amount or contribution.amount
            unpaid = max(0, expected - new_paid)
            contribution.db_set("unpaid_amount", unpaid)
            
            # Update status based on payment amount
            if unpaid <= 0:
                contribution.db_set("status", "Paid")
                doc.db_set("status", "Paid")
            elif new_paid > 0:
                contribution.db_set("status", "Partially Paid")
                doc.db_set("status", "Partially Paid")
            else:
                contribution.db_set("status", "Unpaid")
                doc.db_set("status", "Unpaid")
            
            # Update member financial summary
            member = frappe.get_doc("SHG Member", contribution.member)
            member.update_financial_summary()
    
    elif doctype == "SHG Contribution":
        doc = frappe.get_doc(doctype, name)
        
        # Update payment reference
        if payment_entry_name:
            doc.db_set("payment_entry", payment_entry_name)
        
        # Update paid amounts
        current_paid = doc.amount_paid or 0
        new_paid = current_paid + flt(amount)
        doc.db_set("amount_paid", new_paid)
        
        # Recalculate unpaid amount and status
        expected = doc.expected_amount or doc.amount
        unpaid = max(0, expected - new_paid)
        doc.db_set("unpaid_amount", unpaid)
        
        # Update status based on payment amount
        if unpaid <= 0:
            doc.db_set("status", "Paid")
        elif new_paid > 0:
            doc.db_set("status", "Partially Paid")
        else:
            doc.db_set("status", "Unpaid")
        
        # Update member financial summary
        member = frappe.get_doc("SHG Member", doc.member)
        member.update_financial_summary()
    
    elif doctype == "SHG Meeting Fine":
        doc = frappe.get_doc(doctype, name)
        
        # Update payment reference
        if payment_entry_name:
            doc.db_set("payment_entry", payment_entry_name)
        
        # Update status
        doc.db_set("status", "Paid")
        
        # Update member financial summary
        member = frappe.get_doc("SHG Member", doc.member)
        member.update_financial_summary()


def reverse_payment_status(name, doctype):
    """
    Reverse payment status when payment entry is cancelled.
    
    Args:
        name (str): Document name
        doctype (str): Document type
    """
    try:
        doc = frappe.get_doc(doctype, name)
        
        if doctype == "SHG Contribution Invoice":
            # Reset payment reference
            doc.db_set("payment_reference", None)
            doc.db_set("status", "Unpaid")
            
            # Reset linked contribution
            contribution_name = frappe.db.get_value("SHG Contribution", 
                                                  {"invoice_reference": name})
            if contribution_name:
                contribution = frappe.get_doc("SHG Contribution", contribution_name)
                contribution.db_set("payment_entry", None)
                contribution.db_set("amount_paid", 0)
                contribution.db_set("unpaid_amount", contribution.expected_amount or contribution.amount)
                contribution.db_set("status", "Unpaid")
                contribution.update_member_summary()
                
        elif doctype == "SHG Contribution":
            # Reset payment reference
            doc.db_set("payment_entry", None)
            doc.db_set("amount_paid", 0)
            doc.db_set("unpaid_amount", doc.expected_amount or doc.amount)
            doc.db_set("status", "Unpaid")
            doc.update_member_summary()
            
        elif doctype == "SHG Meeting Fine":
            # Reset payment reference
            doc.db_set("payment_entry", None)
            doc.db_set("status", "Pending")
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Reverse Payment Status Failed for {name} ({doctype})")