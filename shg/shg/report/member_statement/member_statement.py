import frappe
from frappe import _
from frappe.utils import getdate, flt

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Date"),
            "fieldname": "date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": _("Particulars"),
            "fieldname": "particulars",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Debit (KES)"),
            "fieldname": "debit",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Credit (KES)"),
            "fieldname": "credit",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Balance (KES)"),
            "fieldname": "balance",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Reference"),
            "fieldname": "reference",
            "fieldtype": "Data",
            "width": 150
        }
    ]

def get_data(filters):
    if not filters.get("member"):
        return []
    
    data = []
    balance = 0
    
    # Get member details
    member = frappe.get_doc("SHG Member", filters.member)
    
    # Get contributions
    contributions = frappe.db.sql("""
        SELECT 
            contribution_date as date,
            contribution_type as particulars,
            0 as debit,
            amount as credit,
            name as reference
        FROM `tabSHG Contribution`
        WHERE member = %s AND docstatus = 1
        ORDER BY contribution_date
    """, filters.member, as_dict=1)
    
    # Get loan disbursements
    loans = frappe.db.sql("""
        SELECT 
            disbursement_date as date,
            CONCAT('Loan Disbursement - ', loan_type) as particulars,
            loan_amount as debit,
            0 as credit,
            name as reference
        FROM `tabSHG Loan`
        WHERE member = %s AND status = 'Disbursed' AND docstatus = 1
        ORDER BY disbursement_date
    """, filters.member, as_dict=1)
    
    # Get loan repayments
    repayments = frappe.db.sql("""
        SELECT 
            repayment_date as date,
            'Loan Repayment' as particulars,
            0 as debit,
            total_paid as credit,
            name as reference
        FROM `tabSHG Loan Repayment`
        WHERE member = %s AND docstatus = 1
        ORDER BY repayment_date
    """, filters.member, as_dict=1)
    
    # Combine all transactions
    all_transactions = contributions + loans + repayments
    
    # Sort by date
    all_transactions.sort(key=lambda x: x.date)
    
    # Calculate running balance
    for transaction in all_transactions:
        if transaction.debit > 0:
            balance += transaction.debit
        if transaction.credit > 0:
            balance -= transaction.credit
            
        transaction.balance = balance
        data.append(transaction)
    
    return data

def get_chart_data(data):
    balance_data = []
    dates = []
    
    for row in data:
        dates.append(row.date)
        balance_data.append(row.balance)
    
    if not dates:
        return []
    
    chart = {
        "data": {
            "labels": dates,
            "datasets": [
                {"name": "Account Balance", "type": "line", "values": balance_data}
            ]
        },
        "chart_type": "line"
    }
    
    return chart

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_members(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""
        SELECT name, member_name
        FROM `tabSHG Member`
        WHERE docstatus = 1
        AND (name LIKE %(txt)s OR member_name LIKE %(txt)s)
        ORDER BY member_name
        LIMIT %(start)s, %(page_len)s
    """, {
        'txt': "%%%s%%" % txt,
        'start': start,
        'page_len': page_len
    })