frappe.ui.form.on('SHG Member', {
    refresh(frm) {
        if (!frm.is_new() && frappe.user.has_role("System Manager")) {
            frm.add_custom_button(__('Delete Member (Purge)'), () => {
                frappe.confirm(
                    `⚠️ This will permanently delete member <b>${frm.doc.member_name}</b> 
                    and ALL related transactions (loans, contributions, invoices, payments, etc.).
                    <br><br><b>This action is irreversible.</b><br><br>Proceed?`,
                    () => {
                        frappe.call({
                            method: 'shg.shg.doctype.shg_member.shg_member.purge_member_data',
                            args: { member_id: frm.doc.name },
                            freeze: true,
                            freeze_message: 'Deleting all member records...',
                            callback: (r) => {
                                if (r.message) {
                                    frappe.msgprint(__('✅ Member and related data deleted successfully.'));
                                    frappe.set_route('List', 'SHG Member');
                                }
                            }
                        });
                    }
                );
            }, __('Danger Zone'));
        }
    }
});