import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, getdate

class SHGMember(Document):
    def validate(self):
        self.validate_id_number()
        self.validate_phone_number()
        self.set_member_id()
        self.set_account_number()
        # Set default party_type to Customer for GL entries
        if not self.party_type:
            self.party_type = "Customer"
        
    def after_insert(self):
        """Create customer link after member is inserted to avoid recursion"""
        self.create_customer_link()
        
    def validate_id_number(self):
        """Validate Kenyan ID number format"""
        if self.id_number:
            # Remove any spaces or dashes
            id_number = ''.join(filter(str.isdigit, self.id_number))
            
            # Check if it's exactly 8 digits
            if len(id_number) != 8:
                frappe.throw(_("Kenyan ID Number must be exactly 8 digits"))
            
            # Update the field with cleaned ID number
            self.id_number = id_number
            
    def validate_phone_number(self):
        """Validate and format phone number"""
        if self.phone_number:
            # Remove any spaces or dashes
            phone = ''.join(filter(str.isdigit, self.phone_number))
            
            # Format for Kenya
            if phone.startswith('0'):
                self.phone_number = '+254' + phone[1:]
            elif phone.startswith('254'):
                self.phone_number = '+' + phone
            else:
                frappe.throw(_("Please enter a valid Kenyan phone number"))
                
    def set_member_id(self):
        """Set member ID if not already set"""
        if not self.member_id:
            self.member_id = self.name
            
    def set_account_number(self):
        """Generate unique account number in format MN001, MN002, etc."""
        if not self.account_number:
            # Get the last member's account number
            last_member = frappe.db.sql("""
                SELECT account_number 
                FROM `tabSHG Member` 
                WHERE account_number IS NOT NULL 
                ORDER BY creation DESC 
                LIMIT 1
            """, as_dict=True)
            
            if last_member:
                # Extract the number part and increment
                last_number = int(last_member[0].account_number[2:])  # Remove "MN" prefix
                new_number = last_number + 1
            else:
                # First member
                new_number = 1
                
            # Format as MN001, MN002, etc.
            self.account_number = f"MN{new_number:03d}"
            
    def create_customer_link(self):
        """Create a Customer record linked to this SHG Member"""
        # Check if customer already exists for this member
        if not self.customer:
            # Create customer record
            customer = frappe.new_doc("Customer")
            customer.customer_name = self.member_name
            customer.customer_type = "Individual"
            customer.customer_group = "SHG Members"  # You may need to adjust this based on your setup
            customer.territory = "Kenya"  # You may need to adjust this based on your setup
            customer.is_shg_member = 1
            customer.shg_member_id = self.name
            
            # Set contact details
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
                
    def update_financial_summary(self):
        """Update member's financial summary"""
        # Update total contributions
        total_contributions = frappe.db.sql("""
            SELECT SUM(amount) 
            FROM `tabSHG Contribution` 
            WHERE member = %s AND docstatus = 1
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
                    WHERE member = %s AND docstatus = 1 AND payment_date <= due_date
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
            "total_loans_taken": total_loans,
            "current_loan_balance": loan_balance,
            "last_contribution_date": last_contribution,
            "last_loan_date": last_loan,
            "credit_score": self.credit_score
        }, update_modified=False)
        
    def on_update_after_submit(self):
        """Handle updates to member information after submission"""
        # Re-validate the member data when fields are updated after submission
        self.validate_id_number()
        self.validate_phone_number()
        self.validate_next_of_kin()
        # Update financial summary
        self.update_financial_summary()
        
    def validate_next_of_kin(self):
        """Validate next of kin information"""
        if self.next_of_kin_id_number:
            # Remove any spaces or dashes
            id_number = ''.join(filter(str.isdigit, self.next_of_kin_id_number))
            
            # Check if it's exactly 8 digits
            if len(id_number) != 8:
                frappe.throw(_("Next of Kin ID Number must be exactly 8 digits"))
            
            # Update the field with cleaned ID number
            self.next_of_kin_id_number = id_number
            
        if self.next_of_kin_phone:
            # Remove any spaces or dashes
            phone = ''.join(filter(str.isdigit, self.next_of_kin_phone))
            
            # Format for Kenya
            if phone.startswith('0'):
                self.next_of_kin_phone = '+254' + phone[1:]
            elif phone.startswith('254'):
                self.next_of_kin_phone = '+' + phone
            else:
                frappe.throw(_("Please enter a valid Kenyan phone number for Next of Kin"))
        
    def handle_member_amendment(self):
        """Handle member amendment to ensure data consistency"""
        # Re-validate the member data
        self.validate()
        # Update financial summary if needed
        self.update_financial_summary()

# --- Hook functions ---
def validate_member(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def create_member_ledger(doc, method):
    """Hook function called from hooks.py"""
    doc.create_member_ledger_account()

def handle_member_amendment(doc, method):
    """Handle member amendment to ensure data consistency"""
    # Re-validate the member data
    doc.validate()
    # Update financial summary if needed
    doc.update_financial_summary()

def handle_member_update_after_submit(doc, method):
    """Handle member updates after submission"""
    # Directly call the method to avoid recursion through hooks
    doc.validate_id_number()
    doc.validate_phone_number()
    doc.validate_next_of_kin()
    doc.update_financial_summary()