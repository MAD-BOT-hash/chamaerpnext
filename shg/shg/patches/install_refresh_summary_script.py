import frappe

def execute():
    """Install or update the '🔄 Refresh Summary' Client Script on SHG Loan"""

    script_name = "SHG Loan Refresh Summary"
    target_doctype = "SHG Loan"

    script_content = """
frappe.ui.form.on('SHG Loan', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button('🔄 Refresh Summary', () => {
                frappe.call({
                    method: 'shg.shg.doctype.shg_loan.shg_loan.refresh_repayment_summary',
                    args: { loan_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __('Refreshing repayment summary...'),
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __('Summary refreshed successfully!'),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }).addClass('btn-primary');
        }
    }
});
    """.strip()

    existing = frappe.db.exists("Client Script", script_name)
    if existing:
        doc = frappe.get_doc("Client Script", script_name)
        doc.script = script_content
        doc.dt = target_doctype
        doc.save()
        frappe.logger().info(f"Updated existing Client Script: {script_name}")
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": script_name,
            "dt": target_doctype,
            "enabled": 1,
            "script": script_content
        }).insert()
        frappe.logger().info(f"Installed new Client Script: {script_name}")

    frappe.db.commit()
    frappe.logger().info("✅ Refresh Summary Client Script installation completed.")