import frappe
from frappe import _
from frappe.utils import flt, today
from shg.shg.utils.account_helpers import get_or_create_member_receivable
from shg.shg.utils.company_utils import get_default_company


@frappe.whitelist(allow_guest=False)
def get_outstanding(doctype, name):
    """
    Get outstanding amount for a document.
    
    Args:
        doctype (str): Document type
        name (str): Document name
        
    Returns:
        float: Outstanding amount
    """
    return _get_outstanding_amount(doctype, name)


@frappe.whitelist(allow_guest=False)
def process_single_payment(payment_doc_name):
    """
    Process a single payment entry.
    
    Args:
        payment_doc_name (str): Name of the SHG Payment Entry document
        
    Returns:
        str: Payment Entry name
    """
    payment_doc = frappe.get_doc("SHG Payment Entry", payment_doc_name)
    return _process_single_payment(payment_doc)


@frappe.whitelist(allow_guest=False)
def process_bulk_payment(parent_doc_name):
    """
    Process a bulk payment for multiple invoices.
    
    Args:
        parent_doc_name (str): Name of the SHG Multi Member Payment document
        
    Returns:
        str: Payment Entry name
    """
    parent_doc = frappe.get_doc("SHG Multi Member Payment", parent_doc_name)
    return _process_bulk_payment(parent_doc)


@frappe.whitelist(allow_guest=False)
def get_unpaid_invoices(member):
    """
    Get all unpaid contribution invoices for a specific member.
    
    Args:
        member (str): Member ID
        
    Returns:
        list: List of unpaid contribution invoices
    """
    if not member:
        return []
    return _get_unpaid_records_for_member("SHG Contribution Invoice", member)


@frappe.whitelist(allow_guest=False)
def get_unpaid_contributions(member):
    """
    Get all unpaid contributions for a specific member.
    
    Args:
        member (str): Member ID
        
    Returns:
        list: List of unpaid contributions
    """
    if not member:
        return []
    return _get_unpaid_records_for_member("SHG Contribution", member)


@frappe.whitelist(allow_guest=False)
def get_unpaid_fines(member):
    """
    Get all unpaid meeting fines for a specific member.
    
    Args:
        member (str): Member ID
        
    Returns:
        list: List of unpaid meeting fines
    """
    if not member:
        return []
    return _get_unpaid_records_for_member("SHG Meeting Fine", member)


@frappe.whitelist(allow_guest=False)
def get_all_unpaid(member):
    """
    Get all unpaid items (invoices, contributions, fines) for a specific member.
    
    Args:
        member (str): Member ID
        
    Returns:
        list: List of all unpaid items
    """
    if not member:
        return []
    
    unpaid_items = []
    unpaid_items.extend(_get_unpaid_records_for_member("SHG Contribution Invoice", member))
    unpaid_items.extend(_get_unpaid_records_for_member("SHG Contribution", member))
    unpaid_items.extend(_get_unpaid_records_for_member("SHG Meeting Fine", member))
    
    # Sort by date descending
    unpaid_items.sort(key=lambda x: x["date"] or "", reverse=True)
    
    return unpaid_items


