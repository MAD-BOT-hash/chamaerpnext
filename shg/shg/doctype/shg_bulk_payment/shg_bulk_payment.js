// Copyright (c) 2025, SHG Solutions
// License: MIT

frappe.ui.form.on('SHG Bulk Payment', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            // Add button to fetch unpaid invoices
            frm.add_custom_button(__('Fetch Unpaid Invoices'), function() {
                if (!frm.doc.company) {
                    frappe.msgprint(__("Please select a Company first."));
                    return;
                }
                
                frappe.call({
                    method: "shg.shg.services.payment.bulk_payment_service.get_unpaid_invoices_for_company",
                    args: { 
                        company: frm.doc.company 
                    },
                    freeze: true,
                    freeze_message: __("Fetching unpaid invoices..."),
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            show_unpaid_items_dialog(frm, r.message, "Invoices");
                        } else {
                            frappe.msgprint(__('No unpaid invoices found for this company'));
                        }
                    }
                });
            }, __("Fetch Unpaid"));
            
            // Add button to fetch unpaid contributions
            frm.add_custom_button(__('Fetch Unpaid Contributions'), function() {
                if (!frm.doc.company) {
                    frappe.msgprint(__("Please select a Company first."));
                    return;
                }
                
                frappe.call({
                    method: "shg.shg.services.payment.bulk_payment_service.get_unpaid_contributions_for_company",
                    args: { 
                        company: frm.doc.company 
                    },
                    freeze: true,
                    freeze_message: __("Fetching unpaid contributions..."),
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            show_unpaid_items_dialog(frm, r.message, "Contributions");
                        } else {
                            frappe.msgprint(__('No unpaid contributions found for this company'));
                        }
                    }
                });
            }, __("Fetch Unpaid"));
            
            // Add button to fetch all unpaid items
            frm.add_custom_button(__('Fetch All Unpaid Items'), function() {
                if (!frm.doc.company) {
                    frappe.msgprint(__("Please select a Company first."));
                    return;
                }
                
                frappe.call({
                    method: "shg.shg.services.payment.bulk_payment_service.get_all_unpaid_items_for_company",
                    args: { 
                        company: frm.doc.company 
                    },
                    freeze: true,
                    freeze_message: __("Fetching all unpaid items..."),
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            show_unpaid_items_dialog(frm, r.message, "All Items");
                        } else {
                            frappe.msgprint(__('No unpaid items found for this company'));
                        }
                    }
                });
            }, __("Fetch Unpaid"));
            
            // Add button to auto-allocate by oldest due date
            frm.add_custom_button(__('Auto Allocate by Due Date'), function() {
                if (!frm.doc.allocations || frm.doc.allocations.length === 0) {
                    frappe.msgprint(__("Please add allocations first."));
                    return;
                }
                
                frappe.call({
                    method: "shg.shg.services.payment.bulk_payment_service.auto_allocate_by_oldest_due_date",
                    args: { 
                        bulk_payment_name: frm.doc.name 
                    },
                    freeze: true,
                    freeze_message: __("Auto-allocating by due date..."),
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frm.reload_doc();
                            frappe.msgprint(__("Auto-allocation completed successfully"));
                        } else {
                            frappe.msgprint(__("Auto-allocation failed: {0}", [r.message?.error || "Unknown error"]));
                        }
                    }
                });
            }, __("Actions"));
            
            // Add button to validate integrity
            frm.add_custom_button(__('Validate Integrity'), function() {
                frappe.call({
                    method: "shg.shg.jobs.bulk_payment_jobs.validate_bulk_payment_integrity",
                    args: { 
                        bulk_payment_name: frm.doc.name 
                    },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            const results = r.message.validation_results;
                            let message = `<strong>Validation Results:</strong><br>`;
                            message += `Total Amount: ${format_currency(frm.doc.total_amount)}<br>`;
                            message += `Calculated Total Allocated: ${format_currency(results.calculated_total_allocated)}<br>`;
                            message += `Calculated Unallocated: ${format_currency(results.calculated_unallocated)}<br>`;
                            message += `Allocations Count: ${results.allocations_count}<br><br>`;
                            
                            if (results.validation_issues.length > 0) {
                                message += `<strong style="color: red;">Validation Issues Found:</strong><br>`;
                                results.validation_issues.forEach(issue => {
                                    message += `• ${issue.type}: ${JSON.stringify(issue)}<br>`;
                                });
                            } else {
                                message += `<strong style="color: green;">✓ No validation issues found</strong>`;
                            }
                            
                            frappe.msgprint({
                                title: __("Validation Results"),
                                message: message,
                                indicator: results.validation_issues.length > 0 ? "orange" : "green"
                            });
                        } else {
                            frappe.msgprint(__("Validation failed: {0}", [r.message?.error || "Unknown error"]));
                        }
                    }
                });
            }, __("Actions"));
        }
        
        // Show processing status if processed
        if (frm.doc.docstatus === 1 && frm.doc.payment_entry) {
            frm.add_custom_button(__('Open Payment Entry'), function() {
                frappe.set_route('Form', 'Payment Entry', frm.doc.payment_entry);
            }, __("View"));
        }
        
        if (frm.doc.processing_status) {
            frm.add_custom_button(__('Refresh Status'), function() {
                frappe.call({
                    method: "shg.shg.jobs.bulk_payment_jobs.get_bulk_payment_processing_status",
                    args: { 
                        bulk_payment_name: frm.doc.name 
                    },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            const status = r.message;
                            let message = `<strong>Processing Status:</strong><br>`;
                            message += `Status: ${status.current_status}<br>`;
                            message += `Payment Entry: ${status.payment_entry || "Not created"}<br>`;
                            message += `Processed Date: ${status.processed_date || "Not processed"}<br>`;
                            message += `Total Amount: ${format_currency(status.total_amount)}<br>`;
                            message += `Total Allocated: ${format_currency(status.total_allocated)}<br>`;
                            message += `Unallocated Amount: ${format_currency(status.unallocated_amount)}<br>`;
                            
                            frappe.msgprint({
                                title: __("Processing Status"),
                                message: message
                            });
                        }
                    }
                });
            }, __("Actions"));
        }
    },
    
    company: function(frm) {
        // Clear existing allocations when company changes
        if (frm.doc.allocations && frm.doc.allocations.length > 0) {
            frappe.confirm(
                __("Changing company will clear all existing allocations. Continue?"),
                function() {
                    frm.clear_table("allocations");
                    frm.refresh_field("allocations");
                    frm.set_value("total_allocated_amount", 0);
                    frm.set_value("total_outstanding_amount", 0);
                    frm.set_value("unallocated_amount", frm.doc.total_amount || 0);
                }
            );
        }
    },
    
    total_amount: function(frm) {
        // Update unallocated amount when total changes
        const allocated = frm.doc.total_allocated_amount || 0;
        frm.set_value("unallocated_amount", (frm.doc.total_amount || 0) - allocated);
    }
});

