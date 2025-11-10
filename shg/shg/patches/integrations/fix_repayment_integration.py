import frappe

def execute():
    """
    Fix repayment integration by ensuring all schedule rows have valid status values.
    Replace any invalid "Due" status with "Pending" as per SHG Loan Repayment Schedule doctype specification.
    """
    # Fix repayment schedule status values
    for loan in frappe.get_all("SHG Loan", fields=["name"]):
        doc = frappe.get_doc("SHG Loan", loan.name)
        if not hasattr(doc, "repayment_schedule") or not doc.repayment_schedule:
            continue
            
        updated = False
        for row in doc.repayment_schedule:
            # Fix invalid status values
            if getattr(row, 'status', None) == "Due":
                row.status = "Pending"
                updated = True
            elif not getattr(row, 'status', None):
                row.status = "Pending"
                updated = True
                
        if updated:
            # Allow updates on submitted loans
            doc.flags.ignore_validate_update_after_submit = True
            doc.save(ignore_permissions=True)
            
    frappe.db.commit()
    frappe.msgprint("Repayment integration fix completed successfully.")