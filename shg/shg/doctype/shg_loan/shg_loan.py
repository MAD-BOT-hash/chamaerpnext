import frappe
from frappe.model.document import Document
from frappe.utils import flt, today, add_months, getdate
from frappe.utils.data import date_diff

class SHGLoan(Document):
    def validate(self):
        """Basic sanity checks before submission."""
        if not self.member:
            frappe.throw("Please select a Member for this loan.")

        if not self.loan_amount or self.loan_amount <= 0:
            frappe.throw("Loan Amount must be greater than zero.")

        # Initialize balance if not set
        if not self.balance_amount:
            self.balance_amount = self.loan_amount

        # Auto-set disbursement date if not provided
        if not self.disbursement_date:
            self.disbursement_date = today()

        # Ensure loan status consistency
        if not self.status:
            self.status = "Draft"

    def before_validate(self):
        """Ensure company is populated from SHG Settings."""
        from shg.shg.utils.company_utils import get_default_company
        if not getattr(self, "company", None):
            default_company = get_default_company()
            if default_company:
                self.company = default_company
            else:
                frappe.throw("Please set Default Company in SHG Settings before continuing.")

    def on_submit(self):
        """When the loan is submitted, mark as 'Disbursed' and create member account if needed."""
        self.status = "Disbursed"

        # Generate repayment schedule
        self.generate_repayment_schedule()

        # Create member account under SHG Members - <abbr>
        create_or_verify_member_account(self.member, self.company)

        # Set initial balance
        if not self.balance_amount:
            self.balance_amount = self.loan_amount

        frappe.msgprint(f"Loan {self.name} disbursed successfully.")

    def on_cancel(self):
        """Revert to draft-like state on cancellation."""
        self.status = "Cancelled"
        frappe.msgprint(f"Loan {self.name} cancelled.")

    def update_balance(self, amount_paid):
        """Safe helper for repayment updates."""
        self.flags.ignore_validate_update_after_submit = True

        new_balance = flt(self.balance_amount or 0) - flt(amount_paid or 0)
        if new_balance < 0:
            frappe.throw("Repayment exceeds remaining balance.")

        self.balance_amount = new_balance
        self.last_repayment_date = today()
        self.status = "Paid" if new_balance == 0 else "Partially Paid"
        
        # Update repayment schedule
        self.update_repayment_schedule(amount_paid)

        self.save(ignore_permissions=True)
        frappe.db.commit()

        self.add_comment(
            "Edit",
            f"Repayment of {amount_paid} applied. Remaining balance: {new_balance}"
        )
        
    def update_repayment_schedule(self, amount_paid):
        """Update repayment schedule with payment information."""
        if not self.repayment_schedule:
            return
            
        remaining_amount = flt(amount_paid)
        
        # Update schedule entries in order
        for schedule_entry in self.repayment_schedule:
            if remaining_amount <= 0:
                break
                
            # Calculate how much of the payment applies to this installment
            amount_for_this_installment = min(remaining_amount, schedule_entry.unpaid_balance)
            
            # Update the schedule entry
            schedule_entry.amount_paid = flt(schedule_entry.amount_paid or 0) + amount_for_this_installment
            schedule_entry.unpaid_balance = flt(schedule_entry.total_payment) - flt(schedule_entry.amount_paid)
            
            # Update status based on payment
            if schedule_entry.unpaid_balance <= 0:
                schedule_entry.status = "Paid"
            else:
                schedule_entry.status = "Partially Paid"
                
            remaining_amount -= amount_for_this_installment
            
            # Update next due date to the next pending installment
            if schedule_entry.status == "Paid" and schedule_entry.due_date == self.next_due_date:
                # Find the next pending installment
                next_due = None
                for next_entry in self.repayment_schedule:
                    if next_entry.status == "Pending" or next_entry.status == "Partially Paid":
                        next_due = next_entry.due_date
                        break
                self.next_due_date = next_due

    def generate_repayment_schedule(self):
        """Generate repayment schedule based on loan terms."""
        # Clear existing schedule
        self.repayment_schedule = []
        
        if not self.loan_amount or not self.loan_period_months or not self.repayment_frequency:
            return
            
        # Calculate repayment dates
        start_date = getdate(self.repayment_start_date or self.disbursement_date)
        if not start_date:
            frappe.throw("Repayment start date is required to generate schedule")
            
        # Calculate interest and payments
        if self.interest_type == "Flat Rate":
            self._generate_flat_rate_schedule(start_date)
        else:
            self._generate_reducing_balance_schedule(start_date)
            
        # Set next due date to first installment
        if self.repayment_schedule:
            self.next_due_date = self.repayment_schedule[0].due_date

    def _generate_flat_rate_schedule(self, start_date):
        """Generate repayment schedule for flat rate interest."""
        # Flat rate: interest calculated on original principal for entire loan period
        total_interest = self.loan_amount * (self.interest_rate / 100) * (self.loan_period_months / 12)
        total_payable = self.loan_amount + total_interest
        monthly_payment = total_payable / self.loan_period_months
        monthly_interest = total_interest / self.loan_period_months
        monthly_principal = self.loan_amount / self.loan_period_months
        
        running_balance = self.loan_amount
        
        for i in range(self.loan_period_months):
            # Calculate payment date based on frequency
            if self.repayment_frequency == "Monthly":
                payment_date = add_months(start_date, i)
            elif self.repayment_frequency == "Bi-Monthly":
                payment_date = add_months(start_date, i * 2)
            elif self.repayment_frequency == "Weekly":
                payment_date = add_months(start_date, int(i / 4))
            else:
                payment_date = add_months(start_date, i)  # Default to monthly
                
            # Create schedule entry
            schedule_entry = self.append("repayment_schedule", {
                "installment_no": i + 1,
                "payment_date": payment_date,
                "due_date": payment_date,
                "principal_amount": monthly_principal,
                "interest_amount": monthly_interest,
                "total_payment": monthly_payment,
                "total_due": monthly_payment,
                "amount_paid": 0,
                "unpaid_balance": monthly_payment,
                "balance_amount": running_balance,
                "status": "Pending"
            })
            
            running_balance -= monthly_principal

    def _generate_reducing_balance_schedule(self, start_date):
        """Generate repayment schedule for reducing balance interest."""
        # Reducing balance: interest calculated on outstanding principal
        monthly_rate = (self.interest_rate / 100) / 12
        
        # Calculate monthly payment using annuity formula
        if monthly_rate > 0:
            monthly_payment = self.loan_amount * monthly_rate * ((1 + monthly_rate) ** self.loan_period_months) / (((1 + monthly_rate) ** self.loan_period_months) - 1)
        else:
            monthly_payment = self.loan_amount / self.loan_period_months
            
        running_balance = self.loan_amount
        total_interest = 0
        
        for i in range(self.loan_period_months):
            # Calculate payment date based on frequency
            if self.repayment_frequency == "Monthly":
                payment_date = add_months(start_date, i)
            elif self.repayment_frequency == "Bi-Monthly":
                payment_date = add_months(start_date, i * 2)
            elif self.repayment_frequency == "Weekly":
                payment_date = add_months(start_date, int(i / 4))
            else:
                payment_date = add_months(start_date, i)  # Default to monthly
                
            # Calculate interest for this period
            interest_payment = running_balance * monthly_rate
            principal_payment = monthly_payment - interest_payment
            
            # Ensure we don't overpay in the last installment
            if i == self.loan_period_months - 1:
                principal_payment = running_balance
                monthly_payment = principal_payment + interest_payment
                
            # Create schedule entry
            schedule_entry = self.append("repayment_schedule", {
                "installment_no": i + 1,
                "payment_date": payment_date,
                "due_date": payment_date,
                "principal_amount": principal_payment,
                "interest_amount": interest_payment,
                "total_payment": monthly_payment,
                "total_due": monthly_payment,
                "amount_paid": 0,
                "unpaid_balance": monthly_payment,
                "balance_amount": running_balance,
                "status": "Pending"
            })
            
            running_balance -= principal_payment
            total_interest += interest_payment
            
            # Break if balance is fully paid
            if running_balance <= 0:
                break


