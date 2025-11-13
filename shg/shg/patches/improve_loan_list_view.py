import frappe

def execute():
    """Improve loan list view with better status indicators"""
    
    # Update list view settings for SHG Loan
    update_list_view_settings()
    
    frappe.msgprint("✅ Loan list view enhanced with better status indicators")

def update_list_view_settings():
    """Update list view settings with enhanced indicators"""
    
    list_view_settings = {
        "doctype": "List View Settings",
        "name": "SHG Loan",
        "fields": [],
        "order_by": "creation desc",
        "filters": [],
        "add_fields": ["balance_amount", "overdue_amount", "total_payable", "total_repaid", "docstatus", "loan_status"],
        "get_indicator": """
if (!doc.docstatus) return [__("Draft"), "gray", "docstatus,=,0"];
let total = doc.total_payable || 0;
let paid = doc.total_repaid || 0;
let overdue = doc.overdue_amount || 0;
let balance = doc.balance_amount || 0;
let status = doc.loan_status || "";
let percent = total > 0 ? Math.round((paid / total) * 100) : 0;

// Status-based indicators
if (status === "Completed") return [__("Completed"), "green", "loan_status,=,Completed"];
if (status === "Overdue") return [__("Overdue"), "red", "loan_status,=,Overdue"];
if (status === "Defaulted") return [__("Defaulted"), "orange", "loan_status,=,Defaulted"];
if (status === "Active") {
    if (balance <= 0) return [__(`${percent}% Paid ✔️`), "green", `name,=,${doc.name}`];
    if (overdue > 0) return [__(`${percent}% Paid – Overdue: Sh ${overdue}`), "red", `name,=,${doc.name}`];
    return [__(`${percent}% Paid – Bal: Sh ${balance}`), "blue", `name,=,${doc.name}`];
}
return [__(status), "gray", `loan_status,=,${status}`];
"""
    }
    
    # Create or update the list view settings
    if frappe.db.exists("List View Settings", "SHG Loan"):
        doc = frappe.get_doc("List View Settings", "SHG Loan")
        doc.update(list_view_settings)
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc(list_view_settings).insert(ignore_permissions=True)
    
    frappe.db.commit()