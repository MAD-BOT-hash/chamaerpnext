// SHG Contribution Invoice Client Script
frappe.ui.form.on('SHG Contribution Invoice', {
    refresh: function(frm) {
        // Add Receive Payment button if invoice is submitted and has outstanding amount
        if (frm.doc.docstatus === 1 && frm.doc.sales_invoice) {
            // Always show the payment button for submitted invoices with sales invoice
            // The actual payment validation will happen on the server side
            frm.add_custom_button(__('Receive Payment'), function() {
                // Open a dialog to get payment amount
                let dialog = new frappe.ui.Dialog({
                    title: __('Receive Payment'),
                    fields: [
                        {
                            label: __('Amount'),
                            fieldname: 'amount',
                            fieldtype: 'Currency',
                            reqd: 1
                        },
                        {
                            label: __('Payment Method'),
                            fieldname: 'payment_method',
                            fieldtype: 'Select',
                            options: 'Cash\nBank Transfer\nMpesa\nCheque',
                            default: 'Cash'
                        },
                        {
                            label: __('Reference Number'),
                            fieldname: 'reference_number',
                            fieldtype: 'Data'
                        }
                    ],
                    primary_action_label: __('Receive Payment'),
                    primary_action: function(values) {
                        dialog.hide();
                        
                        // Call the server method
                        frappe.call({
                            method: 'shg.api.create_payment_entry_from_invoice',
                            args: {
                                invoice_name: frm.doc.sales_invoice,
                                paid_amount: values.amount
                            },
                            freeze: true,
                            freeze_message: __('Creating payment entry...'),
                            callback: function(r) {
                                if (r.message) {
                                    frappe.msgprint(__('Payment received successfully'));
                                    // Refresh the form to update status
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                });
                
                // Fetch the outstanding amount and set it as default
                frappe.call({
                    method: 'frappe.client.get',
                    args: {
                        doctype: 'Sales Invoice',
                        name: frm.doc.sales_invoice
                    },
                    callback: function(r) {
                        if (r.message) {
                            const sales_invoice = r.message;
                            dialog.set_value('amount', sales_invoice.outstanding_amount);
                        }
                    }
                });
                
                dialog.show();
            }, __('Actions'));
        }
    }
});