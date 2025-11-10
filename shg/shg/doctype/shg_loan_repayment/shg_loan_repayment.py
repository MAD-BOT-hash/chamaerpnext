# Copyright (c) 2025
# License: MIT

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, today
from shg.shg.utils.account_helpers import get_or_create_member_receivable

class SHGLoanRepayment(Document):
    def validate(self):
        if not self.loan:
            frappe.throw("Please select a Loan to apply this repayment to.")

        if not self.total_paid or flt(self.total_paid) <= 0:
            frappe.throw("Repayment amount must be greater than zero.")

        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        if loan_doc.docstatus != 1:
            frappe.throw(f"Loan {loan_doc.name} must be submitted before repayment.")

        # Ensure repayment schedule is loaded
        if not loan_doc.get("repayment_schedule"):
            # Try to load from database
            schedule_from_db = frappe.get_all("SHG Loan Repayment Schedule", 
                                            filters={"parent": self.loan, "parenttype": "SHG Loan"},
                                            fields=["*"])  # Load all fields
            if schedule_from_db:
                # Populate the loan document with the schedule
                loan_doc.repayment_schedule = []
                for row_data in schedule_from_db:
                    loan_doc.append("repayment_schedule", row_data)
            else:
                # Try to generate schedule if none exists
                try:
                    loan_doc.create_repayment_schedule_if_needed()
                    loan_doc.reload()  # Reload to get the newly created schedule
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), f"Failed to generate repayment schedule for loan {loan_doc.name} during validation")

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
        frappe.log_error(f"Repayment validation - Loan: {self.loan}, Total Paid: {self.total_paid}, Outstanding: {outstanding_balance}, Schedule Count: {schedule_count}, Schedule Details: {schedule_details}", "SHG Loan Repayment Validation")

        if flt(self.total_paid) > flt(outstanding_balance):
            frappe.throw(
                f"Repayment ({self.total_paid}) exceeds remaining balance ({outstanding_balance}). Loan has {schedule_count} schedule rows."
            )

        # Auto-calculate repayment breakdown
        self.calculate_repayment_breakdown()

    def on_submit(self):
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        
        # Ensure repayment schedule is loaded
        if not loan_doc.get("repayment_schedule"):
            # Try to load from database
            schedule_from_db = frappe.get_all("SHG Loan Repayment Schedule", 
                                            filters={"parent": self.loan, "parenttype": "SHG Loan"},
                                            fields=["*"])  # Load all fields
            if schedule_from_db:
                # Populate the loan document with the schedule
                loan_doc.repayment_schedule = []
                for row_data in schedule_from_db:
                    loan_doc.append("repayment_schedule", row_data)
        
        # Update the loan repayment schedule
        self.update_repayment_schedule(loan_doc)
        
        # Update loan summary
        self.update_loan_summary(loan_doc)
        
        # Post to GL if needed
        self.post_to_ledger(loan_doc)
        
        frappe.msgprint(
            f"✅ Loan repayment {self.name} processed successfully. Remaining balance: {loan_doc.balance_amount}"
        )

    def on_cancel(self):
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        
        # Ensure repayment schedule is loaded
        if not loan_doc.get("repayment_schedule"):
            # Try to load from database
            schedule_from_db = frappe.get_all("SHG Loan Repayment Schedule", 
                                            filters={"parent": self.loan, "parenttype": "SHG Loan"},
                                            fields=["*"])  # Load all fields
            if schedule_from_db:
                # Populate the loan document with the schedule
                loan_doc.repayment_schedule = []
                for row_data in schedule_from_db:
                    loan_doc.append("repayment_schedule", row_data)
        
        # Reverse the repayment schedule updates
        self.reverse_repayment_schedule(loan_doc)
        
        # Update loan summary
        self.update_loan_summary(loan_doc)
        
        # Cancel the payment entry if it exists
        if self.payment_entry:
            try:
                pe = frappe.get_doc("Payment Entry", self.payment_entry)
                if pe.docstatus == 1:
                    pe.cancel()
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Failed to cancel Payment Entry {self.payment_entry}")
        
        frappe.msgprint(f"⚠️ Loan repayment {self.name} cancelled. Balance restored to {loan_doc.balance_amount}")

    def update_repayment_schedule(self, loan_doc):
        """Update the repayment schedule based on this repayment."""
        remaining_amount = flt(self.total_paid)
        
        # Ensure repayment schedule is loaded
        if not loan_doc.get("repayment_schedule"):
            # Try to load from database
            schedule_from_db = frappe.get_all("SHG Loan Repayment Schedule", 
                                            filters={"parent": self.loan, "parenttype": "SHG Loan"},
                                            fields=["*"])  # Load all fields
            if schedule_from_db:
                # Populate the loan document with the schedule
                loan_doc.repayment_schedule = []
                for row_data in schedule_from_db:
                    loan_doc.append("repayment_schedule", row_data)
            else:
                # Try to generate schedule if none exists
                try:
                    loan_doc.create_repayment_schedule_if_needed()
                    loan_doc.reload()  # Reload to get the newly created schedule
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), f"Failed to generate repayment schedule for loan {loan_doc.name}")
                    frappe.throw(f"Loan {loan_doc.name} has no repayment schedule and failed to generate one: {str(e)}")
            
            # Check again after attempting to generate
            if not loan_doc.get("repayment_schedule"):
                frappe.throw(f"Loan {loan_doc.name} has no repayment schedule.")
            
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
            frappe.log_error(frappe.get_traceback(), "Failed to update repayment summary")
            # Fallback to manual calculation
            self.calculate_loan_summary_manually(loan_doc)

    def calculate_loan_summary_manually(self, loan_doc):
        """Fallback method to calculate loan summary manually."""
        # Ensure repayment schedule is loaded
        if not loan_doc.get("repayment_schedule"):
            # Try to load from database
            schedule_from_db = frappe.get_all("SHG Loan Repayment Schedule", 
                                            filters={"parent": loan_doc.name, "parenttype": "SHG Loan"},
                                            fields=["*"])  # Load all fields
            if schedule_from_db:
                # Populate the loan document with the schedule
                loan_doc.repayment_schedule = []
                for row_data in schedule_from_db:
                    loan_doc.append("repayment_schedule", row_data)
            else:
                # Try to generate schedule if none exists
                try:
                    loan_doc.create_repayment_schedule_if_needed()
                    loan_doc.reload()  # Reload to get the newly created schedule
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), f"Failed to generate repayment schedule for loan {loan_doc.name} in manual calculation")
                    return
            
            # Check again after attempting to generate
            if not loan_doc.get("repayment_schedule"):
                return
            
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
        try:
            # Get member details
            member = frappe.get_doc("SHG Member", loan_doc.member)
            customer = member.customer or loan_doc.member
            
            # Get or create member receivable account
            company = loan_doc.company or frappe.db.get_single_value("SHG Settings", "company")
            member_account = get_or_create_member_receivable(loan_doc.member, company)
            
            # Create Payment Entry
            pe = frappe.new_doc("Payment Entry")
            pe.payment_type = "Receive"
            pe.company = company
            pe.posting_date = self.posting_date
            pe.paid_from = member_account
            pe.paid_from_account_type = "Receivable"
            pe.paid_from_account_currency = frappe.db.get_value("Account", member_account, "account_currency")
            pe.paid_to = frappe.db.get_single_value("SHG Settings", "default_bank_account") or "Cash - " + frappe.db.get_value("Company", company, "abbr")
            pe.paid_to_account_type = "Cash"
            pe.paid_to_account_currency = frappe.db.get_value("Account", pe.paid_to, "account_currency")
            pe.paid_amount = flt(self.total_paid)
            pe.received_amount = flt(self.total_paid)
            pe.allocate_payment_amount = 1
            pe.party_type = "Customer"
            pe.party = customer
            pe.remarks = f"Loan repayment for {self.loan}"
            
            # Add reference to the loan
            pe.append("references", {
                "reference_doctype": "SHG Loan",
                "reference_name": self.loan,
                "allocated_amount": flt(self.total_paid)
            })
            
            pe.insert(ignore_permissions=True)
            pe.submit()
            
            # Link the payment entry to this repayment
            self.db_set("payment_entry", pe.name)
            
            frappe.msgprint(f"✅ Payment Entry {pe.name} created successfully.")
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to create Payment Entry for loan repayment")
            frappe.throw(f"Failed to create Payment Entry: {str(e)}")

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