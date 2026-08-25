frappe.ui.form.on('SHG Bulk Contribution Invoice', {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            // Add custom buttons
            frm.add_custom_button(__('Get Active Members'), function() {
                frappe.call({
                    method: 'get_active_members',
                    doc: frm.doc,
                    callback: function(r) {
                        if (r.message) {
                            frm.refresh();
                            frappe.msgprint(r.message);
                        }
                    }
                });
            }).addClass('btn-primary');
            
            frm.add_custom_button(__('Clear Members'), function() {
                frappe.call({
                    method: 'clear_members',
                    doc: frm.doc,
                    callback: function(r) {
                        if (r.message) {
                            frm.refresh();
                            frappe.msgprint(r.message);
                        }
                    }
                });
            });
            
            frm.add_custom_button(__('Create Invoices'), function() {
                frappe.confirm(
                    __('Create contribution invoices for all selected members?'),
                    function() {
                        frappe.call({
                            method: 'create_invoices',
                            doc: frm.doc,
                            callback: function(r) {
                                if (r.message) {
                                    frm.refresh();
                                    frappe.msgprint(r.message);
                                }
                            }
                        });
                    }
                );
            }).addClass('btn-success');
        }
        
        // Show status indicator
        show_status_indicator(frm);
    },
    
    invoice_date(frm) {
        if (!frm.doc.due_date) {
            frm.set_value('due_date', frm.doc.invoice_date);
        }
    },
    
    default_rate(frm) {
        update_all_amounts(frm);
    },
    
    default_qty(frm) {
        update_all_amounts(frm);
    }
});

frappe.ui.form.on('SHG Bulk Contribution Invoice Item', {
    members_add(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        row.qty = frm.doc.default_qty || 1;
        row.rate = frm.doc.default_rate || 0;
        row.selected = 1;
        row.status = 'Pending';
    },
    
    qty(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },
    
    rate(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },
    
    selected(frm) {
        frm.doc.calculate_totals();
        frm.refresh_field('total_members');
        frm.refresh_field('total_amount');
    }
});

// Helper functions
function calculate_amount(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    row.amount = flt(row.qty) * flt(row.rate);
    frm.refresh_field('members');
    frm.doc.calculate_totals();
    frm.refresh_field('total_members');
    frm.refresh_field('total_amount');
}

function update_all_amounts(frm) {
    (frm.doc.members || []).forEach(row => {
        if (!row.qty) row.qty = frm.doc.default_qty || 1;
        if (!row.rate) row.rate = frm.doc.default_rate || 0;
        row.amount = flt(row.qty) * flt(row.rate);
    });
    frm.refresh_field('members');
    frm.doc.calculate_totals();
    frm.refresh_field('total_members');
    frm.refresh_field('total_amount');
}

function show_status_indicator(frm) {
    if (frm.doc.status === 'Invoices Created') {
        frm.set_df_property('status', 'color', 'green');
    } else if (frm.doc.status === 'Cancelled') {
        frm.set_df_property('status', 'color', 'red');
    }
}
