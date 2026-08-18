import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    member = filters.get("member")
    from_date = filters.get("from_date")
    columns = get_columns()
    data = get_data(filters)
    opening_balance = get_opening_balance(member, from_date) if member else 0.0
    report_summary = get_report_summary(data, opening_balance)
    chart = None
    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
        {"label": _("Transaction Type"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 160},
        {"label": _("Reference Type"), "fieldname": "reference_doctype", "fieldtype": "Data", "width": 180},
        {"label": _("Reference"), "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 180},
        {"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 280},
        {"label": _("Debit"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 120},
        {"label": _("Running Balance"), "fieldname": "running_balance", "fieldtype": "Currency", "width": 150},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
    ]


def get_data(filters):
    member = filters.get("member")
    if not member:
        return []

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    transaction_type = (filters.get("transaction_type") or "All").strip()

    opening_balance = get_opening_balance(member, from_date)
    transactions = get_transactions(member, from_date, to_date, transaction_type)

    running_balance = flt(opening_balance)
    for entry in transactions:
        entry["debit"] = flt(entry.get("debit") or 0)
        entry["credit"] = flt(entry.get("credit") or 0)
        entry["outstanding"] = flt(entry.get("outstanding") or 0)
        running_balance += entry["credit"] - entry["debit"]
        entry["running_balance"] = running_balance

    return transactions


def get_opening_balance(member, from_date=None):
    if not member:
        return 0.0

    if not from_date:
        return 0.0

    transactions = get_transactions(member, None, from_date, "All")
    opening_balance = 0.0
    for transaction in transactions:
        opening_balance += flt(transaction.get("credit") or 0) - flt(transaction.get("debit") or 0)

    return opening_balance


def get_transactions(member, from_date=None, to_date=None, transaction_type="All"):
    rows = []
    allowed = {"All", "Contribution", "Contribution Invoice", "Fine", "Loan", "Loan Repayment", "Payment"}
    if transaction_type and transaction_type not in allowed:
        transaction_type = "All"

    if transaction_type in ("All", "Contribution"):
        rows.extend(get_contribution_transactions(member, from_date, to_date))
    if transaction_type in ("All", "Contribution Invoice"):
        rows.extend(get_invoice_transactions(member, from_date, to_date))
    if transaction_type in ("All", "Fine"):
        rows.extend(get_fine_transactions(member, from_date, to_date))
    if transaction_type in ("All", "Loan"):
        rows.extend(get_loan_transactions(member, from_date, to_date))
    if transaction_type in ("All", "Loan Repayment"):
        rows.extend(get_repayment_transactions(member, from_date, to_date))
    if transaction_type in ("All", "Payment"):
        rows.extend(get_payment_transactions(member, from_date, to_date))

    rows = _deduplicate_rows(rows)
    rows.sort(key=lambda row: (
        row.get("date") or "",
        row.get("reference_doctype") or "",
        row.get("reference_name") or "",
        row.get("transaction_type") or "",
    ))

    return rows


def _deduplicate_rows(rows):
    seen = set()
    unique = []
    for row in rows:
        key = (
            row.get("reference_doctype") or "",
            row.get("reference_name") or "",
            row.get("transaction_type") or "",
            row.get("date") or "",
            row.get("description") or "",
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def get_contribution_transactions(member, from_date=None, to_date=None):
    query = """
        SELECT
            name,
            member,
            COALESCE(posting_date, contribution_date) AS date,
            amount,
            status,
            invoice_reference,
            payment_entry,
            contribution_type
        FROM `tabSHG Contribution`
        WHERE member = %(member)s
          AND docstatus = 1
          AND (%(from_date)s IS NULL OR COALESCE(posting_date, contribution_date) >= %(from_date)s)
          AND (%(to_date)s IS NULL OR COALESCE(posting_date, contribution_date) <= %(to_date)s)
        ORDER BY COALESCE(posting_date, contribution_date), name
    """
    rows = frappe.db.sql(query, {
        "member": member,
        "from_date": from_date,
        "to_date": to_date,
    }, as_dict=True)

    result = []
    invoice_reference_map = {doc.name: doc.name for doc in frappe.get_all("SHG Contribution", filters={"member": member, "docstatus": 1}, fields=["name", "invoice_reference"]) if doc.get("invoice_reference")}
    for row in rows:
        if row.get("invoice_reference") and row.get("invoice_reference") in invoice_reference_map:
            # The invoice-linked contribution is the actual posted contribution entry.
            # The related SHG Contribution Invoice is handled separately to avoid double counting.
            pass
        amount = flt(row.get("amount") or 0)
        result.append({
            "date": row.get("date"),
            "transaction_type": "Contribution",
            "reference_doctype": "SHG Contribution",
            "reference_name": row.get("name"),
            "description": "Contribution" if not row.get("contribution_type") else f"Contribution - {row.get('contribution_type')}",
            "debit": 0,
            "credit": amount,
            "outstanding": 0,
            "status": row.get("status") or "Submitted",
        })
    return result


def get_invoice_transactions(member, from_date=None, to_date=None):
    linked_contributions = {
        row.invoice_reference
        for row in frappe.get_all(
            "SHG Contribution",
            filters={"member": member, "docstatus": 1},
            fields=["invoice_reference"],
        )
        if row.get("invoice_reference")
    }

    query = """
        SELECT
            name,
            member,
            invoice_date AS date,
            amount,
            status,
            linked_shg_contribution,
            payment_reference
        FROM `tabSHG Contribution Invoice`
        WHERE member = %(member)s
          AND docstatus = 1
          AND (%(from_date)s IS NULL OR invoice_date >= %(from_date)s)
          AND (%(to_date)s IS NULL OR invoice_date <= %(to_date)s)
        ORDER BY invoice_date, name
    """
    rows = frappe.db.sql(query, {
        "member": member,
        "from_date": from_date,
        "to_date": to_date,
    }, as_dict=True)

    result = []
    for row in rows:
        if row.get("name") in linked_contributions:
            continue
        amount = flt(row.get("amount") or 0)
        result.append({
            "date": row.get("date"),
            "transaction_type": "Contribution Invoice",
            "reference_doctype": "SHG Contribution Invoice",
            "reference_name": row.get("name"),
            "description": "Contribution invoice",
            "debit": amount,
            "credit": 0,
            "outstanding": amount if row.get("status") not in ("Paid", "Cancelled") else 0,
            "status": row.get("status") or "Unpaid",
        })
    return result


def get_fine_transactions(member, from_date=None, to_date=None):
    query = """
        SELECT
            name,
            member,
            fine_date AS date,
            fine_amount,
            status,
            fine_reason
        FROM `tabSHG Meeting Fine`
        WHERE member = %(member)s
          AND docstatus = 1
          AND status != 'Waived'
          AND (%(from_date)s IS NULL OR fine_date >= %(from_date)s)
          AND (%(to_date)s IS NULL OR fine_date <= %(to_date)s)
        ORDER BY fine_date, name
    """
    rows = frappe.db.sql(query, {
        "member": member,
        "from_date": from_date,
        "to_date": to_date,
    }, as_dict=True)

    result = []
    for row in rows:
        amount = flt(row.get("fine_amount") or 0)
        result.append({
            "date": row.get("date"),
            "transaction_type": "Fine",
            "reference_doctype": "SHG Meeting Fine",
            "reference_name": row.get("name"),
            "description": f"Fine - {row.get('fine_reason') or 'Meeting Fine'}",
            "debit": amount,
            "credit": 0,
            "outstanding": amount if row.get("status") != "Paid" else 0,
            "status": row.get("status") or "Pending",
        })
    return result


def get_loan_transactions(member, from_date=None, to_date=None):
    query = """
        SELECT
            name,
            member,
            COALESCE(disbursement_date, posting_date) AS date,
            COALESCE(disbursed_amount, loan_amount, 0) AS amount,
            status,
            loan_amount,
            disbursed_amount,
            loan_balance,
            balance_amount
        FROM `tabSHG Loan`
        WHERE member = %(member)s
          AND docstatus = 1
          AND status IN ('Approved', 'Disbursed', 'Closed')
          AND (%(from_date)s IS NULL OR COALESCE(disbursement_date, posting_date) >= %(from_date)s)
          AND (%(to_date)s IS NULL OR COALESCE(disbursement_date, posting_date) <= %(to_date)s)
        ORDER BY COALESCE(disbursement_date, posting_date), name
    """
    rows = frappe.db.sql(query, {
        "member": member,
        "from_date": from_date,
        "to_date": to_date,
    }, as_dict=True)

    result = []
    for row in rows:
        amount = flt(row.get("amount") or 0)
        result.append({
            "date": row.get("date"),
            "transaction_type": "Loan",
            "reference_doctype": "SHG Loan",
            "reference_name": row.get("name"),
            "description": "Loan disbursement",
            "debit": amount,
            "credit": 0,
            "outstanding": amount,
            "status": row.get("status") or "Disbursed",
        })
    return result


def get_repayment_transactions(member, from_date=None, to_date=None):
    query = """
        SELECT
            name,
            member,
            COALESCE(repayment_date, posting_date) AS date,
            total_paid,
            loan,
            status,
            outstanding_balance,
            balance_after_payment
        FROM `tabSHG Loan Repayment`
        WHERE member = %(member)s
          AND docstatus = 1
          AND (%(from_date)s IS NULL OR COALESCE(repayment_date, posting_date) >= %(from_date)s)
          AND (%(to_date)s IS NULL OR COALESCE(repayment_date, posting_date) <= %(to_date)s)
        ORDER BY COALESCE(repayment_date, posting_date), name
    """
    rows = frappe.db.sql(query, {
        "member": member,
        "from_date": from_date,
        "to_date": to_date,
    }, as_dict=True)

    result = []
    for row in rows:
        amount = flt(row.get("total_paid") or 0)
        result.append({
            "date": row.get("date"),
            "transaction_type": "Loan Repayment",
            "reference_doctype": "SHG Loan Repayment",
            "reference_name": row.get("name"),
            "description": f"Loan repayment - {row.get('loan') or 'loan'}",
            "debit": 0,
            "credit": amount,
            "outstanding": 0,
            "status": row.get("status") or "Submitted",
        })
    return result


def get_payment_transactions(member, from_date=None, to_date=None):
    query = """
        SELECT
            name,
            member,
            payment_date AS date,
            amount,
            reference_doctype,
            reference_name,
            payment_status,
            status,
            outstanding_amount
        FROM `tabSHG Payment Entry`
        WHERE member = %(member)s
          AND docstatus = 1
          AND (%(from_date)s IS NULL OR payment_date >= %(from_date)s)
          AND (%(to_date)s IS NULL OR payment_date <= %(to_date)s)
        ORDER BY payment_date, name
    """
    rows = frappe.db.sql(query, {
        "member": member,
        "from_date": from_date,
        "to_date": to_date,
    }, as_dict=True)

    result = []
    excluded_reference_pairs = set()
    for row in rows:
        if row.get("reference_doctype") and row.get("reference_name"):
            excluded_reference_pairs.add((row.get("reference_doctype"), row.get("reference_name")))

    for row in rows:
        if row.get("reference_doctype") in ("SHG Contribution Invoice", "SHG Contribution", "SHG Meeting Fine", "SHG Loan Repayment"):
            continue
        amount = flt(row.get("amount") or 0)
        result.append({
            "date": row.get("date"),
            "transaction_type": "Payment",
            "reference_doctype": row.get("reference_doctype") or "SHG Payment Entry",
            "reference_name": row.get("reference_name") or row.get("name"),
            "description": "Independent payment receipt" if not row.get("reference_name") else f"Payment - {row.get('reference_name')}",
            "debit": 0,
            "credit": amount,
            "outstanding": 0,
            "status": row.get("status") or row.get("payment_status") or "Submitted",
        })
    return result


def get_report_summary(data, opening_balance=0.0):
    total_debits = 0.0
    total_credits = 0.0
    contributions = 0.0
    fines = 0.0
    loans = 0.0
    loan_repayments = 0.0
    payments = 0.0

    for row in data:
        total_debits += flt(row.get("debit") or 0)
        total_credits += flt(row.get("credit") or 0)
        if row.get("transaction_type") == "Contribution":
            contributions += flt(row.get("credit") or 0)
        elif row.get("transaction_type") == "Fine":
            fines += flt(row.get("debit") or 0)
        elif row.get("transaction_type") == "Loan":
            loans += flt(row.get("debit") or 0)
        elif row.get("transaction_type") == "Loan Repayment":
            loan_repayments += flt(row.get("credit") or 0)
        elif row.get("transaction_type") == "Payment":
            payments += flt(row.get("credit") or 0)

    closing_balance = opening_balance + total_credits - total_debits

    return [
        {"label": _("Opening Balance"), "datatype": "Currency", "value": opening_balance},
        {"label": _("Total Debits"), "datatype": "Currency", "value": total_debits},
        {"label": _("Total Credits"), "datatype": "Currency", "value": total_credits},
        {"label": _("Closing Balance"), "datatype": "Currency", "value": closing_balance},
        {"label": _("Contributions"), "datatype": "Currency", "value": contributions},
        {"label": _("Fines"), "datatype": "Currency", "value": fines},
        {"label": _("Loans"), "datatype": "Currency", "value": loans},
        {"label": _("Loan Repayments"), "datatype": "Currency", "value": loan_repayments},
        {"label": _("Payments"), "datatype": "Currency", "value": payments},
    ]
