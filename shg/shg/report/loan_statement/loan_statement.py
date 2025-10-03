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
            "label": _("Loan Amount"),
            "fieldname": "loan_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Principal Paid"),
            "fieldname": "principal_paid",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Interest Paid"),
            "fieldname": "interest_paid",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Penalty Paid"),
            "fieldname": "penalty_paid",
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
    
    # Get loan disbursements
    loans = frappe.db.sql("""
        SELECT 
            disbursement_date as date,
            name as loan_id,
            loan_amount,
            'Loan Disbursement' as description
        FROM `tabSHG Loan`
        WHERE member = %(member)s AND docstatus = 1 AND status = 'Disbursed'
        ORDER BY disbursement_date
    """, filters, as_dict=1)
    
    # Get loan repayments
    repayments = frappe.db.sql("""
        SELECT 
            repayment_date as date,
            loan as loan_id,
            principal_amount,
            interest_amount,
            penalty_amount,
            total_paid,
            'Loan Repayment' as description
        FROM `tabSHG Loan Repayment`
        WHERE member = %(member)s AND docstatus = 1
        ORDER BY repayment_date
    """, filters, as_dict=1)
    
    # Combine and sort all transactions
    all_transactions = []
    all_transactions.extend(loans)
    all_transactions.extend(repayments)
    all_transactions.sort(key=lambda x: x['date'])
    
    # Process transactions
    for transaction in all_transactions:
        if transaction.get('loan_amount'):
            # Loan disbursement
            running_balance += transaction.loan_amount
            result.append({
                'date': transaction.date,
                'description': transaction.description + f" ({transaction.loan_id})",
                'loan_amount': transaction.loan_amount,
                'principal_paid': 0,
                'interest_paid': 0,
                'penalty_paid': 0,
                'balance': running_balance
            })
        else:
            # Loan repayment
            running_balance -= transaction.total_paid
            result.append({
                'date': transaction.date,
                'description': transaction.description + f" ({transaction.loan_id})",
                'loan_amount': 0,
                'principal_paid': transaction.principal_amount,
                'interest_paid': transaction.interest_amount,
                'penalty_paid': transaction.penalty_amount,
                'balance': running_balance
            })
    
    return result