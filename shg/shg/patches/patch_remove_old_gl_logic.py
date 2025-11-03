import frappe

def execute():
    """Compatibility shim.
    This patch used to remove legacy GL logic. It is now a no-op so old
    sites can migrate cleanly without failing on missing module."""
    # Optional: quietly disable any legacy server scripts if present.
    legacy_names = [
        "SHG Loan | Legacy GL Post",
        "SHG Loan | Legacy Post To Ledger",
    ]
    for n in legacy_names:
        if frappe.db.exists("Server Script", n):
            ss = frappe.get_doc("Server Script", n)
            if not ss.disabled:
                ss.disabled = 1
                ss.save()
    frappe.db.commit()