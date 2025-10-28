import frappe

def get_default_company():
    """Fetch the default company from SHG Settings (safe fallback)."""
    try:
        settings = frappe.get_single("SHG Settings")
        if settings and settings.company:
            return settings.company
    except Exception as e:
        frappe.log_error(f"Error fetching default company: {e}", "get_default_company")
    return None

def ensure_company_field(doc, method=None):
    """Global hook to attach company from SHG Settings if missing."""
    if not getattr(doc, "company", None):
        default_company = get_default_company()
        if default_company:
            doc.company = default_company
        else:
            frappe.throw("Default Company not set in SHG Settings.")