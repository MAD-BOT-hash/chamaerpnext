// Copyright (c) 2026, SHG Solutions
// License: MIT

frappe.ui.form.on('SHG Multi Member Loan Repayment', {
    setup: function(frm) {
        frm.set_query('payment_account', function() {
            return {
                filters: {
                    'account_type': ['in', ['Cash', 'Bank']],
                    'is_group': 0
                }
            };
        });
    },
    
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Get Active Loans'), function() {
                frappe.call({
                    method: "shg.api.loan_repayment.get_active_loans",
                    args: {
                        member: frm.doc.member || null
                    },
                    callback: function(r) {
                        if (r.message && r.message.success && r.message.data.length > 0) {
                            // Clear existing rows
                            frm.clear_table('loans');
                            
                            // Add new rows for each active loan
                            r.message.data.forEach(function(loan) {
                                var row = frm.add_child('loans');
                                row.member = loan.member;
                                row.loan = loan.name;
                                row.loan_type = loan.loan_type;
                                row.outstanding = loan.total_outstanding_amount;
                                row.repayment_amount = loan.total_outstanding_amount; // Set default to full amount
                                row.installment_due_date = loan.repayment_start_date;
                                
                                // Fetch member name
                                if (loan.member) {
                                    frappe.call({
                                        method: "frappe.client.get_value",
                                        args: {
                                            doctype: "SHG Member",
                                            fieldname: "member_name",
                                            filters: { name: loan.member }
                                        },
                                        callback: function(member_r) {
                                            if (member_r.message && member_r.message.member_name) {
                                                frappe.model.set_value(row.doctype, row.name, 'member_name', member_r.message.member_name);
                                            }
                                        }
                                    });
                                }
                            });
                            
                            frm.refresh_field('loans');
                            frm.trigger('recalculate_totals');
                            
                            frappe.show_alert({
                                message: __("Loaded {0} active loans", [r.message.data.length]),
                                indicator: 'green'
                            });
                        } else {
                            var message = r.message ? r.message.message : "No active loans found";
                            frappe.show_alert({
                                message: __(message),
                                indicator: 'orange'
                            });
                        }
                    }
                });
            });
            
            // Add button to refresh outstanding amounts for existing rows
            frm.add_custom_button(__('Refresh Outstanding'), function() {
                // Refresh outstanding amounts for all rows
                (frm.doc.loans || []).forEach(function(row) {
                    if (row.loan) {
                        frappe.call({
                            method: "shg.api.loan_repayment.get_outstanding_amount",
                            args: {
                                loan: row.loan
                            },
                            callback: function(r) {
                                if (r.message && r.message.success) {
                                    frappe.model.set_value(row.doctype, row.name, 'outstanding', r.message.data);
                                }
                            }
                        });
                    }
                });
            });
        }
    },
    
    recalculate_totals: function(frm) {
        var total = 0;
        var count = 0;
        (frm.doc.loans || []).forEach(function(row) {
            total += row.repayment_amount || 0;
            count += 1;
        });
        frm.set_value('total_repayment_amount', total);
        frm.set_value('total_selected_loans', count);
    }
});

frappe.ui.form.on('SHG Multi Member Loan Repayment Item', {
    loans_add: function(frm, cdt, cdn) {
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
    
    loan: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        if (row.loan) {
            // Auto-fetch loan details
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "SHG Loan",
                    fieldname: ["loan_type", "total_outstanding_amount", "repayment_start_date", "member"],
                    filters: { name: row.loan }
                },
                callback: function(r) {
                    if (r.message) {
                        // Set loan type
                        if (r.message.loan_type) {
                            frappe.model.set_value(cdt, cdn, 'loan_type', r.message.loan_type);
                        }
                        
                        // Set outstanding loan balance
                        if (r.message.total_outstanding_amount !== undefined) {
                            frappe.model.set_value(cdt, cdn, 'outstanding', r.message.total_outstanding_amount);
                            
                            // Set repayment amount to outstanding amount by default
                            frappe.model.set_value(cdt, cdn, 'repayment_amount', r.message.total_outstanding_amount);
                        }
                        
                        // Set installment due date
                        if (r.message.repayment_start_date) {
                            frappe.model.set_value(cdt, cdn, 'installment_due_date', r.message.repayment_start_date);
                        }
                        
                        // Set member if not already set
                        if (!row.member && r.message.member) {
                            frappe.model.set_value(cdt, cdn, 'member', r.message.member);
                            
                            // Fetch member name
                            frappe.call({
                                method: "frappe.client.get_value",
                                args: {
                                    doctype: "SHG Member",
                                    fieldname: "member_name",
                                    filters: { name: r.message.member }
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
            });
        }
    },
    
    repayment_amount: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        
        // Validate that repayment amount does not exceed outstanding loan balance
        if (row.repayment_amount && row.outstanding && row.repayment_amount > row.outstanding) {
            frappe.show_alert({
                message: __("Repayment amount cannot exceed outstanding loan balance"),
                indicator: 'red'
            });
            
            // Reset repayment amount to outstanding loan balance
            frappe.model.set_value(cdt, cdn, 'repayment_amount', row.outstanding);
            frappe.validated = false;
        }
        
        // Update total when repayment amount changes
        var total = 0;
        (frm.doc.loans || []).forEach(function(row) {
            total += row.repayment_amount || 0;
        });
        frm.set_value('total_repayment_amount', total);
    }
});