import frappe
from frappe import _
from frappe.utils import getdate, flt

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)
    report_summary = get_report_summary(data)
    chart = get_chart_data(data)
    
    return columns, data, report_summary, chart

def get_columns():
    return [
        {"label": _("Member ID"), "fieldname": "member_id", "fieldtype": "Link", "options": "SHG Member", "width": 120},
        {"label": _("Member Name"), "fieldname": "member_name", "fieldtype": "Data", "width": 150},
        {"label": _("Total Contributions (KES)"), "fieldname": "total_contributions", "fieldtype": "Currency", "width": 150},
        {"label": _("Total Fines (KES)"), "fieldname": "total_fines", "fieldtype": "Currency", "width": 120},
        {"label": _("Total Loan Balance (KES)"), "fieldname": "total_loan_balance", "fieldtype": "Currency", "width": 160},
        {"label": _("Unpaid Contributions (KES)"), "fieldname": "unpaid_contributions", "fieldtype": "Currency", "width": 170},
        {"label": _("Unpaid Fines (KES)"), "fieldname": "unpaid_fines", "fieldtype": "Currency", "width": 130},
    ]

def get_data(filters):
    member_filter = filters.get("member")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    show_only_outstanding = filters.get("show_only_with_outstanding")
    
    # Base query conditions
    member_condition = ""
    if member_filter:
        member_condition = f" AND m.name = '{member_filter}'"
        
    date_condition_contributions = ""
    date_condition_fines = ""
    date_condition_loans = ""
    
    if from_date and to_date:
        date_condition_contributions = f" AND c.contribution_date BETWEEN '{from_date}' AND '{to_date}'"
        date_condition_fines = f" AND f.fine_date BETWEEN '{from_date}' AND '{to_date}'"
        date_condition_loans = f" AND l.posting_date BETWEEN '{from_date}' AND '{to_date}'"
    elif from_date:
        date_condition_contributions = f" AND c.contribution_date >= '{from_date}'"
        date_condition_fines = f" AND f.fine_date >= '{from_date}'"
        date_condition_loans = f" AND l.posting_date >= '{from_date}'"
    elif to_date:
        date_condition_contributions = f" AND c.contribution_date <= '{to_date}'"
        date_condition_fines = f" AND f.fine_date <= '{to_date}'"
        date_condition_loans = f" AND l.posting_date <= '{to_date}'"
    
    # Query to get members with their financial data
    query = f"""
        SELECT 
            m.name as member_id,
            m.member_name as member_name,
            COALESCE(contrib.total_contributions, 0) as total_contributions,
            COALESCE(fines.total_fines, 0) as total_fines,
            COALESCE(loans.total_loan_balance, 0) as total_loan_balance,
            COALESCE(contrib.unpaid_contributions, 0) as unpaid_contributions,
            COALESCE(fines.unpaid_fines, 0) as unpaid_fines
        FROM `tabSHG Member` m
        LEFT JOIN (
            SELECT 
                c.member,
                SUM(c.amount) as total_contributions,
                SUM(CASE WHEN c.status != 'Paid' THEN c.amount ELSE 0 END) as unpaid_contributions
            FROM `tabSHG Contribution` c
            WHERE c.docstatus = 1 {date_condition_contributions}
            GROUP BY c.member
        ) contrib ON m.name = contrib.member
        LEFT JOIN (
            SELECT 
                f.member,
                SUM(f.fine_amount) as total_fines,
                SUM(CASE WHEN f.status != 'Paid' THEN f.fine_amount ELSE 0 END) as unpaid_fines
            FROM `tabSHG Meeting Fine` f
            WHERE f.docstatus = 1 {date_condition_fines}
            GROUP BY f.member
        ) fines ON m.name = fines.member
        LEFT JOIN (
            SELECT 
                l.member,
                SUM(l.loan_amount - COALESCE(repayments.total_repayment, 0)) as total_loan_balance
            FROM `tabSHG Loan` l
            LEFT JOIN (
                SELECT 
                    loan,
                    SUM(total_paid) as total_repayment
                FROM `tabSHG Loan Repayment`
                WHERE docstatus = 1
                GROUP BY loan
            ) repayments ON l.name = repayments.loan
            WHERE l.docstatus = 1 AND l.status IN ('Disbursed', 'Active') {date_condition_loans}
            GROUP BY l.member
        ) loans ON m.name = loans.member
        WHERE m.docstatus = 1 {member_condition}
        ORDER BY m.member_name
    """
    
    data = frappe.db.sql(query, as_dict=True)
    
    # Apply "Show Only With Outstanding" filter
    if show_only_outstanding:
        data = [row for row in data if (
            flt(row.total_contributions) > 0 or 
            flt(row.total_fines) > 0 or 
            flt(row.total_loan_balance) > 0 or
            flt(row.unpaid_contributions) > 0 or
            flt(row.unpaid_fines) > 0
        )]
    
    # Add summary row at bottom
    if data:
        total_contributions = sum(flt(row.total_contributions) for row in data)
        total_fines = sum(flt(row.total_fines) for row in data)
        total_loan_balance = sum(flt(row.total_loan_balance) for row in data)
        unpaid_contributions = sum(flt(row.unpaid_contributions) for row in data)
        unpaid_fines = sum(flt(row.unpaid_fines) for row in data)
        
        summary_row = {
            "member_id": "",
            "member_name": "<strong>GRAND TOTAL</strong>",
            "total_contributions": total_contributions,
            "total_fines": total_fines,
            "total_loan_balance": total_loan_balance,
            "unpaid_contributions": unpaid_contributions,
            "unpaid_fines": unpaid_fines
        }
        data.append(summary_row)
    
    return data

def get_report_summary(data):
    """Generate the summary for the report"""
    if not data:
        return []
    
    # Remove the summary row for calculations
    report_data = [row for row in data if row.get("member_id")]
    
    total_contributions = sum(flt(row.total_contributions) for row in report_data)
    total_fines = sum(flt(row.total_fines) for row in report_data)
    total_loan_balance = sum(flt(row.total_loan_balance) for row in report_data)
    unpaid_contributions = sum(flt(row.unpaid_contributions) for row in report_data)
    unpaid_fines = sum(flt(row.unpaid_fines) for row in report_data)
    
    return [
        {
            "label": _("Grand Total Contributions"),
            "datatype": "Currency",
            "value": total_contributions
        },
        {
            "label": _("Grand Total Fines"),
            "datatype": "Currency",
            "value": total_fines
        },
        {
            "label": _("Total Outstanding Loans"),
            "datatype": "Currency",
            "value": total_loan_balance
        },
        {
            "label": _("Total Unpaid Contributions"),
            "datatype": "Currency",
            "value": unpaid_contributions
        },
        {
            "label": _("Total Unpaid Fines"),
            "datatype": "Currency",
            "value": unpaid_fines
        }
    ]

def get_chart_data(data):
    """Generate chart data for the report"""
    # Since this is a summary report, we won't generate a chart
    return None

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