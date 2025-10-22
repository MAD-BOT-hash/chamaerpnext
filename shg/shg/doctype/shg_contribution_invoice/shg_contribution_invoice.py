# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, formatdate, today, nowdate, add_days, flt

class SHGContributionInvoice(Document):
    def validate(self):
        self.validate_qty()
        self.validate_rate()
        self.validate_amount()
        self.set_description()
        self.validate_payment_method()
        
        # Ensure amount is rounded to 2 decimal places
        if self.amount:
            self.amount = round(flt(self.amount), 2)
        
        # Ensure due_date is not before invoice_date
        if self.due_date and self.invoice_date:
            invoice_date = getdate(self.invoice_date)
            due_date = getdate(self.due_date)
            
            if due_date < invoice_date:
                frappe.throw(_("Due Date cannot be before Invoice Date"))
                
    def validate_rate(self):
        """Validate rate field and set default to amount if not provided"""
        # If rate is not set, default it to the amount field
        if not self.rate and self.amount:
            self.rate = self.amount
        elif self.rate:
            # Ensure rate is a valid number
            try:
                rate = flt(self.rate)
                if rate < 0:
                    frappe.throw(_("Rate cannot be negative"))
                self.rate = rate
            except (ValueError, TypeError):
                frappe.throw(_("Invalid rate. Please enter a numeric value."))
                
    def validate_qty(self):
        """Validate quantity field"""
        # If qty is not set, default to 1
        if not self.qty:
            self.qty = 1
        else:
            # Ensure qty is a valid number
            try:
                qty = flt(self.qty)
                if qty <= 0:
                    frappe.throw(_("Quantity must be greater than zero"))
                self.qty = qty
            except (ValueError, TypeError):
                frappe.throw(_("Invalid quantity. Please enter a numeric value."))
                
    def validate_amount(self):
        """Validate contribution invoice amount"""
        # Initialize amount to 0 if None or empty
        amount = 0
        if self.amount:
            try:
                amount = flt(self.amount)
            except (ValueError, TypeError):
                frappe.throw(_("Invalid amount. Please enter a numeric value."))
        else:
            frappe.throw(_("Contribution invoice amount is required"))
        
        if amount <= 0:
            frappe.throw(_("Contribution invoice amount must be greater than zero"))
        
        self.amount = amount
            
    def set_description(self):
        """Set default description if not provided"""
        # Use supplier_invoice_date if available, otherwise fall back to invoice_date
        date_to_use = self.supplier_invoice_date or self.invoice_date
        if not self.description and date_to_use:
            month_year = formatdate(date_to_use, "MMMM yyyy")
            self.description = f"Contribution invoice for {month_year}"
            
    def validate_payment_method(self):
        valid_methods = ["Cash", "Mobile Money", "Mpesa", "Bank Transfer", "Cheque"]
        if not self.payment_method or self.payment_method not in valid_methods:
            default_method = frappe.db.get_single_value("SHG Settings", "default_payment_method") or "Mpesa"
            self.payment_method = default_method
            
    def on_submit(self):
        """Handle submission of SHG Contribution Invoice"""
        # Check if auto-generation of Sales Invoice is enabled
        auto_generate_sales_invoice = frappe.db.get_single_value("SHG Settings", "auto_generate_sales_invoice")
        
        # Create Sales Invoice if enabled and not already created
        if auto_generate_sales_invoice and not self.sales_invoice:
            self.create_sales_invoice()
        # Set status to Unpaid when submitted
        elif not self.status or self.status == "Draft":
            self.db_set("status", "Unpaid")
        
        # Check if auto-creation of SHG Contribution is enabled
        auto_create_contribution = frappe.db.get_single_value("SHG Settings", "auto_create_contribution_on_invoice_submit")
        
        # Create SHG Contribution record if enabled
        if auto_create_contribution:
            contribution = create_contribution_from_invoice(self, None)
            # Link the created contribution to this invoice
            if contribution:
                self.db_set("linked_shg_contribution", contribution.name)

    def create_sales_invoice(self):
        company = frappe.db.get_single_value("SHG Settings", "company") or "Pioneer Friends Group"

        member_account = get_or_create_member_account(self.member, company)
        income_account = frappe.db.get_value(
            "Account", {"account_type": "Income Account", "company": company, "is_group": 0}, "name"
        ) or frappe.throw("No Income Account found for this Company.")

        # Protect from NoneType math
        qty = self.qty or 1
        rate = self.rate or self.amount or 0

        invoice = frappe.new_doc("Sales Invoice")
        invoice.company = company
        invoice.customer = self.member_name
        invoice.posting_date = self.invoice_date or nowdate()
        invoice.due_date = self.invoice_date or nowdate()
        invoice.debit_to = member_account
        invoice.append("items", {
            "item_name": "SHG Contribution",
            "qty": qty,
            "rate": rate,
            "income_account": income_account,
            "description": f"Contribution for {self.member}"
        })

        invoice.flags.ignore_mandatory = True
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        frappe.msgprint(f"Sales Invoice {invoice.name} created and submitted for {self.member_name}")

        return invoice

    def calculate_late_fee(self):
        """Calculate late payment fee based on SHG Settings"""
        # Check if late fee policy is enabled
        apply_late_fee = frappe.db.get_single_value("SHG Settings", "apply_late_fee_policy")
        if not apply_late_fee:
            return 0
            
        # Check if the invoice is overdue
        if self.status != "Overdue":
            return 0
            
        # Get late fee rate from settings
        late_fee_rate = frappe.db.get_single_value("SHG Settings", "late_fee_rate") or 0
        
        # Calculate days overdue
        today_date = getdate(today())
        due_date = getdate(self.due_date)
        
        if today_date <= due_date:
            return 0
            
        days_overdue = (today_date - due_date).days
        
        # Calculate late fee amount safely using flt() to prevent NoneType multiplication
        amount = flt(self.amount or 0)
        rate = flt(late_fee_rate or 0)
        days = flt(days_overdue or 0)
        late_fee_amount = amount * (rate / 100) * days
        
        return late_fee_amount

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

