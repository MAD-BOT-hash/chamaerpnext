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
            
            # Ensure we don't go below zero
            new_outstanding = max(0, new_outstanding)
            sales_invoice.db_set("outstanding_amount", new_outstanding)
            
            # Update invoice status based on outstanding amount
            if new_outstanding <= 0:
                invoice.db_set("status", "Paid")
                # Also update the Sales Invoice status
                sales_invoice.db_set("status", "Paid")
            elif new_outstanding < sales_invoice.grand_total:
                invoice.db_set("status", "Partially Paid")
                # Also update the Sales Invoice status
                sales_invoice.db_set("status", "Partially Paid")
            else:
                invoice.db_set("status", "Unpaid")
                # Also update the Sales Invoice status
                sales_invoice.db_set("status", "Unpaid")
                
        # Update member financial summary
        member = frappe.get_doc("SHG Member", invoice.member)
        total_unpaid = (member.total_unpaid_contributions or 0) - paid_amount
        member.db_set("total_unpaid_contributions", max(0, total_unpaid))
        
        # Reload the invoice to reflect changes
        invoice.reload()
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Invoice Status Failed")
        frappe.throw(_("Failed to update invoice status: {0}").format(str(e)))

def create_payment_entry_for_invoice(invoice_name, paid_amount, payment_date, member):
    """
    Create a Payment Entry for a Sales Invoice with correct GL entries
    
    Args:
        invoice_name (str): Name of the Sales Invoice
        paid_amount (float): Amount to pay
        payment_date (str): Payment date
        member (str): Member ID
        
    Returns:
        str: Name of the created Payment Entry
    """
    try:
        # Get the Sales Invoice
        sales_invoice = frappe.get_doc("Sales Invoice", invoice_name)
        
        # Get company defaults
        company = sales_invoice.company
        default_receivable_account = frappe.db.get_value("Company", company, "default_receivable_account")
        default_cash_account = frappe.db.get_value("Company", company, "default_cash_account")
        
        if not default_receivable_account:
            frappe.throw(_("Please set default receivable account in Company {0}").format(company))
            
        if not default_cash_account:
            frappe.throw(_("Please set default cash account in Company {0}").format(company))
        
        # For SHG Contributions, payment direction must be:
        # paid_from = member's account (receivable), paid_to = cash/bank account
        # This reflects members bringing cash to the group
        paid_from = default_receivable_account  # Member's account (receivable)
        paid_to = default_cash_account  # Group's cash account
        
        # Create Payment Entry
        payment_entry = frappe.new_doc("Payment Entry")
        payment_entry.payment_type = "Receive"
        payment_entry.party_type = "Customer"
        payment_entry.party = sales_invoice.customer
        payment_entry.company = company
        payment_entry.posting_date = payment_date
        payment_entry.paid_from = paid_from
        payment_entry.paid_to = paid_to
        payment_entry.received_amount = paid_amount
        payment_entry.paid_amount = paid_amount
        payment_entry.allocate_payment_amount = 1
        
        # Add reference to the invoice
        payment_entry.append("references", {
            "reference_doctype": "Sales Invoice",
            "reference_name": sales_invoice.name,
            "total_amount": sales_invoice.grand_total,
            "outstanding_amount": sales_invoice.outstanding_amount,
            "allocated_amount": paid_amount,
        })
        
        # Set reference fields for traceability
        payment_entry.reference_no = sales_invoice.name
        payment_entry.reference_date = payment_date
        
        # Set remarks
        shg_invoice_name = frappe.db.get_value("SHG Contribution Invoice", {"sales_invoice": invoice_name})
        if shg_invoice_name:
            payment_entry.remarks = f"Payment for Contribution Invoice {shg_invoice_name}"
        else:
            payment_entry.remarks = f"Payment for Sales Invoice {invoice_name}"
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Update the Sales Invoice outstanding amount
        sales_invoice.reload()
        
        return payment_entry.name
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Payment Entry Creation Failed")
        frappe.throw(_("Failed to create payment entry: {0}").format(str(e)))

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