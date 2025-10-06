import frappe
from frappe import _
from frappe.utils import getdate, flt

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    return columns, data, None, chart

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
    if not member:
        frappe.msgprint(_("Please select a Member"))
        return []

    data, balance = [], 0

    # Member Summary Header
    member_doc = frappe.get_doc("SHG Member", member)
    summary = [
        {"particulars": f"Member: {member_doc.member_name}"},
        {"particulars": f"Member ID: {member_doc.name}"},
        {"particulars": f"Phone: {member_doc.phone_number or '-'}"},
        {"particulars": f"Total Contributions: KES {flt(member_doc.total_contributions):,.2f}"},
        {"particulars": f"Current Loan Balance: KES {flt(member_doc.current_loan_balance):,.2f}"},
        {}
    ]
    data.extend(summary)

    # Contributions
    contributions = frappe.db.sql("""
        SELECT
            contribution_date as date,
            CONCAT('Contribution - ', COALESCE(contribution_type, contribution_type_link)) as particulars,
            0 as debit,
            amount as credit,
            name as reference
        FROM `tabSHG Contribution`
        WHERE member = %s AND docstatus = 1
    """, member, as_dict=True)

    # Loans
    loans = frappe.db.sql("""
        SELECT
            COALESCE(disbursement_date, posting_date) as date,
            CONCAT('Loan Disbursement - ', COALESCE(loan_type, 'Loan')) as particulars,
            loan_amount as debit,
            0 as credit,
            name as reference
        FROM `tabSHG Loan`
        WHERE member = %s AND status IN ('Disbursed', 'Closed') AND docstatus = 1
    """, member, as_dict=True)

    # Repayments
    repayments = frappe.db.sql("""
        SELECT
            repayment_date as date,
            'Loan Repayment' as particulars,
            0 as debit,
            total_paid as credit,
            name as reference
        FROM `tabSHG Loan Repayment`
        WHERE member = %s AND docstatus = 1
    """, member, as_dict=True)

    # Meeting Fines
    fines = frappe.db.sql("""
        SELECT
            fine_date as date,
            CONCAT('Meeting Fine - ', COALESCE(fine_reason, 'Fine')) as particulars,
            fine_amount as debit,
            0 as credit,
            name as reference
        FROM `tabSHG Meeting Fine`
        WHERE member = %s AND docstatus = 1
    """, member, as_dict=True)

    all_txns = contributions + loans + repayments + fines
    all_txns = [t for t in all_txns if t.date]

    # Sort by date
    all_txns.sort(key=lambda x: getdate(x.date))

    # Running Balance
    for txn in all_txns:
        balance += (flt(txn.debit) - flt(txn.credit))
        txn.balance = balance
        data.append(txn)

    if not all_txns:
        data.append({"particulars": _("No financial activity found for this member.")})

    return data

def get_chart_data(data):
    dates, balances = [], []
    for row in data:
        if row.get("date"):
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
