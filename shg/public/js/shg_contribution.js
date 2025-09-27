frappe.ui.form.on('SHG Contribution', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.posted_to_gl) {
            frm.dashboard.add_indicator(__('Posted to General Ledger'), 'green');
        }
        
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Print Receipt'), function() {
                frappe.utils.print(
                    frm.doc.doctype,
                    frm.doc.name,
                    'SHG Contribution Receipt'
                );
            });
        }
    },
    
    member: function(frm) {
        if (frm.doc.member) {
            // Get member details and suggested amount
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SHG Member',
                    name: frm.doc.member
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('member_name', r.message.member_name);
                        
                        if (r.message.membership_status !== 'Active') {
                            frappe.msgprint(__('Warning: This member is not active'));
                        }
                    }
                }
            });
            
            get_suggested_contribution_amount(frm);
        }
    },
    
    contribution_type: function(frm) {
        if (frm.doc.contribution_type && frm.doc.member) {
            get_suggested_contribution_amount(frm);
        }
    },
});