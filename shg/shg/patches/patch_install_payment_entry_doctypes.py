import frappe

def execute():
    """Install SHG Payment Entry doctypes"""
    # Create SHG Payment Entry Detail doctype
    if not frappe.db.exists("DocType", "SHG Payment Entry Detail"):
        frappe.get_doc({
            "doctype": "DocType",
            "name": "SHG Payment Entry Detail",
            "module": "SHG",
            "custom": 0,
            "istable": 1,
            "fields": [
                {
                    "fieldname": "invoice_type",
                    "fieldtype": "Select",
                    "label": "Invoice Type",
                    "options": "SHG Contribution Invoice",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "invoice",
                    "fieldtype": "Link",
                    "label": "Invoice",
                    "options": "SHG Contribution Invoice",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "invoice_date",
                    "fieldtype": "Date",
                    "label": "Invoice Date",
                    "read_only": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "outstanding_amount",
                    "fieldtype": "Currency",
                    "label": "Outstanding Amount",
                    "read_only": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "amount",
                    "fieldtype": "Currency",
                    "label": "Amount",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "column_break_4",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "description",
                    "fieldtype": "Small Text",
                    "label": "Description",
                    "read_only": 1
                }
            ]
        }).insert()
        
    # Create SHG Payment Entry doctype
    if not frappe.db.exists("DocType", "SHG Payment Entry"):
        frappe.get_doc({
            "doctype": "DocType",
            "name": "SHG Payment Entry",
            "module": "SHG",
            "custom": 0,
            "is_submittable": 1,
            "autoname": "naming_series:",
            "fields": [
                {
                    "fieldname": "naming_series",
                    "fieldtype": "Select",
                    "label": "Naming Series",
                    "options": "SHPAY-.YYYY.-.#####",
                    "reqd": 1
                },
                {
                    "fieldname": "payment_details_section",
                    "fieldtype": "Section Break",
                    "label": "Payment Details"
                },
                {
                    "fieldname": "member",
                    "fieldtype": "Link",
                    "label": "Member",
                    "options": "SHG Member",
                    "reqd": 1
                },
                {
                    "fieldname": "member_name",
                    "fieldtype": "Data",
                    "label": "Member Name",
                    "read_only": 1,
                    "fetch_from": "member.member_name"
                },
                {
                    "fieldname": "payment_date",
                    "fieldtype": "Date",
                    "label": "Payment Date",
                    "reqd": 1,
                    "default": "Today"
                },
                {
                    "fieldname": "payment_method",
                    "fieldtype": "Select",
                    "label": "Payment Method",
                    "options": "Cash\nBank Transfer\nMobile Money\nCheque",
                    "reqd": 1
                },
                {
                    "fieldname": "total_amount",
                    "fieldtype": "Currency",
                    "label": "Total Amount",
                    "reqd": 1,
                    "read_only": 1
                },
                {
                    "fieldname": "column_break_4",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "reference_number",
                    "fieldtype": "Data",
                    "label": "Reference Number"
                },
                {
                    "fieldname": "description",
                    "fieldtype": "Small Text",
                    "label": "Description"
                },
                {
                    "fieldname": "accounting_section",
                    "fieldtype": "Section Break",
                    "label": "Accounting"
                },
                {
                    "fieldname": "debit_account",
                    "fieldtype": "Link",
                    "label": "Debit Account",
                    "options": "Account",
                    "reqd": 1
                },
                {
                    "fieldname": "credit_account",
                    "fieldtype": "Link",
                    "label": "Credit Account",
                    "options": "Account",
                    "reqd": 1
                },
                {
                    "fieldname": "payment_entries_section",
                    "fieldtype": "Section Break",
                    "label": "Payment Entries"
                },
                {
                    "fieldname": "payment_entries",
                    "fieldtype": "Table",
                    "label": "Payment Entries",
                    "options": "SHG Payment Entry Detail"
                }
            ],
            "permissions": [
                {
                    "create": 1,
                    "delete": 1,
                    "email": 1,
                    "export": 1,
                    "print": 1,
                    "read": 1,
                    "report": 1,
                    "role": "SHG Admin",
                    "share": 1,
                    "submit": 1,
                    "write": 1
                },
                {
                    "create": 1,
                    "email": 1,
                    "export": 1,
                    "print": 1,
                    "read": 1,
                    "report": 1,
                    "role": "SHG Treasurer",
                    "share": 1,
                    "submit": 1,
                    "write": 1
                },
                {
                    "email": 1,
                    "export": 1,
                    "print": 1,
                    "read": 1,
                    "report": 1,
                    "role": "SHG Auditor"
                }
            ]
        }).insert()