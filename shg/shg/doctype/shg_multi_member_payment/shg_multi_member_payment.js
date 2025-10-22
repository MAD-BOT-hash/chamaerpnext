// Copyright (c) 2025, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on('SHG Multi Member Payment', {
    setup: function(frm) {
        frm.set_query('account', function() {
            return {
                filters: {
                    company: frm.doc.company,
                    is_group: 0
                }
            };
        });
    },

    refresh: function(frm) {
        // Add Get Unpaid Invoices button in the form
        frm.clear_custom_buttons();
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Get Unpaid Invoices'), function() {
                frm.trigger('get_unpaid_invoices');
            }).addClass('btn-primary');
            
            frm.add_custom_button(__('Add Invoice'), function() {
                frm.trigger('add_invoice');
            });
        }
    },

    company: function(frm) {
        if (frm.doc.company) {
            // Set default account based on payment method
            frm.trigger('set_default_account');
        }
    },

    payment_method: function(frm) {
        if (frm.doc.payment_method) {
            // Set default account based on payment method
            frm.trigger('set_default_account');
        }
    },

    set_default_account: function(frm) {
        if (!frm.doc.company || !frm.doc.payment_method) return;

        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'SHG Settings',
                fieldname: get_account_field_for_payment_method(frm.doc.payment_method)
            },
            callback: function(r) {
                if (r.message && r.message[get_account_field_for_payment_method(frm.doc.payment_method)]) {
                    frm.set_value('account', r.message[get_account_field_for_payment_method(frm.doc.payment_method)]);
                }
            }
        });
    },

    get_unpaid_invoices: function(frm) {
        if (!frm.doc.company) {
            frappe.msgprint(__('Please select a company first'));
            return;
        }

        // Show a dialog to filter invoices
        var dialog = new frappe.ui.Dialog({
            title: __('Select Invoices'),
            fields: [
                {
                    label: __('Member'),
                    fieldtype: 'Link',
                    fieldname: 'member',
                    options: 'SHG Member'
                },
                {
                    label: __('Contribution Type'),
                    fieldtype: 'Link',
                    fieldname: 'contribution_type',
                    options: 'SHG Contribution Type'
                },
                {
                    label: __('From Date'),
                    fieldtype: 'Date',
                    fieldname: 'from_date'
                },
                {
                    label: __('To Date'),
                    fieldtype: 'Date',
                    fieldname: 'to_date'
                }
            ],
            primary_action_label: __('Get Invoices'),
            primary_action: function() {
                var data = dialog.get_values();
                
                frappe.call({
                    method: 'shg.shg.doctype.shg_multi_member_payment.shg_multi_member_payment.get_unpaid_invoices',
                    args: {
                        filters: data
                    },
                    callback: function(r) {
                        if (r.message) {
                            // Clear existing rows
                            frm.clear_table('invoices');
                            
                            // Add new rows
                            $.each(r.message, function(i, invoice) {
                                var row = frappe.model.add_child(frm.doc, 'SHG Multi Member Payment Invoice', 'invoices');
                                row.invoice = invoice.invoice;
                                row.member = invoice.member;
                                row.member_name = invoice.member_name;
                                row.contribution_type = invoice.contribution_type;
                                row.invoice_date = invoice.invoice_date;
                                row.due_date = invoice.due_date;
                                row.outstanding_amount = invoice.outstanding_amount;
                                row.payment_amount = invoice.payment_amount;
                                row.status = invoice.status;
                            });
                            
                            frm.refresh_field('invoices');
                            frm.trigger('calculate_totals');
                            
                            frappe.msgprint(__('{0} unpaid invoices added', [r.message.length]));
                        }
                        dialog.hide();
                    }
                });
            }
        });
        
        dialog.show();
    },
    
    add_invoice: function(frm) {
        // Show a dialog to add a single invoice
        var dialog = new frappe.ui.Dialog({
            title: __('Add Invoice'),
            fields: [
                {
                    label: __('Invoice'),
                    fieldtype: 'Link',
                    fieldname: 'invoice',
                    options: 'SHG Contribution Invoice',
                    get_query: function() {
                        return {
                            filters: {
                                status: ['in', ['Unpaid', 'Partially Paid']],
                                docstatus: 1
                            }
                        };
                    },
                    reqd: 1
                }
            ],
            primary_action_label: __('Add'),
            primary_action: function() {
                var data = dialog.get_values();
                
                // Check if invoice is already added
                var exists = false;
                $.each(frm.doc.invoices || [], function(i, row) {
                    if (row.invoice === data.invoice) {
                        exists = true;
                        return false;
                    }
                });
                
                if (exists) {
                    frappe.msgprint(__('This invoice is already added'));
                    return;
                }
                
                // Fetch invoice details
                frappe.call({
                    method: 'frappe.client.get',
                    args: {
                        doctype: 'SHG Contribution Invoice',
                        name: data.invoice
                    },
                    callback: function(r) {
                        if (r.message) {
                            var row = frappe.model.add_child(frm.doc, 'SHG Multi Member Payment Invoice', 'invoices');
                            row.invoice = r.message.name;
                            row.member = r.message.member;
                            row.member_name = r.message.member_name;
                            row.contribution_type = r.message.contribution_type;
                            row.invoice_date = r.message.invoice_date;
                            row.due_date = r.message.due_date;
                            var outstanding = flt(r.message.amount) - flt(r.message.paid_amount || 0);
                            row.outstanding_amount = outstanding;
                            row.payment_amount = outstanding;
                            row.status = r.message.status;
                            
                            frm.refresh_field('invoices');
                            frm.trigger('calculate_totals');
                            
                            frappe.msgprint(__('Invoice {0} added', [r.message.name]));
                        }
                        dialog.hide();
                    }
                });
            }
        });
        
        dialog.show();
    }
});

function get_account_field_for_payment_method(payment_method) {
    switch(payment_method) {
        case 'Cash':
            return 'default_cash_account';
        case 'Bank Transfer':
        case 'Mpesa':
            return 'default_bank_account';
        default:
            return 'default_debit_account';
    }
}

frappe.ui.form.on('SHG Multi Member Payment Invoice', {
    payment_amount: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.payment_amount > row.outstanding_amount) {
            frappe.msgprint(__('Payment amount cannot exceed outstanding amount of {0}', [row.outstanding_amount]));
            frappe.model.set_value(cdt, cdn, 'payment_amount', row.outstanding_amount);
        }
        frm.trigger('calculate_totals');
    },

    invoices_remove: function(frm) {
        frm.trigger('calculate_totals');
    },
    
    invoice: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.invoice && !row.outstanding_amount) {
            // Fetch invoice details if not already populated
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
                        var outstanding = flt(r.message.amount) - flt(r.message.paid_amount || 0);
                        frappe.model.set_value(cdt, cdn, 'outstanding_amount', outstanding);
                        frappe.model.set_value(cdt, cdn, 'payment_amount', outstanding);
                        frappe.model.set_value(cdt, cdn, 'status', r.message.status);
                        frm.trigger('calculate_totals');
                    }
                }
            });
        }
    }
});