import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, getdate, formatdate, add_days, today
from frappe.utils import flt

class SHGContribution(Document):
    def validate(self):
        self.validate_amount()
        self.validate_duplicate()
        self.set_contribution_details()
        self.calculate_unpaid_amount()
        
        # Ensure amount is rounded to 2 decimal places using flt for safety
        if self.amount:
            self.amount = round(flt(self.amount), 2)
        if self.expected_amount:
            self.expected_amount = round(flt(self.expected_amount), 2)
        if self.amount_paid:
            self.amount_paid = round(flt(self.amount_paid), 2)
        if self.unpaid_amount:
            self.unpaid_amount = round(flt(self.unpaid_amount), 2)
        
    def before_validate(self):
        """Ensure company is populated from SHG Settings."""
        from shg.shg.utils.company_utils import get_default_company
        if not getattr(self, "company", None):
            default_company = get_default_company()
            if default_company:
                self.company = default_company
            else:
                frappe.throw("Please set Default Company in SHG Settings before continuing.")

    def validate_amount(self):
        """Validate contribution amount"""
        # Safely convert to float to prevent NoneType errors
        amount = flt(self.amount)
        if amount <= 0:
            frappe.throw(_("Contribution amount must be greater than zero"))
            
    def validate_duplicate(self):
        """Check for duplicate contributions on same date"""
        existing = frappe.db.exists("SHG Contribution", {
            "member": self.member,
            "contribution_date": self.contribution_date,
            "docstatus": 1,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(_("A contribution already exists for this member on this date"))
            
    def set_contribution_details(self):
        """Set contribution details from contribution type"""
        if self.contribution_type_link:
            contrib_type = frappe.get_doc("SHG Contribution Type", self.contribution_type_link)
            if not self.expected_amount and contrib_type.default_amount:
                self.expected_amount = contrib_type.default_amount
        elif self.contribution_type:
            # Get from settings
            settings = frappe.get_doc("SHG Settings")
            if not self.expected_amount:
                if self.contribution_type == "Regular Weekly":
                    self.expected_amount = settings.default_contribution_amount
                elif self.contribution_type == "Regular Monthly":
                    self.expected_amount = settings.default_contribution_amount * 4  # Approximate
                elif self.contribution_type == "Bi-Monthly":
                    self.expected_amount = settings.default_contribution_amount * 8  # Approximate
                    
        # If expected_amount is set but amount_paid is not, initialize amount_paid to 0
        if self.expected_amount and not self.amount_paid:
            self.amount_paid = 0
            
    def calculate_unpaid_amount(self):
        """Calculate unpaid amount and set status"""
        # Safely handle None values with flt()
        expected = flt(self.expected_amount)
        amount = flt(self.amount)
        paid = flt(self.amount_paid)
        
        # If expected_amount is not set, use the amount field as expected_amount
        if expected <= 0:
            expected = amount
            self.expected_amount = expected
            
        # If amount_paid is not set, initialize it to 0
        if paid <= 0:
            paid = 0
            self.amount_paid = paid
            
        # Calculate unpaid amount safely
        unpaid = flt(max(0, expected - paid))
        self.unpaid_amount = unpaid
        
        # Set status based on unpaid amount
        if unpaid <= 0:
            self.status = "Paid"
        elif paid > 0:
            self.status = "Partially Paid"
        else:
            self.status = "Unpaid"
            
    def update_payment_status(self, paid_amount):
        """Update payment status when a payment is received"""
        try:
            # Safely handle numeric fields
            current_paid = flt(self.amount_paid or 0)
            new_paid = flt(current_paid + flt(paid_amount))
            self.db_set("amount_paid", new_paid)
            
            # Recalculate unpaid amount and status
            expected = flt(self.expected_amount or self.amount)
            unpaid = flt(max(0, flt(expected) - flt(new_paid)))
            self.db_set("unpaid_amount", unpaid)
            
            # Update status
            if unpaid <= 0:
                self.db_set("status", "Paid")
            elif new_paid > 0:
                self.db_set("status", "Partially Paid")
            else:
                self.db_set("status", "Unpaid")
                
            # Update the linked SHG Contribution Invoice if exists
            if self.invoice_reference:
                invoice = frappe.get_doc("SHG Contribution Invoice", self.invoice_reference)
                if invoice:
                    # Update invoice status based on contribution status
                    invoice.db_set("status", self.status)
                    
            # Update member financial summary
            member = frappe.get_doc("SHG Member", self.member)
            member.update_financial_summary()
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Update Payment Status Failed for Member {self.member} with Amount {paid_amount}")
            frappe.throw(_("Failed to update payment status: {0}").format(str(e)))
            
    def on_submit(self):
        # ensure idempotent: if already posted -> skip
        if not self.get("posted_to_gl"):
            self.post_to_ledger()
        self.update_member_summary()
        
    def on_cancel(self):
        self.cancel_journal_entry()
        self.update_member_summary()
        
    def validate_gl_entries(self):
        """Validate that GL entries were created properly"""
        if not self.journal_entry and not self.payment_entry:
            frappe.throw(_("Failed to create Journal Entry or Payment Entry for this contribution. Please check the system logs."))
            
        # Use validation utilities
        from shg.shg.utils.validation_utils import validate_reference_types_and_names, validate_custom_field_linking, validate_accounting_integrity
        validate_reference_types_and_names(self)
        validate_custom_field_linking(self)
        validate_accounting_integrity(self)
        
    def post_to_ledger(self):
        """Post this contribution to GL using correct member ledger accounts."""
        # Add company source fallback
        if not self.company:
            settings_company = frappe.db.get_single_value("SHG Settings", "default_company")
            if not settings_company:
                frappe.throw("Default Company is missing in SHG Settings.")
            self.company = settings_company

        # Get the contribution posting method from settings
        settings = frappe.get_single("SHG Settings")
        posting_method = settings.contribution_posting_method or "Journal Entry"
        
        if posting_method == "Payment Entry":
            # Create a Payment Entry for this contribution
            from shg.shg.utils.gl_utils import create_contribution_payment_entry, update_document_with_payment_entry
            payment_entry = create_contribution_payment_entry(self)
            update_document_with_payment_entry(self, payment_entry)
        else:
            # Create a Journal Entry for this contribution (default)
            from shg.shg.utils.gl_utils import create_contribution_journal_entry, update_document_with_journal_entry
            
            # Use the new account helper
            from shg.shg.utils.account_utils import get_account
            member_account = get_account(self.company, "contributions", self.member)
            
            # Get customer for the member
            customer = frappe.db.get_value("SHG Member", self.member, "customer")
            
            # Create journal entry with proper accounts
            je = frappe.new_doc("Journal Entry")
            je.voucher_type = "Journal Entry"
            je.company = self.company
            je.posting_date = self.contribution_date or today()
            je.remark = f"Contribution from {self.member}"

            # Debit: member receivable
            je.append("accounts", {
                "account": member_account,
                "party_type": "Customer",
                "party": customer,
                "debit_in_account_currency": self.amount,
                "credit_in_account_currency": 0,
                "company": self.company
            })

            # Credit: contributions income account
            income_account = get_account(self.company, "contributions")
            je.append("accounts", {
                "account": income_account,
                "debit_in_account_currency": 0,
                "credit_in_account_currency": self.amount,
                "company": self.company
            })

            je.insert(ignore_permissions=True)
            je.submit()
            
            update_document_with_journal_entry(self, je)

    def cancel_journal_entry(self):
        """Cancel the associated journal entry or payment entry"""
        if self.journal_entry:
            je = frappe.get_doc("Journal Entry", self.journal_entry)
            if je.docstatus == 1:
                je.cancel()
        elif self.payment_entry:
            pe = frappe.get_doc("Payment Entry", self.payment_entry)
            if pe.docstatus == 1:
                pe.cancel()
                
    def get_member_account(self):
        """Get member's ledger account, create if not exists"""
        member = frappe.get_doc("SHG Member", self.member)
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
            else:
                frappe.throw(_("Please create a company first"))
                
        from shg.shg.utils.account_utils import get_or_create_member_account
        return get_or_create_member_account(member, company)
        
    def get_member_customer(self):
        """Get member's customer link"""
        member = frappe.get_doc("SHG Member", self.member)
        return member.customer
        
    def update_member_summary(self):
        """Update member's financial summary"""
        member = frappe.get_doc("SHG Member", self.member)
        member.update_financial_summary()
        
    @frappe.whitelist()
    def get_suggested_amount(self):
        """Get suggested contribution amount based on type and member"""
        if self.contribution_type_link:
            contrib_type = frappe.get_doc("SHG Contribution Type", self.contribution_type_link)
            return contrib_type.default_amount
        elif self.contribution_type:
            # Get from settings
            settings = frappe.get_doc("SHG Settings")
            if self.contribution_type == "Regular Weekly":
                return settings.default_contribution_amount
            elif self.contribution_type == "Regular Monthly":
                return settings.default_contribution_amount * 4  # Approximate
            elif self.contribution_type == "Bi-Monthly":
                return settings.default_contribution_amount * 8  # Approximate
        return 0
        
    @frappe.whitelist()
    def send_payment_confirmation(self):
        """Send payment confirmation SMS"""
        member = frappe.get_doc("SHG Member", self.member)
        
        message = f"Dear {member.member_name}, your contribution of KES {self.amount:,.2f} has been received. Thank you for your continued support."
        
        # Log notification
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log",
            "member": self.member,
            "notification_type": "Payment Confirmation",
            "message": message,
            "channel": "SMS",
            "reference_document": "SHG Contribution",
            "reference_name": self.name
        })
        notification.insert()
        
        # In a real implementation, you would send the actual SMS
        # send_sms(member.phone_number, message)
        return True
        
    @frappe.whitelist()
    def initiate_mpesa_stk_push(self):
        """Initiate Mpesa STK Push for contribution payment"""
        try:
            # Check if Mpesa is enabled
            settings = frappe.get_doc("SHG Settings")
            if not settings.mpesa_enabled:
                return {"success": False, "error": "Mpesa payments are not enabled"}
                
            member = frappe.get_doc("SHG Member", self.member)
            
            # In a real implementation, you would integrate with Mpesa API
            # This is a placeholder for the actual implementation
            # mpesa_response = make_mpesa_stk_push_request(
            #     phone_number=member.phone_number,
            #     amount=self.amount,
            #     account_reference=self.name,
            #     transaction_desc=f"SHG Contribution - {self.member_name}"
            # )
            
            # For now, return a success response
            return {"success": True, "message": "Mpesa STK Push initiated successfully"}
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Contribution - Mpesa STK Push Failed")
            return {"success": False, "error": str(e)}

