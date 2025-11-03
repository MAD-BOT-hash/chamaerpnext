import frappe
from frappe.model.document import Document
from frappe.utils import flt

class SHGLoanRepaymentSchedule(Document):
    def on_update(self):
        """Update parent loan summary when schedule row is updated."""
        if self.parent:
            try:
                loan = frappe.get_doc("SHG Loan", self.parent)
                # Use a safer approach instead of hasattr for Server Script compatibility
                try:
                    # Try to get the method - if it doesn't exist, this will raise an AttributeError
                    loan.update_repayment_summary
                    method_exists = True
                except AttributeError:
                    method_exists = False
                
                if method_exists:
                    loan.update_repayment_summary()
            except Exception:
                # If we can't update the parent, log the error but don't fail
                frappe.log_error(frappe.get_traceback(), f"Failed to update loan summary for {self.parent}")

    def mark_as_paid(self, amount=None):
        """Mark an installment as paid and refresh loan totals."""
        amount_to_pay = flt(amount or self.total_payment)
        self.amount_paid = amount_to_pay
        self.unpaid_balance = max(0, flt(self.total_payment) - amount_to_pay)
        self.status = "Paid" if self.unpaid_balance == 0 else "Partially Paid"
        self.actual_payment_date = frappe.utils.today()
        self.save(ignore_permissions=True)

        # Refresh parent loan summary
        if self.parent:
            try:
                loan = frappe.get_doc("SHG Loan", self.parent)
                # Use a safer approach instead of hasattr for Server Script compatibility
                try:
                    # Try to get the method - if it doesn't exist, this will raise an AttributeError
                    loan.update_repayment_summary
                    method_exists = True
                except AttributeError:
                    method_exists = False
                
                if method_exists:
                    # Allow updates on submitted loans
                    loan.flags.ignore_validate_update_after_submit = True
                    loan.update_repayment_summary()
            except Exception:
                # If we can't update the parent, log the error but don't fail
                frappe.log_error(frappe.get_traceback(), f"Failed to update loan summary for {self.parent}")

        frappe.msgprint(f"✅ Installment {self.name} marked as Paid ({amount_to_pay})")