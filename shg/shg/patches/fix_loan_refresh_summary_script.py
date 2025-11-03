import frappe

def execute():
    """Fix loan refresh summary script by removing old Server Script and installing new Client Script."""
    
    # Disable old Server Script if it exists
    disable_old_server_script()
    
    # Ensure new Client Script is installed
    ensure_client_script()
    
    frappe.msgprint("✅ Loan refresh summary script fixed")

def disable_old_server_script():
    """Disable the outdated Server Script version if exists."""
    OLD_SERVER_SCRIPT_NAME = "SHG Loan | refresh_repayment_summary"
    
    if frappe.db.exists("Server Script", OLD_SERVER_SCRIPT_NAME):
        doc = frappe.get_doc("Server Script", OLD_SERVER_SCRIPT_NAME)
        doc.disabled = 1
        doc.save(ignore_permissions=True)
        frappe.msgprint(f"⚠️ Disabled old Server Script: {OLD_SERVER_SCRIPT_NAME}")

def ensure_client_script():
    """Create or update the client script for SHG Loan to add refresh button."""
    CLIENT_SCRIPT_NAME = "SHG Loan - Refresh Summary Button"
    CLIENT_SCRIPT_CONTENT = """frappe.ui.form.on('SHG Loan', {
  refresh(frm) {
    // Button
    frm.add_custom_button('📊 Recalculate Loan Summary (SHG)', () => {
      if (!frm.doc.name) return;
      frappe.call({
        method: 'shg.shg.doctype.shg_loan.api.refresh_repayment_summary',
        args: { loan_name: frm.doc.name },
        freeze: true,
        freeze_message: __('Updating repayment summary...'),
        callback: () => frm.reload_doc()
      });
    }).addClass('btn-primary');

    // Header indicator + dashboard progress
    const total = flt(frm.doc.total_payable || 0);
    const paid  = flt(frm.doc.total_repaid || 0);
    const bal   = Math.max(total - paid, 0);
    const overdue = flt(frm.doc.overdue_amount || 0);

    if (total > 0) {
      const pct = Math.min(Math.round((paid / total) * 100), 100);
      frm.dashboard.add_progress(__('Repayment Progress'), [
        { title: __('Paid'), percent: pct, progress_class: 'progress-bar-success' }
      ]);
    }

    frm.dashboard.set_headline(__('Outstanding: {0}{1}', [
      frappe.format(bal, { fieldtype: 'Currency' }),
      overdue > 0 ? __(' • Overdue: {0}', [frappe.format(overdue, { fieldtype: 'Currency' })]) : ''
    ]));
  }
});"""
    
    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        # Update existing client script
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.script = CLIENT_SCRIPT_CONTENT
        doc.enabled = 1
        doc.save(ignore_permissions=True)
        frappe.msgprint("🔃 Updated existing Client Script for refresh button.")
    else:
        # Create new client script
        client_script = frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "SHG Loan",
            "script": CLIENT_SCRIPT_CONTENT,
            "enabled": 1
        })
        client_script.insert(ignore_permissions=True)
        frappe.msgprint("✅ Installed new Client Script for refresh button.")