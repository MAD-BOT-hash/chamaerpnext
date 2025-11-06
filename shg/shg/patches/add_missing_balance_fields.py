import frappe

def execute():
    """Ensure missing financial fields exist in SHG Loan."""
    loan_fields = [
        {"fieldname": "total_payable", "fieldtype": "Currency", "label": "Total Payable"},
        {"fieldname": "total_repaid", "fieldtype": "Currency", "label": "Total Repaid"},
        {"fieldname": "outstanding_balance", "fieldtype": "Currency", "label": "Outstanding Balance"},
        {"fieldname": "loan_balance", "fieldtype": "Currency", "label": "Loan Balance"},
        {"fieldname": "balance_amount", "fieldtype": "Currency", "label": "Balance Amount"},
        {"fieldname": "overdue_amount", "fieldtype": "Currency", "label": "Overdue Amount"},
    ]

    for field in loan_fields:
        if not frappe.db.has_column("SHG Loan", field["fieldname"]):
            frappe.db.add_column("SHG Loan", field["fieldname"], field["fieldtype"])
            frappe.msgprint(f"Added missing field {field['fieldname']} to SHG Loan")