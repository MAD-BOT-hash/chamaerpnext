import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime
import json

@frappe.whitelist(allow_guest=True)
def login(member_id, password):
    """Authenticate member for mobile app"""
    try:
        # In a real implementation, you would verify credentials
        # This is a simplified version
        member = frappe.db.get_value("SHG Member", 
            {"member_id": member_id, "membership_status": "Active"}, 
            ["name", "member_name", "account_number"], as_dict=True)
            
        if member:
            return {
                "status": "success",
                "message": "Login successful",
                "member": member
            }
        else:
            return {
                "status": "error",
                "message": "Invalid member ID or inactive membership"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_member_statement(member):
    """Get member statement for mobile app"""
    try:
        # Get contributions
        contributions = frappe.db.sql("""
            SELECT 
                contribution_date as date,
                contribution_type as description,
                amount as credit,
                0 as debit
            FROM `tabSHG Contribution`
            WHERE member = %s AND docstatus = 1
            ORDER BY contribution_date DESC
            LIMIT 20
        """, member, as_dict=1)
        
        # Get loan disbursements
        loans = frappe.db.sql("""
            SELECT 
                disbursement_date as date,
                CONCAT('Loan - ', loan_purpose) as description,
                0 as credit,
                loan_amount as debit
            FROM `tabSHG Loan`
            WHERE member = %s AND status = 'Disbursed'
            ORDER BY disbursement_date DESC
            LIMIT 20
        """, member, as_dict=1)
        
        # Get loan repayments
        repayments = frappe.db.sql("""
            SELECT 
                payment_date as date,
                'Loan Repayment' as description,
                amount as credit,
                0 as debit
            FROM `tabSHG Loan Repayment`
            WHERE member = %s AND docstatus = 1
            ORDER BY payment_date DESC
            LIMIT 20
        """, member, as_dict=1)
        
        # Combine and sort transactions
        transactions = contributions + loans + repayments
        transactions.sort(key=lambda x: x.date, reverse=True)
        
        return {
            "status": "success",
            "transactions": transactions
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def submit_contribution(member, amount, contribution_type, payment_method="Mpesa"):
    """Submit contribution from mobile app"""
    try:
        # Create contribution record
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member,
            "contribution_date": nowdate(),
            "contribution_type": contribution_type,
            "amount": amount,
            "payment_method": payment_method
        })
        contribution.insert()
        contribution.submit()
        
        return {
            "status": "success",
            "message": "Contribution submitted successfully",
            "contribution_id": contribution.name
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def apply_loan(member, loan_type, loan_amount, loan_purpose):
    """Apply for loan from mobile app"""
    try:
        # Create loan application
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member,
            "loan_type": loan_type,
            "loan_amount": loan_amount,
            "loan_purpose": loan_purpose,
            "application_date": nowdate()
        })
        loan.insert()
        
        return {
            "status": "success",
            "message": "Loan application submitted successfully",
            "loan_id": loan.name
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_notifications(member):
    """Get member notifications"""
    try:
        notifications = frappe.db.sql("""
            SELECT 
                creation as date,
                message,
                notification_type,
                reference_document,
                reference_name
            FROM `tabSHG Notification Log`
            WHERE member = %s
            ORDER BY creation DESC
            LIMIT 10
        """, member, as_dict=1)
        
        return {
            "status": "success",
            "notifications": notifications
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_upcoming_meetings():
    """Get upcoming meetings"""
    try:
        meetings = frappe.db.sql("""
            SELECT 
                name,
                meeting_date,
                meeting_time,
                venue,
                agenda
            FROM `tabSHG Meeting`
            WHERE meeting_date >= %s AND docstatus = 1
            ORDER BY meeting_date
            LIMIT 5
        """, nowdate(), as_dict=1)
        
        return {
            "status": "success",
            "meetings": meetings
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_member_profile(member):
    """Get member profile information"""
    try:
        member_doc = frappe.get_doc("SHG Member", member)
        
        # Get financial summary
        financial_summary = {
            "total_contributions": member_doc.total_contributions,
            "total_loans_taken": member_doc.total_loans_taken,
            "current_loan_balance": member_doc.current_loan_balance,
            "credit_score": member_doc.credit_score
        }
        
        profile = {
            "member_name": member_doc.member_name,
            "account_number": member_doc.account_number,
            "phone_number": member_doc.phone_number,
            "email": member_doc.email,
            "membership_date": member_doc.membership_date,
            "membership_status": member_doc.membership_status,
            "financial_summary": financial_summary
        }
        
        return {
            "status": "success",
            "profile": profile
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }