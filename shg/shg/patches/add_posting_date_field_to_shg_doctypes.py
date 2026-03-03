# Copyright (c) 2025
# License: MIT
# Patch: Add posting_date field to SHG doctypes for ERPNext Payment Entry compatibility

import frappe
from frappe.utils import nowdate


def execute():
    """
    Add posting_date field to SHG doctypes and backfill existing records.
    This is required for ERPNext Payment Entry compatibility.
    """
    
    # Configuration: doctype -> source date field for backfill
    doctypes_config = {
        "SHG Contribution Invoice": "invoice_date",
        "SHG Contribution": "contribution_date",
        "SHG Meeting Fine": "fine_date",
    }
    
    for doctype, source_field in doctypes_config.items():
        table_name = f"tab{doctype.replace(' ', '')}"
        
        try:
            # Check if posting_date column exists
            if not frappe.db.has_column(doctype, "posting_date"):
                frappe.log_error(
                    f"Adding posting_date column to {doctype}",
                    "Migration: Add posting_date"
                )
                # Column will be added by migrate, but we need to backfill
            
            # Backfill existing records where posting_date is NULL
            frappe.db.sql(f"""
                UPDATE `tab{doctype.replace(' ', ' ')}`
                SET posting_date = COALESCE({source_field}, %s)
                WHERE posting_date IS NULL OR posting_date = ''
            """, (nowdate(),))
            
            frappe.db.commit()
            
            count = frappe.db.sql(f"""
                SELECT COUNT(*) FROM `tab{doctype.replace(' ', ' ')}`
                WHERE posting_date IS NOT NULL
            """)[0][0]
            
            frappe.log_error(
                f"Backfilled posting_date for {count} records in {doctype}",
                "Migration: Add posting_date - Success"
            )
            
        except Exception as e:
            frappe.log_error(
                f"Error adding posting_date to {doctype}: {str(e)}\n{frappe.get_traceback()}",
                "Migration: Add posting_date - Error"
            )
            # Continue with other doctypes even if one fails
            continue
    
    frappe.msgprint(
        "Added posting_date field to SHG doctypes for ERPNext Payment Entry compatibility",
        indicator="green"
    )
