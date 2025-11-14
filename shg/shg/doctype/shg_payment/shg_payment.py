import frappe
from frappe import _
from frappe.utils import flt, nowdate
from shg.shg.utils.company_utils import get_default_company
from shg.shg.utils.account_utils import get_or_create_member_account


@frappe.whitelist()
def shg_receive_single_payment(document_type, document_name, amount, mode_of_payment, posting_date=None, reference_no=None):
    """
    Receive payment for a single document (Contribution Invoice, Contribution, or Meeting Fine)
    """
    # 1. Validate Inputs
    if document_type not in ["SHG Contribution Invoice", "SHG Contribution", "SHG Meeting Fine"]:
        frappe.throw(_("Invalid document type: {0}").format(document_type))
    
    if flt(amount) <= 0:
        frappe.throw(_("Payment amount must be greater than zero"))
    
    # Check if document exists
    if not frappe.db.exists(document_type, document_name):
        frappe.throw(_("Document {0} {1} not found").format(document_type, document_name))
    
    # Get document
    doc = frappe.get_doc(document_type, document_name)
    
    # Check if document is already fully paid
    if document_type == "SHG Contribution Invoice":
        if doc.status == "Paid":
            frappe.throw(_("Invoice {0} is already fully paid").format(document_name))
    elif document_type == "SHG Meeting Fine":
        if doc.status == "Paid":
            frappe.throw(_("Fine {0} is already fully paid").format(document_name))
    
    # 2. Determine Company
    company = get_default_company()
    if not company:
        frappe.throw(_("Default company not found in SHG Settings"))
    
    # 3. Get Member Account
    member = None
    if document_type in ["SHG Contribution Invoice", "SHG Contribution"]:
        member = doc.member
    elif document_type == "SHG Meeting Fine":
        member = doc.member
    
    if not member:
        frappe.throw(_("Member not found for document {0}").format(document_name))
    
    account = get_or_create_member_account(member, company)
    if not account:
        frappe.throw(_("Could not create or fetch member account for {0}").format(member))
    
    # 4. Create Payment Entry
    payment_entry = frappe.new_doc("Payment Entry")
    payment_entry.payment_type = "Receive"
    payment_entry.party_type = "Customer"
    payment_entry.party = member
    payment_entry.company = company
    payment_entry.posting_date = posting_date or nowdate()
    payment_entry.mode_of_payment = mode_of_payment
    payment_entry.paid_amount = flt(amount)
    payment_entry.received_amount = flt(amount)
    payment_entry.reference_no = reference_no
    
    # Get cash/bank account from SHG Settings
    if mode_of_payment == "Cash":
        cash_account = frappe.db.get_single_value("SHG Settings", "default_cash_account")
        if cash_account:
            payment_entry.paid_to = cash_account
    else:
        bank_account = frappe.db.get_single_value("SHG Settings", "default_bank_account")
        if bank_account:
            payment_entry.paid_to = bank_account
    
    # Set member account as paid from
    payment_entry.paid_from = account
    
    # Add reference
    payment_entry.append("references", {
        "reference_doctype": document_type,
        "reference_name": document_name,
        "allocated_amount": flt(amount)
    })
    
    # 5. Submit Payment Entry
    payment_entry.insert(ignore_permissions=True)
    payment_entry.submit()
    
    # 6. Update Linked Document
    if document_type == "SHG Contribution Invoice":
        # Update invoice status
        if doc.sales_invoice:
            # If linked to Sales Invoice, check outstanding amount
            sales_invoice = frappe.get_doc("Sales Invoice", doc.sales_invoice)
            if flt(amount) >= flt(sales_invoice.outstanding_amount):
                doc.db_set("status", "Paid")
                doc.db_set("is_closed", 1)
            else:
                doc.db_set("status", "Partially Paid")
        else:
            # For standalone invoices
            if flt(amount) >= flt(doc.amount):
                doc.db_set("status", "Paid")
                doc.db_set("is_closed", 1)
            else:
                doc.db_set("status", "Partially Paid")
        
        # Update linked contribution
        try:
            doc.mark_linked_contribution_as_paid()
        except Exception:
            frappe.log_error(frappe.get_traceback(), "SHG Payment - Update Linked Contribution Failed")
    
    elif document_type == "SHG Contribution":
        # Update contribution payment status
        try:
            doc.update_payment_status(flt(amount))
        except Exception:
            frappe.log_error(frappe.get_traceback(), "SHG Payment - Update Contribution Status Failed")
    
    elif document_type == "SHG Meeting Fine":
        # Update fine status
        doc.db_set("status", "Paid")
        # Post to ledger
        try:
            doc.post_to_ledger()
        except Exception:
            frappe.log_error(frappe.get_traceback(), "SHG Payment - Post Fine to Ledger Failed")
    
    # Update member financial summary
    try:
        member_doc = frappe.get_doc("SHG Member", member)
        member_doc.update_financial_summary()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "SHG Payment - Update Member Financial Summary Failed")
    
    return {
        "payment_entry": payment_entry.name,
        "status": "success",
        "message": _("Payment received successfully")
    }


