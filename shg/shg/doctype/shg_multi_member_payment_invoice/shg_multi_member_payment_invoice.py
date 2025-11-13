# Copyright (c) 2025
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SHGMultiMemberPaymentInvoice(Document):
    """
    Child table row for SHG Multi Member Payment.

    Typical fields on this DocType:
    - invoice (Link to SHG Contribution Invoice)
    - member
    - member_name
    - contribution_type
    - invoice_date
    - due_date
    - amount
    - status
    - outstanding_amount
    - payment_amount

    All heavy logic (totals, validation, posting) is on the parent
    SHG Multi Member Payment DocType.
    """
    pass