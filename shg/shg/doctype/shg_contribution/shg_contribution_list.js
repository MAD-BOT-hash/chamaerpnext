frappe.listview_settings['SHG Contribution'] = {
    onload: function(listview) {
        listview.page.add_menu_item(__('Generate Invoices'), function() {
            let d = new frappe.ui.Dialog({
                title: __('Generate Contribution Invoices'),
                fields: [
                    { 
                        fieldtype: 'Date', 
                        fieldname: 'invoice_date', 
                        label: 'Invoice Date', 
                        default: frappe.datetime.get_today(), 
                        reqd: 1 
                    },
                    { 
                        fieldtype: 'Currency', 
                        fieldname: 'amount', 
                        label: 'Amount (KES)', 
                        reqd: 1 
                    },
                    { 
                        fieldtype: 'Link', 
                        fieldname: 'contribution_type', 
                        label: 'Contribution Type', 
                        options: 'SHG Contribution Type' 
                    },
                    { 
                        fieldtype: 'Small Text', 
                        fieldname: 'remarks', 
                        label: 'Remarks' 
                    },
                    { 
                        fieldtype: 'Check', 
                        fieldname: 'send_email', 
                        label: 'Send Email to Members', 
                        default: 0 
                    }
                ],
                primary_action_label: __('Generate'),
                primary_action(values) {
                    frappe.call({
                        method: 'shg.shg.doctype.shg_contribution.shg_contribution.generate_contribution_invoices',
                        args: values,
                        callback: function(r) {
                            if (!r.exc) {
                                frappe.msgprint(__('Invoices generated successfully!'));
                                if (values.send_email) {
                                    frappe.confirm(
                                        __('Invoices created successfully — would you like to email them to all members?'),
                                        function() {
                                            // User clicked Yes, send emails
                                            frappe.call({
                                                method: 'shg.shg.doctype.shg_contribution.shg_contribution.send_contribution_invoice_emails',
                                                args: {
                                                    invoice_date: values.invoice_date
                                                },
                                                callback: function(email_r) {
                                                    if (!email_r.exc) {
                                                        frappe.msgprint(__('Emails sent successfully!'));
                                                    }
                                                }
                                            });
                                        }
                                    );
                                }
                            }
                            d.hide();
                            listview.refresh();
                        }
                    });
                }
            });
            d.show();
        });
    }
};