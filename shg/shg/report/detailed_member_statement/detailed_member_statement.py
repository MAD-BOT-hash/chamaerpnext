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
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 120},
        {"label": "DocType", "fieldname": "document_doctype", "fieldtype": "Data", "width": 150},
        {"label": "Document", "fieldname": "document_link", "fieldtype": "Link", "options": "document_doctype", "width": 150},
        {"label": "Description", "fieldname": "description", "fieldtype": "Data", "width": 300},
        {"label": "Debit (KES)", "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": "Credit (KES)", "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": "Running Balance (KES)", "fieldname": "balance", "fieldtype": "Currency", "width": 150},
    ]


def get_data(filters):
    member = filters.get("member")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not member:
        return []

    # Build date filter conditions
    date_conditions = []
    params = {"member": member}
    
    if from_date:
        date_conditions.append("t.date >= %(from_date)s")
        params["from_date"] = from_date
        
    if to_date:
        date_conditions.append("t.date <= %(to_date)s")
        params["to_date"] = to_date
    
    # Join all date conditions
    date_filter = ""
    if date_conditions:
        date_filter = " AND " + " AND ".join(date_conditions)

    query = f"""
        SELECT 
            t.date,
            t.document_doctype,
            t.document_link,
            t.description,
            t.debit,
            t.credit
        FROM (
            SELECT
                c.contribution_date AS date,
                'SHG Contribution' AS document_doctype,
                c.name AS document_link,
                CONCAT('Contribution - ', COALESCE(ct.contribution_type_name, 'Regular')) AS description,
                0 AS debit,
                c.amount AS credit
            FROM `tabSHG Contribution` c
            LEFT JOIN `tabSHG Contribution Type` ct ON ct.name = c.contribution_type
            WHERE c.member = %(member)s AND c.docstatus = 1

            UNION ALL

            SELECT
                i.invoice_date AS date,
                'SHG Contribution Invoice' AS document_doctype,
                i.name AS document_link,
                'Contribution Invoice' AS description,
                0 AS debit,
                i.amount AS credit
            FROM `tabSHG Contribution Invoice` i
            WHERE i.member = %(member)s AND i.docstatus = 1

            UNION ALL

            SELECT
                f.fine_date AS date,
                'SHG Meeting Fine' AS document_doctype,
                f.name AS document_link,
                CONCAT('Fine - ', f.fine_reason) AS description,
                0 AS debit,
                f.fine_amount AS credit
            FROM `tabSHG Meeting Fine` f
            WHERE f.member = %(member)s AND f.docstatus = 1

            UNION ALL

            SELECT
                l.disbursement_date AS date,
                'SHG Loan' AS document_doctype,
                l.name AS document_link,
                CONCAT('Loan Disbursement - ', l.name) AS description,
                l.loan_amount AS debit,
                0 AS credit
            FROM `tabSHG Loan` l
            WHERE l.member = %(member)s AND l.docstatus = 1

            UNION ALL

            SELECT
                r.repayment_date AS date,
                'SHG Loan Repayment' AS document_doctype,
                r.name AS document_link,
                CONCAT('Loan Repayment - ', r.loan) AS description,
                0 AS debit,
                r.total_paid AS credit
            FROM `tabSHG Loan Repayment` r
            WHERE r.member = %(member)s AND r.docstatus = 1

            UNION ALL

            SELECT
                pe.payment_date AS date,
                'SHG Payment Entry' AS document_doctype,
                pe.name AS document_link,
                'Payment Received' AS description,
                0 AS debit,
                pe.total_amount AS credit
            FROM `tabSHG Payment Entry` pe
            WHERE pe.member = %(member)s AND pe.docstatus = 1
        ) AS t
        WHERE 1=1 {date_filter}
        ORDER BY t.date, t.document_doctype, t.document_link
    """

    rows = frappe.db.sql(query, params, as_dict=True)

    # Calculate running balance
    balance = 0
    for r in rows:
        balance += flt(r.credit) - flt(r.debit)
        r.balance = balance

    return rows