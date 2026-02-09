import frappe
from frappe import _

@frappe.whitelist()
def get_active_loans(member=None):
    """Get active loans for bulk repayment - API endpoint"""
    try:
        filters = {"status": ["in", ["Disbursed", "Partially Paid"]]}
        if member:
            filters["member"] = member
        
        loans = frappe.get_all(
            "SHG Loan",
            filters=filters,
            fields=["name", "member", "loan_type", "total_outstanding_amount", "repayment_start_date"],
            order_by="member, name"
        )
        
        return {
            "success": True,
            "data": loans,
            "message": f"Found {len(loans)} active loans"
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Active Loans API Error")
        return {
            "success": False,
            "data": [],
            "message": f"Error fetching loans: {str(e)}"
        }

@frappe.whitelist()
def get_outstanding_amount(loan):
    """Get outstanding amount for a specific loan"""
    try:
        if not loan:
            return {"success": False, "message": "Loan name is required"}
        
        loan_doc = frappe.get_doc("SHG Loan", loan)
        outstanding = loan_doc.total_outstanding_amount or 0.0
        
        return {
            "success": True,
            "data": outstanding,
            "message": f"Outstanding amount: {outstanding}"
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Get Outstanding Amount API Error for loan {loan}")
        return {
            "success": False,
            "data": 0.0,
            "message": f"Error fetching outstanding amount: {str(e)}"
        }