// Payment UI for SHG App
frappe.ready(function() {
    // Add "Receive Payment" button to relevant doctypes
    frappe.ui.form.on('SHG Contribution Invoice', {
        refresh: function(frm) {
            if (frm.doc.docstatus === 1 && frm.doc.status !== 'Paid') {
                frm.add_custom_button(__('Receive Payment'), function() {
                    show_payment_dialog(frm, 'SHG Contribution Invoice');
                }, __('Actions'));
            }
        }
    });
    
    frappe.ui.form.on('SHG Meeting Fine', {
        refresh: function(frm) {
            if (frm.doc.docstatus === 1 && frm.doc.status !== 'Paid') {
                frm.add_custom_button(__('Receive Payment'), function() {
                    show_payment_dialog(frm, 'SHG Meeting Fine');
                }, __('Actions'));
            }
        }
    });
    
    frappe.ui.form.on('SHG Contribution', {
        refresh: function(frm) {
            if (frm.doc.docstatus === 1 && frm.doc.status !== 'Paid') {
                frm.add_custom_button(__('Receive Payment'), function() {
                    show_payment_dialog(frm, 'SHG Contribution');
                }, __('Actions'));
            }
        }
    });
});

function show_payment_dialog(frm, doctype) {
    let dialog = new frappe.ui.Dialog({
        title: __('Receive Payment for {0}', [doctype]),
        fields: [
            {
                label: __('Document'),
                fieldtype: 'Read Only',
                fieldname: 'document',
                default: frm.doc.name
            },
            {
                label: __('Member'),
                fieldtype: 'Link',
                fieldname: 'member',
                options: 'SHG Member',
                default: frm.doc.member,
                read_only: 1
            },
            {
                label: __('Amount'),
                fieldtype: 'Currency',
                fieldname: 'amount',
                default: get_outstanding_amount(frm, doctype),
                reqd: 1
            },
            {
                label: __('Mode of Payment'),
                fieldtype: 'Select',
                fieldname: 'mode_of_payment',
                options: ['Cash', 'Mpesa', 'Bank Transfer'],
                default: 'Cash',
                reqd: 1
            },
            {
                label: __('Posting Date'),
                fieldtype: 'Date',
                fieldname: 'posting_date',
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                label: __('Reference No'),
                fieldtype: 'Data',
                fieldname: 'reference_no'
            }
        ],
        primary_action_label: __('Receive Payment'),
        primary_action: function(values) {
            frappe.call({
                method: 'shg.shg.api.payment.receive_single_payment',
                args: {
                    document_type: doctype,
                    document_name: values.document,
                    amount: values.amount,
                    mode_of_payment: values.mode_of_payment,
                    posting_date: values.posting_date,
                    reference_no: values.reference_no
                },
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint(__('Payment received successfully. Payment Entry: {0}', [r.message.payment_entry]));
                        dialog.hide();
                        frm.reload_doc();
                    } else {
                        frappe.msgprint(__('Failed to receive payment: {0}', [r.message?.message || 'Unknown error']));
                    }
                }
            });
        }
    });
    
    dialog.show();
}

function get_outstanding_amount(frm, doctype) {
    if (doctype === 'SHG Contribution Invoice') {
        if (frm.doc.sales_invoice) {
            // Try to get outstanding from linked Sales Invoice
            return frm.doc.outstanding_amount || frm.doc.amount;
        } else {
            return frm.doc.amount;
        }
    } else if (doctype === 'SHG Meeting Fine') {
        return frm.doc.amount;
    } else if (doctype === 'SHG Contribution') {
        return (frm.doc.expected_amount || frm.doc.amount) - (frm.doc.amount_paid || 0);
    }
    return 0;
}

// Bulk Payment Dialog
function show_bulk_payment_dialog(member) {
    // First, fetch unpaid invoices for the member
    frappe.call({
        method: 'shg.shg.api.payment.get_unpaid_invoices',
        args: {
            member: member
        },
        callback: function(r) {
            if (r.message) {
                let invoices = r.message;
                
                // Prepare options for multi-select
                let invoice_options = invoices.map(inv => {
                    return {
                        label: `${inv.doctype}: ${inv.name} (${inv.amount}) - ${inv.date}`,
                        value: JSON.stringify({
                            doctype: inv.doctype,
                            name: inv.name,
                            amount: inv.amount
                        })
                    };
                });
                
                let dialog = new frappe.ui.Dialog({
                    title: __('Bulk Payment for Member {0}', [member]),
                    fields: [
                        {
                            label: __('Member'),
                            fieldtype: 'Link',
                            fieldname: 'member',
                            options: 'SHG Member',
                            default: member,
                            read_only: 1
                        },
                        {
                            label: __('Select Invoices'),
                            fieldtype: 'MultiSelect',
                            fieldname: 'selected_invoices',
                            options: invoice_options,
                            reqd: 1
                        },
                        {
                            label: __('Total Amount'),
                            fieldtype: 'Currency',
                            fieldname: 'total_amount',
                            read_only: 1
                        },
                        {
                            label: __('Mode of Payment'),
                            fieldtype: 'Select',
                            fieldname: 'mode_of_payment',
                            options: ['Cash', 'Mpesa', 'Bank Transfer'],
                            default: 'Cash',
                            reqd: 1
                        },
                        {
                            label: __('Posting Date'),
                            fieldtype: 'Date',
                            fieldname: 'posting_date',
                            default: frappe.datetime.get_today(),
                            reqd: 1
                        },
                        {
                            label: __('Reference No'),
                            fieldtype: 'Data',
                            fieldname: 'reference_no'
                        }
                    ],
                    primary_action_label: __('Process Bulk Payment'),
                    primary_action: function(values) {
                        let selected_docs = [];
                        try {
                            // Parse selected invoices
                            let selected_values = values.selected_invoices.split('\n');
                            selected_values.forEach(val => {
                                if (val.trim()) {
                                    selected_docs.push(JSON.parse(val.trim()));
                                }
                            });
                        } catch (e) {
                            frappe.msgprint(__('Invalid selection format'));
                            return;
                        }
                        
                        if (selected_docs.length === 0) {
                            frappe.msgprint(__('Please select at least one invoice'));
                            return;
                        }
                        
                        frappe.call({
                            method: 'shg.shg.api.payment.receive_bulk_payment',
                            args: {
                                member: values.member,
                                documents: selected_docs,
                                amount: values.total_amount,
                                mode_of_payment: values.mode_of_payment,
                                posting_date: values.posting_date,
                                reference_no: values.reference_no
                            },
                            callback: function(r) {
                                if (r.message && r.message.status === 'success') {
                                    frappe.msgprint(__('Bulk payment processed successfully. Payment Entry: {0}', [r.message.payment_entry]));
                                    dialog.hide();
                                    // Reload related forms
                                    frappe.set_route('Form', 'SHG Member', member);
                                } else {
                                    frappe.msgprint(__('Failed to process bulk payment: {0}', [r.message?.message || 'Unknown error']));
                                }
                            }
                        });
                    }
                });
                
                // Update total when selections change
                dialog.fields_dict.selected_invoices.$input.on('change', function() {
                    let total = 0;
                    try {
                        let selected_values = dialog.get_value('selected_invoices').split('\n');
                        selected_values.forEach(val => {
                            if (val.trim()) {
                                let doc = JSON.parse(val.trim());
                                total += parseFloat(doc.amount) || 0;
                            }
                        });
                    } catch (e) {
                        // Ignore parsing errors
                    }
                    dialog.set_value('total_amount', total);
                });
                
                dialog.show();
            } else {
                frappe.msgprint(__('Failed to fetch unpaid invoices'));
            }
        }
    });
}