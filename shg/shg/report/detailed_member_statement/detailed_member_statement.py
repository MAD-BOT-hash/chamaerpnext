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
    
    # Handle case where no member is selected - show for all members
    if not member_filter:
        # Get all active members if no specific member is selected
        members = frappe.get_all("SHG Member", filters={"docstatus": 1}, pluck="name")
        if not members:
            return []
    else:
        members = [member_filter]
    
    all_transactions = []
    
    for member in members:
        # Base query conditions
        date_condition = ""
        params = {"member": member}
        
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
        
        # Query to get all member transactions - fetch all statuses
        query = f"""
            SELECT 
                date,
                reference,
                description,
                debit,
                credit
            FROM (
                -- Contributions (all statuses)
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
                
                -- Fines (all statuses)
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
                
                -- Loan Disbursements (all statuses)
                SELECT 
                    l.disbursement_date as date,
                    'SHG Loan' as reference,
                    l.name as reference_name,
                    CONCAT('Loan Disbursement - Loan #', l.name) as description,
                    l.loan_amount as debit,
                    0 as credit
                FROM `tabSHG Loan` l
                WHERE l.member = %(member)s AND l.docstatus = 1 {date_condition}
                
                UNION ALL
                
                -- Loan Repayments (all statuses)
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
                
                -- Payment Entries (all statuses)
                SELECT 
                    pe.payment_date as date,
                    'SHG Payment Entry' as reference,
                    pe.name as reference_name,
                    'Payment Received' as description,
                    0 as debit,
                    pe.total_amount as credit
                FROM `tabSHG Payment Entry` pe
                WHERE pe.member = %(member)s AND pe.docstatus = 1 {date_condition}
                
                UNION ALL
                
                -- Loan Transactions (accruals, write-offs, etc.)
                SELECT 
                    t.posting_date as date,
                    'SHG Loan Transaction' as reference,
                    t.name as reference_name,
                    CONCAT(t.transaction_type, ' - Loan #', t.loan) as description,
                    CASE 
                        WHEN t.transaction_type IN ('Disbursement', 'Interest Accrual', 'Penalty Accrual') THEN t.amount
                        ELSE 0
                    END as debit,
                    CASE 
                        WHEN t.transaction_type IN ('Repayment', 'Write-off Reversal') THEN t.amount
                        ELSE 0
                    END as credit
                FROM `tabSHG Loan Transaction` t
                WHERE t.member = %(member)s AND t.docstatus = 1 {date_condition}
            ) transactions
            ORDER BY date, reference
        """
        
        transactions = frappe.db.sql(query, params, as_dict=True)
        all_transactions.extend(transactions)
    
    # Sort all transactions by date
    all_transactions.sort(key=lambda x: (x['date'], x['reference']))
    
    # Calculate running balance
    running_balance = 0
    for transaction in all_transactions:
        running_balance += flt(transaction.credit) - flt(transaction.debit)
        transaction.balance = running_balance
    
    # Add debug log
    frappe.log(f"Detailed Member Statement: Found {len(all_transactions)} transactions")
    
    return all_transactions