@frappe.whitelist()
def generate_contribution_invoices(invoice_date, amount, contribution_type=None, remarks=None, send_email=0, supplier_invoice_date=None):
    active_members = frappe.get_all("SHG Member", filters={"membership_status": "Active"}, fields=["name", "member_name", "email"])
    created = 0

    for m in active_members:
        # Use supplier_invoice_date logic for due date
        # Use supplier_invoice_date as both posting_date and due_date to prevent ERPNext validation errors
        # Fallback to invoice_date, then to today's date if missing
        supplier_inv_date = None
        if supplier_invoice_date:
            supplier_inv_date = getdate(supplier_invoice_date)
        elif invoice_date:
            supplier_inv_date = getdate(invoice_date)
        else:
            supplier_inv_date = getdate(today())
        
        due_date = supplier_inv_date
        
        inv = frappe.get_doc({
            "doctype": "SHG Contribution Invoice",
            "member": m.name,
            "member_name": m.member_name,
            "invoice_date": supplier_inv_date,
            "due_date": due_date,
            "supplier_invoice_date": supplier_invoice_date or supplier_inv_date,  # Store the supplier invoice date
            "amount": amount,
            "contribution_type": contribution_type,
            "status": "Unpaid",
            "description": remarks or f"Contribution invoice for {formatdate(supplier_inv_date, 'MMMM yyyy')}"
        })
        inv.insert(ignore_permissions=True)
        inv.submit()
        created += 1

    frappe.msgprint(_("{0} contribution invoices created successfully.").format(created))
    return created

