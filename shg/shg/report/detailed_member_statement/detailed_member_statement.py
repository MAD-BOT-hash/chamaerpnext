import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


# ------------------------------------------------------
# COLUMNS (Fully Frappe-Compatible)
# ------------------------------------------------------
def get_columns():
    return [
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 120},

        # Fully valid dynamic link pattern:
        {"label": "DocType", "fieldname": "document_doctype", "fieldtype": "Data", "width": 180},
        {"label": "Document", "fieldname": "document_link", 
         "fieldtype": "Dynamic Link", "options": "document_doctype", "width": 180},

        {"label": "Description", "fieldname": "description", "fieldtype": "Data", "width": 350},
        {"label": "Debit (KES)", "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": "Credit (KES)", "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": "Running Balance (KES)", "fieldname": "balance", "fieldtype": "Currency", "width": 150},
    ]


# ------------------------------------------------------
# DATA FETCH
# ------------------------------------------------------
def get_data(filters):
    member = filters.get("member")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not member:
        return []

    # Build date filter safely
    date_filter = ""
    params = {"member": member}

    if from_date and to_date:
        date_filter = " AND date BETWEEN %(from_date)s AND %(to_date)s"
        params.update({"from_date": from_date, "to_date": to_date})
    elif from_date:
        date_filter = " AND date >= %(from_date)s"
        params.update({"from_date": from_date})
    elif to_date:
        date_filter = " AND date <= %(to_date)s"
        params.update({"to_date": to_date})

    # --------------------------------------------------
    # THE FINAL COMBINED SQL QUERY
    # --------------------------------------------------
    query = f"""
        SELECT * FROM (

            -- Contributions
            SELECT
                c.contribution_date AS date,
                'SHG Contribution' AS document_doctype,
                c.name AS document_link,
                CONCAT('Contribution - ', COALESCE(ct.contribution_type_name, 'Regular')) AS description,
                0 AS debit,
                c.amount AS credit
            FROM `tabSHG Contribution` c
            LEFT JOIN `tabSHG Contribution Type` ct ON ct.name = c.contribution_type
            WHERE c.member = %(member)s AND c.docstatus = 1 {date_filter}

            UNION ALL

            -- Contribution Invoices
            SELECT
                i.invoice_date AS date,
                'SHG Contribution Invoice' AS document_doctype,
                i.name AS document_link,
                'Contribution Invoice' AS description,
                0 AS debit,
                i.amount AS credit
            FROM `tabSHG Contribution Invoice` i
            WHERE i.member = %(member)s AND i.docstatus = 1 {date_filter}

            UNION ALL

            -- Meeting Fines
            SELECT
                f.fine_date AS date,
                'SHG Meeting Fine' AS document_doctype,
                f.name AS document_link,
                CONCAT('Fine - ', f.fine_reason) AS description,
                0 AS debit,
                f.fine_amount AS credit
            FROM `tabSHG Meeting Fine` f
            WHERE f.member = %(member)s AND f.docstatus = 1 {date_filter}

            UNION ALL

            -- Loan Disbursements
            SELECT
                l.disbursement_date AS date,
                'SHG Loan' AS document_doctype,
                l.name AS document_link,
                CONCAT('Loan Disbursement - ', l.name) AS description,
                l.loan_amount AS debit,
                0 AS credit
            FROM `tabSHG Loan` l
            WHERE l.member = %(member)s AND l.docstatus = 1 {date_filter}

            UNION ALL

            -- Loan Repayments
            SELECT
                r.repayment_date AS date,
                'SHG Loan Repayment' AS document_doctype,
                r.name AS document_link,
                CONCAT('Loan Repayment - ', r.loan) AS description,
                0 AS debit,
                r.total_paid AS credit
            FROM `tabSHG Loan Repayment` r
            WHERE r.member = %(member)s AND r.docstatus = 1 {date_filter}

            UNION ALL

            -- Payment Entries (money received)
            SELECT
                pe.payment_date AS date,
                'SHG Payment Entry' AS document_doctype,
                pe.name AS document_link,
                'Payment Received' AS description,
                0 AS debit,
                pe.total_amount AS credit
            FROM `tabSHG Payment Entry` pe
            WHERE pe.member = %(member)s AND pe.docstatus = 1 {date_filter}

        ) AS combined

        ORDER BY date ASC, document_doctype ASC, document_link ASC
    """

    rows = frappe.db.sql(query, params, as_dict=True)

    # --------------------------------------------------
    # RUNNING BALANCE CALCULATION
    # --------------------------------------------------
    balance = 0
    for r in rows:
        balance += flt(r.credit) - flt(r.debit)
        r.balance = balance

    return rows