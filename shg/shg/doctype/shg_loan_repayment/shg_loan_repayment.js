frappe.ui.form.on('SHG Loan Repayment', {
  refresh(frm) {
    if (!frm.doc.loan) return;

    if (!frm.custom_buttons_added) {
      // Add button to fetch unpaid installments for repayment breakdown
      frm.add_custom_button(__('Fetch Unpaid Installments'), function() {
        if (!frm.doc.loan) {
          frappe.msgprint('Select a Loan first.');
          return;
        }
        frm.call({
          method: 'get_unpaid_installments',
          doc: frm.doc,
          callback: function(r) {
            if (r.message) {
              frm.refresh_field('repayment_breakdown');
              frappe.show_alert('Unpaid installments loaded successfully.');
            }
          }
        });
      });

      // Add button to apply repayment
      frm.add_custom_button(__('Apply Repayment'), function() {
        if (frm.doc.total_paid > 0) {
          frappe.confirm(
            'Are you sure you want to apply this repayment?',
            function() {
              // Submit the document
              frm.savesubmit();
            }
          );
        } else {
          frappe.msgprint('Please enter a repayment amount first.');
        }
      });

      frm.custom_buttons_added = true;
    }
  }
});

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
        
        // Set query for reference_schedule_row to only show unpaid schedule rows for the selected loan
        frm.set_query("reference_schedule_row", function() {
            if (frm.doc.loan) {
                return {
                    query: "shg.shg.doctype.shg_loan_repayment.shg_loan_repayment.get_unpaid_schedule_rows",
                    filters: {
                        loan: frm.doc.loan
                    }
                };
            }
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
        } else {
            // Clear values if loan is cleared
            frm.set_value("member", "");
            frm.set_value("member_name", "");
            frm.set_value("outstanding_balance", 0);
            frm.refresh_fields();
        }
    },
    
    total_paid: function(frm) {
        if (frm.doc.loan && frm.doc.total_paid) {
            // Auto-calculate breakdown when total paid changes
            frm.trigger("calculate_breakdown");
        }
    },
    
    calculate_breakdown: function(frm) {
        if (frm.doc.loan && frm.doc.total_paid) {
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
        
        // Validate that amount to repay does not exceed unpaid balance
        if (flt(row.amount_to_repay) > flt(row.unpaid_balance)) {
            frappe.msgprint(`Amount to repay cannot exceed unpaid balance (${row.unpaid_balance}).`);
            row.amount_to_repay = row.unpaid_balance;
        }
        
        // Update status based on amount to repay
        if (flt(row.amount_to_repay) >= flt(row.unpaid_balance)) {
            row.status = "Paid";
        } else if (flt(row.amount_to_repay) > 0) {
            row.status = "Partially Paid";
        } else {
            row.status = "Pending";
        }
        
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

// Handle changes in repayment breakdown table
frappe.ui.form.on("SHG Repayment Breakdown", {
    amount_to_pay: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        
        // Validate that amount to pay does not exceed unpaid balance
        if (flt(row.amount_to_pay) > flt(row.unpaid_balance)) {
            frappe.msgprint(`Amount to pay cannot exceed unpaid balance (${row.unpaid_balance}).`);
            row.amount_to_pay = row.unpaid_balance;
            frm.refresh_field("repayment_breakdown");
        }
        
        // Update status based on amount to pay
        if (flt(row.amount_to_pay) >= flt(row.unpaid_balance)) {
            row.status = "Fully Paid";
        } else if (flt(row.amount_to_pay) > 0) {
            row.status = "Partially Paid";
        } else {
            row.status = "Unpaid";
        }
        
        // Recalculate total paid
        let total_paid = 0;
        frm.doc.repayment_breakdown.forEach(installment => {
            total_paid += flt(installment.amount_to_pay);
        });
        frm.set_value("total_paid", total_paid);
        
        // Auto-calculate breakdown when total paid changes
        if (frm.doc.loan && total_paid > 0) {
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
    },
    
    repayment_breakdown_remove: function(frm) {
        // Recalculate total paid when an installment is removed
        let total_paid = 0;
        frm.doc.repayment_breakdown.forEach(installment => {
            total_paid += flt(installment.amount_to_pay);
        });
        frm.set_value("total_paid", total_paid);
    }
});