@frappe.whitelist()
def send_contribution_invoice_emails(invoice_date):
    """Send emails for all contribution invoices created on the given date"""
    # Get all contribution invoices created on the given date
    invoices = frappe.get_all("SHG Contribution Invoice", 
                             filters={
                                 "invoice_date": invoice_date,
                                 "status": "Unpaid",
                                 "docstatus": 1
                             },
                             fields=["name"])
    
    sent = 0
    for invoice in invoices:
        try:
            inv_doc = frappe.get_doc("SHG Contribution Invoice", invoice.name)
            inv_doc.send_invoice_email()
            sent += 1
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to send email for invoice {invoice.name}")
    
    frappe.msgprint(_("{0} invoice emails sent successfully.").format(sent))
    return sent

# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_contribution(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger()

def update_overdue_contributions():
    """Scheduled job to update overdue contributions"""
    # Get all unpaid contributions where due date has passed
    overdue_contributions = frappe.db.sql("""
        SELECT name
        FROM `tabSHG Contribution`
        WHERE docstatus = 1 
        AND status = 'Unpaid'
        AND contribution_date < %s
    """, getdate(), as_dict=True)
    
    updated_count = 0
    for contrib in overdue_contributions:
        try:
            contribution = frappe.get_doc("SHG Contribution", contrib.name)
            # Send reminder email
            send_contribution_reminder(contribution)
            updated_count += 1
        except Exception as e:
            frappe.log_error(f"Failed to process overdue contribution {contrib.name}: {str(e)}")
    
    frappe.msgprint(f"Processed {updated_count} overdue contributions")

