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
            frm.add_custom_button(__('Fetch Unpaid Items'), function() {
                frappe.call({
                    method: 'shg.shg.utils.payment_utils.get_unpaid_items',
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            show_unpaid_items_dialog(frm, r.message);
                        } else {
                            frappe.msgprint(__('No unpaid items found'));
                        }
                    }
                });
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
        item.outstanding
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
                                </tr>
                            </thead>
                            <tbody id="unpaid-items-body">
                                ${data.map((row, index) => `
                                    <tr>
                                        <td><input type="checkbox" class="item-checkbox" data-index="${index}"></td>
                                        <td>${row[1]}</td>
                                        <td>${row[2]}</td>
                                        <td>${row[3]}</td>
                                        <td>${row[4]}</td>
                                        <td>${row[5]}</td>
                                        <td>${row[6]}</td>
                                    </tr>
                                `).join('')}
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
                    reference_doctype: item.doctype,
                    reference_name: item.name,
                    member: item.member,
                    member_name: item.member_name,
                    date: item.date,
                    amount: item.amount,
                    outstanding_amount: item.outstanding,
                    payment_amount: item.outstanding
                });
            });
            
            frm.refresh_field('invoices');
            dialog.hide();
        }
    });
    
    // Handle select all checkbox
    dialog.$wrapper.on('change', '#select-all-items', function() {
        const checked = $(this).is(':checked');
        dialog.$wrapper.find('.item-checkbox').prop('checked', checked);
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
    }
});