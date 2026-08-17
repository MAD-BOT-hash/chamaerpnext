import frappe
from frappe.utils import flt, now_datetime, getdate
from frappe import _

def execute():
    """
    Patch adds:
      1. update_repayment_summary() to SHG Loan
      2. mark_as_paid() to SHG Loan Repayment Schedule
      3. Auto-refresh repayment summary after each payment
    """

    frappe.msgprint("🔧 Installing SHG Loan repayment summary enhancement patch...")

    # ----------------------------------------------------------------------
    # 1️⃣ Add helper function to SHG Loan (if not already present)
    # ----------------------------------------------------------------------
    # Use a safer approach instead of hasattr for Server Script compatibility
    try:
        # Try to get the method - if it doesn't exist, this will raise an AttributeError
        frappe.get_doc("DocType", "SHG Loan").update_repayment_summary
        method_exists = True
    except AttributeError:
        method_exists = False
    
    if not method_exists:
        frappe.msgprint("✅ Adding update_repayment_summary() to SHG Loan runtime class...")

        def update_repayment_summary(self):
            """Recalculate repayment summary fields from schedule child table."""
            schedule = self.get("repayment_schedule") or []

            total_payable = sum(flt(getattr(r, "total_payment", 0)) for r in schedule)
            total_repaid = sum(flt(getattr(r, "amount_paid", 0)) for r in schedule)
            overdue_amount = sum(flt(getattr(r, "unpaid_balance", 0)) for r in schedule if getattr(r, "status", None) == "Overdue")
            balance = total_payable - total_repaid

            frappe.db.set_value(
                "SHG Loan",
                self.name,
                {
                    "total_payable": round(total_payable, 2),
                    "total_repaid": round(total_repaid, 2),
                    "overdue_amount": round(overdue_amount, 2),
                    "balance_amount": round(balance, 2),
                    "modified": now_datetime()
                },
            )
            frappe.db.commit()

        # Bind to class dynamically
        from shg.shg.doctype.shg_loan.shg_loan import SHGLoan
        setattr(SHGLoan, "update_repayment_summary", update_repayment_summary)

    # ----------------------------------------------------------------------
    # 2️⃣ Add mark_as_paid() to SHG Loan Repayment Schedule class
    # ----------------------------------------------------------------------
    try:
        from shg.shg.doctype.shg_loan_repayment_schedule.shg_loan_repayment_schedule import SHGLoanRepaymentSchedule

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
                # Use a safer approach instead of hasattr for Server Script compatibility
                try:
                    # Try to get the method - if it doesn't exist, this will raise an AttributeError
                    loan.update_repayment_summary
                    method_exists = True
                except AttributeError:
                    method_exists = False
                
                if method_exists:
                    loan.update_repayment_summary()

            frappe.msgprint(f"✅ Installment {self.name} marked as Paid ({amount_to_pay})")

        setattr(SHGLoanRepaymentSchedule, "mark_as_paid", mark_as_paid)
        frappe.msgprint("✅ Added mark_as_paid() to SHG Loan Repayment Schedule.")

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Loan Repayment Patch Error")
        frappe.msgprint(f"⚠️ Could not attach mark_as_paid(): {e}")

    frappe.msgprint("🎯 Repayment summary patch installation complete.")