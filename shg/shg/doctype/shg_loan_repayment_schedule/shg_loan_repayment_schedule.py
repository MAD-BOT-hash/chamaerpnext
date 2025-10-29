import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate, flt


class SHGLoanRepaymentSchedule(Document):
    """
    Controller for individual loan repayment schedule rows.
    Handles:
      - Automatic status updates
      - Triggering Payment Entries when installment is paid
      - Reversing incorrect payments
      - Updating parent loan balances
    """

    def validate(self):
        """Auto-update repayment totals and status before save."""
        self.principal_amount = flt(self.principal_amount)
        self.interest_amount = flt(self.interest_amount)
        self.amount_paid = flt(self.amount_paid or 0)

        # Calculate total and unpaid balances
        self.total_due = self.principal_amount + self.interest_amount
        self.unpaid_balance = self.total_due - self.amount_paid

        self.set_status()

    # ----------------------------------------------------------------------
    # STATUS MANAGEMENT
    # ----------------------------------------------------------------------
    def set_status(self):
        """Set installment status depending on payments and due date."""
        today = getdate(nowdate())
        due_date = getdate(self.due_date) if self.due_date else today

        if self.amount_paid >= self.total_due:
            self.status = "Paid"
        elif 0 < self.amount_paid < self.total_due:
            self.status = "Partially Paid"
        elif self.amount_paid == 0 and due_date < today:
            self.status = "Overdue"
        else:
            self.status = "Pending"

    # ----------------------------------------------------------------------
    # PAYMENT ACTIONS
    # ----------------------------------------------------------------------
    @frappe.whitelist()
    def mark_as_paid(self, payment_amount=None):
        """
        Mark this installment as paid and automatically trigger a Payment Entry.
        """
        payment_amount = flt(payment_amount or self.total_due)

        if payment_amount <= 0:
            frappe.throw("Payment amount must be greater than zero.")

        if self.status == "Paid":
            frappe.throw(f"Installment {self.installment_no} is already paid.")

        # Fetch the parent loan
        loan = frappe.get_doc("SHG Loan", self.parent)

        # Create a Payment Entry via loan helper (_create_loan_payment_entry)
        try:
            loan._create_loan_payment_entry(self, payment_amount)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Loan Payment Entry failed for {self.name}")
            frappe.throw(f"Failed to create Payment Entry: {e}")

        # Update amounts
        self.amount_paid += payment_amount
        self.unpaid_balance = max(0, self.total_due - self.amount_paid)

        # Set correct status
        self.status = (
            "Paid" if self.unpaid_balance <= 0 else "Partially Paid"
        )

        # Update parent loan balances
        loan.recalculate_outstanding_after_payment()
        loan.save(ignore_permissions=True)

        self.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.msgprint(
            f"✅ Installment {self.installment_no} for Loan {loan.name} marked as {self.status}."
        )

        return {"ok": True, "status": self.status, "payment_amount": payment_amount}

    # ----------------------------------------------------------------------
    # REVERSAL ACTIONS
    # ----------------------------------------------------------------------
    @frappe.whitelist()
    def reverse_payment(self):
        """
        Reverse a payment if it was recorded by mistake.
        """
        if self.amount_paid <= 0:
            frappe.throw("No payment found to reverse for this installment.")

        # Get parent loan
        loan = frappe.get_doc("SHG Loan", self.parent)

        # Reset fields
        self.amount_paid = 0
        self.unpaid_balance = self.total_due
        self.status = "Pending"
        self.save(ignore_permissions=True)

        # Recalculate parent loan balance
        loan.recalculate_outstanding_after_payment()
        loan.save(ignore_permissions=True)

        frappe.msgprint(f"⚠️ Payment for Installment {self.installment_no} has been reversed.")
        return {"ok": True, "status": self.status}