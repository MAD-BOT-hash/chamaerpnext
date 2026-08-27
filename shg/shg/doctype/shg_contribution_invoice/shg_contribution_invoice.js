// Copyright (c) 2025, SHG Solutions
// License: MIT

frappe.ui.form.on('SHG Contribution Invoice', {
    refresh: function(frm) {
        // Calculate amount from qty * rate if not set
        if (!frm.doc.amount && frm.doc.qty && frm.doc.rate) {
            frm.set_value('amount', flt(frm.doc.qty) * flt(frm.doc.rate));
        }

        if (frm.doc.docstatus === 1) {
            // --- Post to Contribution button ---
            if (!frm.doc.posted_to_contribution) {
                frm.add_custom_button(__('Post to Contribution'), function() {
                    frappe.confirm(
                        __('Post this invoice to SHG Contributions? A Contribution record will be created and submitted.'),
                        function() {
                            frappe.call({
                                method: 'shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice.post_to_contribution',
                                args: { docname: frm.doc.name },
                                freeze: true,
                                freeze_message: __('Posting to Contribution...'),
                                callback: function(r) {
                                    if (r.message && r.message.contribution) {
                                        frappe.show_alert({
                                            message: __('Contribution {0} created successfully.', [r.message.contribution]),
                                            indicator: 'green'
                                        });
                                        frm.reload_doc();
                                    }
                                }
                            });
                        }
                    );
                }, __('Actions'));
            } else {
                // Show link to existing contribution
                if (frm.doc.linked_shg_contribution) {
                    frm.add_custom_button(__('View Contribution'), function() {
                        frappe.set_route('Form', 'SHG Contribution', frm.doc.linked_shg_contribution);
                    }, __('Actions'));
                }
            }

            // --- Make Payment (single button — Invoice is the canonical payment target) ---
            if (frm.doc.status !== 'Paid') {
                frm.add_custom_button(__('Make Payment'), function() {
                    frappe.new_doc('SHG Payment Entry', {
                        member: frm.doc.member,
                        reference_doctype: 'SHG Contribution Invoice',
                        reference_name: frm.doc.name,
                        amount: flt(frm.doc.amount),
                    });
                }, __('Actions'));
            }
        }

        // Status indicator colors
        if (frm.doc.status) {
            const color_map = {
                'Draft': 'grey',
                'Unpaid': 'orange',
                'Paid': 'green',
                'Overdue': 'red',
                'Cancelled': 'red'
            };
            frm.page.set_indicator(frm.doc.status, color_map[frm.doc.status] || 'blue');
        }

        // Show posted_to_contribution badge
        if (frm.doc.posted_to_contribution) {
            frm.dashboard.add_indicator(__('Posted to Contribution'), 'green');
        }
    },

    qty: function(frm) {
        if (frm.doc.qty && frm.doc.rate) {
            frm.set_value('amount', flt(frm.doc.qty) * flt(frm.doc.rate));
        }
    },

    rate: function(frm) {
        if (frm.doc.qty && frm.doc.rate) {
            frm.set_value('amount', flt(frm.doc.qty) * flt(frm.doc.rate));
        }
    },

    member: function(frm) {
        if (frm.doc.member) {
            frappe.db.get_value('SHG Member', frm.doc.member, 'member_name', function(r) {
                if (r && r.member_name) {
                    frm.set_value('member_name', r.member_name);
                }
            });
        }
    }
});