def create_or_verify_member_account(member_id, company):
    """Ensure the member has a personal ledger account under SHG Members - <abbr>."""
    company_abbr = frappe.db.get_value("Company", company, "abbr")
    if not company_abbr:
        frappe.throw(f"Company abbreviation not found for {company}")

    parent_name = f"SHG Members - {company_abbr}"

    # Check for parent group
    parent_account = frappe.db.exists(
        "Account",
        {"account_name": parent_name, "company": company, "is_group": 1},
    )
    if not parent_account:
        # Create if missing under Accounts Receivable
        ar_account = frappe.db.get_value(
            "Account", {"account_name": f"Accounts Receivable - {company_abbr}"}, "name"
        )
        if not ar_account:
            frappe.throw(
                f"Accounts Receivable - {company_abbr} not found for {company}. Please create it first."
            )

        parent_account = frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": parent_name,
                "parent_account": ar_account,
                "is_group": 1,
                "company": company,
                "account_type": "Receivable",
            }
        ).insert(ignore_permissions=True)

    # Check if member subaccount exists
    member_account = frappe.db.exists(
        "Account",
        {"account_name": f"{member_id} - {company}", "company": company},
    )

    if not member_account:
        frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": f"{member_id} - {company}",
                "parent_account": parent_name,
                "is_group": 0,
                "company": company,
                "account_type": "Receivable",
            }
        ).insert(ignore_permissions=True)

    frappe.db.commit()

