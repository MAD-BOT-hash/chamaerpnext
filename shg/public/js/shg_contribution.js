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
            
            frm.add_custom_button(__('Send SMS Receipt'), function() {
                frappe.call({
                    method: 'send_payment_confirmation',
                    doc: frm.doc,
                    callback: function(r) {
                        frappe.msgprint(__('SMS receipt sent successfully'));
                    }
                });
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
    
    amount: function(frm) {
        if (frm.doc.amount && frm.doc.contribution_type === 'Regular Weekly') {
            // Validate against minimum contribution
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'SHG Settings',
                    fieldname: 'minimum_contribution'
                },
                callback: function(r) {
                    if (r.message && r.message.minimum_contribution) {
                        let min_amount = r.message.minimum_contribution;
                        if (frm.doc.amount < min_amount) {
                            frappe.msgprint({
                                title: __('Below Minimum'),
                                message: __('Contribution amount is below the minimum of KES {0}', [format_currency(min_amount, 'KES')]),
                                indicator: 'orange'
                            });
                        }
                    }
                }
            });
        }
    },
    
    payment_method: function(frm) {
        // Make reference number required for certain payment methods
        if (frm.doc.payment_method === 'Mobile Money' || frm.doc.payment_method === 'Bank Transfer') {
            frm.toggle_reqd('reference_number', true);
        } else {
            frm.toggle_reqd('reference_number', false);
        }
    },
});

function get_suggested_contribution_amount(frm) {
    if (!frm.doc.member || !frm.doc.contribution_type) return;
    
    frappe.call({
        method: 'get_suggested_amount',
        doc: frm.doc,
        callback: function(r) {
            if (r.message && !frm.doc.amount) {
                frm.set_value('amount', r.message);
            }
        }
    });
}