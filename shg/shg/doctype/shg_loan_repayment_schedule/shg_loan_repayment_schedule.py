import frappe
from frappe.model.document import Document
from frappe.utils import flt

class SHGLoanRepaymentSchedule(Document):
    def mark_as_paid(self, amount=None):
        """Mark an installment as paid and refresh loan totals."""
        amount_to_pay = flt(amount or self.total_payment)
        self.amount_paid = amount_to_pay
        self.unpaid_balance = 0
        self.status = "Paid"
        self.save(ignore_permissions=True)

        # Refresh parent loan summary
        if self.parent:
            loan = frappe.get_doc("SHG Loan", self.parent)
            if hasattr(loan, "update_repayment_summary"):
                loan.update_repayment_summary()

        frappe.msgprint(f"✅ Installment {self.name} marked as Paid ({amount_to_pay})")