import frappe
from frappe import _
from frappe.utils import flt, today
from shg.shg.utils.account_helpers import get_or_create_member_receivable
from shg.shg.utils.company_utils import get_default_company


DOCUMENT_META = {
    "SHG Contribution Invoice": {
        "date_field": "invoice_date",
        "amount_field": "amount",
        "status_field": "status",
        "status_paid_values": {"Paid"},
        "status_unpaid_values": {"Unpaid", "Partially Paid"},
        "is_closed_field": "is_closed",
        "posted_to_gl_field": "posted_to_gl",
        "payment_reference_field": "payment_reference",
    },
    "SHG Contribution": {
        "date_field": "contribution_date",
        "amount_field": "expected_amount",
        "fallback_amount_field": "amount",
        "outstanding_field": "unpaid_amount",
        "status_field": "status",
        "status_paid_values": {"Paid"},
        "status_unpaid_values": {"Unpaid", "Partially Paid"},
        "is_closed_field": "is_closed",
        "posted_to_gl_field": "posted_to_gl",
        "payment_reference_field": "payment_entry",
    },
    "SHG Meeting Fine": {
        "date_field": "fine_date",
        "amount_field": "fine_amount",
        "status_field": "status",
        "status_paid_values": {"Paid"},
        "status_unpaid_values": {"Pending"},
        "is_closed_field": "is_closed",
        "posted_to_gl_field": "posted_to_gl",
        "payment_reference_field": "payment_entry",
    },
    "SHG Loan Repayment": {
        "date_field": "repayment_date",
        "amount_field": "total_paid",
        "status_field": None,
        "is_closed_field": None,
        "posted_to_gl_field": "posted_to_gl",
        "payment_reference_field": "payment_entry",
    },
    "SHG Payment Entry": {
        "date_field": "payment_date",
        "amount_field": "amount",
        "outstanding_field": "outstanding_amount",
        "status_field": "payment_status",
        "display_status_field": "status",
        "status_paid_values": {"Paid"},
        "status_unpaid_values": {"Unpaid", "Partially Paid"},
        "is_closed_field": "is_closed",
        "posted_to_gl_field": "posted_to_gl",
        "payment_reference_field": "payment_entry",
    },
}


def _get_doctype_meta(doctype):
    return DOCUMENT_META.get(doctype, {})


def _read_optional_value(doctype, name, fieldname, default=None):
    if not fieldname or not frappe.db.has_column(doctype, fieldname):
        return default
    return frappe.db.get_value(doctype, name, fieldname) or default


def _normalize_document_status(doctype, row_or_doc):
    meta = _get_doctype_meta(doctype)
    status_field = meta.get("status_field")
    if status_field:
        status_value = row_or_doc.get(status_field) if isinstance(row_or_doc, dict) else getattr(row_or_doc, status_field, None)
        if status_value:
            return status_value

    display_status_field = meta.get("display_status_field")
    if display_status_field:
        status_value = row_or_doc.get(display_status_field) if isinstance(row_or_doc, dict) else getattr(row_or_doc, display_status_field, None)
        if status_value:
            return status_value

    docstatus = row_or_doc.get("docstatus") if isinstance(row_or_doc, dict) else getattr(row_or_doc, "docstatus", None)
    if docstatus == 2:
        return "Cancelled"
    if docstatus == 1:
        return "Submitted"
    return "Draft"


def _build_unpaid_invoice_query(member=None):
    conditions = ["docstatus = 1", "status IN ('Unpaid', 'Partially Paid')"]
    params = {}
    if member:
        conditions.append("member = %(member)s")
        params["member"] = member

    if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
        conditions.append("(is_closed IS NULL OR is_closed = 0)")

    query = f"""
        SELECT
            name,
            member,
            member_name,
            invoice_date AS date,
            amount,
            status,
            docstatus
        FROM `tabSHG Contribution Invoice`
        WHERE {' AND '.join(conditions)}
    """
    return query, params


def _build_unpaid_contribution_query(member=None):
    conditions = ["c.docstatus = 1", "c.status IN ('Unpaid', 'Partially Paid')"]
    params = {}
    if member:
        conditions.append("c.member = %(member)s")
        params["member"] = member

    # Exclude contributions whose linked invoice is already paid (anti-double-pay)
    conditions.append(
        "NOT EXISTS ("
        "SELECT 1 FROM `tabSHG Contribution Invoice` inv"
        " WHERE inv.name = c.invoice_reference"
        " AND inv.docstatus = 1 AND inv.status = 'Paid'"
        ")"
    )

    query = f"""
        SELECT
            c.name,
            c.member,
            c.member_name,
            c.contribution_date AS date,
            c.expected_amount,
            c.amount,
            c.amount_paid,
            c.unpaid_amount,
            c.status,
            c.docstatus
        FROM `tabSHG Contribution` c
        WHERE {' AND '.join(conditions)}
    """
    return query, params


