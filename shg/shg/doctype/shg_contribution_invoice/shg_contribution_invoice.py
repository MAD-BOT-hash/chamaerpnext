# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, formatdate, today, nowdate

class SHGContributionInvoice(Document):
    def validate(self):
        self.validate_amount()
        self.set_description()
        
        # Ensure amount is rounded to 2 decimal places
        if self.amount:
            self.amount = round(float(self.amount), 2)
        
        # Ensure due_date is not before invoice_date
        if self.due_date and self.invoice_date:
            invoice_date = getdate(self.invoice_date)
            due_date = getdate(self.due_date)
            
            if due_date < invoice_date:
                frappe.throw(_("Due Date cannot be before Invoice Date"))
        
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
        # Set status to Unpaid when submitted
        elif not self.status or self.status == "Draft":
            self.db_set("status", "Unpaid")
        
        # Create SHG Contribution record
        create_contribution_from_invoice(self, None)

@frappe.whitelist()
def create_contribution_from_invoice(doc, method=None):
    """
    Automatically create SHG Contribution when a Contribution Invoice is submitted
    """
    try:
        # Prevent duplicates
        existing = frappe.db.exists("SHG Contribution", {"invoice_reference": doc.name})
        if existing:
            frappe.logger().info(f"SHG Contribution already exists for Invoice {doc.name}")
            return

        # Attempt to find related Payment Entry (if exists)
        payment_entry = frappe.db.get_value(
            "Payment Entry Reference",
            {"reference_name": doc.name},
            "parent"
        )
        payment_method = None
        if payment_entry:
            payment_method = frappe.db.get_value("Payment Entry", payment_entry, "mode_of_payment")

        # Create new SHG Contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": doc.member,                 # Link field
            "member_name": doc.member_name,
            "contribution_type": doc.contribution_type,
            "contribution_date": doc.invoice_date or nowdate(),
            "posting_date": doc.invoice_date or nowdate(),
            "amount": float(doc.amount or 0),
            "payment_method": payment_method or "Not Specified",
            "invoice_reference": doc.name,
            "status": "Unpaid"
        })
        
        contribution.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(f"[SHG] Created SHG Contribution {contribution.name} from Invoice {doc.name}")

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title=f"Auto SHG Contribution Creation Failed for {doc.name}")

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
            
            # Use invoice_date as the reference date for validation
            invoice_date = getdate(self.invoice_date or today())
            due_date = getdate(self.due_date or invoice_date)
            
            # Ensure due_date is not earlier than invoice_date
            if due_date < invoice_date:
                due_date = invoice_date
            
            # Create Sales Invoice
            sales_invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": member.customer,
                "posting_date": invoice_date,
                "due_date": due_date,
                "supplier_invoice_date": invoice_date,  # Set supplier invoice date to match
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
            # Set status to Unpaid when Sales Invoice is created
            self.db_set("status", "Unpaid")
            
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
    def update_status_based_on_sales_invoice(self):
        """Update status based on linked Sales Invoice outstanding amount"""
        if self.sales_invoice:
            sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
            
            # Update status based on outstanding amount
            if sales_invoice.outstanding_amount <= 0:
                self.db_set("status", "Paid")
            elif sales_invoice.outstanding_amount < sales_invoice.grand_total:
                self.db_set("status", "Partially Paid")
            else:
                self.db_set("status", "Unpaid")
            
            # Also update the linked SHG Contribution
            contribution_name = frappe.db.get_value("SHG Contribution", 
                                                  {"invoice_reference": self.name})
            if contribution_name:
                contribution = frappe.get_doc("SHG Contribution", contribution_name)
                # Update contribution status to match invoice status
                contribution.db_set("status", self.status)