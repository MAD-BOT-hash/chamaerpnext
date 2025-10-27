# Copyright (c) 2025
# License: MIT

import frappe
from frappe.model.document import Document
from frappe.utils import flt

class SHGLoanRepayment(Document):
    def validate(self):
        if not self.loan:
            frappe.throw("Please select a Loan to apply this repayment to.")

        if not self.amount_paid or flt(self.amount_paid) <= 0:
            frappe.throw("Repayment amount must be greater than zero.")

        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        if loan_doc.docstatus != 1:
            frappe.throw(f"Loan {loan_doc.name} must be submitted before repayment.")

        if flt(self.amount_paid) > flt(loan_doc.balance_amount):
            frappe.throw(
                f"Repayment ({self.amount_paid}) exceeds remaining balance ({loan_doc.balance_amount})."
            )

    def on_submit(self):
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        paid_amount = flt(self.amount_paid or 0)

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
        paid_amount = flt(self.amount_paid or 0)

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