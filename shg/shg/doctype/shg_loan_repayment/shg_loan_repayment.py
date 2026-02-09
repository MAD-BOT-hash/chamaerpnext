# Copyright (c) 2025
# License: MIT

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, today, nowdate
from shg.shg.utils.account_helpers import get_or_create_member_receivable


class SHGLoanRepayment(Document):
    # --------------------------
    # CORE LIFECYCLE
    # --------------------------
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

        # Validate posting date against locked periods
        self.validate_posting_date()

        # Auto-calculate repayment breakdown
        self.calculate_repayment_breakdown()

    def on_submit(self):
        loan_doc = frappe.get_doc("SHG Loan", self.loan)

        # Clean any ghost payment_entry links on schedule + breakdown
        self.clean_invalid_payment_entry_links(loan_doc)

        # Create Payment Entry if missing or invalid
        if not self.payment_entry or not frappe.db.exists("Payment Entry", self.payment_entry):
            pe_name = self.create_payment_entry(loan_doc)
            self.db_set("payment_entry", pe_name)
        else:
            pe_name = self.payment_entry

        # Update the loan repayment schedule
        self.update_repayment_schedule(loan_doc)

        # Link schedule rows touched by this repayment to the Payment Entry
        self.link_payment_entry_to_schedule(loan_doc, pe_name)

        # Update loan summary
        self.update_loan_summary(loan_doc)

        frappe.msgprint(
            f"✅ Loan repayment {self.name} processed successfully."
        )

    def on_cancel(self):
        loan_doc = frappe.get_doc("SHG Loan", self.loan)

        # Reverse the repayment schedule updates
        self.reverse_repayment_schedule(loan_doc)

        # Update loan summary
        self.update_loan_summary(loan_doc)

        # Cancel the payment entry if it exists
        if self.payment_entry and frappe.db.exists("Payment Entry", self.payment_entry):
            try:
                pe = frappe.get_doc("Payment Entry", self.payment_entry)
                if pe.docstatus == 1:
                    pe.cancel()
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Failed to cancel Payment Entry {self.payment_entry}",
                )

        frappe.msgprint(
            f"⚠️ Loan repayment {self.name} cancelled."
        )

    # --------------------------
    # PAYMENT ENTRY HELPERS
    # --------------------------
    def clean_invalid_payment_entry_links(self, loan_doc):
        """Remove ghost payment_entry links that don't point to real Payment Entry docs."""
        # Clean breakdown table (if it has payment_entry column)
        for row in self.get("repayment_breakdown", []):
            if getattr(row, "payment_entry", None) and not frappe.db.exists(
                "Payment Entry", row.payment_entry
            ):
                row.payment_entry = None

        # Clean schedule table on the loan
        for s in loan_doc.get("repayment_schedule", []):
            if getattr(s, "payment_entry", None) and not frappe.db.exists(
                "Payment Entry", s.payment_entry
            ):
                s.payment_entry = None

        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.save(ignore_permissions=True)

    def _ensure_ledger_account(self, account_name, company):
        """Given any account name, ensure we return a ledger (non-group) account."""
        if not account_name:
            return None

        acc = frappe.get_doc("Account", account_name)
        if not acc.is_group:
            return acc.name

        # Try to find a ledger child under this group
        child = frappe.db.get_value(
            "Account",
            {"parent_account": acc.name, "is_group": 0, "company": company},
            "name",
        )
        if child:
            return child

        # As last resort, create a ledger child
        new_child = frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": f"{acc.account_name} - Ledger",
                "parent_account": acc.name,
                "is_group": 0,
                "company": company,
                "report_type": acc.report_type,
                "root_type": acc.root_type,
            }
        )
        new_child.insert(ignore_permissions=True)
        return new_child.name

    def create_payment_entry(self, loan_doc):
        """Create a valid ERPNext Payment Entry for this repayment."""
        # Company
        company = loan_doc.company or frappe.db.get_single_value("SHG Settings", "company")
        if not company:
            frappe.throw("Company not configured in SHG Settings or Loan.")

        # Member / customer
        member = frappe.get_doc("SHG Member", loan_doc.member)
        customer = member.customer or loan_doc.member

        # Member receivable ledger (per-member)
        member_account = get_or_create_member_receivable(loan_doc.member, company)
        member_account = self._ensure_ledger_account(member_account, company)

        # Bank / Cash account (ledger)
        default_bank = frappe.db.get_single_value("SHG Settings", "default_bank_account")
        if not default_bank:
            abbr = frappe.db.get_value("Company", company, "abbr")
            default_bank = f"Cash - {abbr}"
        paid_to = self._ensure_ledger_account(default_bank, company)

        if not member_account or not paid_to:
            frappe.throw("Could not resolve ledger accounts for Payment Entry.")

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.company = company
        pe.posting_date = self.posting_date or nowdate()

        pe.party_type = "Customer"
        pe.party = customer

        pe.paid_from = member_account
        pe.paid_from_account_type = "Receivable"
        pe.paid_from_account_currency = frappe.db.get_value(
            "Account", member_account, "account_currency"
        )

        pe.paid_to = paid_to
        pe.paid_to_account_type = "Cash"  # good default; ERPNext can adjust if bank
        pe.paid_to_account_currency = frappe.db.get_value(
            "Account", paid_to, "account_currency"
        )

        pe.paid_amount = flt(self.total_paid)
        pe.received_amount = flt(self.total_paid)
        pe.allocate_payment_amount = 1

        pe.mode_of_payment = getattr(self, "payment_method", None) or "Cash"

        # Bank transaction requirement
        pe.reference_no = self.name
        pe.reference_date = self.posting_date or nowdate()

        # DO NOT use references.append for SHG Loan (ERPNext blocks it)
        pe.remarks = f"Loan repayment for {self.loan} via SHG Loan Repayment {self.name}"

        try:
            pe.insert(ignore_permissions=True)
            pe.submit()
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Failed to create Payment Entry for loan repayment {self.name}",
            )
            frappe.throw("Failed to create Payment Entry for this repayment.")

        frappe.msgprint(f"✅ Payment Entry {pe.name} created successfully.")
        return pe.name

    def link_payment_entry_to_schedule(self, loan_doc, payment_entry_name):
        """Link Payment Entry to all schedule rows affected by this repayment."""
        for row in loan_doc.get("repayment_schedule", []):
            # If your child table has a dedicated repayment_reference field, prefer using that.
            # Fallback: link rows that changed status/amount in this repayment.
            if getattr(row, "payment_entry", None) in (None, ""):
                # Simple heuristic: link all rows that are Paid/Partially Paid and have amount_paid > 0
                if flt(row.amount_paid or 0) > 0 and row.status in ("Paid", "Partially Paid"):
                    row.payment_entry = payment_entry_name
                    row.db_update()

        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.save(ignore_permissions=True)

    # --------------------------
    # REPAYMENT SCHEDULE
    # --------------------------
    def update_repayment_schedule(self, loan_doc):
        """Update the repayment schedule based on this repayment."""
        remaining_amount = flt(self.total_paid)

        if not loan_doc.get("repayment_schedule"):
            frappe.throw(f"Loan {loan_doc.name} has no repayment schedule.")

        # If a specific schedule row is selected, apply to that row only
        if self.reference_schedule_row:
            row = frappe.get_doc("SHG Loan Repayment Schedule", self.reference_schedule_row)
            if row.parent != self.loan:
                frappe.throw("Selected schedule row does not belong to the selected loan.")

            if flt(row.unpaid_balance) > 0 and remaining_amount > 0:
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

                # Link repayment reference (NOT Payment Entry)
                if hasattr(row, "repayment_reference"):
                    row.repayment_reference = self.name

                row.db_update()
        else:
            # Apply to schedule rows in FIFO order (oldest first)
            schedule_rows = sorted(
                loan_doc.get("repayment_schedule"), key=lambda x: getdate(x.due_date)
            )

            for row in schedule_rows:
                if remaining_amount <= 0:
                    break

                if flt(row.unpaid_balance) > 0:
                    alloc = min(flt(row.unpaid_balance), remaining_amount)
                    row.amount_paid = flt(row.amount_paid or 0) + alloc
                    row.unpaid_balance = flt(row.unpaid_balance) - alloc
                    remaining_amount -= alloc

                    if row.unpaid_balance <= 0:
                        row.status = "Paid"
                        row.actual_payment_date = self.posting_date
                    else:
                        row.status = "Partially Paid"

                    if hasattr(row, "repayment_reference"):
                        row.repayment_reference = self.name

                    row.db_update()

        # Update last repayment date
        loan_doc.last_repayment_date = self.posting_date
        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

    def reverse_repayment_schedule(self, loan_doc):
        """Reverse the repayment schedule updates when cancelling."""
        # Find schedule rows that were affected by this repayment
        for row in loan_doc.get("repayment_schedule", []):
            if getattr(row, "repayment_reference", None) == self.name:
                # Reverse this payment
                row.amount_paid = flt(row.amount_paid or 0) - flt(self.total_paid or 0)
                row.unpaid_balance = flt(row.total_due or row.total_payment) - flt(row.amount_paid or 0)
                if row.unpaid_balance <= 0:
                    row.status = "Paid"
                elif row.amount_paid > 0:
                    row.status = "Partially Paid"
                else:
                    row.status = "Pending"
                row.repayment_reference = None
                row.actual_payment_date = None
                row.payment_entry = None
                row.db_update()
            elif getattr(row, "payment_entry", None):
                # Guard against invalid payment entry references
                if not frappe.db.exists("Payment Entry", row.payment_entry):
                    frappe.log_error(
                        f"Missing Payment Entry {row.payment_entry}",
                        {
                            "loan": self.loan,
                            "installment_no": row.installment_no
                        }
                    )
                    row.payment_entry = None
                    row.db_update()

        # Clear last repayment date if this was the last payment
        loan_doc.last_repayment_date = None
        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

    # --------------------------
    # LOAN SUMMARY
    # --------------------------
    def update_loan_summary(self, loan_doc):
        """Update loan summary fields after repayment."""
        try:
            # Use our new API method to refresh the repayment summary
            from shg.shg.api.loan import refresh_repayment_summary
            result = refresh_repayment_summary(loan_doc.name)

            # Reload the loan to get updated values
            loan_doc.reload()
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Failed to update repayment summary")
            # Fallback to manual calculation
            self.calculate_loan_summary_manually(loan_doc)

    def calculate_loan_summary_manually(self, loan_doc):
        """Fallback method to calculate loan summary manually."""
        if not loan_doc.get("repayment_schedule"):
            return

        total_repaid = 0.0
        balance_amount = 0.0
        overdue_amount = 0.0
        next_due_date = None

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

    def validate_posting_date(self):
        """Validate that the posting date is not in a locked period"""
        from shg.shg.utils.posting_locks import validate_posting_date
        
        # Use the posting date if available, otherwise use repayment date
        posting_date = self.posting_date or self.repayment_date or today()
        
        if posting_date:
            validate_posting_date(posting_date)

    @frappe.whitelist()
    def fetch_unpaid_balances(self):
        """
        Fetch unpaid balances for the selected loan
        This method is called from the frontend JavaScript
        """
        if not self.loan:
            frappe.throw("Please select a loan first")
        
        # Get the loan document
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        
        # Update member information
        self.member = loan_doc.member
        self.member_name = loan_doc.member_name
        
        # Update outstanding balance
        self.outstanding_balance = loan_doc.balance_amount or 0
        
        # If there's a repayment schedule, populate the breakdown table
        if loan_doc.get("repayment_schedule"):
            # Clear existing breakdown entries
            self.set("repayment_breakdown", [])
            
            # Add unpaid schedule items to the breakdown
            for schedule_row in loan_doc.repayment_schedule:
                if schedule_row.unpaid_balance and schedule_row.unpaid_balance > 0:
                    breakdown_row = self.append("repayment_breakdown", {})
                    breakdown_row.installment_no = schedule_row.installment_no
                    breakdown_row.due_date = schedule_row.due_date
                    breakdown_row.total_payment = schedule_row.total_payment
                    breakdown_row.unpaid_balance = schedule_row.unpaid_balance
                    breakdown_row.status = schedule_row.status
                    breakdown_row.amount_to_pay = 0  # Initialize with 0, user will update as needed
        
        # Calculate the total unpaid amount
        total_unpaid = sum(
            row.unpaid_balance or 0 
            for row in loan_doc.repayment_schedule 
            if row.unpaid_balance and row.unpaid_balance > 0
        ) if loan_doc.get("repayment_schedule") else loan_doc.balance_amount or 0
        
        self.outstanding_balance = total_unpaid
        
        # Refresh the form
        self.save()
        
        return {
            "status": "success",
            "outstanding_balance": self.outstanding_balance,
            "breakdown_items_count": len(self.repayment_breakdown or []),
            "member": self.member,
            "member_name": self.member_name
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
def get_unpaid_schedule_rows(loan):
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
