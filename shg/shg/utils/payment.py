import frappe
from frappe import _

def get_unpaid_invoices_for_member(member):
    """
    Get all unpaid contribution invoices for a member
    
    Args:
        member (str): Member ID
        
    Returns:
        list: List of unpaid contribution invoices
    """
    try:
        # Get unpaid contribution invoices
        invoices = frappe.get_all(
            "SHG Contribution Invoice",
            filters={
                "member": member,
                "docstatus": 1,
                "status": ["!=", "Paid"]
            },
            fields=["name", "invoice_date", "amount", "description"]
        )
        
        # Add outstanding amount from linked Sales Invoice
        for invoice in invoices:
            shg_invoice = frappe.get_doc("SHG Contribution Invoice", invoice.name)
            if shg_invoice.sales_invoice:
                sales_invoice = frappe.get_doc("Sales Invoice", shg_invoice.sales_invoice)
                invoice.outstanding_amount = sales_invoice.outstanding_amount
            else:
                invoice.outstanding_amount = invoice.amount
                
        # Filter out fully paid invoices
        unpaid_invoices = [inv for inv in invoices if inv.outstanding_amount > 0]
        
        return unpaid_invoices
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Unpaid Invoices for Member Failed")
        frappe.throw(_("Failed to get unpaid invoices for member: {0}").format(str(e)))

def update_invoice_status(invoice_name, paid_amount):
    """
    Update contribution invoice status after payment
    
    Args:
        invoice_name (str): SHG Contribution Invoice name
        paid_amount (float): Amount paid
    """
    try:
        # Get the invoice
        invoice = frappe.get_doc("SHG Contribution Invoice", invoice_name)
        
        if invoice.sales_invoice:
            # Update linked Sales Invoice
            sales_invoice = frappe.get_doc("Sales Invoice", invoice.sales_invoice)
            new_outstanding = sales_invoice.outstanding_amount - paid_amount
            sales_invoice.db_set("outstanding_amount", max(0, new_outstanding))
            
            # Update invoice status
            if new_outstanding <= 0:
                invoice.db_set("status", "Paid")
            else:
                invoice.db_set("status", "Partially Paid")
                
        # Update member financial summary
        member = frappe.get_doc("SHG Member", invoice.member)
        total_unpaid = member.total_unpaid_contributions - paid_amount
        member.db_set("total_unpaid_contributions", max(0, total_unpaid))
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Invoice Status Failed")
        frappe.throw(_("Failed to update invoice status: {0}").format(str(e)))

def send_payment_receipt(payment_entry):
    """
    Send payment receipt via email
    
    Args:
        payment_entry (Document): SHG Payment Entry document
    """
    try:
        member = frappe.get_doc("SHG Member", payment_entry.member)
        
        if not member.email:
            return
            
        # Prepare email content
        subject = f"Payment Receipt - {payment_entry.name}"
        
        message = f"""Dear {payment_entry.member_name},

Thank you for your payment. Here are the details:

Payment Reference: {payment_entry.name}
Payment Date: {payment_entry.payment_date}
Total Amount: KES {payment_entry.total_amount:,.2f}
Payment Method: {payment_entry.payment_method}

Payment Details:
"""
        
        for entry in payment_entry.payment_entries:
            message += f"- Invoice {entry.invoice}: KES {entry.amount:,.2f}\n"
            
        message += """

Thank you for your continued support.

SHG Management"""
        
        # Send email
        frappe.sendmail(
            recipients=[member.email],
            subject=subject,
            message=message
        )
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Send Payment Receipt Failed")