def _get_unpaid_records(doctype):
    """
    Internal helper to get unpaid records of a specific doctype.
    
    Args:
        doctype (str): Document type
        
    Returns:
        list: List of unpaid records
    """
    try:
        unpaid_items = []
        
        if doctype == "SHG Contribution Invoice":
            # Build query for contribution invoices
            query = """
                SELECT name, member, member_name, invoice_date AS date, amount, status
                FROM `tabSHG Contribution Invoice`
                WHERE status IN ('Unpaid', 'Partially Paid') 
                  AND docstatus = 1
            """
            # Add is_closed check if column exists
            if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
                query += " AND (is_closed IS NULL OR is_closed = 0)"
            
            invoice_data = frappe.db.sql(query, as_dict=True)
            
            for invoice in invoice_data:
                # For contribution invoices: if status = Partially Paid, treat outstanding = full amount
                # (until part-payment logic exists)
                outstanding = flt(invoice.amount or 0)
                if outstanding > 0:  # Only include if outstanding > 0
                    # Get additional info
                    is_closed = 0
                    posted_to_gl = 0
                    if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
                        is_closed = frappe.db.get_value("SHG Contribution Invoice", invoice.name, "is_closed") or 0
                    if frappe.db.has_column("SHG Contribution Invoice", "posted_to_gl"):
                        posted_to_gl = frappe.db.get_value("SHG Contribution Invoice", invoice.name, "posted_to_gl") or 0
                    
                    unpaid_items.append({
                        "reference_doctype": "SHG Contribution Invoice",
                        "reference_name": invoice.name,
                        "member": invoice.member,
                        "member_name": invoice.member_name,
                        "date": invoice.date,
                        "amount": flt(invoice.amount),
                        "outstanding_amount": outstanding,
                        "status": invoice.status,
                        "is_closed": is_closed,
                        "posted_to_gl": posted_to_gl
                    })
        
        elif doctype == "SHG Contribution":
            # Get unpaid SHG Contributions
            contribution_data = frappe.db.sql("""
                SELECT name, member, member_name, contribution_date AS date,
                       expected_amount, amount, amount_paid, unpaid_amount, status
                FROM `tabSHG Contribution`
                WHERE status IN ('Unpaid', 'Partially Paid') AND docstatus = 1
            """, as_dict=True)
            
            for contribution in contribution_data:
                # For contributions: outstanding = unpaid_amount
                outstanding = flt(contribution.unpaid_amount or 0)
                if outstanding > 0:  # Only include if outstanding > 0
                    # Get additional info
                    is_closed = 0
                    posted_to_gl = 0
                    if frappe.db.has_column("SHG Contribution", "is_closed"):
                        is_closed = frappe.db.get_value("SHG Contribution", contribution.name, "is_closed") or 0
                    if frappe.db.has_column("SHG Contribution", "posted_to_gl"):
                        posted_to_gl = frappe.db.get_value("SHG Contribution", contribution.name, "posted_to_gl") or 0
                    
                    unpaid_items.append({
                        "reference_doctype": "SHG Contribution",
                        "reference_name": contribution.name,
                        "member": contribution.member,
                        "member_name": contribution.member_name,
                        "date": contribution.date,
                        "amount": flt(contribution.expected_amount or contribution.amount),
                        "outstanding_amount": outstanding,
                        "status": contribution.status,
                        "is_closed": is_closed,
                        "posted_to_gl": posted_to_gl
                    })
        
        elif doctype == "SHG Meeting Fine":
            # Get unpaid SHG Meeting Fines
            fine_data = frappe.db.sql("""
                SELECT name, member, member_name, fine_amount, meeting, status, fine_date
                FROM `tabSHG Meeting Fine`
                WHERE status != 'Paid' AND docstatus = 1
            """, as_dict=True)
            
            for fine in fine_data:
                # For meeting fines: outstanding = fine_amount
                outstanding = flt(fine.fine_amount or 0)
                if outstanding > 0:  # Only include if outstanding > 0
                    # Get additional info
                    is_closed = 0
                    posted_to_gl = 0
                    if frappe.db.has_column("SHG Meeting Fine", "is_closed"):
                        is_closed = frappe.db.get_value("SHG Meeting Fine", fine.name, "is_closed") or 0
                    if frappe.db.has_column("SHG Meeting Fine", "posted_to_gl"):
                        posted_to_gl = frappe.db.get_value("SHG Meeting Fine", fine.name, "posted_to_gl") or 0
                    
                    # Get meeting date if meeting exists
                    meeting_date = fine.fine_date
                    if fine.meeting:
                        meeting_date = frappe.db.get_value("SHG Meeting", fine.meeting, "meeting_date") or fine.fine_date
                    
                    unpaid_items.append({
                        "reference_doctype": "SHG Meeting Fine",
                        "reference_name": fine.name,
                        "member": fine.member,
                        "member_name": fine.member_name,
                        "date": meeting_date,
                        "amount": flt(fine.fine_amount),
                        "outstanding_amount": outstanding,
                        "status": fine.status,
                        "is_closed": is_closed,
                        "posted_to_gl": posted_to_gl
                    })
        
        return unpaid_items
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Get Unpaid Records Failed for {doctype}")
        frappe.throw(_("Failed to fetch unpaid records for {0}: {1}").format(doctype, str(e)))


