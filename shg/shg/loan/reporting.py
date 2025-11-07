import frappe
from frappe import _
from frappe.utils import flt, getdate, today, formatdate
from shg.shg.loan.schedule import get_schedule, compute_totals

class LoanReporting:
    """Comprehensive loan reporting system."""
    
    @staticmethod
    def get_loan_portfolio_summary(filters=None):
        """
        Get comprehensive loan portfolio summary.
        
        Args:
            filters (dict): Optional filters for the report
            
        Returns:
            dict: Portfolio summary with key metrics
        """
        conditions = ""
        params = {"today": getdate(today())}
        
        if filters:
            if filters.get("status"):
                conditions += " AND l.status = %(status)s"
                params["status"] = filters.get("status")
                
            if filters.get("member"):
                conditions += " AND l.member = %(member)s"
                params["member"] = filters.get("member")
                
            if filters.get("from_date"):
                conditions += " AND l.disbursement_date >= %(from_date)s"
                params["from_date"] = filters.get("from_date")
                
            if filters.get("to_date"):
                conditions += " AND l.disbursement_date <= %(to_date)s"
                params["to_date"] = filters.get("to_date")
        
        query = f"""
            SELECT 
                COUNT(*) as total_loans,
                SUM(l.loan_amount) as total_disbursed,
                SUM(l.total_payable) as total_payable,
                SUM(l.total_repaid) as total_repaid,
                SUM(l.balance_amount) as total_outstanding,
                SUM(CASE 
                    WHEN l.next_due_date < %(today)s AND l.balance_amount > 0 THEN l.overdue_amount
                    ELSE 0
                END) as total_overdue,
                AVG(l.interest_rate) as avg_interest_rate,
                AVG(l.loan_period_months) as avg_loan_period
            FROM `tabSHG Loan` l
            WHERE l.docstatus = 1 {conditions}
        """
        
        result = frappe.db.sql(query, params, as_dict=1)
        return result[0] if result else {}
    
    @staticmethod
    def get_member_loan_summary(member):
        """
        Get loan summary for a specific member.
        
        Args:
            member (str): Member ID
            
        Returns:
            dict: Member loan summary
        """
        loans = frappe.get_all(
            "SHG Loan",
            filters={"member": member, "docstatus": 1},
            fields=[
                "name", "loan_amount", "total_payable", "total_repaid", 
                "balance_amount", "overdue_amount", "status", "disbursement_date"
            ]
        )
        
        total_loans = len(loans)
        total_disbursed = sum(flt(loan.loan_amount) for loan in loans)
        total_payable = sum(flt(loan.total_payable) for loan in loans)
        total_repaid = sum(flt(loan.total_repaid) for loan in loans)
        total_outstanding = sum(flt(loan.balance_amount) for loan in loans)
        total_overdue = sum(flt(loan.overdue_amount) for loan in loans)
        
        # Calculate performance metrics
        paid_percentage = 0
        if total_payable > 0:
            paid_percentage = (total_repaid / total_payable) * 100
        
        active_loans = len([loan for loan in loans if loan.status == "Active"])
        overdue_loans = len([loan for loan in loans if loan.status == "Overdue"])
        completed_loans = len([loan for loan in loans if loan.status == "Completed"])
        
        return {
            "member": member,
            "total_loans": total_loans,
            "active_loans": active_loans,
            "overdue_loans": overdue_loans,
            "completed_loans": completed_loans,
            "total_disbursed": flt(total_disbursed, 2),
            "total_payable": flt(total_payable, 2),
            "total_repaid": flt(total_repaid, 2),
            "total_outstanding": flt(total_outstanding, 2),
            "total_overdue": flt(total_overdue, 2),
            "paid_percentage": flt(paid_percentage, 2),
            "loans": loans
        }
    
    @staticmethod
    def get_loan_aging_report():
        """
        Get loan aging report with bucket analysis.
        
        Returns:
            list: Aging report data
        """
        query = """
            SELECT 
                l.name as loan_id,
                l.member,
                l.member_name,
                l.loan_amount,
                l.total_payable,
                l.total_repaid,
                l.balance_amount,
                l.next_due_date,
                l.disbursement_date,
                DATEDIFF(%(today)s, l.next_due_date) as days_overdue
            FROM `tabSHG Loan` l
            WHERE l.docstatus = 1 
                AND l.balance_amount > 0
                AND l.next_due_date < %(today)s
            ORDER BY l.next_due_date ASC
        """
        
        loans = frappe.db.sql(query, {"today": today()}, as_dict=1)
        
        # Categorize by aging buckets
        aging_buckets = {
            "current": {"count": 0, "amount": 0},
            "0_30_days": {"count": 0, "amount": 0},
            "31_60_days": {"count": 0, "amount": 0},
            "61_90_days": {"count": 0, "amount": 0},
            "90_plus_days": {"count": 0, "amount": 0}
        }
        
        for loan in loans:
            days_overdue = loan.days_overdue or 0
            outstanding = flt(loan.balance_amount)
            
            if days_overdue <= 0:
                aging_buckets["current"]["count"] += 1
                aging_buckets["current"]["amount"] += outstanding
            elif days_overdue <= 30:
                aging_buckets["0_30_days"]["count"] += 1
                aging_buckets["0_30_days"]["amount"] += outstanding
            elif days_overdue <= 60:
                aging_buckets["31_60_days"]["count"] += 1
                aging_buckets["31_60_days"]["amount"] += outstanding
            elif days_overdue <= 90:
                aging_buckets["61_90_days"]["count"] += 1
                aging_buckets["61_90_days"]["amount"] += outstanding
            else:
                aging_buckets["90_plus_days"]["count"] += 1
                aging_buckets["90_plus_days"]["amount"] += outstanding
        
        return {
            "aging_buckets": aging_buckets,
            "total_outstanding": sum(bucket["amount"] for bucket in aging_buckets.values()),
            "total_loans_overdue": sum(bucket["count"] for bucket in aging_buckets.values()) - aging_buckets["current"]["count"]
        }
    
    @staticmethod
    def get_monthly_performance_report(month=None, year=None):
        """
        Get monthly loan performance report.
        
        Args:
            month (int): Month number (1-12)
            year (int): Year
            
        Returns:
            dict: Monthly performance data
        """
        from datetime import datetime
        
        # Default to current month/year
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year
            
        # Format for SQL
        month_year = f"{year}-{month:02d}"
        
        # Get disbursements for the month
        disbursement_query = """
            SELECT 
                COUNT(*) as loans_disbursed,
                SUM(loan_amount) as total_disbursed
            FROM `tabSHG Loan`
            WHERE docstatus = 1
                AND DATE_FORMAT(disbursement_date, '%%Y-%%m') = %(month_year)s
        """
        
        disbursements = frappe.db.sql(disbursement_query, {"month_year": month_year}, as_dict=1)
        
        # Get repayments for the month
        repayment_query = """
            SELECT 
                COUNT(*) as repayment_count,
                SUM(total_paid) as total_repaid
            FROM `tabSHG Loan Repayment`
            WHERE docstatus = 1
                AND DATE_FORMAT(posting_date, '%%Y-%%m') = %(month_year)s
        """
        
        repayments = frappe.db.sql(repayment_query, {"month_year": month_year}, as_dict=1)
        
        return {
            "month": month,
            "year": year,
            "month_year": month_year,
            "loans_disbursed": disbursements[0].loans_disbursed if disbursements else 0,
            "total_disbursed": flt(disbursements[0].total_disbursed if disbursements else 0, 2),
            "repayment_count": repayments[0].repayment_count if repayments else 0,
            "total_repaid": flt(repayments[0].total_repaid if repayments else 0, 2)
        }
    
    @staticmethod
    def get_detailed_loan_statement(loan_name):
        """
        Get detailed loan statement with repayment schedule.
        
        Args:
            loan_name (str): Loan document name
            
        Returns:
            dict: Detailed loan statement
        """
        loan = frappe.get_doc("SHG Loan", loan_name)
        
        # Get repayment schedule
        schedule = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={"parent": loan_name},
            fields=[
                "installment_no", "due_date", "principal_component", 
                "interest_component", "total_payment", "amount_paid", 
                "unpaid_balance", "status", "actual_payment_date"
            ],
            order_by="installment_no"
        )
        
        # Calculate totals
        total_principal = sum(flt(row.principal_component) for row in schedule)
        total_interest = sum(flt(row.interest_component) for row in schedule)
        total_payment = sum(flt(row.total_payment) for row in schedule)
        total_paid = sum(flt(row.amount_paid) for row in schedule)
        total_outstanding = sum(flt(row.unpaid_balance) for row in schedule)
        
        return {
            "loan_details": {
                "loan_id": loan.name,
                "member": loan.member,
                "member_name": loan.member_name,
                "loan_amount": flt(loan.loan_amount, 2),
                "interest_rate": flt(loan.interest_rate, 2),
                "interest_type": loan.interest_type,
                "loan_period_months": loan.loan_period_months,
                "disbursement_date": loan.disbursement_date,
                "repayment_start_date": loan.repayment_start_date,
                "status": loan.status
            },
            "financial_summary": {
                "total_principal": flt(total_principal, 2),
                "total_interest": flt(total_interest, 2),
                "total_payable": flt(total_payment, 2),
                "total_paid": flt(total_paid, 2),
                "total_outstanding": flt(total_outstanding, 2)
            },
            "repayment_schedule": schedule
        }

@frappe.whitelist()
def get_portfolio_summary(filters=None):
    """API endpoint to get portfolio summary."""
    reporting = LoanReporting()
    return reporting.get_loan_portfolio_summary(filters)

@frappe.whitelist()
def get_member_summary(member):
    """API endpoint to get member loan summary."""
    reporting = LoanReporting()
    return reporting.get_member_loan_summary(member)

@frappe.whitelist()
def get_aging_report():
    """API endpoint to get loan aging report."""
    reporting = LoanReporting()
    return reporting.get_loan_aging_report()

@frappe.whitelist()
def get_monthly_performance(month=None, year=None):
    """API endpoint to get monthly performance report."""
    reporting = LoanReporting()
    return reporting.get_monthly_performance_report(month, year)

@frappe.whitelist()
def get_loan_statement(loan_name):
    """API endpoint to get detailed loan statement."""
    reporting = LoanReporting()
    return reporting.get_detailed_loan_statement(loan_name)