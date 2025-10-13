import frappe
from frappe import _
from frappe.utils import getdate, flt

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    report_summary = get_report_summary(filters)
    return columns, data, report_summary, chart

def get_columns():
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
        {"label": _("Particulars"), "fieldname": "particulars", "fieldtype": "Data", "width": 240},
        {"label": _("Debit (KES)"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": _("Credit (KES)"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": _("Balance (KES)"), "fieldname": "balance", "fieldtype": "Currency", "width": 120},
        {"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 150},
    ]

def get_data(filters):
    member = filters.get("member")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    transaction_type = filters.get("transaction_type")
    
    if not member:
        return []

    # Get member details
    member_doc = frappe.get_doc("SHG Member", member)
    
    # Get all transactions
    transactions = []
    
    # Base query conditions
    date_condition = ""
    if from_date and to_date:
        date_condition = f" AND t.date BETWEEN '{from_date}' AND '{to_date}'"
    elif from_date:
        date_condition = f" AND t.date >= '{from_date}'"
    elif to_date:
        date_condition = f" AND t.date <= '{to_date}'"

    # Build query based on transaction type filter
    if not transaction_type or transaction_type == "All" or transaction_type == "Contribution":
        # Contributions
        contributions = frappe.db.sql(f"""
            SELECT
                contribution_date as date,
                CONCAT('Contribution - ', COALESCE(contribution_type, contribution_type_link)) as particulars,
                0 as debit,
                amount as credit,
                name as reference
            FROM `tabSHG Contribution`
            WHERE member = %s AND docstatus = 1 {date_condition}
            ORDER BY contribution_date
        """, member, as_dict=True)
        transactions.extend(contributions)

    if not transaction_type or transaction_type == "All" or transaction_type == "Loan Disbursement":
        # Loans
        loans = frappe.db.sql(f"""
            SELECT
                COALESCE(disbursement_date, posting_date) as date,
                CONCAT('Loan Disbursement - ', COALESCE(loan_type, 'Loan')) as particulars,
                loan_amount as debit,
                0 as credit,
                name as reference
            FROM `tabSHG Loan`
            WHERE member = %s AND status IN ('Disbursed', 'Closed') AND docstatus = 1 {date_condition}
            ORDER BY COALESCE(disbursement_date, posting_date)
        """, member, as_dict=True)
        transactions.extend(loans)

    if not transaction_type or transaction_type == "All" or transaction_type == "Loan Repayment":
        # Repayments
        repayments = frappe.db.sql(f"""
            SELECT
                repayment_date as date,
                'Loan Repayment' as particulars,
                0 as debit,
                total_paid as credit,
                name as reference
            FROM `tabSHG Loan Repayment`
            WHERE member = %s AND docstatus = 1 {date_condition}
            ORDER BY repayment_date
        """, member, as_dict=True)
        transactions.extend(repayments)

    if not transaction_type or transaction_type == "All" or transaction_type == "Fine":
        # Meeting Fines
        fines = frappe.db.sql(f"""
            SELECT
                fine_date as date,
                CONCAT('Meeting Fine - ', COALESCE(fine_reason, 'Fine')) as particulars,
                fine_amount as debit,
                0 as credit,
                name as reference
            FROM `tabSHG Meeting Fine`
            WHERE member = %s AND docstatus = 1 {date_condition}
            ORDER BY fine_date
        """, member, as_dict=True)
        transactions.extend(fines)

    # Sort all transactions by date
    transactions.sort(key=lambda x: getdate(x.date))

    # Calculate running balance
    balance = 0
    for txn in transactions:
        # Debit increases balance (money owed to SHG), Credit decreases balance (money paid to SHG)
        balance += flt(txn.debit) - flt(txn.credit)
        txn.balance = balance

    # Add totals row if there are transactions
    if transactions:
        total_debit = sum(flt(t.debit) for t in transactions)
        total_credit = sum(flt(t.credit) for t in transactions)
        final_balance = transactions[-1].balance if transactions else 0
        
        totals_row = {
            "particulars": "Totals",
            "debit": total_debit,
            "credit": total_credit,
            "balance": final_balance,
            "reference": ""
        }
        transactions.append(totals_row)

    if not transactions:
        transactions.append({"particulars": _("No financial activity found for this member.")})

    return transactions

def get_report_summary(filters):
    """Generate the header summary for the report"""
    member = filters.get("member")
    if not member:
        return []
    
    member_doc = frappe.get_doc("SHG Member", member)
    
    return [
        {
            "label": _("Member Name"),
            "datatype": "Data",
            "value": member_doc.member_name or "-"
        },
        {
            "label": _("Member ID"),
            "datatype": "Data",
            "value": member_doc.name or "-"
        },
        {
            "label": _("Phone"),
            "datatype": "Data",
            "value": member_doc.phone_number or "-"
        },
        {
            "label": _("Total Contributions"),
            "datatype": "Currency",
            "value": member_doc.total_contributions or 0
        },
        {
            "label": _("Current Loan Balance"),
            "datatype": "Currency",
            "value": member_doc.current_loan_balance or 0
        },
        {
            "label": _("Total Fines"),
            "datatype": "Currency",
            "value": get_total_fines(member)
        }
    ]

def get_total_fines(member):
    """Calculate total fines for a member"""
    total_fines = frappe.db.sql("""
        SELECT SUM(fine_amount)
        FROM `tabSHG Meeting Fine`
        WHERE member = %s AND docstatus = 1
    """, member)[0][0] or 0
    
    return total_fines

def get_chart_data(data):
    """Generate chart data for the report"""
    dates, balances = [], []
    for row in data:
        if row.get("date") and row.get("particulars") != "Totals":
            dates.append(str(row["date"]))
            balances.append(flt(row.get("balance", 0)))

    if not dates:
        return None

    return {
        "data": {"labels": dates, "datasets": [{"name": "Balance", "type": "line", "values": balances}]},
        "type": "line",
        "colors": ["#5e64ff"]
    }

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
    """, {'txt': f"%{txt}%", 'start': start, 'page_len': page_len})