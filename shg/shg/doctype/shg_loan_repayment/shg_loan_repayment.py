# Copyright (c) 2025
# License: MIT

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, today, add_days
from shg.shg.utils.account_helpers import get_or_create_member_receivable
from shg.shg.loan_utils import allocate_payment_to_schedule, update_loan_summary

class SHGLoanRepayment(Document):
    def validate(self):
        if flt(self.total_paid) <= 0:
            frappe.throw("Repayment amount must be greater than 0.")

        # Recompute schedule first, then validate
        if self.loan:
            from shg.shg.loan_utils import get_schedule, compute_totals
            rows = get_schedule(self.loan)
            totals = compute_totals(rows)
            outstanding_total = totals["outstanding_balance"]
            
            if flt(self.total_paid) > flt(outstanding_total):
                frappe.throw(
                    f"Repayment ({self.total_paid}) exceeds remaining balance ({outstanding_total})."
                )

    def on_submit(self):
        if self.loan:
            allocate_payment_to_schedule(self.loan, self.total_paid)
            update_loan_summary(self.loan)

    def on_cancel(self):
        # Recompute from ledger to maintain data integrity
        if self.loan:
            recompute_from_ledger(self.loan)

def recompute_from_ledger(loan_name):
    """
    Recompute schedule amounts_paid from all submitted repayment docs.
    Use if you need a clean rebuild (cancel/back-date scenarios).
    """
    rows = frappe.get_all("SHG Loan Repayment Schedule", filters={"parent": loan_name}, fields=["name","total_payment"])
    # reset rows
    for r in rows:
        frappe.db.set_value("SHG Loan Repayment Schedule", r.name, {
            "amount_paid": 0, "unpaid_balance": r["total_payment"], "status": "Pending"
        }, update_modified=False)

    # read repayments in posting_date order
    pays = frappe.get_all("SHG Loan Repayment", filters={"loan": loan_name, "docstatus":1}, fields=["total_paid"], order_by="posting_date asc, creation asc")
    from shg.shg.loan_utils import allocate_payment_to_schedule
    for p in pays:
        allocate_payment_to_schedule(loan_name, p["total_paid"])

    update_loan_summary(loan_name)

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

    def validate_installment_adjustments(self):
        """Validate installment adjustments if provided."""
        if not self.installment_adjustment:
            return
            
        total_amount = 0
        for row in self.installment_adjustment:
            # Validate that amount to repay is not negative
            if flt(row.amount_to_repay) < 0:
                frappe.throw(f"Amount to repay for installment {row.installment_no} cannot be negative.")
            
            # Validate that amount to repay does not exceed unpaid balance
            if flt(row.amount_to_repay) > flt(row.unpaid_balance):
                frappe.throw(f"Amount to repay for installment {row.installment_no} cannot exceed unpaid balance ({row.unpaid_balance}).")
            
            total_amount += flt(row.amount_to_repay)
            
            # Update status based on amount to repay
            if flt(row.amount_to_repay) >= flt(row.unpaid_balance):
                row.status = "Paid"
            elif flt(row.amount_to_repay) > 0:
                row.status = "Partially Paid"
            else:
                row.status = "Pending"
        
        # Validate that total installment payments match total paid
        if flt(total_amount) != flt(self.total_paid):
            frappe.throw(f"Total installment payments ({total_amount}) must equal Total Paid ({self.total_paid}).")

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
                "total_amount": flt(loan_doc.balance_amount),
                "outstanding_amount": flt(loan_doc.balance_amount),
                "allocated_amount": flt(self.total_paid)
            })
            
            pe.insert(ignore_permissions=True)
            pe.submit()
            
            # Link payment entry to repayment
            self.db_set("payment_entry", pe.name)
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to post repayment to ledger for {self.name}")
            frappe.throw(f"Failed to post repayment to ledger: {str(e)}")

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
            monthly_rate = flt(loan_doc.interest_rate) / 100 / 12
            interest_amount = min(outstanding_balance * monthly_rate, amount_paid)

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