def _get_unpaid_records_for_member(doctype, member):
    """
    Internal helper to get unpaid records of a specific doctype for a specific member.
    
    Args:
        doctype (str): Document type
        member (str): Member ID
        
    Returns:
        list: List of unpaid records for the member
    """
    try:
        unpaid_items = []
        
        if doctype == "SHG Contribution Invoice":
            # Build query for contribution invoices
            query = """
                SELECT name, member, member_name, invoice_date AS date, amount, status
                FROM `tabSHG Contribution Invoice`
                WHERE member = %(member)s
                  AND status IN ('Unpaid', 'Partially Paid') 
                  AND docstatus = 1
            """
            # Add is_closed check if column exists
            if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
                query += " AND (is_closed IS NULL OR is_closed = 0)"
            
            invoice_data = frappe.db.sql(query, {"member": member}, as_dict=True)
            
            for invoice in invoice_data:
                # For contribution invoices: if status = Partially Paid, treat outstanding = full amount
                # (until part-payment logic exists)
                outstanding = flt(invoice.amount or 0)
                if outstanding > 0:  # Only include if outstanding > 0
                    # Get additional info
                    is_closed = 0
                    posted_to_gl = 0
                    if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
                        is_closed = frappe.db.get_value("SHG Contribution Invoice", invoice.name, "is_closed") or 0
                    if frappe.db.has_column("SHG Contribution Invoice", "posted_to_gl"):
                        posted_to_gl = frappe.db.get_value("SHG Contribution Invoice", invoice.name, "posted_to_gl") or 0
                    
                    unpaid_items.append({
                        "reference_doctype": "SHG Contribution Invoice",
                        "reference_name": invoice.name,
                        "member": invoice.member,
                        "member_name": invoice.member_name,
                        "date": invoice.date,
                        "amount": flt(invoice.amount),
                        "outstanding_amount": outstanding,
                        "status": invoice.status,
                        "is_closed": is_closed,
                        "posted_to_gl": posted_to_gl
                    })
        
        elif doctype == "SHG Contribution":
            # Get unpaid SHG Contributions
            contribution_data = frappe.db.sql("""
                SELECT name, member, member_name, contribution_date AS date,
                       expected_amount, amount, amount_paid, unpaid_amount, status
                FROM `tabSHG Contribution`
                WHERE member = %(member)s
                  AND status IN ('Unpaid', 'Partially Paid') AND docstatus = 1
            """, {"member": member}, as_dict=True)
            
            for contribution in contribution_data:
                # For contributions: outstanding = unpaid_amount
                outstanding = flt(contribution.unpaid_amount or 0)
                if outstanding > 0:  # Only include if outstanding > 0
                    # Get additional info
                    is_closed = 0
                    posted_to_gl = 0
                    if frappe.db.has_column("SHG Contribution", "is_closed"):
                        is_closed = frappe.db.get_value("SHG Contribution", contribution.name, "is_closed") or 0
                    if frappe.db.has_column("SHG Contribution", "posted_to_gl"):
                        posted_to_gl = frappe.db.get_value("SHG Contribution", contribution.name, "posted_to_gl") or 0
                    
                    unpaid_items.append({
                        "reference_doctype": "SHG Contribution",
                        "reference_name": contribution.name,
                        "member": contribution.member,
                        "member_name": contribution.member_name,
                        "date": contribution.date,
                        "amount": flt(contribution.expected_amount or contribution.amount),
                        "outstanding_amount": outstanding,
                        "status": contribution.status,
                        "is_closed": is_closed,
                        "posted_to_gl": posted_to_gl
                    })
        
        elif doctype == "SHG Meeting Fine":
            # Get unpaid SHG Meeting Fines
            fine_data = frappe.db.sql("""
                SELECT name, member, member_name, fine_amount, meeting, status, fine_date
                FROM `tabSHG Meeting Fine`
                WHERE member = %(member)s
                  AND status != 'Paid' AND docstatus = 1
            """, {"member": member}, as_dict=True)
            
            for fine in fine_data:
                # For meeting fines: outstanding = fine_amount
                outstanding = flt(fine.fine_amount or 0)
                if outstanding > 0:  # Only include if outstanding > 0
                    # Get additional info
                    is_closed = 0
                    posted_to_gl = 0
                    if frappe.db.has_column("SHG Meeting Fine", "is_closed"):
                        is_closed = frappe.db.get_value("SHG Meeting Fine", fine.name, "is_closed") or 0
                    if frappe.db.has_column("SHG Meeting Fine", "posted_to_gl"):
                        posted_to_gl = frappe.db.get_value("SHG Meeting Fine", fine.name, "posted_to_gl") or 0
                    
                    unpaid_items.append({
                        "reference_doctype": "SHG Meeting Fine",
                        "reference_name": fine.name,
                        "member": fine.member,
                        "member_name": fine.member_name,
                        "date": fine.fine_date,
                        "amount": flt(fine.fine_amount),
                        "outstanding_amount": outstanding,
                        "status": fine.status,
                        "is_closed": is_closed,
                        "posted_to_gl": posted_to_gl
                    })
        
        return unpaid_items
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Get Unpaid Records for Member Failed for {doctype}")
        frappe.throw(_("Failed to fetch unpaid records for {0} for member {1}: {2}").format(doctype, member, str(e)))


