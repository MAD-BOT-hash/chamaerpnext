# Copyright (c) 2025
# License: MIT

import frappe
from frappe.model.document import Document


class SHGPaymentEntry(Document):
    """
    Wrapper DocType for summarising or grouping SHG-related payments.

    NOTE:
    - Core GL impact is handled by ERPNext's standard Payment Entry DocType.
    - This DocType is intended as a logical wrapper / reporting anchor.
    - You can later add hooks like validate(), on_submit(), etc. here if needed.
    """
    pass