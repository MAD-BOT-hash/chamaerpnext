// Copyright (c) 2025, SHG Solutions
// License: MIT

frappe.ui.form.on('SHG Contribution', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.status !== 'Paid') {
            frm.add_custom_button(__('Make Payment'), function() {
                frappe.new_doc('SHG Payment Entry', {
                    member: frm.doc.member,
                    reference_doctype: 'SHG Contribution',
                    reference_name: frm.doc.name,
                    amount: flt(frm.doc.unpaid_amount || frm.doc.amount),
                });
            }, __('Actions'));
        }

        if (frm.doc.invoice_reference) {
            frm.add_custom_button(__('View Invoice'), function() {
                frappe.set_route('Form', 'SHG Contribution Invoice', frm.doc.invoice_reference);
            }, __('Actions'));
        }

        // Status indicator
        if (frm.doc.status) {
            const color_map = { 'Paid': 'green', 'Partially Paid': 'orange', 'Unpaid': 'red' };
            frm.page.set_indicator(frm.doc.status, color_map[frm.doc.status] || 'blue');
        }
    },

    amount: function(frm) {
        if (!frm.doc.expected_amount && frm.doc.amount) {
            frm.set_value('expected_amount', frm.doc.amount);
        }
    }
});
