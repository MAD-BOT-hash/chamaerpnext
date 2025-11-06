frappe.ui.form.on("SHG Loan", {
    refresh: function(frm) {
        // Add "Pull Unpaid Installments" button
        frm.add_custom_button(__("Pull Unpaid Installments"), function() {
            pull_unpaid_installments(frm);
        });
        
        // Add "Apply Payments" button
        frm.add_custom_button(__("Apply Payments"), function() {
            apply_inline_repayments(frm);
        });
        
        // Add "🔄 Recalculate Loan Summary (SHG)" button (visible even after submit)
        frm.add_custom_button("🔄 Recalculate Loan Summary (SHG)", function () {
            frappe.call({
                method: "shg.shg.doctype.shg_loan.shg_loan.recalculate_loan_summary",
                args: { loan_name: frm.doc.name },
                callback: function (r) {
                    if (r.message) {
                        frappe.show_alert(__("Loan summary recalculated successfully"));
                        frm.reload_doc();
                    }
                }
            });
        }).addClass("btn-primary");
    }
});

// Handle changes in the repayment schedule table
frappe.ui.form.on('SHG Loan Repayment Schedule', {
    pay_now: function(frm, cdt, cdn) {
        compute_and_update_totals(frm);
    },
    
    amount_to_pay: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        // Validate that amount_to_pay doesn't exceed remaining amount
        if (flt(row.amount_to_pay) > flt(row.remaining_amount)) {
            frappe.msgprint(__("Amount to pay cannot exceed remaining amount"));
            row.amount_to_pay = row.remaining_amount;
            frm.refresh_field("repayment_schedule");
        }
        compute_and_update_totals(frm);
    }
});

// Function to pull unpaid installments
function pull_unpaid_installments(frm) {
    if (!frm.doc.name) {
        frappe.msgprint(__("Please save the loan first."));
        return;
    }
    
    frappe.call({
        method: "shg.shg.doctype.shg_loan.shg_loan.pull_unpaid_installments",
        args: {
            loan_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                // Clear existing schedule
                frm.clear_table('repayment_schedule');
                
                // Add unpaid installments to the schedule
                r.message.forEach(function(installment) {
                    var row = frm.add_child('repayment_schedule');
                    row.name = installment.name;
                    row.installment_no = installment.installment_no;
                    row.due_date = installment.due_date;
                    row.principal_component = installment.principal_component;
                    row.interest_component = installment.interest_component;
                    row.total_payment = installment.total_payment;
                    row.amount_paid = installment.amount_paid;
                    row.unpaid_balance = installment.unpaid_balance;
                    row.status = installment.status;
                    row.remaining_amount = installment.remaining_amount;
                    row.pay_now = installment.pay_now;
                    row.amount_to_pay = installment.amount_to_pay;
                });
                
                frm.refresh_field('repayment_schedule');
                frappe.show_alert(__("Unpaid installments pulled successfully"));
                
                // Compute and update totals
                compute_and_update_totals(frm);
            }
        }
    });
}

// Function to apply inline repayments
function apply_inline_repayments(frm) {
    if (!frm.doc.name) {
        frappe.msgprint(__("Please save the loan first."));
        return;
    }
    
    // Collect selected repayments
    var repayments = [];
    var total_selected = 0;
    
    (frm.doc.repayment_schedule || []).forEach(function(row) {
        if (row.pay_now && flt(row.amount_to_pay) > 0) {
            repayments.push({
                rowname: row.name,
                amount_to_pay: flt(row.amount_to_pay)
            });
            total_selected += flt(row.amount_to_pay);
        }
    });
    
    if (repayments.length === 0) {
        frappe.msgprint(__("Please select at least one installment and enter amount to pay."));
        return;
    }
    
    // Confirm before posting
    frappe.confirm(
        __("Are you sure you want to post payments totaling {0}?", [format_currency(total_selected)]),
        function() {
            // User clicked "Yes"
            frappe.call({
                method: "shg.shg.doctype.shg_loan.shg_loan.apply_inline_repayments",
                args: {
                    loan_name: frm.doc.name,
                    allocations: repayments,
                    posting_date: frappe.datetime.get_today()
                },
                callback: function(r) {
                    if (r.message && r.message.status === "success") {
                        frappe.show_alert(r.message.message);
                        frm.reload_doc();
                    } else {
                        frappe.msgprint(__("Failed to post payments"));
                    }
                }
            });
        }
    );
}

// Function to compute and update totals
function compute_and_update_totals(frm) {
    var total_selected = 0;
    var overdue_amount = 0;
    var outstanding_amount = 0;
    var today = frappe.datetime.get_today();
    
    // Calculate totals from repayment schedule
    (frm.doc.repayment_schedule || []).forEach(function(row) {
        // Add to total selected if pay_now is checked
        if (row.pay_now) {
            total_selected += flt(row.amount_to_pay);
        }
        
        // Add to outstanding amount
        outstanding_amount += flt(row.unpaid_balance);
        
        // Check if overdue
        if (row.due_date && row.due_date < today && 
            row.status !== "Paid" && flt(row.unpaid_balance) > 0) {
            overdue_amount += flt(row.unpaid_balance);
        }
    });
    
    // Update parent document fields
    frm.set_value("inline_total_selected", total_selected);
    frm.set_value("inline_overdue", overdue_amount);
    frm.set_value("inline_outstanding", outstanding_amount);
    
    // Refresh the fields
    frm.refresh_field("inline_total_selected");
    frm.refresh_field("inline_overdue");
    frm.refresh_field("inline_outstanding");
    
    // Update EMI breakdown HTML
    update_emi_breakdown(frm, total_selected, overdue_amount, outstanding_amount);
}

// Function to update EMI breakdown HTML
function update_emi_breakdown(frm, total_selected, overdue_amount, outstanding_amount) {
    var html = `
        <div style="padding: 10px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;">
            <h4 style="margin-top: 0;">EMI Summary</h4>
            <div style="display: flex; justify-content: space-between;">
                <div><strong>Total Selected:</strong></div>
                <div>${format_currency(total_selected)}</div>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <div><strong>Overdue Amount:</strong></div>
                <div>${format_currency(overdue_amount)}</div>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <div><strong>Outstanding Amount:</strong></div>
                <div>${format_currency(outstanding_amount)}</div>
            </div>
        </div>
    `;
    
    frm.set_value("emi_breakdown", html);
    frm.refresh_field("emi_breakdown");
}

// Helper function to format currency
function format_currency(amount) {
    return frappe.format(amount, {fieldtype: "Currency", options: "KES"});
}