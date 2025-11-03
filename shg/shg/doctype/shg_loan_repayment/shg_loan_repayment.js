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
                    frappe.call({
                        method: "shg.shg.doctype.shg_loan_repayment.shg_loan_repayment.calculate_repayment_breakdown",
                        args: {
                            doc: frm.doc
                        },
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
            frappe.call({
                method: "shg.shg.doctype.shg_loan_repayment.shg_loan_repayment.calculate_repayment_breakdown",
                args: {
                    doc: frm.doc
                },
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