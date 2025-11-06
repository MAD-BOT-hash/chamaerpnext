frappe.ui.form.on('SHG Loan Repayment', {
  refresh(frm) {
    if (!frm.doc.loan) return;

    if (!frm.custom_buttons_added) {
      frm.add_custom_button('Fetch Unpaid Installments', async () => {
        if (!frm.doc.loan) {
          frappe.msgprint('Select a Loan first.');
          return;
        }
        const rows = await frappe.call({
          method: 'shg.shg.api.loan.get_unpaid_installments',
          args: { loan: frm.doc.loan }
        });
        // Display in a child table named "Repayment Items" (create it if you don't have it)
        const data = rows.message || [];
        frm.clear_table('repayment_items');
        data.forEach(r => {
          const d = frm.add_child('repayment_items');
          d.schedule_row = r.name;
          d.due_date = r.due_date;
          d.installment = r.total_payment;
          d.amount_paid = r.amount_paid || 0;
          d.remaining_amount = r.remaining_amount || (r.total_payment - (r.amount_paid || 0));
          d.to_pay = 0; // user may enter partial here
        });
        frm.refresh_fields('repayment_items');
        frappe.show_alert('Unpaid installments fetched.');
      });

      frm.custom_buttons_added = true;
    }
  },

  // helper: sum user-entered partials into `amount`
  repayment_items_add(frm, cdt, cdn) { sum_to_pay(frm); },
  repayment_items_remove(frm, cdt, cdn) { sum_to_pay(frm); }
});

function sum_to_pay(frm){
  let total = 0;
  (frm.doc.repayment_items || []).forEach(r => total += (r.to_pay || 0));
  frm.set_value('total_paid', total);
  frm.refresh_field('total_paid');
}

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
            
            // Add button to fetch unpaid installments
            if (frm.doc.loan) {
                frm.add_custom_button(__('Fetch Unpaid Installments'), function() {
                    frm.call({
                        method: 'get_unpaid_installments',
                        doc: frm.doc,
                        callback: function(r) {
                            if (r.message) {
                                frm.refresh_field('installment_adjustment');
                                frappe.msgprint("Unpaid installments fetched successfully.");
                            }
                        }
                    });
                });
            }
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