def send_contribution_reminder(contribution):
    """Send email reminder for unpaid contribution"""
    try:
        member = frappe.get_doc("SHG Member", contribution.member)
        if member.email:
            # Create email content
            subject = "Unpaid Contribution Reminder"
            message = f"""
            <p>Dear {member.member_name},</p>
            <p>This is a reminder that you have an unpaid contribution of KES {contribution.unpaid_amount:,.2f} 
            due on {formatdate(contribution.contribution_date)}.</p>
            <p>Please make the payment at your earliest convenience.</p>
            <p>Thank you for your continued support.</p>
            """
            
            # Send email
            frappe.sendmail(
                recipients=[member.email],
                subject=subject,
                message=message
            )
            
            frappe.msgprint(f"Reminder email sent to {member.member_name}")
    except Exception as e:
        frappe.log_error(f"Failed to send reminder for contribution {contribution.name}: {str(e)}")

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
        
        # Safely handle numeric fields
        amount = flt(doc.amount or 0)
        expected_amount = flt(doc.amount or 0)
        
        # Validate amount
        if amount <= 0:
            # Try to get default amount from contribution type
            if doc.contribution_type:
                default_amount = frappe.db.get_value("SHG Contribution Type", doc.contribution_type, "default_amount")
                amount = flt(default_amount or 0)
                expected_amount = flt(default_amount or 0)
            
            # If still no valid amount, try SHG Settings
            if amount <= 0:
                default_amount = frappe.db.get_single_value("SHG Settings", "default_contribution_amount")
                amount = flt(default_amount or 0)
                expected_amount = flt(default_amount or 0)
                
            # If still no valid amount, throw error
            if amount <= 0:
                frappe.throw(_("Contribution amount must be greater than zero. No valid amount found in invoice, contribution type, or SHG Settings."))

        # Create new SHG Contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": doc.member,                 # Link field
            "member_name": doc.member_name,
            "contribution_type": doc.contribution_type,
            "contribution_date": doc.invoice_date or nowdate(),
            "posting_date": doc.invoice_date or nowdate(),
            "amount": amount,
            "expected_amount": expected_amount,
            "payment_method": payment_method or default_payment_method,
            "invoice_reference": doc.name,
            "status": "Unpaid"
        })
        
        # Use flags before insert instead of passing parameters
        contribution.flags.ignore_permissions = True
        contribution.insert()
        frappe.db.commit()

        frappe.logger().info(f"[SHG] Created SHG Contribution {contribution.name} from Invoice {doc.name}")
        return contribution

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title=f"Auto SHG Contribution Creation Failed for Member {doc.member} with Invoice {doc.name}")
        return None