def _get_outstanding_amount(doctype, name):
    """
    Internal helper to get outstanding amount for a document.
    
    Args:
        doctype (str): Document type
        name (str): Document name
        
    Returns:
        float: Outstanding amount
    """
    if doctype == "SHG Contribution Invoice":
        doc = frappe.get_doc(doctype, name)
        # For contribution invoices: amount (no amount_paid field exists)
        return flt(doc.amount or 0)
    
    elif doctype == "SHG Contribution":
        doc = frappe.get_doc(doctype, name)
        # For contributions: unpaid_amount
        return flt(doc.unpaid_amount or 0)
    
    elif doctype == "SHG Meeting Fine":
        doc = frappe.get_doc(doctype, name)
        # For meeting fines: fine_amount if status != "Paid"
        if doc.status == "Paid":
            return 0.0
        return flt(doc.fine_amount or 0)
    
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


def _process_single_payment(payment_doc):
    """
    Internal helper to process a single payment entry.
    
    Args:
        payment_doc: SHG Payment Entry document
        
    Returns:
        str: Payment Entry name
    """
    try:
        # Validate reference
        if payment_doc.reference_doctype and payment_doc.reference_name:
            _validate_doc_exists(payment_doc.reference_doctype, payment_doc.reference_name)
            
            # Get outstanding
            outstanding = _get_outstanding_amount(payment_doc.reference_doctype, payment_doc.reference_name)
            if outstanding <= 0:
                frappe.throw(_("Referenced document has no outstanding amount"))
        
        # Create Payment Entry using correct ERPNext Payment Entry fields
        # Safely get company from document with fallback to SHG Settings
        company = getattr(payment_doc, "company", None)
        if not company:
            company = frappe.db.get_single_value("SHG Settings", "company")
        
        pe_name = _create_payment_entry_for_shg(
            company=company,
            mode_of_payment=payment_doc.mode_of_payment,
            member=payment_doc.member,
            posting_date=payment_doc.payment_date,
            paid_amount=flt(payment_doc.amount),
            received_amount=flt(payment_doc.amount),
            reference_doctype=payment_doc.reference_doctype,
            reference_name=payment_doc.reference_name
        )
        
        # Apply payment
        if payment_doc.reference_doctype and payment_doc.reference_name:
            _apply_payment_to_document(
                payment_doc.reference_doctype,
                payment_doc.reference_name,
                flt(payment_doc.amount),
                pe_name
            )
        
        # Update payment entry reference
        payment_doc.db_set("payment_entry", pe_name)
        
        return pe_name
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Process Single Payment Failed for {payment_doc.name}")
        frappe.throw(_("Failed to process payment: {0}").format(str(e)))


