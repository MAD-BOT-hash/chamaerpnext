import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, getdate, get_first_day, get_last_day, formatdate, add_days

class SHGContributionInvoice(Document):
    def validate(self):
        self.validate_amount()
        self.set_description()
        
        # Ensure amount is rounded to 2 decimal places
        if self.amount:
            self.amount = round(float(self.amount), 2)
        
    def validate_amount(self):
        """Validate contribution invoice amount"""
        # Initialize amount to 0 if None or empty
        amount = 0
        if self.amount:
            try:
                amount = float(self.amount)
            except (ValueError, TypeError):
                frappe.throw(_("Invalid amount. Please enter a numeric value."))
        else:
            frappe.throw(_("Contribution invoice amount is required"))
        
        if amount <= 0:
            frappe.throw(_("Contribution invoice amount must be greater than zero"))
        
        self.amount = amount
            
    def set_description(self):
        """Set default description if not provided"""
        if not self.description and self.invoice_date:
            month_year = formatdate(self.invoice_date, "MMMM yyyy")
            self.description = f"Contribution invoice for {month_year}"
            
    def on_submit(self):
        # Create Sales Invoice
        if not self.sales_invoice:
            self.create_sales_invoice()
            
    def create_sales_invoice(self):
        """Create a Sales Invoice for this contribution invoice"""
        try:
            member = frappe.get_doc("SHG Member", self.member)
            
            if not member.customer:
                frappe.throw(_("Member {0} does not have a linked Customer record").format(self.member_name))
                
            # Get contribution type details for item
            item_code = "SHG Contribution"
            item_name = "SHG Contribution"
            description = self.description or f"Contribution invoice for {formatdate(self.invoice_date, 'MMMM yyyy')}"
            
            if self.contribution_type:
                contrib_type = frappe.get_doc("SHG Contribution Type", self.contribution_type)
                if contrib_type.item_code:
                    item_code = contrib_type.item_code
                    item_name = contrib_type.contribution_type_name
            
            # Create Sales Invoice
            sales_invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": member.customer,
                "posting_date": self.invoice_date,
                "due_date": self.due_date,
                "shg_contribution_invoice": self.name,
                "items": [{
                    "item_code": item_code,
                    "item_name": item_name,
                    "description": description,
                    "qty": 1,
                    "rate": self.amount,
                    "amount": self.amount
                }]
            })
            
            sales_invoice.insert()
            sales_invoice.submit()
            
            # Link the Sales Invoice to this Contribution Invoice
            self.db_set("sales_invoice", sales_invoice.name)
            
            frappe.msgprint(_("Sales Invoice {0} created successfully").format(sales_invoice.name))
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Contribution Invoice - Sales Invoice Creation Failed")
            frappe.throw(_("Failed to create Sales Invoice: {0}").format(str(e)))
            
    @frappe.whitelist()
    def send_invoice_email(self):
        """Send invoice email to member"""
        try:
            if not self.sales_invoice:
                frappe.throw(_("No Sales Invoice linked to this Contribution Invoice"))
                
            member = frappe.get_doc("SHG Member", self.member)
            
            if not member.email:
                frappe.throw(_("Member {0} does not have an email address").format(self.member_name))
                
            # Prepare email content
            month_year = formatdate(self.invoice_date, "MMMM yyyy")
            subject = f"Your {month_year} SHG Contribution Invoice"
            
            message = f"""Dear {self.member_name},

Your contribution invoice for {month_year} amounting to KES {self.amount:,.2f} has been generated.
Please make payment by {formatdate(self.due_date)}.

Thank you for your continued support.

SHG Management"""
            
            # Send email with invoice attachment
            frappe.sendmail(
                recipients=[member.email],
                subject=subject,
                message=message,
                attachments=[frappe.attach_print("Sales Invoice", self.sales_invoice, file_name=self.sales_invoice)]
            )
            
            frappe.msgprint(_("Invoice email sent to {0}").format(member.email))
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Contribution Invoice - Email Sending Failed")
            frappe.throw(_("Failed to send invoice email: {0}").format(str(e)))

@frappe.whitelist()
def generate_multiple_contribution_invoices(invoice_date=None, due_date=None, amount=None, contribution_type=None, remarks=None):
    """
    Generate contribution invoices for all active members
    
    Args:
        invoice_date (str): Date for the invoice
        due_date (str): Due date for the invoice
        amount (float): Amount to invoice
        contribution_type (str): Contribution type
        remarks (str): Description for the invoices
    
    Returns:
        dict: Summary of created invoices
    """
    if not invoice_date:
        invoice_date = nowdate()
        
    # If due_date is not provided, calculate it as 30 days from invoice_date
    if not due_date:
        due_date = add_days(getdate(invoice_date), 30)
        
    # Get all active members
    active_members = frappe.get_all("SHG Member", 
                                   filters={"membership_status": "Active"}, 
                                   fields=["name", "member_name", "email"])
    
    created_count = 0
    skipped_count = 0
    error_count = 0
    errors = []
    
    for member in active_members:
        try:
            # Check if an invoice already exists for this member and period
            existing_invoice = frappe.db.exists("SHG Contribution Invoice", {
                "member": member.name,
                "invoice_date": invoice_date,
                "docstatus": ["!=", 2]  # Not cancelled
            })
            
            if existing_invoice:
                skipped_count += 1
                continue
            
            # Create contribution invoice
            invoice = frappe.get_doc({
                "doctype": "SHG Contribution Invoice",
                "member": member.name,
                "member_name": member.member_name,
                "invoice_date": invoice_date,
                "due_date": due_date,
                "amount": amount,
                "contribution_type": contribution_type,
                "status": "Unpaid",
                "description": remarks or f"Contribution invoice for {formatdate(invoice_date, 'MMMM yyyy')}"
            })
            
            invoice.insert()
            invoice.submit()
            created_count += 1
            
        except Exception as e:
            error_count += 1
            errors.append(f"Failed to create invoice for {member.member_name}: {str(e)}")
            frappe.log_error(frappe.get_traceback(), f"SHG Contribution Invoice Creation Failed for {member.name}")
    
    # Prepare summary
    summary = {
        "created": created_count,
        "skipped": skipped_count,
        "errors": error_count,
        "total_processed": len(active_members),
        "error_details": errors
    }
    
    # Create a log message
    message = f"Generated {created_count} contribution invoices. "
    if skipped_count > 0:
        message += f"Skipped {skipped_count} members (invoices already exist). "
    if error_count > 0:
        message += f"Encountered {error_count} errors."
    
    frappe.msgprint(_(message))
    
    return summary

# --- Hook functions ---
def validate_contribution_invoice(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()