Your contribution invoice for {month_year} amounting to KES {flt(self.amount or 0):,.2f} has been generated.
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
def create_contribution_from_invoice(doc, method=None):
    """
    Automatically create SHG Contribution when a Contribution Invoice is submitted
    """
    try:
        # Prevent duplicates
        existing = frappe.db.exists("SHG Contribution", {"invoice_reference": doc.name})
        if existing:
            frappe.logger().info(f"SHG Contribution already exists for Invoice {doc.name}")
            return frappe.get_doc("SHG Contribution", existing)

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
            "amount": flt(doc.amount or 0),
            "expected_amount": flt(doc.amount or 0),
            "payment_method": payment_method or default_payment_method,
            "invoice_reference": doc.name,
            "status": "Unpaid"
        })
        
        contribution.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(f"[SHG] Created SHG Contribution {contribution.name} from Invoice {doc.name}")
        return contribution

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title=f"Auto SHG Contribution Creation Failed for {doc.name}")
        return None

@frappe.whitelist()
def generate_multiple_contribution_invoices(contribution_type=None, amount=None, invoice_date=None, supplier_invoice_date=None, qty=None, rate=None):
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
            
            # Check if historical backdated invoices are allowed
            allow_historical = frappe.db.get_single_value("SHG Settings", "allow_historical_backdated_invoices") or 0
            
            # Get invoice date - use supplier_invoice_date logic
            # Use supplier_invoice_date as both posting_date and due_date to prevent ERPNext validation errors
            # Fallback to invoice_date, then to today's date if missing
            supplier_inv_date = None
            if supplier_invoice_date:
                supplier_inv_date = getdate(supplier_invoice_date)
            elif invoice_date:
                supplier_inv_date = getdate(invoice_date)
            else:
                supplier_inv_date = getdate(today())
            
            # If historical backdated invoices are not allowed, ensure date is not in the past
            if not allow_historical and supplier_inv_date < getdate(today()):
                supplier_inv_date = getdate(today())
            
            inv_date = supplier_inv_date
            
            # Get default credit period from settings or default to 30 days
            default_credit_period = frappe.db.get_single_value("SHG Settings", "default_credit_period_days") or 30
            due_date = add_days(inv_date, int(default_credit_period))
            
            # For backdated invoices, set due_date same as invoice_date to prevent ERPNext validation errors
            if supplier_invoice_date or (invoice_date and getdate(invoice_date) != getdate(today())):
                due_date = inv_date
            
            # Safely handle numeric fields with flt() to prevent NoneType multiplication
            # Use safe defaults for qty and rate
            safe_qty = flt(qty or 1)
            safe_rate = flt(rate or amount or 0)
            safe_amount = flt(amount or 0)
            
            # If rate is not provided but amount is, calculate rate based on qty
            if not rate and amount:
                if safe_qty > 0:
                    safe_rate = flt(safe_amount / safe_qty)
                else:
                    safe_rate = flt(safe_amount)
                    safe_qty = flt(1)
            
            # Create SHG Contribution Invoice
            invoice = frappe.get_doc({
                "doctype": "SHG Contribution Invoice",
                "member": member.name,
                "member_name": member.member_name,
                "contribution_type": contribution_type,
                "qty": safe_qty,
                "rate": safe_rate,
                "amount": safe_amount,
                "payment_method": default_payment_method,
                "invoice_date": inv_date,
                "due_date": due_date,
                "supplier_invoice_date": supplier_invoice_date or inv_date,  # Store the supplier invoice date
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
        
        # Safely handle numeric fields with flt() to prevent NoneType multiplication
        safe_qty = flt(invoice_doc.qty or 1)
        safe_rate = flt(invoice_doc.rate or invoice_doc.amount or 0)
        safe_amount = flt(invoice_doc.amount or 0)
        
        # Create new SHG Contribution in draft status
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": invoice_doc.member,
            "member_name": invoice_doc.member_name,
            "contribution_type": invoice_doc.contribution_type,
            "contribution_date": invoice_doc.invoice_date or nowdate(),
            "posting_date": invoice_doc.invoice_date or nowdate(),
            "qty": safe_qty,
            "rate": safe_rate,
            "amount": safe_amount,
            "expected_amount": safe_amount,
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
        if flt(invoice.amount) <= 0:
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

@frappe.whitelist()
def mark_overdue_invoices():
    """
    Scheduled function to mark overdue invoices and calculate late fees
    """
    try:
        # Get all unpaid invoices where due date has passed
        overdue_invoices = frappe.get_all("SHG Contribution Invoice",
                                        filters={
                                            "status": "Unpaid",
                                            "due_date": ["<", today()],
                                            "docstatus": 1
                                        },
                                        fields=["name"])
        
        updated_count = 0
        for invoice_data in overdue_invoices:
            try:
                invoice = frappe.get_doc("SHG Contribution Invoice", invoice_data.name)
                # Update status to Overdue
                invoice.db_set("status", "Overdue")
                
                # Calculate and store late fee
                late_fee = invoice.calculate_late_fee()
                if late_fee > 0:
                    invoice.db_set("late_fee_amount", late_fee)
                
                updated_count += 1
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Failed to process overdue invoice {invoice_data.name}")
        
        frappe.msgprint(f"Marked {updated_count} invoices as overdue")
        return updated_count
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Mark Overdue Invoices Failed")
        frappe.throw(str(e))


def get_or_create_member_account(member_id, company):
    """Ensure the member has a personal ledger account under SHG Members."""
    parent_account = frappe.db.get_value(
        "Account",
        {"account_name": "SHG Members - " + company, "company": company, "is_group": 1},
        "name"
    )

    if not parent_account:
        frappe.throw(f"Parent account 'SHG Members - {company}' not found. Please create it under Accounts Receivable.")

    member_account = frappe.db.exists("Account", {"account_name": f"{member_id} - {company}", "company": company})
    if member_account:
        return member_account

    # Auto-create member sub-account
    acc = frappe.get_doc({
        "doctype": "Account",
        "account_name": f"{member_id} - {company}",
        "parent_account": parent_account,
        "is_group": 0,
        "company": company,
        "account_type": "Receivable"
    })
    acc.insert(ignore_permissions=True)
    frappe.msgprint(f"Created ledger account for {member_id}")
    return acc.name
