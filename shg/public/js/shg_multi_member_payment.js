// Copyright (c) 2025, SHG Solutions
// License: MIT

frappe.ui.form.on('SHG Multi Member Payment', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Fetch Unpaid Invoices'), function() {
                if (!frm.doc.member) {
                    frappe.msgprint(__("Please select a Member first."));
                    return;
                }
                
                frappe.call({
                    method: 'shg.shg.utils.payment_utils.get_unpaid_invoices',
                    args: { member: frm.doc.member },
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            show_unpaid_items_dialog(frm, r.message);
                        } else {
                            frappe.msgprint(__('No unpaid invoices found'));
                        }
                    }
                });
            });
            
            frm.add_custom_button(__('Fetch Unpaid Contributions'), function() {
                if (!frm.doc.member) {
                    frappe.msgprint(__("Please select a Member first."));
                    return;
                }
                
                frappe.call({
                    method: 'shg.shg.utils.payment_utils.get_unpaid_contributions',
                    args: { member: frm.doc.member },
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            show_unpaid_items_dialog(frm, r.message);
                        } else {
                            frappe.msgprint(__('No unpaid contributions found'));
                        }
                    }
                });
            });
            
            frm.add_custom_button(__('Fetch Unpaid Fines'), function() {
                if (!frm.doc.member) {
                    frappe.msgprint(__("Please select a Member first."));
                    return;
                }
                
                frappe.call({
                    method: 'shg.shg.utils.payment_utils.get_unpaid_fines',
                    args: { member: frm.doc.member },
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            show_unpaid_items_dialog(frm, r.message);
                        } else {
                            frappe.msgprint(__('No unpaid fines found'));
                        }
                    }
                });
            });
            
            frm.add_custom_button(__('Fetch All Unpaid'), function() {
                if (!frm.doc.member) {
                    frappe.msgprint(__("Please select a Member first."));
                    return;
                }
                
                frappe.call({
                    method: 'shg.shg.utils.payment_utils.get_all_unpaid',
                    args: { member: frm.doc.member },
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            show_unpaid_items_dialog(frm, r.message);
                        } else {
                            frappe.msgprint(__('No unpaid items found'));
                        }
                    }
                });
            });
            
            frm.add_custom_button(__('Recalculate Totals'), function() {
                frappe.call({
                    doc: frm.doc,
                    method: "recalculate_totals",
                    callback: function(r) {
                        frm.refresh_fields();
                        frappe.msgprint("Totals updated successfully");
                    }
                });
            });
        }
        
        if (frm.doc.docstatus === 1 && frm.doc.payment_entry) {
            frm.add_custom_button(__('Open Linked Payment Entry'), function() {
                frappe.set_route('Form', 'Payment Entry', frm.doc.payment_entry);
            });
        }
    }
});

function show_unpaid_items_dialog(frm, unpaid_items) {
    // Prepare data for the dialog
    const data = unpaid_items.map(item => [
        0, // Select checkbox (default unchecked)
        item.doctype,
        item.name,
        item.member_name || item.member,
        item.date,
        item.amount,
        item.outstanding,
        item.status,
        item.is_closed ? 'Yes' : 'No',
        item.posted_to_gl ? 'Yes' : 'No'
    ]);
    
    // Create dialog
    const dialog = new frappe.ui.Dialog({
        title: __('Select Unpaid Items'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'items_table',
                options: `
                    <div style="max-height: 400px; overflow-y: auto;">
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th style="width: 50px;"><input type="checkbox" id="select-all-items"> Select All</th>
                                    <th>Doctype</th>
                                    <th>Document Name</th>
                                    <th>Member</th>
                                    <th>Date</th>
                                    <th>Amount</th>
                                    <th>Outstanding</th>
                                    <th>Status</th>
                                    <th>Closed</th>
                                    <th>Posted to GL</th>
                                </tr>
                            </thead>
                            <tbody id="unpaid-items-body">
                                ${data.map((row, index) => {
                                    const isClosedOrPaid = row[8] === 'Yes' || row[7] === 'Paid';
                                    const rowClass = isClosedOrPaid ? 'style="background-color: #ffe6e6;"' : '';
                                    const disabledAttr = isClosedOrPaid ? 'disabled' : '';
                                    return `
                                        <tr ${rowClass}>
                                            <td><input type="checkbox" class="item-checkbox" data-index="${index}" ${disabledAttr}></td>
                                            <td>${row[1]}</td>
                                            <td>${row[2]}</td>
                                            <td>${row[3]}</td>
                                            <td>${row[4]}</td>
                                            <td>${row[5]}</td>
                                            <td>${row[6]}</td>
                                            <td>${row[7]}</td>
                                            <td>${row[8]}</td>
                                            <td>${row[9]}</td>
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>
                `
            }
        ],
        primary_action_label: __('Add Selected Items'),
        primary_action: function() {
            // Get selected items
            const selected_indices = [];
            dialog.$wrapper.find('.item-checkbox:checked').each(function() {
                selected_indices.push(parseInt($(this).data('index')));
            });
            
            // Add selected items to child table
            selected_indices.forEach(index => {
                const item = unpaid_items[index];
                const row = frm.add_child('invoices', {
                    reference_doctype: item.reference_doctype,
                    reference_name: item.reference_name,
                    member: item.member,
                    member_name: item.member_name,
                    date: item.date,
                    amount: item.amount,
                    outstanding_amount: item.outstanding,
                    payment_amount: item.outstanding,
                    status: item.status,
                    is_closed: item.is_closed,
                    posted_to_gl: item.posted_to_gl,
                    remarks: ""
                });
            });
            
            frm.refresh_field('invoices');
            
            // Recalculate totals
            frappe.call({
                doc: frm.doc,
                method: "recalculate_totals",
                callback: function(r) {
                    frm.refresh_fields();
                    frappe.msgprint("Totals updated successfully");
                }
            });
            
            dialog.hide();
        }
    });
    
    // Handle select all checkbox
    dialog.$wrapper.on('change', '#select-all-items', function() {
        const checked = $(this).is(':checked');
        dialog.$wrapper.find('.item-checkbox').not(':disabled').prop('checked', checked);
    });
    
    // Show dialog
    dialog.show();
}

frappe.ui.form.on('SHG Multi Member Payment Invoice', {
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
                method: 'shg.shg.utils.payment_utils.get_outstanding',
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
        
        // Recalculate totals
        frappe.call({
            doc: frm.doc,
            method: "recalculate_totals",
            callback: function(r) {
                frm.refresh_fields();
                frappe.msgprint("Totals updated successfully");
            }
        });
    }
});