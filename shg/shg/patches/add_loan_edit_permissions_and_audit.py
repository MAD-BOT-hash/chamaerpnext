import frappe
from frappe.utils import now_datetime, get_fullname

def execute():
    """Add edit permissions for loan details and implement audit trail"""
    
    # 1. Add custom fields for tracking loan edits
    add_audit_fields()
    
    # 2. Update permissions for SHG Loan doctype
    update_loan_permissions()
    
    # 3. Create server script for audit trail
    create_audit_server_script()
    
    frappe.msgprint("✅ Enhanced loan edit permissions and audit trail implemented")

def add_audit_fields():
    """Add custom fields for tracking edits"""
    # Last edited by field
    if not frappe.db.exists("Custom Field", {"dt": "SHG Loan", "fieldname": "last_edited_by"}):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "SHG Loan",
            "fieldname": "last_edited_by",
            "label": "Last Edited By",
            "fieldtype": "Data",
            "read_only": 1,
            "allow_on_submit": 1,
            "insert_after": "modified_by"
        }).insert(ignore_permissions=True)
    
    # Last edited on field
    if not frappe.db.exists("Custom Field", {"dt": "SHG Loan", "fieldname": "last_edited_on"}):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "SHG Loan",
            "fieldname": "last_edited_on",
            "label": "Last Edited On",
            "fieldtype": "Datetime",
            "read_only": 1,
            "allow_on_submit": 1,
            "insert_after": "last_edited_by"
        }).insert(ignore_permissions=True)
    
    # Edit log field
    if not frappe.db.exists("Custom Field", {"dt": "SHG Loan", "fieldname": "edit_log"}):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "SHG Loan",
            "fieldname": "edit_log",
            "label": "Edit Log",
            "fieldtype": "Table",
            "options": "SHG Loan Edit Log",
            "allow_on_submit": 1,
            "insert_after": "last_edited_on"
        }).insert(ignore_permissions=True)
    
    frappe.db.commit()

def update_loan_permissions():
    """Update permissions to allow admins/treasurers to edit loan details"""
    # Get SHG Loan doctype
    if frappe.db.exists("DocType", "SHG Loan"):
        loan_doctype = frappe.get_doc("DocType", "SHG Loan")
        
        # Ensure SHG Admin and SHG Treasurer roles have write permissions
        roles_updated = False
        for perm in loan_doctype.permissions:
            if perm.role in ["SHG Admin", "SHG Treasurer"] and not perm.write:
                perm.write = 1
                roles_updated = True
        
        if roles_updated:
            loan_doctype.save(ignore_permissions=True)
    
    frappe.db.commit()

def create_audit_server_script():
    """Create server script to track loan edits"""
    script_name = "SHG Loan - Audit Trail"
    
    script_content = """
# Track changes to loan details
import frappe
from frappe.utils import now_datetime, get_fullname

def before_save(doc, method):
    # Only track changes for submitted loans
    if doc.docstatus != 1:
        return
    
    # Check for changes in key fields
    key_fields = ["disbursement_date", "interest_rate", "loan_period_months"]
    changed_fields = []
    
    # Get the previous version of the document
    if doc.name:
        try:
            previous = frappe.get_doc("SHG Loan", doc.name)
            for field in key_fields:
                if getattr(doc, field, None) != getattr(previous, field, None):
                    changed_fields.append(field)
        except:
            pass
    
    # If any key fields changed, log the edit
    if changed_fields:
        # Update last edited info
        doc.last_edited_by = get_fullname(frappe.session.user)
        doc.last_edited_on = now_datetime()
        
        # Add to edit log
        log_entry = {
            "edited_by": get_fullname(frappe.session.user),
            "edited_on": now_datetime(),
            "changed_fields": ", ".join(changed_fields)
        }
        doc.append("edit_log", log_entry)
        
        # Add comment to document
        comment = f"Loan details edited by {get_fullname(frappe.session.user)} on {now_datetime()}. Changed fields: {', '.join(changed_fields)}"
        frappe.get_doc({
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "SHG Loan",
            "reference_name": doc.name,
            "content": comment
        }).insert(ignore_permissions=True)
"""

    # Create or update the server script
    if frappe.db.exists("Server Script", script_name):
        script = frappe.get_doc("Server Script", script_name)
        script.script = script_content
        script.enabled = 1
        script.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Server Script",
            "name": script_name,
            "script_type": "DocType Event",
            "reference_doctype": "SHG Loan",
            "event": "Before Save",
            "script": script_content,
            "enabled": 1
        }).insert(ignore_permissions=True)
    
    frappe.db.commit()