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
    },
    
    validate: function(frm) {
        // Validate installment adjustments before saving
        if (frm.doc.installment_adjustment && frm.doc.installment_adjustment.length > 0) {
            var total_installment_payments = 0;
            
            $.each(frm.doc.installment_adjustment, function(i, row) {
                // Validate that amount to repay is not negative
                if (flt(row.amount_to_repay) < 0) {
                    frappe.throw(__("Amount to repay for installment {0} cannot be negative.", [row.installment_no]));
                }
                
                // Validate that amount to repay does not exceed unpaid balance
                if (flt(row.amount_to_repay) > flt(row.unpaid_balance)) {
                    frappe.throw(
                        __("Amount to pay ({0}) cannot exceed remaining amount ({1}) for Installment {2}.",
                           [format_currency(row.amount_to_repay), format_currency(row.unpaid_balance), row.installment_no])
                    );
                }
                
                total_installment_payments += flt(row.amount_to_repay);
            });
            
            // Validate that total installment payments match total paid
            if (flt(total_installment_payments) !== flt(frm.doc.total_paid)) {
                frappe.throw(__("Total installment payments ({0}) must equal Total Paid ({1}).",
                               [format_currency(total_installment_payments), format_currency(frm.doc.total_paid)]));
            }
        }
    }
});

frappe.ui.form.on("SHG Repayment Installment Adjustment", {
    amount_to_repay: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        
        // Validate that amount to repay is not negative
        if (flt(row.amount_to_repay) < 0) {
            frappe.msgprint(__("Amount to repay cannot be negative."));
            frappe.model.set_value(cdt, cdn, "amount_to_repay", 0);
            return;
        }
        
        // Validate that amount to repay does not exceed unpaid balance
        if (flt(row.amount_to_repay) > flt(row.unpaid_balance)) {
            frappe.msgprint(
                __("Amount to pay ({0}) cannot exceed remaining amount ({1}) for Installment {2}.",
                   [format_currency(row.amount_to_repay), format_currency(row.unpaid_balance), row.installment_no])
            );
            frappe.model.set_value(cdt, cdn, "amount_to_repay", row.unpaid_balance);
        }
        
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

// Helper function to format currency
function format_currency(amount) {
    return frappe.format(amount, {fieldtype: "Currency", options: "KES"});
}