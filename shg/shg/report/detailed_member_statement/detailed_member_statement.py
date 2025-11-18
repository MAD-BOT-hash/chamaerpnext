import frappe
from frappe import _
from frappe.utils import getdate, flt


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)
    
    return columns, data


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 120},
        {"label": _("Reference Type"), "fieldname": "reference_type", "fieldtype": "Data", "width": 160},
        {"label": _("Reference Name"), "fieldname": "reference_name", "fieldtype": "Data", "width": 150},
        {"label": _("Document"), "fieldname": "document_link", "fieldtype": "Dynamic Link", "options": "reference_type", "width": 200},
        {"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 300},
        {"label": _("Debit (KES)"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": _("Credit (KES)"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": _("Running Balance (KES)"), "fieldname": "balance", "fieldtype": "Currency", "width": 150},
    ]


def get_data(filters):
    member = filters.get("member")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not member:
        return []

    date_filter = ""
    params = {"member": member}

    if from_date and to_date:
        date_filter = " AND date BETWEEN %(from_date)s AND %(to_date)s"
        params["from_date"] = from_date
        params["to_date"] = to_date
    elif from_date:
        date_filter = " AND date >= %(from_date)s"
        params["from_date"] = from_date
    elif to_date:
        date_filter = " AND date <= %(to_date)s"
        params["to_date"] = to_date

    query = f"""
        SELECT * FROM (
            SELECT
                c.contribution_date AS date,
                'SHG Contribution' AS reference_type,
                c.name AS reference_name,
                c.name AS document_link,
                CONCAT('Contribution - ', COALESCE(ct.contribution_type_name, 'Regular')) AS description,
                0 AS debit,
                c.amount AS credit
            FROM `tabSHG Contribution` c
            LEFT JOIN `tabSHG Contribution Type` ct ON ct.name = c.contribution_type
            WHERE c.member = %(member)s AND c.docstatus = 1 {date_filter}

            UNION ALL

            SELECT
                i.invoice_date AS date,
                'SHG Contribution Invoice' AS reference_type,
                i.name AS reference_name,
                i.name AS document_link,
                'Contribution Invoice' AS description,
                0 AS debit,
                i.amount AS credit
            FROM `tabSHG Contribution Invoice` i
            WHERE i.member = %(member)s AND i.docstatus = 1 {date_filter}

            UNION ALL

            SELECT
                f.fine_date AS date,
                'SHG Meeting Fine' AS reference_type,
                f.name AS reference_name,
                f.name AS document_link,
                CONCAT('Fine - ', f.fine_reason) AS description,
                0 AS debit,
                f.fine_amount AS credit
            FROM `tabSHG Meeting Fine` f
            WHERE f.member = %(member)s AND f.docstatus = 1 {date_filter}

            UNION ALL

            SELECT
                l.disbursement_date AS date,
                'SHG Loan' AS reference_type,
                l.name AS reference_name,
                l.name AS document_link,
                CONCAT('Loan Disbursement - ', l.name) AS description,
                l.loan_amount AS debit,
                0 AS credit
            FROM `tabSHG Loan` l
            WHERE l.member = %(member)s AND l.docstatus = 1 {date_filter}

            UNION ALL

            SELECT
                r.repayment_date AS date,
                'SHG Loan Repayment' AS reference_type,
                r.name AS reference_name,
                r.name AS document_link,
                CONCAT('Loan Repayment - ', r.loan) AS description,
                0 AS debit,
                r.total_paid AS credit
            FROM `tabSHG Loan Repayment` r
            WHERE r.member = %(member)s AND r.docstatus = 1 {date_filter}

            UNION ALL

            SELECT
                pe.payment_date AS date,
                'SHG Payment Entry' AS reference_type,
                pe.name AS reference_name,
                pe.name AS document_link,
                'Payment Received' AS description,
                0 AS debit,
                pe.total_amount AS credit
            FROM `tabSHG Payment Entry` pe
            WHERE pe.member = %(member)s AND pe.docstatus = 1 {date_filter}
        ) AS t
        ORDER BY date, reference_type, reference_name
    """

    rows = frappe.db.sql(query, params, as_dict=True)

    balance = 0
    for r in rows:
        balance += flt(r.credit) - flt(r.debit)
        r.balance = balance

    return rows