@frappe.whitelist()
def shg_receive_bulk_payment(member, documents, amount, mode_of_payment, posting_date=None, reference_no=None):
    """
    Receive payment for multiple documents in a single Payment Entry
    """
    # 1. Validate total requested allocation = received amount
    total_allocated = sum(flt(row.get("amount", 0)) for row in documents)
    if abs(flt(total_allocated) - flt(amount)) > 0.01:
        frappe.throw(_("Total allocated amount ({0}) does not match payment amount ({1})").format(total_allocated, amount))
    
    # 2. Determine Company
    company = get_default_company()
    if not company:
        frappe.throw(_("Default company not found in SHG Settings"))
    
    # 3. Validate all documents exist and are not fully paid
    for row in documents:
        doctype = row.get("doctype")
        docname = row.get("name")
        
        if not frappe.db.exists(doctype, docname):
            frappe.throw(_("Document {0} {1} not found").format(doctype, docname))
        
        doc = frappe.get_doc(doctype, docname)
        
        if doctype == "SHG Contribution Invoice" and doc.status == "Paid":
            frappe.throw(_("Invoice {0} is already fully paid").format(docname))
        elif doctype == "SHG Meeting Fine" and doc.status == "Paid":
            frappe.throw(_("Fine {0} is already fully paid").format(docname))
    
    # 4. Get Member Account
    account = get_or_create_member_account(member, company)
    if not account:
        frappe.throw(_("Could not create or fetch member account for {0}").format(member))
    
    # 5. Create ONE Payment Entry for all references
    payment_entry = frappe.new_doc("Payment Entry")
    payment_entry.payment_type = "Receive"
    payment_entry.party_type = "Customer"
    payment_entry.party = member
    payment_entry.company = company
    payment_entry.posting_date = posting_date or nowdate()
    payment_entry.mode_of_payment = mode_of_payment
    payment_entry.paid_amount = flt(amount)
    payment_entry.received_amount = flt(amount)
    payment_entry.reference_no = reference_no
    
    # Get cash/bank account from SHG Settings
    if mode_of_payment == "Cash":
        cash_account = frappe.db.get_single_value("SHG Settings", "default_cash_account")
        if cash_account:
            payment_entry.paid_to = cash_account
    else:
        bank_account = frappe.db.get_single_value("SHG Settings", "default_bank_account")
        if bank_account:
            payment_entry.paid_to = bank_account
    
    # Set member account as paid from
    payment_entry.paid_from = account
    
    # Add multiple references
    updated_documents = []
    for row in documents:
        doctype = row.get("doctype")
        docname = row.get("name")
        alloc_amount = flt(row.get("amount", 0))
        
        if alloc_amount <= 0:
            continue
            
        payment_entry.append("references", {
            "reference_doctype": doctype,
            "reference_name": docname,
            "allocated_amount": alloc_amount
        })
    
    # 6. Submit Payment Entry
    payment_entry.insert(ignore_permissions=True)
    payment_entry.submit()
    
    # 7. Loop through all documents and update them
    for row in documents:
        doctype = row.get("doctype")
        docname = row.get("name")
        alloc_amount = flt(row.get("amount", 0))
        
        if alloc_amount <= 0:
            continue
            
        doc = frappe.get_doc(doctype, docname)
        
        if doctype == "SHG Contribution Invoice":
            # Update invoice status
            if doc.sales_invoice:
                # If linked to Sales Invoice, check outstanding amount
                sales_invoice = frappe.get_doc("Sales Invoice", doc.sales_invoice)
                if flt(alloc_amount) >= flt(sales_invoice.outstanding_amount):
                    doc.db_set("status", "Paid")
                    doc.db_set("is_closed", 1)
                else:
                    doc.db_set("status", "Partially Paid")
            else:
                # For standalone invoices
                if flt(alloc_amount) >= flt(doc.amount):
                    doc.db_set("status", "Paid")
                    doc.db_set("is_closed", 1)
                else:
                    doc.db_set("status", "Partially Paid")
            
            # Update linked contribution
            try:
                doc.mark_linked_contribution_as_paid()
            except Exception:
                frappe.log_error(frappe.get_traceback(), "SHG Bulk Payment - Update Linked Contribution Failed")
                
            updated_documents.append({
                "doctype": doctype,
                "name": docname,
                "new_status": doc.status
            })
        
        elif doctype == "SHG Contribution":
            # Update contribution payment status
            try:
                doc.update_payment_status(flt(alloc_amount))
                updated_documents.append({
                    "doctype": doctype,
                    "name": docname,
                    "new_status": doc.status
                })
            except Exception:
                frappe.log_error(frappe.get_traceback(), "SHG Bulk Payment - Update Contribution Status Failed")
        
        elif doctype == "SHG Meeting Fine":
            # Update fine status
            doc.db_set("status", "Paid")
            # Post to ledger
            try:
                doc.post_to_ledger()
            except Exception:
                frappe.log_error(frappe.get_traceback(), "SHG Bulk Payment - Post Fine to Ledger Failed")
                
            updated_documents.append({
                "doctype": doctype,
                "name": docname,
                "new_status": "Paid"
            })
    
    # Update member financial summary
    try:
        member_doc = frappe.get_doc("SHG Member", member)
        member_doc.update_financial_summary()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "SHG Bulk Payment - Update Member Financial Summary Failed")
    
    return {
        "payment_entry": payment_entry.name,
        "updated_documents": updated_documents,
        "status": "success",
        "message": _("Bulk payment processed successfully for {0} documents").format(len(documents))
    }


