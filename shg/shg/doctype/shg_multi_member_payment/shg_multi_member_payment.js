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
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('Get Unpaid Invoices'), function() {
                frm.trigger('get_unpaid_invoices');
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

        frappe.call({
            method: 'shg.shg.doctype.shg_multi_member_payment.shg_multi_member_payment.get_unpaid_invoices',
            args: {
                company: frm.doc.company
            },
            callback: function(r) {
                if (r.message) {
                    frm.clear_table('invoices');
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
                }
            }
        });
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
        frm.trigger('calculate_totals');
    },

    invoices_remove: function(frm) {
        frm.trigger('calculate_totals');
    }
});