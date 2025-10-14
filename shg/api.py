import frappe
from frappe import _

def create_payment_entry_from_invoice(invoice_name, paid_amount=None):
    """
    Create a payment entry from a sales invoice
    
    Args:
        invoice_name (str): Name of the Sales Invoice
        paid_amount (float, optional): Amount to pay (defaults to outstanding amount)
    
    Returns:
        str: Name of the created Payment Entry
    """
    try:
        invoice = frappe.get_doc("Sales Invoice", invoice_name)
        
        # Determine amount to pay
        amount_to_pay = paid_amount if paid_amount is not None else invoice.outstanding_amount
        
        # Validate amount
        if amount_to_pay <= 0:
            frappe.throw(_("Payment amount must be greater than zero"))
            
        if amount_to_pay > invoice.outstanding_amount:
            frappe.throw(_("Payment amount cannot exceed outstanding amount"))
        
        # Get company defaults
        company = invoice.company
        default_receivable_account = frappe.db.get_value("Company", company, "default_receivable_account")
        default_cash_account = frappe.db.get_value("Company", company, "default_cash_account")
        
        if not default_receivable_account:
            frappe.throw(_("Please set default receivable account in Company {0}").format(company))
            
        if not default_cash_account:
            frappe.throw(_("Please set default cash account in Company {0}").format(company))
        
        # For SHG Contributions, payment direction must be:
        # paid_from = member's account, paid_to = cash/bank account
        # This reflects members bringing cash to the group
        paid_from = default_receivable_account  # Member's account (receivable)
        paid_to = default_cash_account  # Group's cash account
        
        # Create Payment Entry
        payment_entry = frappe.new_doc("Payment Entry")
        payment_entry.payment_type = "Receive"
        payment_entry.party_type = "Customer"
        payment_entry.party = invoice.customer
        payment_entry.company = company
        payment_entry.posting_date = invoice.posting_date
        payment_entry.paid_from = paid_from
        payment_entry.paid_to = paid_to
        payment_entry.received_amount = amount_to_pay
        payment_entry.paid_amount = amount_to_pay
        payment_entry.allocate_payment_amount = 1
        
        # Add reference to the invoice
        payment_entry.append("references", {
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
            "total_amount": invoice.grand_total,
            "outstanding_amount": invoice.outstanding_amount,
            "allocated_amount": amount_to_pay,
        })
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Reload invoice to update outstanding amount
        invoice.reload()
        
        # Update the SHG Contribution Invoice status based on the Sales Invoice status
        update_shg_contribution_invoice_status(invoice.name)
        
        frappe.msgprint(_("Payment Entry {0} created and submitted for Invoice {1}").format(payment_entry.name, invoice.name))
        
        return payment_entry.name
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Payment Entry Creation Failed")
        frappe.throw(_("Failed to create payment entry: {0}").format(str(e)))

def update_shg_contribution_invoice_status(sales_invoice_name):
    """
    Update the SHG Contribution Invoice status based on the Sales Invoice status
    
    Args:
        sales_invoice_name (str): Name of the Sales Invoice
    """
    try:
        # Get the SHG Contribution Invoice linked to this Sales Invoice
        shg_invoice_name = frappe.db.get_value("SHG Contribution Invoice", 
                                              {"sales_invoice": sales_invoice_name})
        
        if shg_invoice_name:
            shg_invoice = frappe.get_doc("SHG Contribution Invoice", shg_invoice_name)
            sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
            
            # Update status based on outstanding amount
            if sales_invoice.outstanding_amount <= 0:
                shg_invoice.db_set("status", "Paid")
            elif sales_invoice.outstanding_amount < sales_invoice.grand_total:
                shg_invoice.db_set("status", "Partially Paid")
            else:
                shg_invoice.db_set("status", "Unpaid")
                
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Contribution Invoice Status Update Failed")
