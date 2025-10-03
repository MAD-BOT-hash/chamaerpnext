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
            "label": _("Month"),
            "fieldname": "month",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Year"),
            "fieldname": "year",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Total Contributions"),
            "fieldname": "total_contributions",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Total Loan Disbursements"),
            "fieldname": "total_loan_disbursements",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Total Loan Repayments"),
            "fieldname": "total_loan_repayments",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Total Interest Collected"),
            "fieldname": "total_interest_collected",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Net Cash Flow"),
            "fieldname": "net_cash_flow",
            "fieldtype": "Currency",
            "width": 150
        }
    ]

def get_data(filters):
    # Get contributions summary
    contributions = frappe.db.sql("""
        SELECT 
            MONTH(contribution_date) as month,
            YEAR(contribution_date) as year,
            SUM(amount) as total_contributions
        FROM `tabSHG Contribution`
        WHERE docstatus = 1
        GROUP BY YEAR(contribution_date), MONTH(contribution_date)
        ORDER BY year, month
    """, as_dict=1)
    
    # Get loan disbursements summary
    disbursements = frappe.db.sql("""
        SELECT 
            MONTH(disbursement_date) as month,
            YEAR(disbursement_date) as year,
            SUM(loan_amount) as total_loan_disbursements
        FROM `tabSHG Loan`
        WHERE docstatus = 1 AND status = 'Disbursed'
        GROUP BY YEAR(disbursement_date), MONTH(disbursement_date)
        ORDER BY year, month
    """, as_dict=1)
    
    # Get loan repayments summary
    repayments = frappe.db.sql("""
        SELECT 
            MONTH(repayment_date) as month,
            YEAR(repayment_date) as year,
            SUM(total_paid) as total_loan_repayments,
            SUM(interest_amount) as total_interest_collected
        FROM `tabSHG Loan Repayment`
        WHERE docstatus = 1
        GROUP BY YEAR(repayment_date), MONTH(repayment_date)
        ORDER BY year, month
    """, as_dict=1)
    
    # Combine data
    result = []
    months_data = {}
    
    # Process contributions
    for item in contributions:
        key = (item.year, item.month)
        if key not in months_data:
            months_data[key] = {}
        months_data[key]['total_contributions'] = item.total_contributions
    
    # Process disbursements
    for item in disbursements:
        key = (item.year, item.month)
        if key not in months_data:
            months_data[key] = {}
        months_data[key]['total_loan_disbursements'] = item.total_loan_disbursements
    
    # Process repayments
    for item in repayments:
        key = (item.year, item.month)
        if key not in months_data:
            months_data[key] = {}
        months_data[key]['total_loan_repayments'] = item.total_loan_repayments
        months_data[key]['total_interest_collected'] = item.total_interest_collected
    
    # Create result data
    for (year, month), values in months_data.items():
        total_contributions = flt(values.get('total_contributions', 0))
        total_disbursements = flt(values.get('total_loan_disbursements', 0))
        total_repayments = flt(values.get('total_loan_repayments', 0))
        total_interest = flt(values.get('total_interest_collected', 0))
        
        net_cash_flow = total_contributions + total_repayments - total_disbursements
        
        result.append({
            'month': get_month_name(month),
            'year': year,
            'total_contributions': total_contributions,
            'total_loan_disbursements': total_disbursements,
            'total_loan_repayments': total_repayments,
            'total_interest_collected': total_interest,
            'net_cash_flow': net_cash_flow
        })
    
    return sorted(result, key=lambda x: (x['year'], get_month_number(x['month'])))

def get_month_name(month_num):
    months = ["", "January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    return months[month_num] if 1 <= month_num <= 12 else ""

def get_month_number(month_name):
    months = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
              "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12}
    return months.get(month_name, 0)