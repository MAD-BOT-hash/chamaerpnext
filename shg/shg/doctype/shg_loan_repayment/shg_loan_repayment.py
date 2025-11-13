import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, today, add_months, nowdate
from shg.shg.utils.account_helpers import get_or_create_member_receivable

class SHGLoanRepayment(Document):
    def before_insert(self):
        """Auto-fill company from linked loan before inserting the document."""
        if self.loan:
            self.company = frappe.db.get_value("SHG Loan", self.loan, "company")

    def validate(self):
        """Validate the loan repayment before saving."""
        if not self.loan:
            frappe.throw("Please select a Loan to apply this repayment to.")

        if not self.total_paid or flt(self.total_paid) <= 0:
            frappe.throw("Repayment amount must be greater than zero.")

        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        if loan_doc.docstatus != 1:
            frappe.throw(f"Loan {loan_doc.name} must be submitted before repayment.")

        # Ensure repayment schedule is loaded
        if not loan_doc.get("repayment_schedule"):
            self.generate_and_attach_schedule(loan_doc)

        # Calculate outstanding balance directly from repayment schedule
        outstanding_balance = 0
        schedule_count = 0
        schedule_details = []
        if loan_doc.get("repayment_schedule"):
            schedule_count = len(loan_doc.get("repayment_schedule"))
            for row in loan_doc.get("repayment_schedule"):
                unpaid = flt(row.unpaid_balance or 0)
                outstanding_balance += unpaid
                schedule_details.append({
                    "installment": row.installment_no,
                    "due_date": row.due_date,
                    "total_payment": row.total_payment,
                    "amount_paid": row.amount_paid,
                    "unpaid_balance": unpaid,
                    "status": row.status
                })
        else:
            # If no schedule, calculate from loan fields
            outstanding_balance = flt(loan_doc.balance_amount or loan_doc.loan_amount or 0)

        # Debug information
        from shg.shg.utils.logger import safe_log_error
        safe_log_error(f"Repayment validation - Loan {self.loan}", {
            "total_paid": self.total_paid,
            "outstanding_balance": outstanding_balance,
            "schedule_count": schedule_count,
            "schedule_details": schedule_details
        })

        if flt(self.total_paid) > flt(outstanding_balance):
            frappe.throw(
                f"Repayment ({self.total_paid}) exceeds remaining balance ({outstanding_balance}). Loan has {schedule_count} schedule rows."
            )

        # Validate that if payment_entry is set, it exists
        if self.payment_entry and not frappe.db.exists("Payment Entry", self.payment_entry):
            frappe.throw(f"Linked Payment Entry {self.payment_entry} does not exist.")

        # Auto-calculate repayment breakdown
        self.calculate_repayment_breakdown()

    def clean_invalid_payment_entry_links(self):
        """Removes invalid or ghost payment_entry values such as REP-xxxx."""
        for row in self.repayment_breakdown:
            if row.payment_entry and not frappe.db.exists("Payment Entry", row.payment_entry):
                row.payment_entry = None

        # Also fix the loan's repayment schedule table
        loan = frappe.get_doc("SHG Loan", self.loan)
        for s in loan.repayment_schedule:
            if s.payment_entry and not frappe.db.exists("Payment Entry", s.payment_entry):
                s.payment_entry = None
        loan.save(ignore_permissions=True)

    def on_submit(self):
        # Clean bad references like REP-0003
        self.clean_invalid_payment_entry_links()

        # Ensure valid Payment Entry exists
        if not self.payment_entry or not frappe.db.exists("Payment Entry", self.payment_entry):
            self.payment_entry = self.create_payment_entry()
            self.db_update()

        # Get the loan document
        loan_doc = frappe.get_doc("SHG Loan", self.loan)

        # 2️⃣ normal loan/schedule updates
        self.update_repayment_schedule(loan_doc)
        self.update_loan_summary(loan_doc)

        frappe.msgprint(f"Linked Payment Entry: {self.payment_entry}")

    def on_cancel(self):
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        
        # Ensure repayment schedule is loaded
        if not loan_doc.get("repayment_schedule"):
            self.generate_and_attach_schedule(loan_doc)
        
        # Reverse the repayment schedule updates
        self.reverse_repayment_schedule(loan_doc)
        
        # Update loan summary
        self.update_loan_summary(loan_doc)
        
        # Cancel the payment entry if it exists
        if self.payment_entry and frappe.db.exists("Payment Entry", self.payment_entry):
            pe = frappe.get_doc("Payment Entry", self.payment_entry)
            if pe.docstatus == 1:
                pe.cancel()
        
        frappe.msgprint(f"⚠️ Loan repayment {self.name} cancelled. Balance restored to {loan_doc.balance_amount}")

    def update_repayment_schedule(self, loan_doc):
        """Update the repayment schedule based on this repayment."""
        remaining_amount = flt(self.total_paid)
        
        # Ensure repayment schedule is loaded
        if not loan_doc.get("repayment_schedule"):
            self.generate_and_attach_schedule(loan_doc)
            
        # If a specific schedule row is selected, apply to that row only
        if self.reference_schedule_row:
            row = frappe.get_doc("SHG Loan Repayment Schedule", self.reference_schedule_row)
            if row.parent != self.loan:
                frappe.throw("Selected schedule row does not belong to the selected loan.")
                
            if flt(row.unpaid_balance) > 0:
                alloc = min(flt(row.unpaid_balance), remaining_amount)
                row.amount_paid = flt(row.amount_paid or 0) + alloc
                row.unpaid_balance = flt(row.unpaid_balance) - alloc
                remaining_amount -= alloc
                
                # Update status
                if row.unpaid_balance <= 0:
                    row.status = "Paid"
                    row.actual_payment_date = self.posting_date
                else:
                    row.status = "Partially Paid"
                
                # Link this repayment to the schedule row
                row.payment_entry = self.name
                row.db_update()
        else:
            # Apply to schedule rows in FIFO order (oldest first)
            schedule_rows = sorted(loan_doc.get("repayment_schedule"), key=lambda x: getdate(x.due_date))
            
            for row in schedule_rows:
                if remaining_amount <= 0:
                    break
                    
                if flt(row.unpaid_balance) > 0:
                    # Allocate amount to this row
                    alloc = min(flt(row.unpaid_balance), remaining_amount)
                    row.amount_paid = flt(row.amount_paid or 0) + alloc
                    row.unpaid_balance = flt(row.unpaid_balance) - alloc
                    remaining_amount -= alloc
                    
                    # Update status
                    if row.unpaid_balance <= 0:
                        row.status = "Paid"
                        row.actual_payment_date = self.posting_date
                    else:
                        row.status = "Partially Paid"
                    
                    # Link this repayment to the schedule row
                    row.payment_entry = self.name
                    row.db_update()
        
        # Update last repayment date
        loan_doc.last_repayment_date = self.posting_date
        # Allow updates on submitted loans
        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

    def reverse_repayment_schedule(self, loan_doc):
        """Reverse the repayment schedule updates when cancelling."""
        if not loan_doc.get("repayment_schedule"):
            # Nothing to reverse if there's no schedule
            return
            
        # Find schedule rows that were affected by this repayment
        for row in loan_doc.get("repayment_schedule"):
            if row.payment_entry == self.name:
                # Reverse this payment
                row.amount_paid = flt(row.amount_paid or 0) - flt(self.total_paid or 0)
                row.unpaid_balance = flt(row.total_due or row.total_payment) - flt(row.amount_paid or 0)
                if row.unpaid_balance <= 0:
                    row.status = "Paid"
                elif row.amount_paid > 0:
                    row.status = "Partially Paid"
                else:
                    row.status = "Pending"
                row.payment_entry = None
                row.actual_payment_date = None
                row.db_update()
            elif row.payment_entry:
                # Guard against invalid payment entry references
                if not frappe.db.exists("Payment Entry", row.payment_entry):
                    from shg.shg.utils.logger import safe_log_error
                    safe_log_error(f"Missing Payment Entry {row.payment_entry}", {
                        "loan": self.loan,
                        "installment_no": row.installment_no
                    })
                    row.payment_entry = None
                    row.db_update()
        
        # Clear last repayment date if this was the last payment
        loan_doc.last_repayment_date = None
        # Allow updates on submitted loans
        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

    def update_loan_summary(self, loan_doc):
        """Update loan summary fields after repayment."""
        try:
            # Use our new API method to refresh the repayment summary
            from shg.shg.api.loan import refresh_repayment_summary
            result = refresh_repayment_summary(loan_doc.name)
            
            # Reload the loan to get updated values
            loan_doc.reload()
        except Exception as e:
            from shg.shg.utils.logger import safe_log_error
            safe_log_error("Failed to update repayment summary", {
                "loan": loan_doc.name,
                "error": str(e),
                "traceback": frappe.get_traceback()
            })
            # Fallback to manual calculation
            self.calculate_loan_summary_manually(loan_doc)

    def calculate_loan_summary_manually(self, loan_doc):
        """Fallback method to calculate loan summary manually."""
        # Ensure repayment schedule is loaded
        if not loan_doc.get("repayment_schedule"):
            self.generate_and_attach_schedule(loan_doc)
            
        total_repaid = 0.0
        balance_amount = 0.0
        overdue_amount = 0.0
        next_due_date = None
        last_repayment_date = None
        
        today_date = getdate(today())
        
        for row in loan_doc.get("repayment_schedule"):
            total_repaid += flt(row.amount_paid or 0)
            balance_amount += flt(row.unpaid_balance or 0)
            
            # Check for overdue payments
            if row.status == "Overdue" or (getdate(row.due_date) < today_date and flt(row.unpaid_balance) > 0):
                overdue_amount += flt(row.unpaid_balance or 0)
            
            # Find next due date
            if flt(row.unpaid_balance) > 0 and (not next_due_date or getdate(row.due_date) < getdate(next_due_date)):
                next_due_date = row.due_date
        
        # Update loan document
        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.total_repaid = total_repaid
        loan_doc.balance_amount = balance_amount
        loan_doc.overdue_amount = overdue_amount
        loan_doc.next_due_date = next_due_date
        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

    def post_to_ledger(self, loan_doc):
        """Post repayment to ledger by creating a Payment Entry."""
        # Check if payment entry already exists and is valid
        if self.payment_entry:
            if not frappe.db.exists("Payment Entry", self.payment_entry):
                frappe.msgprint(f"⚠️ Payment Entry {self.payment_entry} not found – recreating...")
                self.payment_entry = self.create_payment_entry()
                return
            else:
                # Payment entry exists, nothing to do
                return
        
        # No payment entry exists, create one
        self.payment_entry = self.create_payment_entry()

    @frappe.whitelist()
    def fetch_unpaid_balances(self):
        """Fetch unpaid balances from the linked loan's repayment schedule."""
        if not self.loan:
            frappe.throw("Please select a Loan first.")

        loan = frappe.get_doc("SHG Loan", self.loan)

        # Track if we generated a schedule
        generated_schedule = False
        
        # --- Load schedule if missing ---
        if not loan.repayment_schedule:
            self.generate_and_attach_schedule(loan)
            generated_schedule = True

        # --- Ensure all schedule rows have proper default values ---
        for row in loan.repayment_schedule:
            # Set default status if missing
            if not getattr(row, 'status', None):
                row.status = "Pending"
            # Set default amount_paid if missing
            if not hasattr(row, 'amount_paid'):
                row.amount_paid = 0.0
            # Set default unpaid_balance if missing
            if not hasattr(row, 'unpaid_balance'):
                row.unpaid_balance = flt(getattr(row, 'total_payment', 0) or getattr(row, 'total_due', 0)) - flt(row.amount_paid)
        
        # --- Filter unpaid installments ---
        unpaid = [
            row for row in loan.repayment_schedule
            if row.status in ("Pending", "Overdue", "Partially Paid") and flt(row.unpaid_balance) > 0
        ]

        if not unpaid:
            frappe.msgprint(f"Loan {loan.name} has no unpaid installments.")
            return []

        # --- Clear current breakdown ---
        self.set("repayment_breakdown", [])

        total_due = total_paid = balance = 0
        for row in unpaid:
            balance_row = flt(row.unpaid_balance or 0)
            self.append("repayment_breakdown", {
                "installment_no": row.installment_no,
                "due_date": row.due_date,
                "emi_amount": row.emi_amount or row.total_payment,
                "principal_component": row.principal_component,
                "interest_component": row.interest_component,
                "unpaid_balance": balance_row,
                "amount_to_pay": 0,  # Default to 0, user can edit
                "status": row.status
            })
            total_due += flt(row.total_payment or 0)
            total_paid += flt(row.amount_paid or 0)
            balance += balance_row

        # --- Update totals on parent ---
        self.total_paid = total_paid
        self.outstanding_balance = balance
        self.balance_after_payment = balance
        self.save()

        frappe.msgprint(
            f"Fetched {len(unpaid)} unpaid installments "
            f"(Total Due KES {frappe.utils.fmt_money(balance, currency='KES')})"
        )
        
        # Optional enhancement - show schedule refresh message for newly generated schedules
        if generated_schedule:  # If we generated a schedule
            frappe.msgprint(f"Refreshed repayment schedule for Loan {loan.name}. You can now mark installments as Paid.")
        
        return [r.as_dict() for r in unpaid]

    # --------------------------
    # REPAYMENT BREAKDOWN
    # --------------------------
    @frappe.whitelist()
    def calculate_repayment_breakdown(self):
        """
        Calculate principal, interest, and penalty breakdown for the repayment.
        This method is called from the frontend via JavaScript.
        """
        if not self.loan or not self.total_paid:
            self.principal_amount = 0
            self.interest_amount = 0
            self.penalty_amount = 0
            self.outstanding_balance = 0
            self.balance_after_payment = 0
            return

        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        outstanding_balance = flt(loan_doc.balance_amount)
        amount_paid = flt(self.total_paid)
        
        self.outstanding_balance = outstanding_balance
        self.balance_after_payment = max(0, outstanding_balance - amount_paid)

        # Get settings for penalty calculation
        settings = frappe.get_single("SHG Settings")
        penalty_rate = flt(getattr(settings, "loan_penalty_rate", 5))  # Default 5%

        # Calculate penalty if repayment is late
        penalty_amount = 0
        if loan_doc.next_due_date and getdate(self.repayment_date) > getdate(loan_doc.next_due_date):
            # Calculate days overdue
            days_overdue = (getdate(self.repayment_date) - getdate(loan_doc.next_due_date)).days
            if days_overdue > 0:
                # Calculate penalty based on outstanding balance and days overdue
                daily_penalty_rate = penalty_rate / 100 / 30  # Monthly rate converted to daily
                penalty_amount = outstanding_balance * daily_penalty_rate * days_overdue

        # Calculate interest based on loan type
        interest_amount = 0
        if loan_doc.interest_type == "Flat Rate":
            # For flat rate, interest is calculated on original principal
            monthly_interest = (flt(loan_doc.loan_amount) * flt(loan_doc.interest_rate) / 100) / 12
            interest_amount = min(monthly_interest, amount_paid)
        else:
            # For reducing balance, interest is calculated on current outstanding balance
            monthly_interest_rate = flt(loan_doc.interest_rate) / 100 / 12
            interest_amount = outstanding_balance * monthly_interest_rate

        # Cap interest amount to the payment amount
        interest_amount = min(interest_amount, amount_paid)

        # Calculate principal (remaining amount after interest and penalty)
        amount_after_penalty = max(0, amount_paid - penalty_amount)
        amount_after_interest = max(0, amount_after_penalty - interest_amount)
        principal_amount = amount_after_interest

        # Set the calculated values
        self.penalty_amount = round(penalty_amount, 2)
        self.interest_amount = round(interest_amount, 2)
        self.principal_amount = round(principal_amount, 2)

        return {
            "penalty_amount": self.penalty_amount,
            "interest_amount": self.interest_amount,
            "principal_amount": self.principal_amount,
            "balance_after_payment": self.balance_after_payment
        }

    # --------------------------------------------------------------------
    def create_payment_entry(self):
        loan = frappe.get_doc("SHG Loan", self.loan)
        company = loan.company
        member = loan.member

        member_account = get_or_create_member_receivable(member, company)

        paid_to = frappe.db.get_single_value("SHG Settings", "default_bank_account")
        if not paid_to:
            abbr = frappe.db.get_value("Company", company, "abbr")
            paid_to = f"Cash - {abbr}"

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.company = company
        pe.party_type = "Customer"
        pe.party = member
        pe.posting_date = self.posting_date or nowdate()

        pe.paid_from = member_account
        pe.paid_to = paid_to
        pe.paid_amount = flt(self.total_paid)
        pe.received_amount = flt(self.total_paid)
        pe.mode_of_payment = self.payment_method or "Cash"

        # REQUIRED FIX → prevent Bank transaction error
        pe.reference_no = self.name
        pe.reference_date = self.posting_date or nowdate()

        # IMPORTANT → no references.append for SHG Loan
        pe.remarks = f"Auto-created repayment for SHG Loan {self.loan}"

        pe.insert(ignore_permissions=True)
        pe.submit()

        return pe.name

    def generate_and_attach_schedule(self, loan_doc):
        from shg.shg.utils.schedule_math import generate_flat_rate_schedule, generate_reducing_balance_schedule

        principal = flt(loan_doc.loan_amount)
        months = int(loan_doc.loan_period_months)
        start_date = loan_doc.repayment_start_date or add_months(loan_doc.disbursement_date or today(), 1)

        if loan_doc.interest_type == "Flat Rate":
            schedule = generate_flat_rate_schedule(principal, loan_doc.interest_rate, months, start_date)
        else:
            schedule = generate_reducing_balance_schedule(principal, loan_doc.interest_rate, months, start_date)

        loan_doc.set("repayment_schedule", schedule)
        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.save(ignore_permissions=True)
        loan_doc.reload()

# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_repayment(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1:
        # The actual posting to ledger is handled in the on_submit method
        pass

# --- Query methods ---
@frappe.whitelist()
def get_unpaid_schedule_rows(loan, **kwargs):
    """Get unpaid schedule rows for a loan."""
    if not loan:
        return []
    
    # Get schedule rows that are not fully paid
    rows = frappe.get_all("SHG Loan Repayment Schedule",
        filters={
            "parent": loan,
            "unpaid_balance": [">", 0]
        },
        fields=["name", "due_date", "total_payment", "unpaid_balance"],
        order_by="due_date asc"
    )
    
    # Format for select field
    result = []
    for row in rows:
        result.append({
            "value": row.name,
            "label": f"{row.due_date} - {row.unpaid_balance} of {row.total_payment}"
        })
    
    return result