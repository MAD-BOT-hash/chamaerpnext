# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, formatdate, today, nowdate, add_days

class SHGContributionInvoice(Document):
    def validate(self):
        self.validate_amount()
        self.set_description()
        self.validate_payment_method()
        
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
            
    def validate_payment_method(self):
        valid_methods = ["Cash", "Mobile Money", "Mpesa", "Bank Transfer", "Cheque"]
        if not self.payment_method or self.payment_method not in valid_methods:
            default_method = frappe.db.get_single_value("SHG Settings", "default_payment_method") or "Mpesa"
            self.payment_method = default_method
            
    def on_submit(self):
        # Create Sales Invoice
        if not self.sales_invoice:
            self.create_sales_invoice()
        # Set status to Unpaid when submitted
        elif not self.status or self.status == "Draft":
            self.db_set("status", "Unpaid")
        
        # Create SHG Contribution record
        create_contribution_from_invoice(self, None)

    def create_sales_invoice(self):
        """Create a Sales Invoice for this contribution invoice"""
        try:
            # Check if member exists and is active
            member_status = frappe.db.get_value("SHG Member", self.member, "membership_status")
            if not member_status:
                frappe.throw(_(f"Member {self.member} does not exist"))
            if member_status != "Active":
                frappe.throw(_(f"Member {self.member} is not active. Current status: {member_status}"))
                
            member = frappe.get_doc("SHG Member", self.member)
            
            if not member.customer:
                frappe.throw(_("Member {0} does not have a linked Customer record").format(self.member_name))
                
            # Get contribution type details for item
            item_code = "SHG Contribution"
            item_name = self.contribution_type or "SHG Contribution"
            description = self.description or f"Contribution invoice for {formatdate(self.invoice_date, 'MMMM yyyy')}"
            
            if self.contribution_type:
                contrib_type = frappe.get_doc("SHG Contribution Type", self.contribution_type)
                if contrib_type.item_code:
                    item_code = contrib_type.item_code
                    item_name = contrib_type.contribution_type_name
            
            # Use invoice_date as the reference date for validation
            invoice_date = getdate(self.invoice_date or today())
            # Set due date to invoice date plus 1 day
            due_date = add_days(invoice_date, 1)
            
            # Create Sales Invoice
            sales_invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": member.customer,
                "posting_date": invoice_date,
                "due_date": due_date,
                "shg_contribution_invoice": self.name,
                "remarks": f"Auto-generated for SHG Contribution Invoice {self.name}",
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
            
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Contribution Invoice - Sales Invoice Creation Failed")
            frappe.throw(_("Failed to create Sales Invoice: {0}").format(str(e)))

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

        # Get default payment method from settings or default to Mpesa
        default_payment_method = frappe.db.get_single_value("SHG Settings", "default_contribution_payment_method") or "Mpesa"

        # Create new SHG Contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": doc.member,                 # Link field
            "member_name": doc.member_name,
            "contribution_type": doc.contribution_type,
            "contribution_date": doc.invoice_date or nowdate(),
            "posting_date": doc.invoice_date or nowdate(),
            "amount": float(doc.amount or 0),
            "payment_method": payment_method or default_payment_method,
            "invoice_reference": doc.name,
            "status": "Unpaid"
        })
        
        contribution.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(f"[SHG] Created SHG Contribution {contribution.name} from Invoice {doc.name}")

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title=f"Auto SHG Contribution Creation Failed for {doc.name}")

@frappe.whitelist()
def generate_multiple_contribution_invoices(contribution_type=None, amount=None, invoice_date=None):
    """
    Create multiple SHG Contribution Invoices for all active members
    """
    try:
        # Fetch all active members
        active_members = frappe.get_all("SHG Member", filters={"membership_status": "Active"}, fields=["name", "member_name"])
        
        if not active_members:
            frappe.throw("No active members found.")
            
        created_invoices = []
        
        for member in active_members:
            # Get default payment method from settings or default to Mpesa
            default_payment_method = frappe.db.get_single_value("SHG Settings", "default_contribution_payment_method") or "Mpesa"
            
            # Create SHG Contribution Invoice
            invoice = frappe.get_doc({
                "doctype": "SHG Contribution Invoice",
                "member": member.name,
                "member_name": member.member_name,
                "contribution_type": contribution_type,
                "amount": amount,
                "payment_method": default_payment_method,
                "invoice_date": invoice_date or nowdate(),
                "status": "Draft"
            })
            invoice.insert(ignore_permissions=True)
            created_invoices.append({
                "invoice_name": invoice.name,
                "member_name": member.member_name
            })
            
            # Create linked draft SHG Contribution
            create_linked_contribution(invoice)

        frappe.db.commit()
        return {"created_invoices": created_invoices}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Generate Multiple Contribution Invoices Failed")
        frappe.throw(str(e))


def create_linked_contribution(invoice_doc):
    """
    Create a draft SHG Contribution linked to the invoice
    """
    try:
        # Get default payment method from settings or default to Mpesa
        default_payment_method = frappe.db.get_single_value("SHG Settings", "default_contribution_payment_method") or "Mpesa"
        
        # Create new SHG Contribution in draft status
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": invoice_doc.member,
            "member_name": invoice_doc.member_name,
            "contribution_type": invoice_doc.contribution_type,
            "contribution_date": invoice_doc.invoice_date or nowdate(),
            "posting_date": invoice_doc.invoice_date or nowdate(),
            "amount": float(invoice_doc.amount or 0),
            "expected_amount": float(invoice_doc.amount or 0),
            "payment_method": default_payment_method,
            "invoice_reference": invoice_doc.name,
            "status": "Unpaid",
            "docstatus": 0  # Draft status
        })
        
        contribution.insert(ignore_permissions=True)
        frappe.logger().info(f"[SHG] Created draft SHG Contribution {contribution.name} for Invoice {invoice_doc.name}")
        
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title=f"Draft SHG Contribution Creation Failed for Invoice {invoice_doc.name}")
            
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

@frappe.whitelist()
def validate_contribution_invoice(doc, method=None):
    """
    Validate SHG Contribution Invoice before submission.
    Ensures member is active, amount > 0, and required fields are set.
    Can be called as:
    1. A hook function (doc, method) - when used in hooks.py
    2. Directly via API (invoice_name) - when called with invoice_name parameter
    """
    try:
        # Handle both calling conventions
        if isinstance(doc, str):
            # Called directly via API with invoice_name
            invoice_name = doc
            invoice = frappe.get_doc("SHG Contribution Invoice", invoice_name)
        else:
            # Called as hook with document object
            invoice = doc

        # Validate required fields
        required_fields = ["member", "amount", "contribution_type", "invoice_date"]
        for field in required_fields:
            if not invoice.get(field):
                frappe.throw(f"Missing required field: {field}")

        # Validate amount
        if float(invoice.amount) <= 0:
            frappe.throw("Amount must be greater than zero.")

        # Validate member
        member_status = frappe.db.get_value("SHG Member", invoice.member, "membership_status")
        if member_status != "Active":
            frappe.throw(f"Member {invoice.member} is not active. Current status: {member_status}")

        return {"status": "success", "message": "Validation successful"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "validate_contribution_invoice_error")
        frappe.throw(str(e))

@frappe.whitelist()
def auto_submit_contribution_invoices():
    """
    Auto-submit all draft SHG Contribution Invoices
    """
    try:
        # Find all draft invoices
        draft_invoices = frappe.get_all("SHG Contribution Invoice", 
                                      filters={"docstatus": 0, "status": "Draft"},
                                      fields=["name"])
        
        submitted_count = 0
        error_count = 0
        
        for invoice_data in draft_invoices:
            try:
                # Validate the invoice first
                validate_contribution_invoice(invoice_data.name)
                # If validation passes, submit the invoice
                invoice = frappe.get_doc("SHG Contribution Invoice", invoice_data.name)
                invoice.submit()
                submitted_count += 1
                
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), 
                               f"Auto-submit failed for invoice {invoice_data.name}")
                error_count += 1
        
        frappe.db.commit()
        
        return {
            "status": "success",
            "submitted": submitted_count,
            "errors": error_count,
            "message": f"Processed {len(draft_invoices)} draft invoices. Submitted: {submitted_count}, Errors: {error_count}"
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "auto_submit_contribution_invoices_error")
        frappe.throw(str(e))
