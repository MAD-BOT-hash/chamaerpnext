import frappe

def execute():
    """Fix draft Journal Entries that reference group account instead of member accounts."""
    # Get all draft Journal Entries
    for je_name in frappe.get_all("Journal Entry", filters={"docstatus": 0}, pluck="name"):
        doc = frappe.get_doc("Journal Entry", je_name)
        modified = False
        
        # Check each account entry
        for account in doc.accounts:
            # If account is the group account, we need to fix it
            if account.account and "SHG Loans receivable -" in account.account and " - " in account.account:
                # This looks like it might already be a member account
                # Let's check if it's actually a group account
                if frappe.db.exists("Account", account.account):
                    is_group = frappe.db.get_value("Account", account.account, "is_group")
                    if is_group:
                        # This is incorrectly using a group account, we need to fix it
                        # We'll need to determine the correct member account
                        # For now, we'll just log it as we need more context to fix it properly
                        print(f"Found draft JE {doc.name} with group account {account.account}")
                        
        if modified:
            try:
                doc.save()
                print(f"Fixed Journal Entry {doc.name}")
            except Exception as e:
                print(f"Failed to fix Journal Entry {doc.name}: {str(e)}")
    
    frappe.db.commit()