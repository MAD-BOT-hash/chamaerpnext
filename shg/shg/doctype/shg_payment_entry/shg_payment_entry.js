// Copyright (c) 2025, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on('SHG Payment Entry', {
    setup: function(frm) {
        frm.set_query('member', function() {
            return {
                filters: {
                    'membership_status': 'Active'
                }
            };
        });
        
        frm.set_query('debit_account', function() {
            return {
                filters: {
                    'account_type': 'Cash',
                    'is_group': 0
                }
            };
        });
        
        frm.set_query('credit_account', function() {
            return {
                filters: {
                    'account_type': 'Receivable',
                    'is_group': 0
                }
            };
        });
    },
    
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Get Unpaid Invoices'), function() {
                if (!frm.doc.member) {
                    frappe.msgprint(__('Please select a member first'));
                    return;
                }
                
                frappe.call({
                    method: 'shg.api.get_unpaid_contribution_invoices',
                    args: {
                        member: frm.doc.member
                    },
                    callback: function(r) {
                        if (r.message) {
                            frm.clear_table('payment_entries');
                            r.message.forEach(function(invoice) {
                                var row = frm.add_child('payment_entries');
                                row.invoice_type = 'SHG Contribution Invoice';
                                row.invoice = invoice.name;
                                row.invoice_date = invoice.invoice_date;
                                row.outstanding_amount = invoice.outstanding_amount;
                                row.amount = invoice.outstanding_amount;
                                row.description = invoice.description;
                            });
                            frm.refresh_field('payment_entries');
                            frm.trigger('calculate_total');
                        }
                    }
                });
            });
        }
    },
    
    member: function(frm) {
        if (frm.doc.member) {
            // Fetch member account number
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SHG Member',
                    name: frm.doc.member
                },
                callback: function(r) {
                    if (r.message && r.message.account_number) {
                        frm.set_value('account_number', r.message.account_number);
                    }
                }
            });
            
            // Set default accounts from SHG Settings
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SHG Settings'
                },
                callback: function(r) {
                    if (r.message) {
                        if (r.message.default_debit_account) {
                            frm.set_value('debit_account', r.message.default_debit_account);
                        }
                        if (r.message.default_credit_account) {
                            frm.set_value('credit_account', r.message.default_credit_account);
                        }
                        if (r.message.default_payment_method) {
                            frm.set_value('payment_method', r.message.default_payment_method);
                        }
                    }
                }
            });
        }
    },
    
    calculate_total: function(frm) {
        var total = 0;
        frm.doc.payment_entries.forEach(function(entry) {
            total += entry.amount || 0;
        });
        frm.set_value('total_amount', total);
    }
});

frappe.ui.form.on('SHG Payment Entry Detail', {
    amount: function(frm, cdt, cdn) {
        frm.trigger('calculate_total');
    },
    
    invoice: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        if (row.invoice) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SHG Contribution Invoice',
                    name: row.invoice
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'invoice_date', r.message.invoice_date);
                        frappe.model.set_value(cdt, cdn, 'outstanding_amount', r.message.amount);
                        frappe.model.set_value(cdt, cdn, 'amount', r.message.amount);
                        frappe.model.set_value(cdt, cdn, 'description', r.message.description);
                        frm.trigger('calculate_total');
                    }
                }
            });
        }
    }
});