@frappe.whitelist()
def generate_individual_loans(parent_loan):
    parent = frappe.get_doc("SHG Loan", parent_loan)
    created_loans = []

    for m in parent.loan_members:
        # Skip if already linked
        existing = frappe.db.exists("SHG Loan", {"parent_loan": parent.name, "member": m.member})
        if existing:
            continue

        new_loan = frappe.new_doc("SHG Loan")
        new_loan.update({
            "loan_type": parent.loan_type,
            "loan_amount": m.allocated_amount or parent.loan_amount,
            "interest_rate": parent.interest_rate,
            "interest_type": parent.interest_type,
            "loan_period_months": parent.loan_period_months,
            "repayment_frequency": parent.repayment_frequency,
            "member": m.member,
            "member_name": m.member_name,
            "repayment_start_date": parent.repayment_start_date,
            "status": "Applied",
            "parent_loan": parent.name,
            "is_group_loan": 0  # Optional flag
        })
        new_loan.insert(ignore_permissions=True)
        created_loans.append(new_loan.name)

    frappe.db.commit()
    return {"created": created_loans}


def before_save(doc, method=None):
    """Ensure total loan amount = sum of allocations before save"""
    if getattr(doc, "is_group_loan", 0) and getattr(doc, "loan_members", None):
        total_allocated = sum([flt(m.allocated_amount) for m in doc.loan_members])
        doc.loan_amount = total_allocated or 0


def after_insert_or_update(doc):
    """Automatically create individual loans when a group loan is saved or submitted"""
    if not getattr(doc, "loan_members", None):
        return

    # Only for group loans
    if not getattr(doc, "is_group_loan", 0):
        return

    created = []
    for m in doc.loan_members:
        # Skip if missing member or already exists
        if not m.member:
            frappe.msgprint(f"⚠️ Skipping one row — missing member in Loan Members table.")
            continue

        if frappe.db.exists("SHG Loan", {"parent_loan": doc.name, "member": m.member}):
            continue

        # Safely fetch member name if not already filled
        member_name = m.member_name
        if not member_name:
            member_name = frappe.db.get_value("SHG Member", m.member, "member_name")

        # Create individual loan
        new_loan = frappe.new_doc("SHG Loan")
        new_loan.update({
            "loan_type": doc.loan_type,
            "loan_amount": flt(m.allocated_amount) or flt(doc.loan_amount),
            "interest_rate": doc.interest_rate,
            "interest_type": doc.interest_type,
            "loan_period_months": doc.loan_period_months,
            "repayment_frequency": doc.repayment_frequency,
            "member": m.member,
            "member_name": member_name or "",
            "repayment_start_date": doc.repayment_start_date,
            "status": "Applied",
            "parent_loan": doc.name,
            "is_group_loan": 0
        })

        # Prevent insert if still missing member (safety net)
        if not new_loan.member:
            frappe.msgprint(f"⚠️ Skipped creating loan — missing member for child row.")
            continue

        new_loan.insert(ignore_permissions=True)
        created.append(new_loan.name)

    if created:
        frappe.msgprint(
            f"✅ Created {len(created)} individual loan(s):<br>{', '.join(created)}",
            alert=True
        )
        frappe.db.commit()


def on_submit(doc, method=None):
    before_save(doc)
    after_insert_or_update(doc)

def on_update_after_submit(doc, method=None):
    before_save(doc)
    after_insert_or_update(doc)

def after_insert(doc, method=None):
    before_save(doc)
    after_insert_or_update(doc)

# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_loan(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger()