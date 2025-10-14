// SHG Contribution Client Script
frappe.ui.form.on('SHG Contribution', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.journal_entry) {
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
            
            // Mpesa STK Push button
            if (frm.doc.payment_method === 'Mpesa' && !frm.doc.reference_number) {
                frm.add_custom_button(__('Initiate Mpesa STK Push'), function() {
                    initiate_mpesa_stk_push(frm);
                });
            }
        }
        
        // Add button to generate multiple invoices
        if (frm.doc.docstatus === 0) { // Only in draft
            frm.add_custom_button(__('Generate Invoices for All Members'), function() {
                // Open a dialog to get parameters
                let dialog = new frappe.ui.Dialog({
                    title: __('Generate Contribution Invoices for All Active Members'),
                    fields: [
                        {
                            label: __('Invoice Date'),
                            fieldname: 'invoice_date',
                            fieldtype: 'Date',
                            default: frappe.datetime.get_today(),
                            reqd: 1
                        },
                        {
                            label: __('Amount'),
                            fieldname: 'amount',
                            fieldtype: 'Currency',
                            reqd: 1
                        },
                        {
                            label: __('Contribution Type'),
                            fieldname: 'contribution_type',
                            fieldtype: 'Link',
                            options: 'SHG Contribution Type'
                        },
                        {
                            label: __('Description'),
                            fieldname: 'description',
                            fieldtype: 'Small Text'
                        }
                    ],
                    primary_action_label: __('Generate'),
                    primary_action: function(values) {
                        dialog.hide();
                        
                        // Call the server method
                        frappe.call({
                            method: 'shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice.generate_multiple_contribution_invoices',
                            args: {
                                invoice_date: values.invoice_date,
                                amount: values.amount,
                                contribution_type: values.contribution_type,
                                remarks: values.description
                            },
                            freeze: true,
                            freeze_message: __('Generating contribution invoices...'),
                            callback: function(r) {
                                if (r.message) {
                                    let msg = __('Generated {0} contribution invoices.', [r.message.created]);
                                    if (r.message.skipped > 0) {
                                        msg += __(' Skipped {0} members (invoices already exist).', [r.message.skipped]);
                                    }
                                    if (r.message.errors > 0) {
                                        msg += __(' Encountered {0} errors.', [r.message.errors]);
                                    }
                                    frappe.msgprint(msg);
                                }
                            }
                        });
                    }
                });
                
                dialog.show();
            }, __('Actions'));
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
    
    contribution_type_link: function(frm) {
        if (frm.doc.contribution_type_link) {
            // Fetch contribution type details
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SHG Contribution Type',
                    name: frm.doc.contribution_type_link
                },
                callback: function(r) {
                    if (r.message) {
                        if (r.message.default_amount && !frm.doc.amount) {
                            frm.set_value('amount', r.message.default_amount);
                        }
                    }
                }
            });
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
        if (frm.doc.payment_method === 'Mobile Money' || frm.doc.payment_method === 'Bank Transfer' || frm.doc.payment_method === 'Mpesa') {
            frm.toggle_reqd('reference_number', true);
        } else {
            frm.toggle_reqd('reference_number', false);
        }
        
        // Show Mpesa STK Push button
        if (frm.doc.payment_method === 'Mpesa') {
            frm.refresh();
        }
    },
});

function get_suggested_contribution_amount(frm) {
    if (!frm.doc.member || (!frm.doc.contribution_type && !frm.doc.contribution_type_link)) return;
    
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

function initiate_mpesa_stk_push(frm) {
    if (!frm.doc.member || !frm.doc.amount) {
        frappe.msgprint(__('Please select a member and enter an amount'));
        return;
    }
    
    frappe.call({
        method: 'initiate_mpesa_stk_push',
        doc: frm.doc,
        freeze: true,
        freeze_message: __('Initiating Mpesa STK Push...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint(__('Mpesa STK Push initiated successfully. Please check your phone.'));
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message ? r.message.error : __('Failed to initiate Mpesa STK Push'),
                    indicator: 'red'
                });
            }
        }
    });
}