def create_linked_contribution(invoice_doc):
    """
    Create a draft SHG Contribution linked to the invoice
    """
    try:
        # Get default payment method from settings or default to Mpesa
        default_payment_method = frappe.db.get_single_value("SHG Settings", "default_contribution_payment_method") or "Mpesa"
        
        # Safely handle numeric fields
        amount = flt(invoice_doc.amount or 0)
        expected_amount = flt(invoice_doc.amount or 0)
        
        # Validate amount
        if amount <= 0:
            # Try to get default amount from contribution type
            if invoice_doc.contribution_type:
                default_amount = frappe.db.get_value("SHG Contribution Type", invoice_doc.contribution_type, "default_amount")
                amount = flt(default_amount or 0)
                expected_amount = flt(default_amount or 0)
            
            # If still no valid amount, try SHG Settings
            if amount <= 0:
                default_amount = frappe.db.get_single_value("SHG Settings", "default_contribution_amount")
                amount = flt(default_amount or 0)
                expected_amount = flt(default_amount or 0)
                
            # If still no valid amount, throw error
            if amount <= 0:
                frappe.throw(_("Contribution amount must be greater than zero. No valid amount found in invoice, contribution type, or SHG Settings."))

        # Create new SHG Contribution in draft status
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": invoice_doc.member,
            "member_name": invoice_doc.member_name,
            "contribution_type": invoice_doc.contribution_type,
            "contribution_date": invoice_doc.invoice_date or nowdate(),
            "posting_date": invoice_doc.invoice_date or nowdate(),
            "amount": amount,
            "expected_amount": expected_amount,
            "payment_method": default_payment_method,
            "invoice_reference": invoice_doc.name,
            "status": "Unpaid",
            "docstatus": 0  # Draft status
        })
        
        # Use flags before insert instead of passing parameters
        contribution.flags.ignore_permissions = True
        contribution.insert()
        frappe.logger().info(f"[SHG] Created draft SHG Contribution {contribution.name} for Invoice {invoice_doc.name}")
        
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title=f"Draft SHG Contribution Creation Failed for Member {invoice_doc.member} with Invoice {invoice_doc.name}")

def get_or_create_member_account(self, member_id, company):
    """
    Ensure each SHG Member has a personal ledger account under 'SHG Members - [Company Abbr]'.
    Auto-creates the parent and child accounts if missing.
    """

    # --- Get company abbreviation ---
    company_abbr = frappe.db.get_value("Company", company, "abbr")
    if not company_abbr:
        frappe.throw(f"Company abbreviation not found for {company}")

    # --- Get the Accounts Receivable parent ---
    accounts_receivable = frappe.db.get_value(
        "Account",
        {"account_type": "Receivable", "is_group": 1, "company": company},
        "name"
    )
    if not accounts_receivable:
        frappe.throw(f"No 'Accounts Receivable' group account found for {company}.")

    # --- Ensure SHG Members parent account exists ---
    parent_account_name = f"SHG Members - {company_abbr}"
    parent_account = frappe.db.get_value(
        "Account",
        {"account_name": parent_account_name, "company": company},
        "name"
    )

    if not parent_account:
        # Create parent group account automatically
        parent_doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": parent_account_name,
            "company": company,
            "parent_account": accounts_receivable,
            "is_group": 1,
            "account_type": "Receivable",
            "report_type": "Balance Sheet",
            "root_type": "Asset"
        })
        parent_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        parent_account = parent_doc.name
        frappe.msgprint(f"✅ Created parent account '{parent_account_name}' under Accounts Receivable.")

    # --- Check if the member already has an account ---
    member_account_name = f"{member_id} - {company_abbr}"
    member_account = frappe.db.exists("Account", {"account_name": member_account_name, "company": company})

    # --- Create child account if not exists ---
    if not member_account:
        member_doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": member_account_name,
            "company": company,
            "parent_account": parent_account,
            "is_group": 0,
            "account_type": "Receivable",
            "report_type": "Balance Sheet",
            "root_type": "Asset"
        })
        member_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        member_account = member_doc.name
        frappe.msgprint(f"✅ Created member account '{member_account_name}' under '{parent_account_name}'.")

    return member_account
