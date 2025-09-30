import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}
        
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
            "label": _("Description"),
            "fieldname": "description",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Reference"),
            "fieldname": "reference",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Debit"),
            "fieldname": "debit",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Credit"),
            "fieldname": "credit",
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
    member = filters.get("member")
    if not member:
        return []
        
    # Get member details
    member_doc = frappe.get_doc("SHG Member", member)
    
    data = []
    
    # Add opening balance (simplified)
    opening_balance = 0
    data.append({
        "date": "",
        "description": "Opening Balance",
        "reference": "",
        "debit": 0,
        "credit": 0,
        "balance": opening_balance
    })
    
    balance = opening_balance
    
    # Get contributions
    contributions = frappe.db.sql("""
        SELECT 
            contribution_date as date,
            contribution_type as description,
            name as reference,
            0 as debit,
            amount as credit
        FROM `tabSHG Contribution`
        WHERE member = %s AND docstatus = 1
        ORDER BY contribution_date
    """, member, as_dict=1)
    
    # Get loan disbursements
    loans = frappe.db.sql("""
        SELECT 
            disbursement_date as date,
            CONCAT('Loan Disbursement - ', loan_purpose) as description,
            name as reference,
            loan_amount as debit,
            0 as credit
        FROM `tabSHG Loan`
        WHERE member = %s AND status = 'Disbursed'
        ORDER BY disbursement_date
    """, member, as_dict=1)
    
    # Get loan repayments
    repayments = frappe.db.sql("""
        SELECT 
            payment_date as date,
            'Loan Repayment' as description,
            parent as reference,
            0 as debit,
            amount as credit
        FROM `tabSHG Loan Repayment`
        WHERE member = %s AND docstatus = 1
        ORDER BY payment_date
    """, member, as_dict=1)
    
    # Get fines
    fines = frappe.db.sql("""
        SELECT 
            creation as date,
            'Meeting Fine' as description,
            name as reference,
            0 as debit,
            amount as credit
        FROM `tabSHG Meeting Fine`
        WHERE member = %s AND docstatus = 1
        ORDER BY creation
    """, member, as_dict=1)
    
    # Combine all transactions
    transactions = contributions + loans + repayments + fines
    
    # Sort by date
    transactions.sort(key=lambda x: x.date or frappe.utils.nowdate())
    
    # Process transactions
    for transaction in transactions:
        if transaction.debit:
            balance -= transaction.debit
        if transaction.credit:
            balance += transaction.credit
            
        data.append({
            "date": transaction.date,
            "description": transaction.description,
            "reference": transaction.reference,
            "debit": transaction.debit,
            "credit": transaction.credit,
            "balance": balance
        })
        
    # Add summary row
    total_debit = sum(t.debit for t in transactions)
    total_credit = sum(t.credit for t in transactions)
    
    data.append({
        "date": "",
        "description": "Total",
        "reference": "",
        "debit": total_debit,
        "credit": total_credit,
        "balance": balance
    })
    
    return data