def on_payment_submit(doc, method):
    """
    Hook function called when Payment Entry is submitted
    """
    try:
        # Update linked documents when Payment Entry is submitted
        for reference in doc.references:
            if reference.reference_doctype == "SHG Contribution Invoice":
                invoice = frappe.get_doc("SHG Contribution Invoice", reference.reference_name)
                if invoice:
                    # Update invoice status based on payment
                    if reference.allocated_amount >= invoice.amount:
                        invoice.db_set("status", "Paid")
                        invoice.db_set("is_closed", 1)
                    else:
                        invoice.db_set("status", "Partially Paid")
                    
                    # Update linked contribution
                    try:
                        invoice.mark_linked_contribution_as_paid()
                    except Exception:
                        frappe.log_error(frappe.get_traceback(), "Payment Entry Submit - Update Linked Contribution Failed")
            
            elif reference.reference_doctype == "SHG Meeting Fine":
                fine = frappe.get_doc("SHG Meeting Fine", reference.reference_name)
                if fine:
                    fine.db_set("status", "Paid")
                    try:
                        fine.post_to_ledger()
                    except Exception:
                        frappe.log_error(frappe.get_traceback(), "Payment Entry Submit - Post Fine to Ledger Failed")
            
            elif reference.reference_doctype == "SHG Contribution":
                contribution = frappe.get_doc("SHG Contribution", reference.reference_name)
                if contribution:
                    try:
                        contribution.update_payment_status(reference.allocated_amount)
                    except Exception:
                        frappe.log_error(frappe.get_traceback(), "Payment Entry Submit - Update Contribution Status Failed")
        
        # Update member financial summary
        if doc.party_type == "Customer" and doc.party:
            try:
                member_doc = frappe.get_doc("SHG Member", doc.party)
                member_doc.update_financial_summary()
            except Exception:
                frappe.log_error(frappe.get_traceback(), "Payment Entry Submit - Update Member Financial Summary Failed")
                
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Payment Entry Submit Hook Failed")