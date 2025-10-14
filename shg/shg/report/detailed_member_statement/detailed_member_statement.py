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
        {"label": _("Reference"), "fieldname": "reference", "fieldtype": "Link", "options": "DocType", "width": 150},
        {"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 250},
        {"label": _("Debit (KES)"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": _("Credit (KES)"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": _("Running Balance (KES)"), "fieldname": "balance", "fieldtype": "Currency", "width": 150},
    ]

def get_data(filters):
    member_filter = filters.get("member")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    if not member_filter:
        return []
    
    # Base query conditions
    date_condition = ""
    params = {"member": member_filter}
    
    if from_date and to_date:
        date_condition = " AND date BETWEEN %(from_date)s AND %(to_date)s"
        params["from_date"] = from_date
        params["to_date"] = to_date
    elif from_date:
        date_condition = " AND date >= %(from_date)s"
        params["from_date"] = from_date
    elif to_date:
        date_condition = " AND date <= %(to_date)s"
        params["to_date"] = to_date
    
    # Query to get all member transactions
    query = f"""
        SELECT 
            date,
            reference,
            description,
            debit,
            credit
        FROM (
            -- Contributions
            SELECT 
                c.contribution_date as date,
                'SHG Contribution' as reference,
                c.name as reference_name,
                CONCAT('Contribution - ', COALESCE(ct.contribution_type_name, 'Regular')) as description,
                0 as debit,
                c.amount as credit
            FROM `tabSHG Contribution` c
            LEFT JOIN `tabSHG Contribution Type` ct ON c.contribution_type = ct.name
            WHERE c.member = %(member)s AND c.docstatus = 1 {date_condition}
            
            UNION ALL
            
            -- Fines
            SELECT 
                f.fine_date as date,
                'SHG Meeting Fine' as reference,
                f.name as reference_name,
                CONCAT('Fine - ', f.fine_reason) as description,
                0 as debit,
                f.fine_amount as credit
            FROM `tabSHG Meeting Fine` f
            WHERE f.member = %(member)s AND f.docstatus = 1 {date_condition}
            
            UNION ALL
            
            -- Loan Disbursements
            SELECT 
                l.disbursement_date as date,
                'SHG Loan' as reference,
                l.name as reference_name,
                CONCAT('Loan Disbursement - Loan #', l.name) as description,
                l.loan_amount as debit,
                0 as credit
            FROM `tabSHG Loan` l
            WHERE l.member = %(member)s AND l.docstatus = 1 AND l.status = 'Disbursed' {date_condition}
            
            UNION ALL
            
            -- Loan Repayments
            SELECT 
                r.repayment_date as date,
                'SHG Loan Repayment' as reference,
                r.name as reference_name,
                CONCAT('Loan Repayment - Loan #', r.loan) as description,
                0 as debit,
                r.total_paid as credit
            FROM `tabSHG Loan Repayment` r
            WHERE r.member = %(member)s AND r.docstatus = 1 {date_condition}
            
            UNION ALL
            
            -- Payment Entries
            SELECT 
                pe.payment_date as date,
                'SHG Payment Entry' as reference,
                pe.name as reference_name,
                'Payment Received' as description,
                0 as debit,
                pe.total_amount as credit
            FROM `tabSHG Payment Entry` pe
            WHERE pe.member = %(member)s AND pe.docstatus = 1 {date_condition}
        ) transactions
        ORDER BY date, reference
    """
    
    transactions = frappe.db.sql(query, params, as_dict=True)
    
    # Calculate running balance
    running_balance = 0
    for transaction in transactions:
        running_balance += flt(transaction.credit) - flt(transaction.debit)
        transaction.balance = running_balance
    
    return transactions