import frappe
from frappe import _

@frappe.whitelist()
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
        
        # Check if there's any outstanding amount
        if invoice.outstanding_amount <= 0:
            frappe.throw(_("This invoice has already been fully paid"))
        
        # Get company defaults
        company = getattr(invoice, "company", None)
        if not company:
            # Try to get company from SHG Settings
            company = frappe.db.get_single_value("SHG Settings", "company")
        if not company:
            frappe.throw(_("Company not found for invoice {0}. Please set company in SHG Settings.").format(invoice.name))
            
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
        
        # Create SHG Payment Entry
        payment_entry = frappe.new_doc("SHG Payment Entry")
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
        
        # Set reference fields for traceability
        payment_entry.reference_no = invoice.name
        payment_entry.reference_date = invoice.posting_date
        
        # Set remarks
        shg_invoice_name = frappe.db.get_value("SHG Contribution Invoice", {"sales_invoice": invoice.name})
        if shg_invoice_name:
            payment_entry.remarks = f"Payment for Contribution Invoice {shg_invoice_name}"
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Reload invoice to update outstanding amount
        invoice.reload()
        
        # Update the SHG Contribution Invoice status based on the Sales Invoice status
        update_shg_contribution_invoice_status(invoice.name)
        
        frappe.msgprint(_("SHG Payment Entry {0} created and submitted for Invoice {1}").format(payment_entry.name, invoice.name))
        
        return payment_entry.name
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Payment Entry Creation Failed")
        frappe.throw(_("Failed to create SHG payment entry: {0}").format(str(e)))

def update_shg_contribution_invoice_status(sales_invoice_name):
    """
    Update the SHG Contribution Invoice status based on the Sales Invoice status with proper ERPNext v15 logic
    
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
                # Also update the Sales Invoice status
                sales_invoice.db_set("status", "Paid")
            elif sales_invoice.outstanding_amount < sales_invoice.grand_total:
                shg_invoice.db_set("status", "Partially Paid")
                # Also update the Sales Invoice status
                sales_invoice.db_set("status", "Partially Paid")
            else:
                shg_invoice.db_set("status", "Unpaid")
                # Also update the Sales Invoice status
                sales_invoice.db_set("status", "Unpaid")
                
            # Also update the member's unpaid contributions
            member = frappe.get_doc("SHG Member", shg_invoice.member)
            total_invoice_amount = sales_invoice.grand_total
            paid_amount = total_invoice_amount - sales_invoice.outstanding_amount
            
            # Update member's total unpaid contributions
            current_unpaid = member.total_unpaid_contributions or 0
            new_unpaid = current_unpaid - paid_amount
            member.db_set("total_unpaid_contributions", max(0, new_unpaid))
                
            # Recalculate member's financial summary to ensure consistency
            member.update_financial_summary()
                
            # Reload documents to reflect changes
            shg_invoice.reload()
            sales_invoice.reload()
            member.reload()
                
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Contribution Invoice Status Update Failed")

@frappe.whitelist()
def get_unpaid_contribution_invoices(member):
    """
    Get all unpaid contribution invoices for a member
    
    Args:
        member (str): Member ID
        
    Returns:
        list: List of unpaid contribution invoices
    """
    try:
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
        frappe.log_error(frappe.get_traceback(), "Get Unpaid Contribution Invoices Failed")
        frappe.throw(_("Failed to get unpaid contribution invoices: {0}").format(str(e)))