// Copyright (c) 2025, SHG Solutions
// License: MIT

frappe.ui.form.on('SHG Multi Member Payment', {
    setup: function(frm) {
        frm.set_query('mode_of_payment', function() {
            return {
                filters: {
                    'type': 'Cash'
                }
            };
        });
    },
    
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Get Outstanding'), function() {
                // Refresh outstanding amounts for all rows
                (frm.doc.invoices || []).forEach(function(row) {
                    if (row.reference_doctype && row.reference_name) {
                        frappe.call({
                            method: "shg.shg.utils.payment_utils.get_outstanding",
                            args: {
                                doctype: row.reference_doctype,
                                name: row.reference_name
                            },
                            callback: function(r) {
                                if (r.message) {
                                    frappe.model.set_value(row.doctype, row.name, 'outstanding_amount', r.message);
                                }
                            }
                        });
                    }
                });
            });
        }
    }
});

frappe.ui.form.on('SHG Bulk Payment Item', {
    invoices_add: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        // Set default values for new row if needed
    },
    
    reference_doctype: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        frappe.model.set_value(cdt, cdn, 'reference_name', '');
    },
    
    reference_name: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        if (row.reference_doctype && row.reference_name) {
            frappe.call({
                method: "shg.shg.utils.payment_utils.get_outstanding",
                args: {
                    doctype: row.reference_doctype,
                    name: row.reference_name
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'outstanding_amount', r.message);
                        frappe.model.set_value(cdt, cdn, 'payment_amount', r.message);
                    }
                }
            });
        }
    },
    
    payment_amount: function(frm, cdt, cdn) {
        // Update total when payment amount changes
        var total = 0;
        (frm.doc.invoices || []).forEach(function(row) {
            total += row.payment_amount || 0;
        });
        frm.set_value('total_payment_amount', total);
    }
});