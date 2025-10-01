import frappe
from frappe import _

def execute():
    """
    Detect and export legacy GL entries with invalid reference types.
    This patch will:
    1. Find all GL Entry rows where reference_type is an invalid SHG document type
    2. Export them to a CSV file for manual reconciliation
    3. Mark the corresponding SHG documents with posted_to_gl = 0 so they can be re-posted
    """
    
    # List of invalid reference types that need to be detected
    invalid_reference_types = [
        "SHG Contribution",
        "SHG Loan", 
        "SHG Loan Repayment",
        "SHG Meeting Fine"
    ]
    
    print("Detecting legacy GL entries with invalid reference types...")
    
    # Find all GL Entry rows with invalid reference types
    bad_gl_entries = []
    for ref_type in invalid_reference_types:
        entries = frappe.get_all("GL Entry", 
            filters={"reference_type": ref_type},
            fields=["name", "voucher_no", "account", "debit", "credit", "against_voucher", 
                   "posting_date", "company", "party_type", "party", "reference_name"]
        )
        bad_gl_entries.extend(entries)
    
    if not bad_gl_entries:
        print("No legacy GL entries with invalid reference types found.")
        return
    
    print(f"Found {len(bad_gl_entries)} legacy GL entries with invalid reference types.")
    
    # Export to CSV file
    csv_content = "GL Entry Name,Voucher No,Account,Debit,Credit,Against Voucher,Posting Date,Company,Party Type,Party,Reference Name,Reference Type\n"
    for entry in bad_gl_entries:
        csv_content += f"{entry.name},{entry.voucher_no},{entry.account},{entry.debit},{entry.credit},{entry.against_voucher},{entry.posting_date},{entry.company},{entry.party_type},{entry.party},{entry.reference_name},{entry.reference_type}\n"
    
    # Save CSV file
    csv_file = frappe.get_doc({
        "doctype": "File",
        "file_name": "legacy_gl_entries.csv",
        "attached_to_doctype": "SHG Settings",
        "content": csv_content
    })
    csv_file.insert()
    
    print(f"Exported legacy GL entries to CSV file: {csv_file.file_url}")
    
    # Mark corresponding SHG documents with posted_to_gl = 0
    updated_docs = 0
    for entry in bad_gl_entries:
        try:
            # Try to find and update the corresponding SHG document
            if entry.reference_type == "SHG Contribution" and entry.reference_name:
                if frappe.db.exists("SHG Contribution", entry.reference_name):
                    frappe.db.set_value("SHG Contribution", entry.reference_name, "posted_to_gl", 0)
                    updated_docs += 1
                    
            elif entry.reference_type == "SHG Loan" and entry.reference_name:
                if frappe.db.exists("SHG Loan", entry.reference_name):
                    frappe.db.set_value("SHG Loan", entry.reference_name, "posted_to_gl", 0)
                    updated_docs += 1
                    
            elif entry.reference_type == "SHG Loan Repayment" and entry.reference_name:
                if frappe.db.exists("SHG Loan Repayment", entry.reference_name):
                    frappe.db.set_value("SHG Loan Repayment", entry.reference_name, "posted_to_gl", 0)
                    updated_docs += 1
                    
            elif entry.reference_type == "SHG Meeting Fine" and entry.reference_name:
                if frappe.db.exists("SHG Meeting Fine", entry.reference_name):
                    frappe.db.set_value("SHG Meeting Fine", entry.reference_name, "posted_to_gl", 0)
                    updated_docs += 1
                    
        except Exception as e:
            print(f"Error updating document {entry.reference_name}: {str(e)}")
    
    print(f"Updated {updated_docs} SHG documents to allow re-posting.")
    print("Please review the CSV file and manually reconcile the legacy GL entries.")
    print("After reconciliation, you can re-submit the SHG documents to create proper Journal Entries or Payment Entries.")

# For testing purposes
if __name__ == "__main__":
    execute()