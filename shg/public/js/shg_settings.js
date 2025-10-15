// SHG Settings Client Script
frappe.ui.form.on('SHG Settings', {
    refresh: function(frm) {
        // Add button to generate contribution invoices
        frm.add_custom_button(__('Generate Contribution Invoices'), function() {
            // Open a dialog to get parameters
            let dialog = new frappe.ui.Dialog({
                title: __('Generate Contribution Invoices'),
                fields: [
                    {
                        label: __('Invoice Date'),
                        fieldname: 'invoice_date',
                        fieldtype: 'Date',
                        default: frappe.datetime.get_today(),
                        reqd: 1
                    },
                    {
                        label: __('Supplier Invoice Date'),
                        fieldname: 'supplier_invoice_date',
                        fieldtype: 'Date',
                        description: __('Used for posting and due dates in Sales Invoice creation. If blank, Invoice Date will be used.')
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
                    },
                    {
                        label: __('Auto Receive Payment'),
                        fieldname: 'auto_receive_payment',
                        fieldtype: 'Check',
                        description: __('Automatically create payment entries for received amounts')
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
                            supplier_invoice_date: values.supplier_invoice_date,
                            amount: values.amount,
                            contribution_type: values.contribution_type,
                            remarks: values.description,
                            auto_receive_payment: values.auto_receive_payment
                        },
                        freeze: true,
                        freeze_message: __('Generating contribution invoices...'),
                        callback: function(r) {
                            if (r.message) {
                                let msg = __('Generated {0} contribution invoices.', [r.message.created]);
                                if (r.message.skipped > 0) {
                                    msg += __(' Skipped {0} members (invoices already exist).', [r.message.skipped]);
                                }
                                if (r.message.payments > 0) {
                                    msg += __(' Created {0} payment entries.', [r.message.payments]);
                                }
                                if (r.message.errors > 0) {
                                    msg += __(' Encountered {0} errors.', [r.message.errors]);
                                }
                                frappe.msgprint(msg);
                                
                                // Refresh the form
                                frm.reload_doc();
                            }
                        }
                    });
                }
            });
            
            dialog.show();
        }, __('Actions'));
    }
});