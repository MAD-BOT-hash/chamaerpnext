# Copyright (c) 2025
# License: MIT

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, today, add_days

class SHGLoanRepayment(Document):
    def validate(self):
        if not self.loan:
            frappe.throw("Please select a Loan to apply this repayment to.")

        if not self.total_paid or flt(self.total_paid) <= 0:
            frappe.throw("Repayment amount must be greater than zero.")

        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        if loan_doc.docstatus != 1:
            frappe.throw(f"Loan {loan_doc.name} must be submitted before repayment.")

        if flt(self.total_paid) > flt(loan_doc.balance_amount):
            frappe.throw(
                f"Repayment ({self.total_paid}) exceeds remaining balance ({loan_doc.balance_amount})."
            )

    def on_submit(self):
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        paid_amount = flt(self.total_paid or 0)

        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.balance_amount = flt(loan_doc.balance_amount or 0) - paid_amount

        loan_doc.last_repayment_date = self.posting_date
        loan_doc.status = (
            "Paid" if loan_doc.balance_amount == 0 else "Partially Paid"
        )

        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

        loan_doc.add_comment(
            "Edit",
            f"Repayment {self.name} applied ({paid_amount}). Remaining balance: {loan_doc.balance_amount}",
        )

        frappe.msgprint(
            f"✅ Loan {loan_doc.name} updated. Remaining balance: {loan_doc.balance_amount}"
        )

    def on_cancel(self):
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        paid_amount = flt(self.total_paid or 0)

        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.balance_amount = flt(loan_doc.balance_amount or 0) + paid_amount
        loan_doc.status = "Disbursed"
        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

        loan_doc.add_comment(
            "Edit",
            f"⚠️ Repayment {self.name} cancelled. Balance restored to {loan_doc.balance_amount}",
        )

        frappe.msgprint(f"⚠️ Loan {loan_doc.name} balance restored after cancellation.")

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
            return {
                "principal_amount": 0,
                "interest_amount": 0,
                "penalty_amount": 0,
                "balance_after_payment": 0
            }

        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        outstanding_balance = flt(loan_doc.balance_amount)
        amount_paid = flt(self.total_paid)

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

        # Calculate balance after payment
        balance_after_payment = outstanding_balance - principal_amount

        # Ensure monetary values are rounded to 2 decimal places
        penalty_amount = round(float(penalty_amount), 2)
        interest_amount = round(float(interest_amount), 2)
        principal_amount = round(float(principal_amount), 2)
        balance_after_payment = round(float(balance_after_payment), 2)

        return {
            "penalty_amount": penalty_amount,
            "interest_amount": interest_amount,
            "principal_amount": principal_amount,
            "balance_after_payment": balance_after_payment
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