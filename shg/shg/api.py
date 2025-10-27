# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, today

@frappe.whitelist()
def get_unpaid_contribution_invoices(filters=None):
    """API endpoint to fetch unpaid contribution invoices"""
    if filters is None:
        filters = {}
        
    # Default filters for unpaid invoices
    default_filters = {
        "status": ["in", ["Unpaid", "Partially Paid"]],
        "docstatus": 1
    }
    
    # Merge with provided filters
    final_filters = {**default_filters, **filters}
    
    invoices = frappe.get_all(
        "SHG Contribution Invoice",
        filters=final_filters,
        fields=[
            "name as invoice",
            "member",
            "member_name",
            "contribution_type",
            "invoice_date",
            "due_date",
            "amount",
            "paid_amount",
            "status"
        ],
        order_by="invoice_date DESC"
    )
    
    # Calculate outstanding amount for each invoice
    for invoice in invoices:
        invoice["outstanding_amount"] = flt(invoice["amount"]) - flt(invoice["paid_amount"] or 0)
        
    return invoices

@frappe.whitelist()
def create_multi_member_payment(invoice_data, payment_date, payment_method, account, company, description=None):
    """API endpoint to create a multi-member payment entry"""
    try:
        # Create new SHG Multi Member Payment document
        payment = frappe.new_doc("SHG Multi Member Payment")
        payment.payment_date = payment_date
        payment.payment_method = payment_method
        payment.account = account
        payment.company = company
        payment.description = description
        
        # Add invoice rows
        for invoice in invoice_data:
            payment.append("invoices", {
                "invoice": invoice.get("invoice"),
                "member": invoice.get("member"),
                "member_name": invoice.get("member_name"),
                "contribution_type": invoice.get("contribution_type"),
                "invoice_date": invoice.get("invoice_date"),
                "due_date": invoice.get("due_date"),
                "outstanding_amount": invoice.get("outstanding_amount"),
                "payment_amount": invoice.get("payment_amount"),
                "status": invoice.get("status")
            })
            
        # Save and submit the payment
        payment.insert(ignore_permissions=True)
        payment.submit()
        
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": _("Payment entry {0} created successfully").format(payment.name),
            "payment_name": payment.name
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Multi Member Payment Failed")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def get_active_loans(member):
    """Return all active loans for the given member."""
    loans = frappe.get_all(
        "SHG Loan",
        filters={"member": member, "status": ["in", ["Disbursed", "Partially Paid"]], "docstatus": 1},
        fields=["name", "balance_amount"]
    )
    return loans


@frappe.whitelist()
def create_repayment(loan, member, amount_paid, posting_date=None, remarks=None):
    """Create a repayment entry linked to the loan."""
    if not posting_date:
        posting_date = today()

    loan_doc = frappe.get_doc("SHG Loan", loan)
    repayment = frappe.get_doc({
        "doctype": "SHG Loan Repayment",
        "loan": loan,
        "member": member,
        "amount_paid": amount_paid,
        "posting_date": posting_date,
        "remarks": remarks or "",
    })
    repayment.insert(ignore_permissions=True)
    repayment.submit()

    frappe.db.commit()
    return repayment.name