import frappe
from frappe import _

@frappe.whitelist()
def get_member_summary(member):
    """Get summary information for a member"""
    try:
        member_doc = frappe.get_doc("SHG Member", member)
        return {
            "member_name": member_doc.member_name,
            "total_contributions": member_doc.total_contributions,
            "current_loan_balance": member_doc.current_loan_balance,
            "credit_score": member_doc.credit_score,
            "membership_status": member_doc.membership_status
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API - Get Member Summary Failed")
        return {"error": str(e)}

@frappe.whitelist()
def get_suggested_contribution_amount(member, contribution_type="Regular Weekly"):
    """Get suggested contribution amount based on member and type"""
    try:
        settings = frappe.get_single("SHG Settings")
        
        if contribution_type == "Regular Weekly":
            return settings.default_contribution_amount or 500
        else:
            # For other types, return a default or allow custom amount
            return 0
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API - Get Suggested Contribution Failed")
        return 0