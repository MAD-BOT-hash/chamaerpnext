// Copyright (c) 2025, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on('SHG Multi Member Payment Invoice', {
    payment_amount: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        // Validate payment amount doesn't exceed outstanding amount
        if (row.payment_amount > row.outstanding_amount) {
            frappe.msgprint(__('Payment amount cannot exceed outstanding amount'));
            frappe.model.set_value(cdt, cdn, 'payment_amount', row.outstanding_amount);
        }
    },

    invoice: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.invoice) {
            // Fetch invoice details
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SHG Contribution Invoice',
                    name: row.invoice
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'member', r.message.member);
                        frappe.model.set_value(cdt, cdn, 'member_name', r.message.member_name);
                        frappe.model.set_value(cdt, cdn, 'contribution_type', r.message.contribution_type);
                        frappe.model.set_value(cdt, cdn, 'invoice_date', r.message.invoice_date);
                        frappe.model.set_value(cdt, cdn, 'due_date', r.message.due_date);
                        frappe.model.set_value(cdt, cdn, 'outstanding_amount', 
                            flt(r.message.amount) - flt(r.message.paid_amount || 0));
                        frappe.model.set_value(cdt, cdn, 'status', r.message.status);
                        
                        // Set default payment amount to outstanding amount
                        frappe.model.set_value(cdt, cdn, 'payment_amount', 
                            flt(r.message.amount) - flt(r.message.paid_amount || 0));
                    }
                }
            });
        }
    }
});