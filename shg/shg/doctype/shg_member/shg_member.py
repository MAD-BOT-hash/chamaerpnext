# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, getdate
import json

class SHGMember(Document):
    def validate(self):
        """Validate member data"""
        self.validate_id_number()
        self.validate_phone_number()
        self.set_account_number()
        
    def validate_id_number(self):
        """Validate ID number format"""
        if self.id_number:
            # Check if another member has the same ID number
            existing = frappe.db.exists("SHG Member", {
                "id_number": self.id_number,
                "name": ["!=", self.name]
            })
            if existing:
                frappe.throw(_("Another member already exists with ID number {0}").format(self.id_number))
                
    def validate_phone_number(self):
        """Validate phone number format"""
        if self.phone_number:
            # Basic validation - should be 10 digits starting with 07
            if not (self.phone_number.startswith("07") and len(self.phone_number) == 10 and self.phone_number.isdigit()):
                frappe.throw(_("Phone number must be 10 digits starting with 07"))
                
    def set_account_number(self):
        """Set account number if not already set"""
        if not self.account_number:
            # Get the last account number
            last_member = frappe.db.sql("""
                SELECT account_number 
                FROM `tabSHG Member` 
                WHERE account_number IS NOT NULL 
                ORDER BY account_number DESC 
                LIMIT 1
            """, as_dict=True)
            
            if last_member:
                # Extract the number part and increment
                last_number = int(last_member[0].account_number.replace("MN", ""))
                new_number = last_number + 1
            else:
                new_number = 1
                
            self.account_number = f"MN{new_number:03d}"
            
    def after_insert(self):
        """Create linked customer and ledger account after insert"""
        self.create_linked_customer()
        self.create_member_ledger_account()
        
    def create_linked_customer(self):
        """Create linked customer for the member"""
        if not self.customer:
            # Create customer
            customer = frappe.new_doc("Customer")
            customer.customer_name = self.member_name
            customer.customer_type = "Individual"
            customer.customer_group = "SHG Members"
            customer.territory = "Kenya"
            
            # Set phone number if available
            if self.phone_number:
                customer.mobile_no = self.phone_number
            
            # Save customer
            customer.insert()
            
            # Link customer to member (avoid recursion by using db_set)
            self.db_set("customer", customer.name, update_modified=False)
            
    def create_member_ledger_account(self):
        """Create member's ledger account"""
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
            else:
                frappe.throw(_("Please create a company first"))
                
        # Ensure account number is set
        if not self.account_number:
            self.set_account_number()
            # Only save if this is a new document (not yet inserted)
            if not self.get_doc_before_save():
                self.db_set("account_number", self.account_number, update_modified=False)
                
        # Create member's receivable account using account number
        from shg.shg.utils.account_utils import get_or_create_member_account
        get_or_create_member_account(self, company)
                
    @frappe.whitelist()
    def update_financial_summary(self):
        """Update member's financial summary"""
        # Update total contributions
        total_contributions = frappe.db.sql("""
            SELECT SUM(amount) 
            FROM `tabSHG Contribution` 
            WHERE member = %s AND docstatus = 1
        """, self.name)[0][0] or 0
        
        # Update total unpaid contributions
        total_unpaid_contributions = frappe.db.sql("""
            SELECT SUM(unpaid_amount) 
            FROM `tabSHG Contribution` 
            WHERE member = %s AND docstatus = 1 AND status IN ('Unpaid', 'Partially Paid')
        """, self.name)[0][0] or 0
        
        # Update loan information
        total_loans = frappe.db.sql("""
            SELECT SUM(loan_amount) 
            FROM `tabSHG Loan` 
            WHERE member = %s AND status IN ('Disbursed', 'Closed')
        """, self.name)[0][0] or 0
        
        # Update loan balance
        loan_balance = frappe.db.sql("""
            SELECT SUM(balance_amount) 
            FROM `tabSHG Loan` 
            WHERE member = %s AND status = 'Disbursed'
        """, self.name)[0][0] or 0
        
        # Update total unpaid loans (overdue amounts)
        total_unpaid_loans = frappe.db.sql("""
            SELECT SUM(balance_amount) 
            FROM `tabSHG Loan` 
            WHERE member = %s AND status = 'Disbursed' AND next_due_date < %s
        """, (self.name, today()))[0][0] or 0
        
        # Update last contribution date
        last_contribution = frappe.db.sql("""
            SELECT MAX(contribution_date) 
            FROM `tabSHG Contribution` 
            WHERE member = %s AND docstatus = 1
        """, self.name)[0][0]
        
        # Update last loan date
        last_loan = frappe.db.sql("""
            SELECT MAX(disbursement_date) 
            FROM `tabSHG Loan` 
            WHERE member = %s AND status = 'Disbursed'
        """, self.name)[0][0]
        
        # Update total payments received
        total_payments = frappe.db.sql("""
            SELECT SUM(total_amount) 
            FROM `tabSHG Payment Entry` 
            WHERE member = %s AND docstatus = 1
        """, self.name)[0][0] or 0
        
        # Calculate credit score (simplified) only if it hasn't been manually set
        if not hasattr(self, '_credit_score_manually_updated') or not self._credit_score_manually_updated:
            credit_score = 50  # Base score
            
            # Add points for contributions
            if total_contributions > 0:
                credit_score += min(20, total_contributions / 1000)  # Up to 20 points
                
            # Add points for timely repayments (if any loans)
            if total_loans > 0:
                # Get repayment history
                timely_repayments = frappe.db.sql("""
                    SELECT COUNT(*) 
                    FROM `tabSHG Loan Repayment` 
                    WHERE member = %s AND docstatus = 1 AND repayment_date <= due_date
                """, self.name)[0][0] or 0
                
                total_repayments = frappe.db.sql("""
                    SELECT COUNT(*) 
                    FROM `tabSHG Loan Repayment` 
                    WHERE member = %s AND docstatus = 1
                """, self.name)[0][0] or 0
                
                if total_repayments > 0:
                    repayment_rate = timely_repayments / total_repayments
                    credit_score += min(30, repayment_rate * 30)  # Up to 30 points
            
            self.credit_score = int(credit_score)
        # If credit score was manually updated, keep the manually set value
        
        # Update document using db_set to avoid recursion
        self.db_set({
            "total_contributions": total_contributions,
            "total_unpaid_contributions": total_unpaid_contributions,
            "total_loans_taken": total_loans,
            "current_loan_balance": loan_balance,
            "total_unpaid_loans": total_unpaid_loans,
            "last_contribution_date": last_contribution,
            "last_loan_date": last_loan,
            "credit_score": self.credit_score,
            "total_payments_received": total_payments
        }, update_modified=False)
        
    @frappe.whitelist()
    def update_member_statement(self):
        """Update member statement"""
        from shg.shg.utils.member_statement_utils import populate_member_statement
        populate_member_statement(self.name)
        
    def handle_member_id_change(self, old_id, new_id):
        """Update member ID in all linked doctypes"""
        linked_doctypes = [
            ("SHG Loan", "member"),
            ("SHG Contribution", "member"),
            ("SHG Loan Repayment", "member"),
            ("SHG Meeting Fine", "member")
        ]
        
        updated_count = 0
        for doctype, field in linked_doctypes:
            # Count records that will be updated
            count = frappe.db.count(doctype, {field: old_id})
            if count > 0:
                # Update the records
                frappe.db.sql(f"""
                    UPDATE `tab{doctype}` 
                    SET {field} = %s 
                    WHERE {field} = %s
                """, (new_id, old_id))
                updated_count += count
                
        frappe.db.commit()
        if updated_count > 0:
            frappe.msgprint(f"Updated Member ID in {updated_count} linked records from {old_id} to {new_id}")
        
    def handle_member_amendment(self):
        """Handle member amendment"""
        # Re-validate the member data when the document is amended
        self.validate_id_number()
        self.validate_phone_number()
        # Update financial summary
        self.update_financial_summary()

    def on_update_after_submit(self):
        """Handle updates to member information after submission"""
        # Re-validate the member data when fields are updated after submission
        self.validate_id_number()
        self.validate_phone_number()
        
        # Check if member_id has changed
        if self.has_value_changed("member_id"):
            old_id = self.get_doc_before_save().member_id
            new_id = self.member_id
            self.handle_member_id_change(old_id, new_id)
            
        # Update financial summary
        self.update_financial_summary()
        
        # Update linked doctypes with member info
        try:
            # Update linked Loans
            frappe.db.sql("""
                UPDATE `tabSHG Loan`
                SET member_name = %s, phone_number = %s
                WHERE member = %s
            """, (self.member_name, self.phone_number, self.name))

            # Update linked Contributions
            frappe.db.sql("""
                UPDATE `tabSHG Contribution`
                SET member_name = %s, phone_number = %s
                WHERE member = %s
            """, (self.member_name, self.phone_number, self.name))

            # Update linked Loan Repayments
            frappe.db.sql("""
                UPDATE `tabSHG Loan Repayment`
                SET member_name = %s
                WHERE member = %s
            """, (self.member_name, self.name))

            # Update linked Meeting Fines
            frappe.db.sql("""
                UPDATE `tabSHG Meeting Fine`
                SET member_name = %s
                WHERE member = %s
            """, (self.member_name, self.name))

            frappe.db.commit()

            frappe.msgprint(f"Linked records updated for Member {self.member_name}")

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "handle_member_update_after_submit failed")
            frappe.throw(f"Failed to update related records: {str(e)}")

# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()

def handle_member_update_after_submit(doc, method=None):
    """
    Triggered when a submitted SHG Member document is edited.
    Updates all linked doctypes (Loans, Contributions, etc.)
    with the new member info.
    """
    doc.handle_member_update_after_submit()