def _process_bulk_payment(parent_doc):
    """
    Internal helper to process a bulk payment for multiple invoices.
    
    Args:
        parent_doc: SHG Multi Member Payment document
        
    Returns:
        str: Payment Entry name
    """
    try:
        total_allocated = 0.0
        references = []
        
        # Process each invoice
        for row in parent_doc.invoices:
            if row.payment_amount and flt(row.payment_amount) > 0:
                # Validate reference
                _validate_doc_exists(row.reference_doctype, row.reference_name)
                
                # Get outstanding
                outstanding = _get_outstanding_amount(row.reference_doctype, row.reference_name)
                if flt(row.payment_amount) > outstanding:
                    frappe.throw(_("Document {0} has only {1} outstanding, cannot allocate {2}").format(
                        row.reference_name, outstanding, row.payment_amount))
                
                references.append({
                    "reference_doctype": row.reference_doctype,
                    "reference_name": row.reference_name,
                    "allocated_amount": flt(row.payment_amount)
                })
                
                total_allocated += flt(row.payment_amount)
        
        # Validate total matches
        if abs(total_allocated - flt(parent_doc.total_payment_amount)) > 0.01:
            frappe.throw(_("Total allocated amount {0} does not match total payment amount {1}").format(
                total_allocated, parent_doc.total_payment_amount))
        
        # Create Payment Entry using correct ERPNext Payment Entry fields
        # Safely get company from document with fallback to SHG Settings
        company = getattr(parent_doc, "company", None)
        if not company:
            company = frappe.db.get_single_value("SHG Settings", "company")
        
        pe_name = _create_payment_entry_for_shg(
            company=company,
            mode_of_payment=parent_doc.mode_of_payment,
            member=parent_doc.member,  # Use the member from the parent document
            posting_date=parent_doc.payment_date,
            paid_amount=total_allocated,
            received_amount=total_allocated,
            references=references
        )
        
        # Apply payments to all documents
        for row in parent_doc.invoices:
            if row.payment_amount and flt(row.payment_amount) > 0:
                _apply_payment_to_document(
                    row.reference_doctype,
                    row.reference_name,
                    flt(row.payment_amount),
                    pe_name
                )
        
        # Update parent document with payment entry reference
        parent_doc.db_set("payment_entry", pe_name)
        
        return pe_name
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Process Bulk Payment Failed for {parent_doc.name}")
        frappe.throw(_("Failed to process bulk payment: {0}").format(str(e)))


def _create_payment_entry_for_shg(company, mode_of_payment, member, posting_date, paid_amount, received_amount,
                                 reference_doctype=None, reference_name=None, references=None):
    """
    Internal helper to create a Payment Entry for SHG payments.
    
    Args:
        company (str): Company name
        mode_of_payment (str): Mode of payment
        member (str): Member ID (can be None for bulk payments)
        posting_date (str): Posting date
        paid_amount (float): Paid amount
        received_amount (float): Received amount
        reference_doctype (str): Reference doctype
        reference_name (str): Reference name
        references (list): List of references
        
    Returns:
        str: Payment Entry name
    """
    # Get company from SHG Settings instead of from document
    from shg.shg.utils.company_utils import get_default_company
    company = get_default_company()
    if not company:
        frappe.throw(_("Company is required for payment processing. Please set company in SHG Settings."))
    
    # Get default bank account from SHG Settings or fallback to Cash
    default_bank_account = frappe.db.get_single_value("SHG Settings", "default_bank_account")
    if not default_bank_account:
        abbr = frappe.db.get_value("Company", company, "abbr")
        default_bank_account = f"Cash - {abbr}"
    
    # Determine accounts based on payment type (Receive)
    if member:
        # For individual member payments
        paid_from = get_or_create_member_receivable(member, company)
        paid_to = default_bank_account
    else:
        # For bulk payments
        paid_from = default_bank_account
        paid_to = default_bank_account
    
    # Create Payment Entry with correct ERPNext fields
    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.company = company
    pe.mode_of_payment = mode_of_payment
    pe.posting_date = posting_date
    pe.paid_from = paid_from
    pe.paid_to = paid_to
    pe.paid_amount = flt(paid_amount)
    pe.received_amount = flt(received_amount)
    
    # Add party info - for bulk payments, we need to set party_type and party
    if member:
        pe.party_type = "SHG Member"
        pe.party = member
    else:
        # For bulk payments with no specific member, we still need to set party_type
        # But we don't set a specific party since it's a bulk payment
        # This avoids the "Party is mandatory" error in ERPNext
        pass
    
    # Add references
    if references:
        for ref in references:
            pe.append("references", ref)
    elif reference_doctype and reference_name:
        pe.append("references", {
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "allocated_amount": flt(paid_amount)
        })
    
    # Save and submit
    pe.insert(ignore_permissions=True)
    pe.submit()
    
    return pe.name