def _build_unpaid_fine_query(member=None):
    conditions = ["docstatus = 1", "status != 'Paid'"]
    params = {}
    if member:
        conditions.append("member = %(member)s")
        params["member"] = member

    query = f"""
        SELECT
            name,
            member,
            member_name,
            fine_amount,
            meeting,
            fine_date,
            docstatus
        FROM `tabSHG Meeting Fine`
        WHERE {' AND '.join(conditions)}
    """
    return query, params


def _map_invoice_row(invoice):
    outstanding = flt(invoice.get("amount") or 0)
    if outstanding <= 0:
        return None

    is_closed = _read_optional_value("SHG Contribution Invoice", invoice.get("name"), "is_closed", 0)
    posted_to_gl = _read_optional_value("SHG Contribution Invoice", invoice.get("name"), "posted_to_gl", 0)

    return {
        "reference_doctype": "SHG Contribution Invoice",
        "reference_name": invoice.get("name"),
        "member": invoice.get("member"),
        "member_name": invoice.get("member_name"),
        "date": invoice.get("date"),
        "amount": flt(invoice.get("amount")),
        "outstanding_amount": outstanding,
        "status": _normalize_document_status("SHG Contribution Invoice", invoice),
        "is_closed": is_closed,
        "posted_to_gl": posted_to_gl,
    }


def _map_contribution_row(contribution):
    outstanding = flt(contribution.get("unpaid_amount") or 0)
    if outstanding <= 0:
        return None

    is_closed = _read_optional_value("SHG Contribution", contribution.get("name"), "is_closed", 0)
    posted_to_gl = _read_optional_value("SHG Contribution", contribution.get("name"), "posted_to_gl", 0)

    return {
        "reference_doctype": "SHG Contribution",
        "reference_name": contribution.get("name"),
        "member": contribution.get("member"),
        "member_name": contribution.get("member_name"),
        "date": contribution.get("date"),
        "amount": flt(contribution.get("expected_amount") or contribution.get("amount")),
        "outstanding_amount": outstanding,
        "status": _normalize_document_status("SHG Contribution", contribution),
        "is_closed": is_closed,
        "posted_to_gl": posted_to_gl,
    }


def _map_fine_row(fine):
    outstanding = flt(fine.get("fine_amount") or 0)
    if outstanding <= 0:
        return None

    is_closed = _read_optional_value("SHG Meeting Fine", fine.get("name"), "is_closed", 0)
    posted_to_gl = _read_optional_value("SHG Meeting Fine", fine.get("name"), "posted_to_gl", 0)
    meeting_date = fine.get("fine_date")
    if fine.get("meeting"):
        meeting_date = frappe.db.get_value("SHG Meeting", fine.get("meeting"), "meeting_date") or fine.get("fine_date")

    return {
        "reference_doctype": "SHG Meeting Fine",
        "reference_name": fine.get("name"),
        "member": fine.get("member"),
        "member_name": fine.get("member_name"),
        "date": meeting_date,
        "amount": flt(fine.get("fine_amount")),
        "outstanding_amount": outstanding,
        "status": _normalize_document_status("SHG Meeting Fine", fine),
        "is_closed": is_closed,
        "posted_to_gl": posted_to_gl,
    }


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
            query, params = _build_unpaid_invoice_query()
            for invoice in frappe.db.sql(query, params, as_dict=True):
                mapped = _map_invoice_row(invoice)
                if mapped:
                    unpaid_items.append(mapped)
        
        elif doctype == "SHG Contribution":
            query, params = _build_unpaid_contribution_query()
            for contribution in frappe.db.sql(query, params, as_dict=True):
                mapped = _map_contribution_row(contribution)
                if mapped:
                    unpaid_items.append(mapped)
        
        elif doctype == "SHG Meeting Fine":
            query, params = _build_unpaid_fine_query()
            for fine in frappe.db.sql(query, params, as_dict=True):
                mapped = _map_fine_row(fine)
                if mapped:
                    unpaid_items.append(mapped)
        
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
            query, params = _build_unpaid_invoice_query(member)
            for invoice in frappe.db.sql(query, params, as_dict=True):
                mapped = _map_invoice_row(invoice)
                if mapped:
                    unpaid_items.append(mapped)
        
        elif doctype == "SHG Contribution":
            query, params = _build_unpaid_contribution_query(member)
            for contribution in frappe.db.sql(query, params, as_dict=True):
                mapped = _map_contribution_row(contribution)
                if mapped:
                    unpaid_items.append(mapped)
        
        elif doctype == "SHG Meeting Fine":
            query, params = _build_unpaid_fine_query(member)
            for fine in frappe.db.sql(query, params, as_dict=True):
                mapped = _map_fine_row(fine)
                if mapped:
                    unpaid_items.append(mapped)
        
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
        if doc.status == "Paid":
            return 0.0
        if doc.linked_shg_contribution:
            cs = frappe.db.get_value("SHG Contribution", doc.linked_shg_contribution, "status")
            if cs == "Paid":
                frappe.db.set_value("SHG Contribution Invoice", name, "status", "Paid")
                return 0.0
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
    
    elif doctype == "SHG Loan Repayment":
        doc = frappe.get_doc(doctype, name)
        return flt(doc.outstanding_balance or 0)
    
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
        if not abbr:
            frappe.throw(_("Company {0} does not have an abbreviation. Please configure it before processing payments.").format(company))
        default_bank_account = f"Cash - {abbr}"
        if not frappe.db.exists("Account", default_bank_account):
            frappe.throw(_("Default cash account '{0}' does not exist. Please set default_bank_account in SHG Settings.").format(default_bank_account))
    
    # Determine accounts based on payment type (Receive)
    if member:
        # For individual member payments
        paid_from = get_or_create_member_receivable(member, company)
        if not paid_from:
            frappe.throw(_("Cannot create or find receivable account for member {0}").format(member))
        paid_to = default_bank_account
    else:
        # For bulk payments
        paid_from = default_bank_account
        paid_to = default_bank_account
    
    # Validate accounts exist
    for account in [paid_from, paid_to]:
        if not frappe.db.exists("Account", account):
            frappe.throw(_("Account '{0}' does not exist in the chart of accounts.").format(account))
    
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

        # Sync linked Contribution to prevent double-payment
        _sync_linked_contribution_on_invoice_payment(doc, amount, payment_entry_name)

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
        
        # Sync linked Invoice to prevent double-payment
        _sync_linked_invoice_on_contribution_payment(doc, new_paid, expected, payment_entry_name)

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


