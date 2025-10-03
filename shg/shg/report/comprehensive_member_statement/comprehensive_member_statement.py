import frappe
from frappe import _
from frappe.utils import getdate, flt, formatdate

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
            "label": _("Transaction Type"),
            "fieldname": "transaction_type",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Description"),
            "fieldname": "description",
            "fieldtype": "Data",
            "width": 250
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
            "label": _("Running Balance (KES)"),
            "fieldname": "balance",
            "fieldtype": "Currency",
            "width": 140
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
    running_balance = 0
    
    # Get member details
    member = frappe.get_doc("SHG Member", filters.member)
    
    # Add member header information
    data.append({
        "date": None,
        "transaction_type": "MEMBER INFORMATION",
        "description": f"Member: {member.member_name}",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    data.append({
        "date": None,
        "transaction_type": "",
        "description": f"Account Number: {member.account_number}",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    data.append({
        "date": None,
        "transaction_type": "",
        "description": f"Membership Status: {member.membership_status}",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    data.append({
        "date": None,
        "transaction_type": "",
        "description": f"Credit Score: {member.credit_score}",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    data.append({
        "date": None,
        "transaction_type": "",
        "description": "",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    # Section header for financial summary
    data.append({
        "date": None,
        "transaction_type": "FINANCIAL SUMMARY",
        "description": f"Total Contributions: KES {flt(member.total_contributions):,.2f}",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    data.append({
        "date": None,
        "transaction_type": "",
        "description": f"Total Loans Taken: KES {flt(member.total_loans_taken):,.2f}",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    data.append({
        "date": None,
        "transaction_type": "",
        "description": f"Current Loan Balance: KES {flt(member.current_loan_balance):,.2f}",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    data.append({
        "date": None,
        "transaction_type": "",
        "description": "",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    # Section header for transaction history
    data.append({
        "date": None,
        "transaction_type": "TRANSACTION HISTORY",
        "description": "Detailed account transactions",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    # Get all financial transactions
    transactions = []
    
    # Get contributions
    contributions = frappe.db.sql("""
        SELECT 
            contribution_date as date,
            'Contribution' as transaction_type,
            CONCAT(contribution_type, ' Contribution') as description,
            0 as debit,
            amount as credit,
            name as reference
        FROM `tabSHG Contribution`
        WHERE member = %s AND docstatus = 1
        ORDER BY contribution_date
    """, filters.member, as_dict=1)
    transactions.extend(contributions)
    
    # Get loan disbursements
    loans = frappe.db.sql("""
        SELECT 
            disbursement_date as date,
            'Loan Disbursement' as transaction_type,
            CONCAT('Loan Disbursement - ', loan_type) as description,
            loan_amount as debit,
            0 as credit,
            name as reference
        FROM `tabSHG Loan`
        WHERE member = %s AND status IN ('Disbursed', 'Closed') AND docstatus = 1
        ORDER BY disbursement_date
    """, filters.member, as_dict=1)
    transactions.extend(loans)
    
    # Get loan repayments
    repayments = frappe.db.sql("""
        SELECT 
            repayment_date as date,
            'Loan Repayment' as transaction_type,
            CONCAT('Loan Repayment - Principal: KES ', FORMAT(principal_amount, 2), ', Interest: KES ', FORMAT(interest_amount, 2)) as description,
            0 as debit,
            total_paid as credit,
            name as reference
        FROM `tabSHG Loan Repayment`
        WHERE member = %s AND docstatus = 1
        ORDER BY repayment_date
    """, filters.member, as_dict=1)
    transactions.extend(repayments)
    
    # Get meeting fines
    fines = frappe.db.sql("""
        SELECT 
            fine_date as date,
            'Meeting Fine' as transaction_type,
            CONCAT('Meeting Fine - ', fine_reason) as description,
            fine_amount as debit,
            0 as credit,
            name as reference
        FROM `tabSHG Meeting Fine`
        WHERE member = %s AND docstatus = 1
        ORDER BY fine_date
    """, filters.member, as_dict=1)
    transactions.extend(fines)
    
    # Sort all transactions by date
    transactions.sort(key=lambda x: getdate(x.date) if x.date else None)
    
    # Calculate running balance and add to data
    for transaction in transactions:
        if transaction.debit and transaction.debit > 0:
            running_balance += flt(transaction.debit)
        if transaction.credit and transaction.credit > 0:
            running_balance -= flt(transaction.credit)
            
        transaction.balance = running_balance
        data.append(transaction)
    
    # Add section for outstanding loans
    data.append({
        "date": None,
        "transaction_type": "",
        "description": "",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    data.append({
        "date": None,
        "transaction_type": "OUTSTANDING LOANS",
        "description": "Details of active loans",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
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
            monthly_installment,
            interest_rate,
            loan_period_months
        FROM `tabSHG Loan`
        WHERE member = %s AND status = 'Disbursed' AND docstatus = 1
        ORDER BY disbursement_date
    """, filters.member, as_dict=1)
    
    if outstanding_loans:
        for loan in outstanding_loans:
            data.append({
                "date": loan.disbursement_date,
                "transaction_type": "Active Loan",
                "description": f"Loan Type: {loan.loan_type}",
                "debit": None,
                "credit": None,
                "balance": None,
                "reference": loan.name
            })
            
            data.append({
                "date": None,
                "transaction_type": "",
                "description": f"  Original Amount: KES {flt(loan.loan_amount):,.2f}",
                "debit": None,
                "credit": None,
                "balance": None,
                "reference": None
            })
            
            data.append({
                "date": None,
                "transaction_type": "",
                "description": f"  Outstanding Balance: KES {flt(loan.balance_amount):,.2f}",
                "debit": None,
                "credit": None,
                "balance": None,
                "reference": None
            })
            
            data.append({
                "date": None,
                "transaction_type": "",
                "description": f"  Interest Rate: {flt(loan.interest_rate)}%",
                "debit": None,
                "credit": None,
                "balance": None,
                "reference": None
            })
            
            data.append({
                "date": None,
                "transaction_type": "",
                "description": f"  Next Due Date: {formatdate(loan.next_due_date) if loan.next_due_date else 'N/A'}",
                "debit": None,
                "credit": None,
                "balance": None,
                "reference": None
            })
            
            # Get repayment schedule for this loan
            schedule = frappe.db.sql("""
                SELECT 
                    payment_date,
                    principal_amount,
                    interest_amount,
                    total_payment,
                    balance_amount as remaining_balance,
                    status
                FROM `tabSHG Loan Repayment Schedule`
                WHERE loan = %s
                ORDER BY payment_date
                LIMIT 10
            """, loan.name, as_dict=1)
            
            if schedule:
                data.append({
                    "date": None,
                    "transaction_type": "",
                    "description": "  Upcoming Repayments:",
                    "debit": None,
                    "credit": None,
                    "balance": None,
                    "reference": None
                })
                
                for entry in schedule:
                    status_indicator = "✓" if entry.status == "Paid" else "○"
                    data.append({
                        "date": entry.payment_date,
                        "transaction_type": "Repayment Schedule",
                        "description": f"    {status_indicator} {formatdate(entry.payment_date)} - KES {flt(entry.total_payment):,.2f} (Principal: KES {flt(entry.principal_amount):,.2f}, Interest: KES {flt(entry.interest_amount):,.2f})",
                        "debit": None,
                        "credit": None,
                        "balance": f"Bal: KES {flt(entry.remaining_balance):,.2f}",
                        "reference": entry.status
                    })
            
            data.append({
                "date": None,
                "transaction_type": "",
                "description": "",
                "debit": None,
                "credit": None,
                "balance": None,
                "reference": None
            })
    else:
        data.append({
            "date": None,
            "transaction_type": "",
            "description": "No outstanding loans",
            "debit": None,
            "credit": None,
            "balance": None,
            "reference": None
        })
    
    # Add section for meeting attendance summary
    data.append({
        "date": None,
        "transaction_type": "MEETING ATTENDANCE",
        "description": "Attendance and fine summary",
        "debit": None,
        "credit": None,
        "balance": None,
        "reference": None
    })
    
    # Get attendance summary
    attendance_summary = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_meetings,
            SUM(CASE WHEN attendance_status = 'Present' THEN 1 ELSE 0 END) as present,
            SUM(CASE WHEN attendance_status = 'Absent' THEN 1 ELSE 0 END) as absent,
            SUM(CASE WHEN attendance_status = 'Late' THEN 1 ELSE 0 END) as late
        FROM `tabSHG Meeting Attendance Detail`
        WHERE member = %s
    """, filters.member, as_dict=1)
    
    if attendance_summary and attendance_summary[0].total_meetings:
        summary = attendance_summary[0]
        attendance_rate = (summary.present + summary.late) / summary.total_meetings * 100 if summary.total_meetings > 0 else 0
        
        data.append({
            "date": None,
            "transaction_type": "",
            "description": f"Total Meetings: {summary.total_meetings}",
            "debit": None,
            "credit": None,
            "balance": None,
            "reference": None
        })
        
        data.append({
            "date": None,
            "transaction_type": "",
            "description": f"Present: {summary.present}, Late: {summary.late}, Absent: {summary.absent}",
            "debit": None,
            "credit": None,
            "balance": None,
            "reference": None
        })
        
        data.append({
            "date": None,
            "transaction_type": "",
            "description": f"Attendance Rate: {attendance_rate:.1f}%",
            "debit": None,
            "credit": None,
            "balance": None,
            "reference": None
        })
    else:
        data.append({
            "date": None,
            "transaction_type": "",
            "description": "No meeting attendance records",
            "debit": None,
            "credit": None,
            "balance": None,
            "reference": None
        })
    
    return data

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