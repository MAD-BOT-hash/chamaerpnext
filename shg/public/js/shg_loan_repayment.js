frappe.ui.form.on("SHG Loan Repayment", {
    refresh: function(frm) {
        // Add "Pull Unpaid Installments" button
        if (frm.doc.docstatus === 0) { // Only show for draft documents
            frm.add_custom_button(__("Pull Unpaid Installments"), function() {
                frappe.call({
                    method: "shg.shg.doctype.shg_loan_repayment.shg_loan_repayment.fetch_unpaid_installments",
                    doc: frm.doc,
                    callback: function(r) {
                        if (!r.exc) {
                            frm.refresh_fields();
                        }
                    }
                });
            });
        }
    },
    
    total_paid: function(frm) {
        if (frm.doc.loan && frm.doc.total_paid) {
            frappe.call({
                method: "shg.shg.doctype.shg_loan_repayment.shg_loan_repayment.calculate_repayment_breakdown",
                doc: frm.doc,
                callback: function(r) {
                    if (!r.exc && r.message) {
                        frm.refresh_fields();
                    }
                }
            });
        }
    }
});

frappe.ui.form.on("SHG Repayment Installment Adjustment", {
    amount_to_repay: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        
        // Calculate remaining amount
        var remaining = flt(row.unpaid_balance) - flt(row.amount_to_repay);
        frappe.model.set_value(cdt, cdn, "remaining_amount", remaining);
        
        // Update status based on amount to repay
        if (flt(row.amount_to_repay) >= flt(row.unpaid_balance)) {
            frappe.model.set_value(cdt, cdn, "status", "Paid");
        } else if (flt(row.amount_to_repay) > 0) {
            frappe.model.set_value(cdt, cdn, "status", "Partially Paid");
        } else {
            frappe.model.set_value(cdt, cdn, "status", "Unpaid");
        }
        
        // Refresh the grid
        frm.refresh_field("installment_adjustment");
    },
    
    installment_adjustment_add: function(frm, cdt, cdn) {
        // Set default values for new rows
        var row = locals[cdt][cdn];
        if (!row.amount_to_repay) {
            frappe.model.set_value(cdt, cdn, "amount_to_repay", flt(row.unpaid_balance));
            frappe.model.set_value(cdt, cdn, "remaining_amount", 0);
        }
    }
});
