frappe.ui.form.on('SHG Loan', {
    refresh: function(frm) {
        // Add custom buttons based on status
        if (frm.doc.docstatus === 1) {
            if (frm.doc.status === 'Applied') {
                frm.add_custom_button(__('Approve Loan'), function() {
                    frm.set_value('status', 'Approved');
                    frm.save();
                }).addClass('btn-primary');
            }
            
            if (frm.doc.status === 'Approved') {
                frm.add_custom_button(__('Disburse Loan'), function() {
                    frappe.call({
                        method: 'shg.shg.doctype.shg_loan.shg_loan.disburse_loan',
                        args: { docname: frm.doc.name },
                        callback: function(r) {
                            if (!r.exc) {
                                frm.reload_doc();
                                frappe.msgprint(__('Loan disbursed successfully'));
                            }
                        }
                    });
                }).addClass('btn-primary');
            }
            
            if (frm.doc.status === 'Disbursed') {
                frm.add_custom_button(__('Record Repayment'), function() {
                    frappe.new_doc('SHG Loan Repayment', {
                        loan: frm.doc.name,
                        member: frm.doc.member,
                        member_name: frm.doc.member_name
                    });
                });
                
                frm.add_custom_button(__('View Repayment Schedule'), function() {
                    frappe.route_options = {
                        "loan": frm.doc.name
                    };
                    frappe.set_route("query-report", "Loan Repayment Schedule");
                });
            }
            
            // Print loan agreement
            frm.add_custom_button(__('Print Agreement'), function() {
                frappe.utils.print(
                    frm.doc.doctype,
                    frm.doc.name,
                    'SHG Loan Agreement'
                );
            });
        }
        
        // Add dashboard indicators
        if (frm.doc.docstatus === 1) {
            frm.dashboard.add_indicator(__('Status: {0}', [frm.doc.status]), 
                frm.doc.status === 'Disbursed' ? 'green' : 
                frm.doc.status === 'Approved' ? 'blue' : 
                frm.doc.status === 'Applied' ? 'orange' : 'grey');
                
            if (frm.doc.balance_amount > 0) {
                frm.dashboard.add_indicator(__('Balance: {0}', [format_currency(frm.doc.balance_amount, 'KES')]), 'orange');
            }
        }
    },
    
    member: function(frm) {
        if (frm.doc.member) {
            // Auto-populate member name
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'SHG Member',
                    filters: { name: frm.doc.member },
                    fieldname: 'member_name'
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('member_name', r.message.member_name);
                    }
                }
            });
            
            // Check member eligibility
            frappe.call({
                method: 'check_member_eligibility',
                doc: frm.doc,
                callback: function(r) {
                    if (r.message && !r.message.eligible) {
                        frappe.msgprint({
                            title: __('Not Eligible'),
                            message: r.message.reason,
                            indicator: 'orange'
                        });
                    }
                }
            });
        }
    },
    
    loan_type: function(frm) {
        if (frm.doc.loan_type) {
            // Auto-populate loan type details
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SHG Loan Type',
                    name: frm.doc.loan_type
                },
                callback: function(r) {
                    if (r.message) {
                        let loan_type = r.message;
                        
                        // Set default values if not already set
                        if (loan_type.interest_rate && !frm.doc.interest_rate) {
                            frm.set_value('interest_rate', loan_type.interest_rate);
                        }
                        if (loan_type.interest_type && !frm.doc.interest_type) {
                            frm.set_value('interest_type', loan_type.interest_type);
                        }
                        if (loan_type.default_tenure_months && !frm.doc.loan_period_months) {
                            frm.set_value('loan_period_months', loan_type.default_tenure_months);
                        }
                        if (loan_type.repayment_frequency && !frm.doc.repayment_frequency) {
                            frm.set_value('repayment_frequency', loan_type.repayment_frequency);
                        }
                    }
                }
            });
        }
    },
    
    loan_amount: function(frm) {
        if (frm.doc.loan_amount) {
            // Validate against maximum loan amount setting
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'SHG Settings',
                    fieldname: 'maximum_loan_amount'
                },
                callback: function(r) {
                    if (r.message && r.message.maximum_loan_amount) {
                        let max_amount = r.message.maximum_loan_amount;
                        if (frm.doc.loan_amount > max_amount) {
                            frappe.msgprint({
                                title: __('Exceeds Limit'),
                                message: __('Loan amount exceeds the maximum allowed amount of KES {0}', [format_currency(max_amount, 'KES')]),
                                indicator: 'orange'
                            });
                        }
                    }
                }
            });
            
            // Also check against loan type limits
            if (frm.doc.loan_type) {
                frappe.call({
                    method: 'frappe.client.get',
                    args: {
                        doctype: 'SHG Loan Type',
                        name: frm.doc.loan_type
                    },
                    callback: function(r) {
                        if (r.message) {
                            let loan_type = r.message;
                            if (loan_type.minimum_amount && frm.doc.loan_amount < loan_type.minimum_amount) {
                                frappe.msgprint({
                                    title: __('Below Minimum'),
                                    message: __('Loan amount is below the minimum of KES {0} for this loan type', [format_currency(loan_type.minimum_amount, 'KES')]),
                                    indicator: 'orange'
                                });
                            }
                            if (loan_type.maximum_amount && frm.doc.loan_amount > loan_type.maximum_amount) {
                                frappe.msgprint({
                                    title: __('Exceeds Limit'),
                                    message: __('Loan amount exceeds the maximum of KES {0} for this loan type', [format_currency(loan_type.maximum_amount, 'KES')]),
                                    indicator: 'orange'
                                });
                            }
                        }
                    }
                });
            }
        }
        // Recalculate repayment details
        frm.trigger('calculate_repayment_details');
    },
    
    interest_rate: function(frm) {
        // Recalculate repayment details
        frm.trigger('calculate_repayment_details');
    },
    
    loan_period_months: function(frm) {
        // Recalculate repayment details
        frm.trigger('calculate_repayment_details');
    },
    
    calculate_repayment_details: function(frm) {
        if (frm.doc.loan_amount && frm.doc.interest_rate && frm.doc.loan_period_months) {
            frappe.call({
                method: 'calculate_repayment_details',
                doc: frm.doc,
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('monthly_installment', r.message.monthly_installment);
                        frm.set_value('total_payable', r.message.total_payable);
                    }
                }
            });
        }
    },
    
    status: function(frm) {
        if (frm.doc.status === 'Approved' && !frm.doc.approved_date) {
            frm.set_value('approved_date', frappe.datetime.get_today());
            frm.set_value('approved_by', frappe.session.user);
        }
        
        if (frm.doc.status === 'Disbursed' && !frm.doc.disbursement_date) {
            frm.set_value('disbursement_date', frappe.datetime.get_today());
        }
    }
});