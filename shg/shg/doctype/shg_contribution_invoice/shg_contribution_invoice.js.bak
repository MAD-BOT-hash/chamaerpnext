frappe.ui.form.on('SHG Contribution Invoice', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.status === 'Unpaid') {
            frm.add_custom_button(__('Send Email'), function() {
                frappe.call({
                    method: 'shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice.send_invoice_email',
                    doc: frm.doc,
                    callback: function(r) {
                        if (!r.exc) {
                            frm.refresh();
                        }
                    }
                });
            });
        }
        
        if (frm.doc.docstatus === 1 && !frm.doc.sales_invoice) {
            frm.add_custom_button(__('Create Sales Invoice'), function() {
                frappe.call({
                    method: 'shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice.create_sales_invoice',
                    doc: frm.doc,
                    callback: function(r) {
                        if (!r.exc) {
                            frm.refresh();
                        }
                    }
                });
            });
        }
    }
});