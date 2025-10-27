# Copyright (c) 2025
# License: MIT. All rights reserved.

import frappe
from frappe.model.document import Document

class SHGLoanRepayment(Document):
    def validate(self):
        """Perform basic validation before submission."""
        if not self.loan:
            frappe.throw("Please select a Loan to apply this repayment to.")

        if not self.amount_paid or self.amount_paid <= 0:
            frappe.throw("Repayment amount must be greater than zero.")

        loan_doc = frappe.get_doc("SHG Loan", self.loan)

        if loan_doc.docstatus != 1:
            frappe.throw(f"Loan {loan_doc.name} must be submitted before repayment.")

        if self.amount_paid > loan_doc.balance_amount:
            frappe.throw(
                f"Repayment ({self.amount_paid}) cannot exceed remaining balance ({loan_doc.balance_amount})."
            )

    def on_submit(self):
        """Handle updates when a repayment is submitted."""
        if not self.loan:
            return

        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        paid_amount = float(self.amount_paid or 0)

        # Allow safe modification of submitted loan
        loan_doc.flags.ignore_validate_update_after_submit = True

        # Compute new balance
        new_balance = float(loan_doc.balance_amount or 0) - paid_amount
        if new_balance < 0:
            frappe.throw(
                f"Repayment exceeds remaining balance. Current balance: {loan_doc.balance_amount}"
            )

        # Update fields
        loan_doc.balance_amount = new_balance
        loan_doc.last_repayment_date = self.posting_date

        # Update loan status automatically
        loan_doc.status = "Paid" if new_balance == 0 else "Partially Paid"

        # Save and commit safely
        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Add audit comment
        loan_doc.add_comment(
            "Edit",
            f"Loan repayment of {paid_amount} processed via {self.name}. Remaining balance: {new_balance}"
        )

        frappe.msgprint(
            f"✅ Loan {loan_doc.name} updated successfully. Remaining balance: {new_balance}"
        )

    def on_cancel(self):
        """Handle reversal logic when repayment is cancelled."""
        if not self.loan:
            return

        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        paid_amount = float(self.amount_paid or 0)

        # Allow safe modification after submit
        loan_doc.flags.ignore_validate_update_after_submit = True

        # Reverse the repayment
        loan_doc.balance_amount = float(loan_doc.balance_amount or 0) + paid_amount
        loan_doc.status = "Disbursed"

        loan_doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Log reversal
        loan_doc.add_comment(
            "Edit",
            f"⚠️ Repayment {self.name} cancelled. Restored balance: {loan_doc.balance_amount}"
        )

        frappe.msgprint(f"⚠️ Loan {loan_doc.name} balance restored after cancellation.")

# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_repayment(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()


def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger()