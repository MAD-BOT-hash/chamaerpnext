import frappe

def execute():
    """Ensure all required fields exist on SHG Loan, Repayment Schedule and Repayment doctypes."""
    
    # Check and add missing fields to SHG Loan doctype
    ensure_shg_loan_fields()
    
    # Check and add missing fields to SHG Loan Repayment Schedule doctype
    ensure_shg_loan_repayment_schedule_fields()
    
    # Check and add missing fields to SHG Loan Repayment doctype
    ensure_shg_loan_repayment_fields()
    
    frappe.msgprint("Ensured all required fields exist on loan doctypes")

def ensure_shg_loan_fields():
    """Ensure SHG Loan doctype has all required fields."""
    # Fields to check/add
    required_fields = [
        {
            "fieldname": "disbursed_on",
            "label": "Disbursed On",
            "fieldtype": "Datetime",
            "insert_after": "disbursement_date",
            "read_only": 1,
            "allow_on_submit": 1
        },
        {
            "fieldname": "total_interest_payable",
            "label": "Total Interest Payable",
            "fieldtype": "Currency",
            "insert_after": "total_payable",
            "read_only": 1,
            "precision": 2
        },
        {
            "fieldname": "total_payable_amount",
            "label": "Total Payable Amount",
            "fieldtype": "Currency",
            "insert_after": "total_interest_payable",
            "read_only": 1,
            "precision": 2
        }
    ]
    
    for field in required_fields:
        if not frappe.db.exists("Custom Field", {"dt": "SHG Loan", "fieldname": field["fieldname"]}):
            custom_field = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "SHG Loan",
                **field
            })
            custom_field.insert(ignore_permissions=True)

def ensure_shg_loan_repayment_schedule_fields():
    """Ensure SHG Loan Repayment Schedule doctype has all required fields."""
    # Fields to check/add
    required_fields = [
        {
            "fieldname": "actual_payment_date",
            "label": "Actual Payment Date",
            "fieldtype": "Date",
            "insert_after": "due_date",
            "read_only": 1
        },
        {
            "fieldname": "reversed",
            "label": "Reversed",
            "fieldtype": "Check",
            "insert_after": "payment_entry",
            "read_only": 1
        }
    ]
    
    for field in required_fields:
        if not frappe.db.exists("Custom Field", {"dt": "SHG Loan Repayment Schedule", "fieldname": field["fieldname"]}):
            custom_field = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "SHG Loan Repayment Schedule",
                **field
            })
            custom_field.insert(ignore_permissions=True)

def ensure_shg_loan_repayment_fields():
    """Ensure SHG Loan Repayment doctype has all required fields."""
    # Fields to check/add
    required_fields = [
        {
            "fieldname": "reference_schedule_row",
            "label": "Reference Schedule Row",
            "fieldtype": "Link",
            "options": "SHG Loan Repayment Schedule",
            "insert_after": "interest_amount"
        }
    ]
    
    for field in required_fields:
        if not frappe.db.exists("Custom Field", {"dt": "SHG Loan Repayment", "fieldname": field["fieldname"]}):
            custom_field = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "SHG Loan Repayment",
                **field
            })
            custom_field.insert(ignore_permissions=True)