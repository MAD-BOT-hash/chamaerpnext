# Copyright (c) 2025
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from shg.shg.utils.company_utils import get_default_company


class SHGMultiMemberPayment(Document):
    def before_validate(self):
        """Auto-set company from SHG Settings"""
        self.company = self.company or get_default_company()
        
        # Auto-calculate total payment amount
        total = 0.0
        if self.invoices:
            for row in self.invoices:
                total += flt(row.payment_amount or 0)
        self.total_payment_amount = total
    
    def validate(self):
        """Validate bulk payment"""
        # Validate total_payment_amount > 0
        if flt(self.total_payment_amount) <= 0:
            frappe.throw(_("Total payment amount must be greater than zero"))
            
        # Validate no duplicate invoice rows
        invoice_names = []
        for row in self.invoices:
            if row.invoice in invoice_names:
                frappe.throw(_("Duplicate invoice {0} found in rows").format(row.invoice))
            invoice_names.append(row.invoice)
            
        # Validate referenced docs exist and have outstanding amounts
        from shg.shg.utils.payment_utils import get_outstanding
        for row in self.invoices:
            if not frappe.db.exists("SHG Contribution Invoice", row.invoice):
                frappe.throw(_("Invoice {0} does not exist").format(row.invoice))
                
            outstanding = get_outstanding("SHG Contribution Invoice", row.invoice)
            if outstanding < flt(row.payment_amount):
                frappe.throw(_("Invoice {0} has only {1} outstanding, cannot allocate {2}").format(
                    row.invoice, outstanding, row.payment_amount))
    
    def on_submit(self):
        """Process bulk payment"""
        from shg.shg.utils.payment_utils import process_bulk_payment
        process_bulk_payment(self)
    
    def on_cancel(self):
        """Cancel Payment Entry & reverse statuses"""
        from shg.shg.utils.payment_utils import cancel_linked_payment_entry
        cancel_linked_payment_entry(self)
