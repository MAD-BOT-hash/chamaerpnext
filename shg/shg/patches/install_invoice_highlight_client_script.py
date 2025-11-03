import frappe

def execute():
    """Install client script to highlight closed invoices in SHG Multi Member Payment."""
    
    # Install or update the client script
    install_client_script()
    
    frappe.msgprint("✅ Installed client script for highlighting closed invoices")

def install_client_script():
    """Install or update the client script for SHG Multi Member Payment."""
    CLIENT_SCRIPT_NAME = "SHG Multi Member Payment - Invoice Highlight"
    
    # Read the client script content
    script_path = frappe.get_app_path("shg", "shg", "doctype", "shg_multi_member_payment", "shg_multi_member_payment_invoice_highlight.js")
    with open(script_path, "r") as f:
        script_content = f.read()
    
    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        # Update existing client script
        client_script = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        client_script.script = script_content
        client_script.enabled = 1
        client_script.save(ignore_permissions=True)
        frappe.msgprint("Updated existing client script for invoice highlighting")
    else:
        # Create new client script
        client_script = frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "SHG Multi Member Payment",
            "script": script_content,
            "enabled": 1
        })
        client_script.insert(ignore_permissions=True)
        frappe.msgprint("Created new client script for invoice highlighting")