def _apply_payment_to_document(doctype, name, amount, payment_entry_name):
    """
    Internal helper to apply payment to a document and update its status.
    
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
        
        # Update status based on payment (simplified for now)
        doc.db_set("status", "Paid")
        
        # Auto-close invoice after full payment
        mark_invoice_paid_and_closed(name, payment_entry_name)
    
    elif doctype == "SHG Contribution":
        doc = frappe.get_doc(doctype, name)
        
        # Update payment reference
        if payment_entry_name:
            doc.db_set("payment_entry", payment_entry_name)
        
        # Update paid amounts
        current_paid = flt(doc.amount_paid or 0)
        new_paid = current_paid + flt(amount)
        doc.db_set("amount_paid", new_paid)
        
        # Recalculate unpaid amount and status
        expected = flt(doc.expected_amount or doc.amount or 0)
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
        try:
            member = frappe.get_doc("SHG Member", doc.member)
            member.update_financial_summary()
        except Exception:
            pass
    
    elif doctype == "SHG Meeting Fine":
        doc = frappe.get_doc(doctype, name)
        
        # Update payment reference
        if payment_entry_name:
            doc.db_set("payment_entry", payment_entry_name)
        
        # Update status
        doc.db_set("status", "Paid")


def mark_invoice_paid_and_closed(invoice_name, payment_entry_name=None):
    """
    Mark an invoice as paid and closed after full payment.
    
    Args:
        invoice_name (str): Name of the SHG Contribution Invoice
        payment_entry_name (str): Payment Entry name
    """
    invoice = frappe.get_doc("SHG Contribution Invoice", invoice_name)
    invoice.db_set("status", "Paid")
    if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
        invoice.db_set("is_closed", 1)
    if payment_entry_name and frappe.db.has_column("SHG Contribution Invoice", "payment_reference"):
        invoice.db_set("payment_reference", payment_entry_name)
    frappe.logger().info(f"[SHG] Invoice {invoice_name} marked Paid & closed via {payment_entry_name}")


def _validate_doc_exists(doctype, name):
    """
    Internal helper to validate that a document exists.
    
    Args:
        doctype (str): Document type
        name (str): Document name
    """
    if not frappe.db.exists(doctype, name):
        frappe.throw(_("Referenced document {0} {1} does not exist").format(doctype, name))


def _validate_amount(amount, field_name):
    """
    Internal helper to validate that an amount is positive.
    
    Args:
        amount (float): Amount to validate
        field_name (str): Field name for error message
    """
    if flt(amount) <= 0:
        frappe.throw(_("{0} must be greater than zero").format(_(field_name)))


def _get_company(company=None):
    """
    Internal helper to get company.
    
    Args:
        company (str): Company name (optional)
        
    Returns:
        str: Company name
    """
    return company or get_default_company()


def _get_member_account(member, company):
    """
    Internal helper to get member account.
    
    Args:
        member (str): Member ID
        company (str): Company name
        
    Returns:
        str: Member account name
    """
    return get_or_create_member_receivable(member, company)


def compute_document_outstanding(doctype, name):
    """
    Compute outstanding amount for a document.
    
    Args:
        doctype (str): Document type
        name (str): Document name
        
    Returns:
        float: Outstanding amount
    """
    return _get_outstanding_amount(doctype, name)


def is_closed_document(doctype, name):
    """
    Check if a document is closed.
    
    Args:
        doctype (str): Document type
        name (str): Document name
        
    Returns:
        bool: True if document is closed
    """
    if frappe.db.has_column(doctype, "is_closed"):
        return frappe.db.get_value(doctype, name, "is_closed") or False
    return False


def is_paid_document(doctype, name):
    """
    Check if a document is paid.
    
    Args:
        doctype (str): Document type
        name (str): Document name
        
    Returns:
        bool: True if document is paid
    """
    status = frappe.db.get_value(doctype, name, "status")
    return status == "Paid"


def is_document_already_processed(doctype, name, current_parent):
    """
    Check if a document is already processed in another submitted payment batch.
    
    Args:
        doctype (str): Document type
        name (str): Document name
        current_parent (str): Current parent document name
        
    Returns:
        bool: True if document is already processed
    """
    existing_payments = frappe.db.sql("""
        SELECT parent
        FROM `tabSHG Multi Member Payment Invoice`
        WHERE reference_doctype = %s AND reference_name = %s AND parent != %s
    """, (doctype, name, current_parent))
    
    for payment in existing_payments:
        payment_docstatus = frappe.db.get_value("SHG Multi Member Payment", payment[0], "docstatus")
        if payment_docstatus == 1:  # Submitted
            return True
    return False


def prepare_child_row(doctype, name):
    """
    Prepare child row data for insertion into bulk payment.
    
    Args:
        doctype (str): Document type
        name (str): Document name
        
    Returns:
        dict: Child row data
    """
    # Get document data
    if doctype == "SHG Contribution Invoice":
        doc = frappe.get_doc(doctype, name)
        outstanding = flt(doc.amount or 0)
        is_closed = 0
        posted_to_gl = 0
        if frappe.db.has_column(doctype, "is_closed"):
            is_closed = frappe.db.get_value(doctype, name, "is_closed") or 0
        if frappe.db.has_column(doctype, "posted_to_gl"):
            posted_to_gl = frappe.db.get_value(doctype, name, "posted_to_gl") or 0
        
        return {
            "reference_doctype": doctype,
            "reference_name": name,
            "member": doc.member,
            "member_name": doc.member_name,
            "date": doc.invoice_date,
            "amount": flt(doc.amount),
            "outstanding_amount": outstanding,
            "payment_amount": outstanding,
            "status": doc.status,
            "is_closed": is_closed,
            "posted_to_gl": posted_to_gl
        }
    
    elif doctype == "SHG Contribution":
        doc = frappe.get_doc(doctype, name)
        outstanding = flt(doc.unpaid_amount or 0)
        is_closed = 0
        posted_to_gl = 0
        if frappe.db.has_column(doctype, "is_closed"):
            is_closed = frappe.db.get_value(doctype, name, "is_closed") or 0
        if frappe.db.has_column(doctype, "posted_to_gl"):
            posted_to_gl = frappe.db.get_value(doctype, name, "posted_to_gl") or 0
        
        return {
            "reference_doctype": doctype,
            "reference_name": name,
            "member": doc.member,
            "member_name": doc.member_name,
            "date": doc.contribution_date,
            "amount": flt(doc.expected_amount or doc.amount),
            "outstanding_amount": outstanding,
            "payment_amount": outstanding,
            "status": doc.status,
            "is_closed": is_closed,
            "posted_to_gl": posted_to_gl
        }
    
    elif doctype == "SHG Meeting Fine":
        doc = frappe.get_doc(doctype, name)
        outstanding = flt(doc.fine_amount or 0)
        is_closed = 0
        posted_to_gl = 0
        if frappe.db.has_column(doctype, "is_closed"):
            is_closed = frappe.db.get_value(doctype, name, "is_closed") or 0
        if frappe.db.has_column(doctype, "posted_to_gl"):
            posted_to_gl = frappe.db.get_value(doctype, name, "posted_to_gl") or 0
        
        # Get meeting date if meeting exists
        meeting_date = doc.fine_date
        if doc.meeting:
            meeting_date = frappe.db.get_value("SHG Meeting", doc.meeting, "meeting_date") or doc.fine_date
        
        return {
            "reference_doctype": doctype,
            "reference_name": name,
            "member": doc.member,
            "member_name": doc.member_name,
            "date": meeting_date,
            "amount": flt(doc.fine_amount),
            "outstanding_amount": outstanding,
            "payment_amount": outstanding,
            "status": doc.status,
            "is_closed": is_closed,
            "posted_to_gl": posted_to_gl
        }