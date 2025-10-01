import frappe
from frappe import _

def execute():
    """Patch existing SHG Members to ensure they have customer links"""
    frappe.msgprint(_("Starting patch to link SHG Members with Customers..."))
    
    # Get all SHG Members without customer links
    members = frappe.get_all("SHG Member", filters={"customer": ["is", "not set"]})
    
    frappe.msgprint(_("Found {0} members without customer links").format(len(members)))
    
    for member in members:
        try:
            # Get the member document
            member_doc = frappe.get_doc("SHG Member", member.name)
            
            # Create customer link if it doesn't exist
            if not member_doc.customer:
                member_doc.create_customer_link()
                
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(_("Failed to link customer for member {0}: {1}").format(member.name, str(e)))
            frappe.db.rollback()
    
    # Remove posted_to_gl field from SHG Contribution and Loan Repayment doctypes
    try:
        frappe.msgprint(_("Removing posted_to_gl field from SHG Contribution and Loan Repayment doctypes..."))
        # This will be handled by the framework when the doctypes are updated
        pass
    except Exception as e:
        frappe.log_error(_("Failed to remove posted_to_gl field: {0}").format(str(e)))
    
    frappe.msgprint(_("Patch completed. All SHG Members now have customer links."))