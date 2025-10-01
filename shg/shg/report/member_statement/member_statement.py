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
    
    # Add member summary at the top
    data.append({
        "particulars": f"Member: {member.member_name}",
        "debit": "",
        "credit": "",
        "balance": "",
        "reference": ""
    })
    
    data.append({
        "particulars": f"Account Number: {member.account_number}",
        "debit": "",
        "credit": "",
        "balance": "",
        "reference": ""
    })
    
    data.append({
        "particulars": f"Current Loan Balance: KES {flt(member.current_loan_balance):,.2f}",
        "debit": "",
        "credit": "",
        "balance": "",
        "reference": ""
    })
    
    data.append({
        "particulars": f"Total Contributions: KES {flt(member.total_contributions):,.2f}",
        "debit": "",
        "credit": "",
        "balance": "",
        "reference": ""
    })
    
    data.append({
        "particulars": "",
        "debit": "",
        "credit": "",
        "balance": "",
        "reference": ""
    })
    
    # Get contributions
    contributions = frappe.db.sql("""
        SELECT 
            contribution_date as date,
            CONCAT('Contribution - ', contribution_type) as particulars,
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
        WHERE member = %s AND status IN ('Disbursed', 'Closed') AND docstatus = 1
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
    
    # Get meeting fines
    fines = frappe.db.sql("""
        SELECT 
            fine_date as date,
            CONCAT('Meeting Fine - ', fine_reason) as particulars,
            fine_amount as debit,
            0 as credit,
            name as reference
        FROM `tabSHG Meeting Fine`
        WHERE member = %s AND docstatus = 1
        ORDER BY fine_date
    """, filters.member, as_dict=1)
    
    # Combine all transactions
    all_transactions = contributions + loans + repayments + fines
    
    # Sort by date
    all_transactions.sort(key=lambda x: x.date if x.date else getdate())
    
    # Calculate running balance
    for transaction in all_transactions:
        if transaction.debit > 0:
            balance += transaction.debit
        if transaction.credit > 0:
            balance -= transaction.credit
            
        transaction.balance = balance
        data.append(transaction)
    
    # Add loan details section
    data.append({
        "particulars": "",
        "debit": "",
        "credit": "",
        "balance": "",
        "reference": ""
    })
    
    data.append({
        "particulars": "OUTSTANDING LOANS",
        "debit": "",
        "credit": "",
        "balance": "",
        "reference": ""
    })
    
    # Get outstanding loans with repayment schedules
    outstanding_loans = frappe.db.sql("""
        SELECT 
            name,
            loan_type,
            loan_amount,
            balance_amount,
            disbursement_date,
            next_due_date,
            monthly_installment
        FROM `tabSHG Loan`
        WHERE member = %s AND status = 'Disbursed' AND docstatus = 1
        ORDER BY disbursement_date
    """, filters.member, as_dict=1)
    
    for loan in outstanding_loans:
        data.append({
            "particulars": f"Loan: {loan.loan_type}",
            "debit": "",
            "credit": "",
            "balance": "",
            "reference": loan.name
        })
        
        data.append({
            "particulars": f"  Amount: KES {flt(loan.loan_amount):,.2f}",
            "debit": "",
            "credit": "",
            "balance": "",
            "reference": ""
        })
        
        data.append({
            "particulars": f"  Outstanding: KES {flt(loan.balance_amount):,.2f}",
            "debit": "",
            "credit": "",
            "balance": "",
            "reference": ""
        })
        
        # Get repayment schedule for this loan
        schedule = frappe.db.sql("""
            SELECT 
                due_date,
                principal_amount,
                interest_amount,
                total_payment,
                status
            FROM `tabSHG Loan Repayment Schedule`
            WHERE loan = %s
            ORDER BY due_date
        """, loan.name, as_dict=1)
        
        data.append({
            "particulars": "  Repayment Schedule:",
            "debit": "",
            "credit": "",
            "balance": "",
            "reference": ""
        })
        
        for entry in schedule:
            status_indicator = "✓" if entry.status == "Paid" else "○"
            data.append({
                "date": entry.due_date,
                "particulars": f"    {status_indicator} Due: {entry.due_date} - Principal: KES {flt(entry.principal_amount):,.2f}, Interest: KES {flt(entry.interest_amount):,.2f}",
                "debit": "",
                "credit": "",
                "balance": "",
                "reference": ""
            })
        
        data.append({
            "particulars": "",
            "debit": "",
            "credit": "",
            "balance": "",
            "reference": ""
        })
    
    return data

def get_chart_data(data):
    balance_data = []
    dates = []
    
    for row in data:
        if row.date and (row.debit > 0 or row.credit > 0):
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