function show_unpaid_items_dialog(frm, unpaid_items, item_type) {
    // Prepare data for the dialog
    const data = unpaid_items.map((item, index) => [
        0, // Select checkbox (default unchecked)
        item.member_name || item.member || '',
        item.reference_doctype || '',
        item.reference_name || '',
        item.reference_date ? frappe.datetime.str_to_user(item.reference_date) : '',
        item.due_date ? frappe.datetime.str_to_user(item.due_date) : '',
        item.outstanding_amount || 0,
        item.status || '',
        item.description || ''
    ]);
    
    // Create dialog
    const dialog = new frappe.ui.Dialog({
        title: __('Select Unpaid {0}', [item_type]),
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
                                    <th>Member</th>
                                    <th>Document Type</th>
                                    <th>Document Name</th>
                                    <th>Reference Date</th>
                                    <th>Due Date</th>
                                    <th>Outstanding Amount</th>
                                    <th>Status</th>
                                    <th>Description</th>
                                </tr>
                            </thead>
                            <tbody id="unpaid-items-body">
                                ${data.map((row, index) => {
                                    const isPaid = row[7] === 'Paid';
                                    const rowClass = isPaid ? 'style="background-color: #e6ffe6;"' : '';
                                    const disabledAttr = isPaid ? 'disabled' : '';
                                    return `
                                        <tr ${rowClass}>
                                            <td><input type="checkbox" class="item-checkbox" data-index="${index}" ${disabledAttr}></td>
                                            <td>${row[1]}</td>
                                            <td>${row[2]}</td>
                                            <td><a href="/app/${row[2].toLowerCase().replace(/\s+/g, '-')}/${row[3]}" target="_blank">${row[3]}</a></td>
                                            <td>${row[4]}</td>
                                            <td>${row[5]}</td>
                                            <td>${format_currency(row[6])}</td>
                                            <td>${row[7]}</td>
                                            <td>${row[8]}</td>
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
            
            if (selected_indices.length === 0) {
                frappe.msgprint(__("Please select at least one item"));
                return;
            }
            
            // Add selected items to allocations
            selected_indices.forEach(index => {
                const item = unpaid_items[index];
                const row = frappe.model.add_child(frm.doc, 'SHG Bulk Payment Allocation', 'allocations');
                row.member = item.member;
                row.member_name = item.member_name;
                row.reference_doctype = item.reference_doctype;
                row.reference_name = item.reference_name;
                row.reference_date = item.reference_date;
                row.due_date = item.due_date;
                row.outstanding_amount = item.outstanding_amount;
                row.allocated_amount = item.outstanding_amount; // Default to full amount
                row.processing_status = "Pending";
                row.remarks = item.description || "";
            });
            
            frm.refresh_field('allocations');
            
            // Update totals
            update_bulk_payment_totals(frm);
            
            frappe.msgprint(__("{0} items added successfully", [selected_indices.length]));
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

function update_bulk_payment_totals(frm) {
    let total_allocated = 0;
    let total_outstanding = 0;
    
    (frm.doc.allocations || []).forEach(function(row) {
        total_allocated += flt(row.allocated_amount);
        total_outstanding += flt(row.outstanding_amount);
    });
    
    frm.set_value('total_allocated_amount', total_allocated);
    frm.set_value('total_outstanding_amount', total_outstanding);
    frm.set_value('unallocated_amount', flt(frm.doc.total_amount) - total_allocated);
    
    frm.refresh_fields();
}

// Helper function to format currency
function format_currency(value) {
    if (value === null || value === undefined) return '';
    return frappe.format(value, { fieldtype: 'Currency' });
}

// Helper function for float conversion
function flt(value, precision = 2) {
    if (value === null || value === undefined) return 0;
    return parseFloat(value.toFixed(precision));
}

frappe.ui.form.on('SHG Bulk Payment Allocation', {
    allocated_amount: function(frm, cdt, cdn) {
        // Validate allocated amount doesn't exceed outstanding
        var row = frappe.get_doc(cdt, cdn);
        if (flt(row.allocated_amount) > flt(row.outstanding_amount)) {
            frappe.msgprint(__('Allocated amount cannot exceed outstanding amount'));
            frappe.model.set_value(cdt, cdn, 'allocated_amount', row.outstanding_amount);
            return;
        }
        
        // Update totals
        update_bulk_payment_totals(frm);
    },
    
    reference_name: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        if (row.reference_doctype && row.reference_name) {
            // Auto-fetch reference details
            frappe.call({
                method: "frappe.client.get",
                args: {
                    doctype: row.reference_doctype,
                    name: row.reference_name
                },
                callback: function(r) {
                    if (r.message) {
                        const doc = r.message;
                        frappe.model.set_value(cdt, cdn, 'member', doc.member);
                        frappe.model.set_value(cdt, cdn, 'member_name', doc.member_name);
                        
                        // Set dates based on document type
                        if (row.reference_doctype === "SHG Contribution Invoice") {
                            frappe.model.set_value(cdt, cdn, 'reference_date', doc.invoice_date);
                            frappe.model.set_value(cdt, cdn, 'due_date', doc.due_date || doc.invoice_date);
                            frappe.model.set_value(cdt, cdn, 'outstanding_amount', doc.amount);
                        } else if (row.reference_doctype === "SHG Contribution") {
                            frappe.model.set_value(cdt, cdn, 'reference_date', doc.contribution_date);
                            frappe.model.set_value(cdt, cdn, 'due_date', doc.due_date || doc.contribution_date);
                            frappe.model.set_value(cdt, cdn, 'outstanding_amount', (doc.expected_amount || doc.amount) - (doc.paid_amount || 0));
                        } else if (row.reference_doctype === "SHG Meeting Fine") {
                            frappe.model.set_value(cdt, cdn, 'reference_date', doc.fine_date);
                            frappe.model.set_value(cdt, cdn, 'due_date', doc.due_date || doc.fine_date);
                            frappe.model.set_value(cdt, cdn, 'outstanding_amount', doc.amount - (doc.paid_amount || 0));
                        }
                        
                        // Auto-set allocated amount to outstanding amount
                        frappe.model.set_value(cdt, cdn, 'allocated_amount', flt(doc.amount || doc.expected_amount || doc.amount));
                    }
                }
            });
        }
    }
});