def _sync_linked_contribution_on_invoice_payment(invoice_doc, amount_paid, payment_entry_name):
    """
    When a Contribution Invoice is paid, mark its linked SHG Contribution as Paid too.
    This prevents the linked Contribution from being paid a second time.
    """
    try:
        contrib_name = invoice_doc.linked_shg_contribution or frappe.db.get_value(
            "SHG Contribution", {"invoice_reference": invoice_doc.name, "docstatus": 1}, "name"
        )
        if not contrib_name:
            return
        if not frappe.db.exists("SHG Contribution", contrib_name):
            return
        contrib = frappe.get_doc("SHG Contribution", contrib_name)
        if contrib.status == "Paid":
            return  # Already settled — nothing to do
        paid = flt(amount_paid)
        expected = flt(contrib.expected_amount or contrib.amount or 0)
        new_paid = flt(contrib.amount_paid or 0) + paid
        unpaid = max(0, expected - new_paid)
        status = "Paid" if unpaid <= 0 else ("Partially Paid" if new_paid > 0 else "Unpaid")
        frappe.db.set_value("SHG Contribution", contrib_name, {
            "amount_paid": new_paid,
            "unpaid_amount": unpaid,
            "status": status,
            "payment_entry": payment_entry_name or contrib.payment_entry,
        })
        frappe.logger().info(
            f"[SHG] Synced Contribution {contrib_name} to {status} after Invoice {invoice_doc.name} was paid"
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "SHG - Sync Contribution on Invoice Payment Failed")


def _sync_linked_invoice_on_contribution_payment(contribution_doc, new_paid, expected, payment_entry_name):
    """
    When a SHG Contribution is paid, mark its linked SHG Contribution Invoice as Paid too.
    This prevents the linked Invoice from being paid a second time.
    """
    try:
        invoice_name = contribution_doc.invoice_reference or frappe.db.get_value(
            "SHG Contribution Invoice", {"linked_shg_contribution": contribution_doc.name, "docstatus": 1}, "name"
        )
        if not invoice_name:
            return
        if not frappe.db.exists("SHG Contribution Invoice", invoice_name):
            return
        invoice_status = frappe.db.get_value("SHG Contribution Invoice", invoice_name, "status")
        if invoice_status == "Paid":
            return  # Already settled — nothing to do
        unpaid = max(0, expected - new_paid)
        status = "Paid" if unpaid <= 0 else ("Partially Paid" if new_paid > 0 else "Unpaid")
        updates = {"status": status}
        if payment_entry_name and frappe.db.has_column("SHG Contribution Invoice", "payment_reference"):
            updates["payment_reference"] = payment_entry_name
        if status == "Paid" and frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
            updates["is_closed"] = 1
        frappe.db.set_value("SHG Contribution Invoice", invoice_name, updates)
        frappe.logger().info(
            f"[SHG] Synced Invoice {invoice_name} to {status} after Contribution {contribution_doc.name} was paid"
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "SHG - Sync Invoice on Contribution Payment Failed")

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
    meta = _get_doctype_meta(doctype)
    status_field = meta.get("status_field")
    display_status_field = meta.get("display_status_field")

    status = None
    if status_field and frappe.db.has_column(doctype, status_field):
        status = frappe.db.get_value(doctype, name, status_field)
    elif display_status_field and frappe.db.has_column(doctype, display_status_field):
        status = frappe.db.get_value(doctype, name, display_status_field)

    if status:
        return status in meta.get("status_paid_values", {"Paid"})
    return False


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

