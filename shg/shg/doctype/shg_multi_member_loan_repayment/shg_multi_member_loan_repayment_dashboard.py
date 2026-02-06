# Copyright (c) 2026, SHG Solutions
# License: MIT

import frappe


def get_data():
    return {
        "fieldname": "shg_multi_member_loan_repayment",
        "non_standard_fieldnames": {
            "Payment Entry": "reference_name",
            "SHG Loan Repayment": "parent"
        },
        "transactions": [
            {
                "label": "Related Documents",
                "items": ["SHG Loan Repayment", "Payment Entry"]
            }
        ]
    }