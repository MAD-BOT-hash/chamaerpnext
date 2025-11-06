import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    """
    Adds inline-repayment fields safely (idempotent):
      - Child Doctype: SHG Loan Repayment Schedule -> pay_now, amount_to_pay, remaining_amount (read-only)
      - Parent Doctype: SHG Loan -> makes sure the schedule grid is visible/editable and adds a totals section
    """
    # === Child DocType fields on SHG Loan Repayment Schedule ===
    child_fields = {
        "SHG Loan Repayment Schedule": [
            dict(fieldname="pay_now", label="Pay Now", fieldtype="Check", default="0", insert_after="status", allow_on_submit=1),
            dict(fieldname="amount_to_pay", label="Amount To Pay", fieldtype="Currency",
                 depends_on="eval:doc.pay_now==1", mandatory_depends_on="", insert_after="pay_now", allow_on_submit=1),
            dict(fieldname="remaining_amount", label="Remaining (This Installment)", fieldtype="Currency",
                 read_only=1, insert_after="amount_to_pay", allow_on_submit=1),
        ]
    }

    # === Parent additions on SHG Loan (totals & hints) ===
    parent_fields = {
        "SHG Loan": [
            dict(fieldtype="Section Break", fieldname="inline_repayment_sb", label="Inline Repayment",
                 insert_after="repayment_schedule"),  # adjust anchor if needed
            dict(fieldtype="HTML", fieldname="emi_hint", label="EMI Breakdown",
                 options="<div class='text-muted'>EMI = Principal + Interest. Totals update live as you tick <b>Pay Now</b>.</div>",
                 insert_after="inline_repayment_sb"),
            # If your schedule grid field already exists (common: 'repayment_schedule'), this does nothing.
            # If not, we add it pointed to the schedule child doctype.
            dict(fieldtype="Table", fieldname="repayment_schedule", label="Repayment Schedule",
                 options="SHG Loan Repayment Schedule", insert_after="emi_hint"),
            dict(fieldtype="Column Break", fieldname="inline_totals_cb", insert_after="repayment_schedule"),
            dict(fieldtype="Currency", fieldname="inline_total_selected", label="Selected To Pay (Now)", read_only=1,
                 insert_after="inline_totals_cb"),
            dict(fieldtype="Currency", fieldname="inline_overdue", label="Overdue Amount", read_only=1,
                 insert_after="inline_total_selected"),
            dict(fieldtype="Currency", fieldname="inline_outstanding", label="Outstanding (P+I)", read_only=1,
                 insert_after="inline_overdue"),
        ]
    }

    create_custom_fields(child_fields, ignore_validate=True)
    create_custom_fields(parent_fields, ignore_validate=True)

    # Ensure columns exist at DB level (idempotent, safe on MariaDB/MySQL)
    _sql_add_column("tabSHG Loan Repayment Schedule", "pay_now", "int(1) not null default 0")
    _sql_add_column("tabSHG Loan Repayment Schedule", "amount_to_pay", "decimal(21,9) null")
    _sql_add_column("tabSHG Loan Repayment Schedule", "remaining_amount", "decimal(21,9) null")


def _sql_add_column(table, column, ddl_type):
    if not frappe.db.has_column(table.replace("tab", ""), column):
        frappe.db.sql(f"alter table `{table}` add column `{column}` {ddl_type}")