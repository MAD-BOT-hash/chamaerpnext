# Copyright (c) 2025
# License: MIT

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, today, add_days
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

        # Calculate outstanding balance including both principal and interest
        outstanding_balance = self.calculate_outstanding_balance(loan_doc)
        
        if flt(self.total_paid) > flt(outstanding_balance):
            frappe.throw(
                f"Repayment ({self.total_paid}) exceeds remaining balance ({outstanding_balance})."
            )

        # Auto-calculate repayment breakdown
        self.calculate_repayment_breakdown()
        
        # Validate installment adjustments if any
        self.validate_installment_adjustments()

    def calculate_outstanding_balance(self, loan_doc):
        """
        Calculate outstanding balance by summing unpaid balances from repayment schedule.
        This ensures we're using real-time data instead of potentially stale cached values.
        Includes both principal and interest components.
        """
        # Get all repayment schedule rows
        schedule_rows = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={
                "parent": loan_doc.name,
                "parenttype": "SHG Loan"
            },
            fields=["unpaid_balance"]
        )
        
        # Sum all unpaid balances
        outstanding_balance = sum(flt(row.get("unpaid_balance", 0)) for row in schedule_rows)
        
        return outstanding_balance

    def on_submit(self):
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        
        # Update the repayment schedule based on installment adjustments or regular repayment
        if self.installment_adjustment:
            self.update_repayment_schedule_from_installments(loan_doc)
        else:
            self.update_repayment_schedule(loan_doc)
        
        # Update loan summary
        self.update_loan_summary(loan_doc)
        
        # Post to GL if needed
        self.post_to_ledger(loan_doc)
        
        frappe.msgprint(
            f"✅ Loan repayment {self.name} processed successfully. Remaining balance: {loan_doc.balance_amount}"
        )

    def update_repayment_schedule_from_installments(self, loan_doc):
        """Update the repayment schedule based on installment adjustments."""
        for installment in self.installment_adjustment:
            # Get the schedule row
            schedule_row = frappe.get_doc("SHG Loan Repayment Schedule", installment.schedule_row_id)
            
            # Update the schedule row with the payment
            schedule_row.amount_paid = flt(schedule_row.amount_paid or 0) + flt(installment.amount_to_repay)
            schedule_row.unpaid_balance = flt(schedule_row.total_due) - flt(schedule_row.amount_paid)
            
            # Update status
            if schedule_row.unpaid_balance <= 0:
                schedule_row.status = "Paid"
                schedule_row.actual_payment_date = self.posting_date
            elif flt(schedule_row.amount_paid) > 0:
                schedule_row.status = "Partially Paid"
            else:
                schedule_row.status = "Pending"
            
            # Link this repayment to the schedule row
            schedule_row.payment_entry = self.name
            
            # Save the updated row
            schedule_row.save(ignore_permissions=True)
        
        # Update last repayment date
        loan_doc.last_repayment_date = self.posting_date
        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

    def update_repayment_schedule(self, loan_doc):
        """Update the repayment schedule based on this repayment."""
        remaining_amount = flt(self.total_paid)
        
        if not loan_doc.get("repayment_schedule"):
            frappe.throw(f"Loan {loan_doc.name} has no repayment schedule.")
            
        # Sort schedule rows by due date (oldest first)
        schedule_rows = sorted(loan_doc.get("repayment_schedule"), key=lambda x: getdate(x.due_date))
        
        updated_rows = []
        
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
                
                # Save the updated row
                row.db_update()
                updated_rows.append(row)
        
        # Update last repayment date
        loan_doc.last_repayment_date = self.posting_date
        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

    def update_loan_summary(self, loan_doc):
        """
        Update loan summary fields after repayment.
        This ensures loan-level fields are synchronized with schedule-level fields.
        """
        try:
            # Recalculate repayment summary
            loan_doc.update_repayment_summary()
            
            # Also update using the new get_remaining_balance function
            from shg.shg.doctype.shg_loan.shg_loan import get_remaining_balance
            balance_info = get_remaining_balance(loan_doc.name)
            
            # Update loan fields with computed values
            loan_doc.flags.ignore_validate_update_after_submit = True
            loan_doc.balance_amount = flt(balance_info["total_balance"], 2)
            loan_doc.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to update loan summary for {loan_doc.name}")

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

    @frappe.whitelist()
    def get_unpaid_installments(self):
        """
        Fetch all unpaid installments from the linked loan's repayment schedule.
        This method is called from the frontend via JavaScript.
        """
        if not self.loan:
            frappe.throw("Please select a Loan first.")
            
        # Clear existing installment adjustments
        self.installment_adjustment = []
        
        # Get unpaid installments from the loan's repayment schedule
        unpaid_installments = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={
                "parent": self.loan,
                "parenttype": "SHG Loan",
                "unpaid_balance": [">", 0],
                "status": ["!=", "Paid"]
            },
            fields=[
                "name",
                "installment_no",
                "due_date",
                "principal_component",
                "interest_component",
                "total_due",
                "unpaid_balance",
                "status"
            ],
            order_by="due_date"
        )
        
        # Add unpaid installments to the installment adjustment table
        for installment in unpaid_installments:
            self.append("installment_adjustment", {
                "installment_no": installment.installment_no,
                "due_date": installment.due_date,
                "principal_amount": installment.principal_component,
                "interest_amount": installment.interest_component,
                "total_due": installment.total_due,
                "unpaid_balance": installment.unpaid_balance,
                "amount_to_repay": 0,  # Default to 0, user can edit
                "status": installment.status,
                "schedule_row_id": installment.name
            })
        
        return self.installment_adjustment

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