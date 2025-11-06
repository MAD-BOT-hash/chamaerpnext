frappe.ui.form.on("SHG Loan Repayment", {
    setup: function(frm) {
        // Set query for loan field to only show submitted loans with outstanding balance
        frm.set_query("loan", function() {
            return {
                filters: {
                    docstatus: 1,
                    balance_amount: [">", 0]
                }
            };
        });
    },
    
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            // Add button to calculate repayment breakdown
            frm.add_custom_button(__('Calculate Breakdown'), function() {
                if (frm.doc.loan && frm.doc.total_paid) {
                    frm.call({
                        method: 'calculate_repayment_breakdown',
                        doc: frm.doc,
                        callback: function(r) {
                            if (r.message) {
                                frm.set_value("principal_amount", r.message.principal_amount);
                                frm.set_value("interest_amount", r.message.interest_amount);
                                frm.set_value("penalty_amount", r.message.penalty_amount);
                                frm.set_value("balance_after_payment", r.message.balance_after_payment);
                                frm.refresh_fields();
                            }
                        }
                    });
                } else {
                    frappe.msgprint("Please select a loan and enter the total paid amount first.");
                }
            });
            
            // Add button to pull unpaid installments
            if (frm.doc.loan) {
                frm.add_custom_button(__('Pull Unpaid Installments'), function() {
                    frm.call({
                        method: 'pull_unpaid_installments',
                        doc: frm.doc,
                        callback: function(r) {
                            if (r.message) {
                                frm.refresh_fields();
                                frappe.msgprint("Unpaid installments pulled successfully.");
                            }
                        }
                    });
                });
            }
            
            // Add button to recalculate installment balances
            if (frm.doc.installment_adjustment && frm.doc.installment_adjustment.length > 0) {
                frm.add_custom_button(__('Recalculate Balances'), function() {
                    frm.call({
                        method: 'shg.shg.api.repayment_adjustment.recalculate_installment_balances',
                        args: {
                            loan_repayment_name: frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message && r.message.status === "success") {
                                frm.reload_doc();
                                frappe.msgprint(r.message.message);
                            } else if (r.message) {
                                frappe.msgprint("Error: " + r.message.message);
                            }
                        }
                    });
                });
            }
        }
        
        // Add button to refresh installment adjustment
        if (frm.doc.docstatus === 0 && frm.doc.loan) {
            frm.add_custom_button(__('Refresh Installments'), function() {
                frm.call({
                    method: 'shg.shg.api.repayment_adjustment.refresh_installment_adjustment',
                    args: {
                        loan_repayment_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message && r.message.status === "success") {
                            frm.reload_doc();
                            frappe.msgprint(r.message.message);
                        } else if (r.message) {
                            frappe.msgprint("Error: " + r.message.message);
                        }
                    }
                });
            });
        }
    },
    
    loan: function(frm) {
        if (frm.doc.loan) {
            // Fetch member details from loan
            frappe.db.get_doc("SHG Loan", frm.doc.loan).then(loan_doc => {
                frm.set_value("member", loan_doc.member);
                frm.set_value("member_name", loan_doc.member_name);
                frm.set_value("outstanding_balance", loan_doc.balance_amount);
                
                // Suggest amount = next installment unpaid
                if (loan_doc.repayment_schedule) {
                    for (let row of loan_doc.repayment_schedule) {
                        if (row.unpaid_balance > 0) {
                            frm.set_value("total_paid", row.unpaid_balance);
                            break;
                        }
                    }
                }
                
                frm.refresh_fields();
            });
        }
    },
    
    total_paid: function(frm) {
        if (frm.doc.loan && frm.doc.total_paid) {
            // Auto-calculate breakdown when total paid changes
            frm.call({
                method: 'calculate_repayment_breakdown',
                doc: frm.doc,
                callback: function(r) {
                    if (r.message) {
                        frm.set_value("principal_amount", r.message.principal_amount);
                        frm.set_value("interest_amount", r.message.interest_amount);
                        frm.set_value("penalty_amount", r.message.penalty_amount);
                        frm.set_value("outstanding_balance", r.message.outstanding_balance);
                        frm.set_value("balance_after_payment", r.message.balance_after_payment);
                        frm.refresh_fields();
                    }
                }
            });
        }
    }
});

// Handle changes in installment adjustment table
frappe.ui.form.on("SHG Repayment Installment Adjustment", {
    amount_to_repay: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        // Auto-calculate remaining balance
        row.remaining = flt(row.total_due) - flt(row.amount_to_repay);
        frm.refresh_field("installment_adjustment");
        
        // Recalculate total paid
        let total_paid = 0;
        frm.doc.installment_adjustment.forEach(installment => {
            total_paid += flt(installment.amount_to_repay);
        });
        frm.set_value("total_paid", total_paid);
    },
    
    installment_adjustment_remove: function(frm) {
        // Recalculate total paid when an installment is removed
        let total_paid = 0;
        frm.doc.installment_adjustment.forEach(installment => {
            total_paid += flt(installment.amount_to_repay);
        });
        frm.set_value("total_paid", total_paid);
    }
});