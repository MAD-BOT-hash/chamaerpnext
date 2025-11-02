import frappe

def execute():
    """Update SHG Loan form layout: reorganize sections, ensure UI clarity."""

    doctype = "SHG Loan"
    print(f"Updating layout for: {doctype} ...")

    # Check if Custom Form exists for us to modify
    if not frappe.db.exists("Custom Form", doctype):
        print("❌ Custom Form for SHG Loan not found. Skipping patch.")
        return

    custom_form = frappe.get_doc("Custom Form", doctype)

    # Define new layout
    custom_form.fields = [

        # Section: Loan Header
        {"fieldname": "section_loan_info", "fieldtype": "Section Break", "label": "Loan Information"},
        {"fieldname": "loan_type", "fieldtype": "Link", "options": "Loan Type"},
        {"fieldname": "loan_amount", "fieldtype": "Currency"},
        {"fieldname": "interest_rate", "fieldtype": "Float", "label": "Interest Rate (%)"},
        {"fieldname": "loan_period_months", "fieldtype": "Int", "label": "Loan Period (Months)"},
        {"fieldname": "interest_type", "fieldtype": "Select", "options": "Flat Rate\nReducing Balance"},
        {"fieldname": "repayment_frequency", "fieldtype": "Select", "options": "Monthly\nWeekly"},

        # Section: Repayment Details
        {"fieldname": "section_repayment_details", "fieldtype": "Section Break", "label": "Repayment Details"},
        {"fieldname": "repayment_start_date", "fieldtype": "Date"},
        {"fieldname": "monthly_installment", "fieldtype": "Currency", "read_only": 1},
        {"fieldname": "total_payable", "fieldtype": "Currency", "read_only": 1},
        {"fieldname": "balance_amount", "fieldtype": "Currency", "read_only": 1},
        {"fieldname": "total_repaid", "fieldtype": "Currency", "read_only": 1},
        {"fieldname": "overdue_amount", "fieldtype": "Currency", "read_only": 1},

        # Section: Disbursement Details
        {"fieldname": "section_disbursement", "fieldtype": "Section Break", "label": "Disbursement"},
        {"fieldname": "disbursement_date", "fieldtype": "Date"},
        {"fieldname": "disbursed_on", "fieldtype": "Datetime"},
        {"fieldname": "posted_to_gl", "fieldtype": "Check", "read_only": 1},
        {"fieldname": "journal_entry", "fieldtype": "Link", "options": "Journal Entry", "read_only": 1},

    ]

    # Save the changes
    custom_form.save()
    frappe.db.commit()

    print("✅ SHG Loan form layout updated successfully.")