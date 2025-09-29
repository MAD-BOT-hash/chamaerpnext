import frappe
from frappe import _

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
            "width": 120
        },
        {
            "label": _("Description"),
            "fieldname": "description",
            "fieldtype": "Data",
            "width": 300
        },
        {
            "label": _("Contribution"),
            "fieldname": "contribution",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Loan Disbursement"),
            "fieldname": "loan_disbursement",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Loan Repayment"),
            "fieldname": "loan_repayment",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Balance"),
            "fieldname": "balance",
            "fieldtype": "Currency",
            "width": 120
        }
    ]

def get_data(filters):
    if not filters.get("member"):
        return [], []
    
    result = []
    running_balance = 0
    
    # Get contributions
    contributions = frappe.db.sql("""
        SELECT 
            contribution_date as date,
            amount as contribution,
            CONCAT(contribution_type, ' Contribution') as description
        FROM `tabSHG Contribution`
        WHERE member = %(member)s AND docstatus = 1
        ORDER BY contribution_date
    """, filters, as_dict=1)
    
    # Get loan disbursements
    loans = frappe.db.sql("""
        SELECT 
            disbursement_date as date,
            disbursed_amount as loan_disbursement,
            CONCAT('Loan Disbursement (', name, ')') as description
        FROM `tabSHG Loan`
        WHERE member = %(member)s AND docstatus = 1 AND status = 'Disbursed'
        ORDER BY disbursement_date
    """, filters, as_dict=1)
    
    # Get loan repayments
    repayments = frappe.db.sql("""
        SELECT 
            payment_date as date,
            total_paid as loan_repayment,
            CONCAT('Loan Repayment (', loan, ')') as description
        FROM `tabSHG Loan Repayment`
        WHERE member = %(member)s AND docstatus = 1
        ORDER BY payment_date
    """, filters, as_dict=1)
    
    # Combine and sort all transactions
    all_transactions = []
    all_transactions.extend(contributions)
    all_transactions.extend(loans)
    all_transactions.extend(repayments)
    all_transactions.sort(key=lambda x: x['date'])
    
    # Process transactions
    for transaction in all_transactions:
        if transaction.get('contribution'):
            # Contribution
            running_balance += transaction.contribution
            result.append({
                'date': transaction.date,
                'description': transaction.description,
                'contribution': transaction.contribution,
                'loan_disbursement': 0,
                'loan_repayment': 0,
                'balance': running_balance
            })
        elif transaction.get('loan_disbursement'):
            # Loan disbursement
            running_balance -= transaction.loan_disbursement
            result.append({
                'date': transaction.date,
                'description': transaction.description,
                'contribution': 0,
                'loan_disbursement': transaction.loan_disbursement,
                'loan_repayment': 0,
                'balance': running_balance
            })
        else:
            # Loan repayment
            running_balance += transaction.loan_repayment
            result.append({
                'date': transaction.date,
                'description': transaction.description,
                'contribution': 0,
                'loan_disbursement': 0,
                'loan_repayment': transaction.loan_repayment,
                'balance': running_balance
            })
    
    return result