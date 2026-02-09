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

frappe.ui.form.on('SHG Multi Member Payment Invoice', {
    invoices_add: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        // Set default values for new row if needed
    },
    
    member: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        if (row.member) {
            // Auto-fetch member name
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "SHG Member",
                    fieldname: "member_name",
                    filters: { name: row.member }
                },
                callback: function(r) {
                    if (r.message && r.message.member_name) {
                        frappe.model.set_value(cdt, cdn, 'member_name', r.message.member_name);
                    }
                }
            });
        }
    },
    
    reference_name: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        if (row.reference_doctype && row.reference_name) {
            // Auto-fetch invoice date and outstanding amount
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: row.reference_doctype,
                    fieldname: ["posting_date", "date", "due_date"],
                    filters: { name: row.reference_name }
                },
                callback: function(r) {
                    if (r.message) {
                        // Try different possible date field names
                        var date_value = r.message.posting_date || r.message.date || r.message.due_date;
                        if (date_value) {
                            frappe.model.set_value(cdt, cdn, 'date', date_value);
                        }
                        
                        // Also try to get member if not set
                        if (!row.member) {
                            var member_value = r.message.member;
                            if (member_value) {
                                frappe.model.set_value(cdt, cdn, 'member', member_value);
                                
                                // Fetch member name
                                frappe.call({
                                    method: "frappe.client.get_value",
                                    args: {
                                        doctype: "SHG Member",
                                        fieldname: "member_name",
                                        filters: { name: member_value }
                                    },
                                    callback: function(member_r) {
                                        if (member_r.message && member_r.message.member_name) {
                                            frappe.model.set_value(cdt, cdn, 'member_name', member_r.message.member_name);
                                        }
                                    }
                                });
                            }
                        }
                    }
                }
            });
            
            // Get outstanding amount
            frappe.call({
                method: "shg.shg.utils.payment_utils.get_outstanding",
                args: {
                    doctype: row.reference_doctype,
                    name: row.reference_name
                },
                callback: function(r) {
                    if (r.message !== undefined) {
                        frappe.model.set_value(cdt, cdn, 'outstanding_amount', r.message);
                        // Set payment amount to outstanding amount by default
                        frappe.model.set_value(cdt, cdn, 'payment_amount', r.message);
                    }
                }
            });
        }
    },
    
    payment_amount: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        
        // Validate that payment amount does not exceed outstanding amount
        if (row.payment_amount && row.outstanding_amount && row.payment_amount > row.outstanding_amount) {
            frappe.show_alert({
                message: __("Payment amount cannot exceed outstanding amount"),
                indicator: 'red'
            });
            
            // Reset payment amount to outstanding amount
            frappe.model.set_value(cdt, cdn, 'payment_amount', row.outstanding_amount);
            frappe.validated = false;
        }
        
        // Update total when payment amount changes
        var total = 0;
        (frm.doc.invoices || []).forEach(function(row) {
            total += row.payment_amount || 0;
        });
        frm.set_value('total_payment_amount', total);
    }
});