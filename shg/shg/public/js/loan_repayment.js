// Enhanced SHG Loan Repayment Client-Side Logic
// This module provides real-time calculations, validations, and improved UX

frappe.provide("shg.loan_repayment");

shg.loan_repayment = {
    // Cache for storing loan data to reduce server calls
    loan_cache: {},
    
    // Format currency values
    format_currency: function(value) {
        return frappe.format(value, {"fieldtype": "Currency"});
    },
    
    // Calculate payment breakdown in real-time
    calculate_payment_breakdown: function(frm) {
        if (!frm.doc.loan || !frm.doc.total_paid) return;
        
        // Use cached loan data if available
        let loan_data = this.loan_cache[frm.doc.loan];
        if (!loan_data) {
            // Fetch loan data if not cached
            frappe.db.get_doc("SHG Loan", frm.doc.loan).then(loan_doc => {
                this.loan_cache[frm.doc.loan] = loan_doc;
                this._perform_breakdown_calculation(frm, loan_doc);
            });
        } else {
            this._perform_breakdown_calculation(frm, loan_data);
        }
    },
    
    // Internal method to perform breakdown calculation
    _perform_breakdown_calculation: function(frm, loan_doc) {
        let total_paid = flt(frm.doc.total_paid);
        let outstanding_balance = flt(loan_doc.balance_amount);
        let balance_after_payment = Math.max(0, outstanding_balance - total_paid);
        
        // Get settings for penalty calculation
        frappe.db.get_single_value("SHG Settings", "loan_penalty_rate").then(penalty_rate => {
            penalty_rate = flt(penalty_rate || 5); // Default 5%
            
            // Calculate penalty if repayment is late
            let penalty_amount = 0;
            if (loan_doc.next_due_date && frappe.datetime.get_diff(frm.doc.repayment_date, loan_doc.next_due_date) > 0) {
                // Calculate days overdue
                let days_overdue = frappe.datetime.get_diff(frm.doc.repayment_date, loan_doc.next_due_date);
                if (days_overdue > 0) {
                    // Calculate penalty based on outstanding balance and days overdue
                    let daily_penalty_rate = penalty_rate / 100 / 30; // Monthly rate converted to daily
                    penalty_amount = outstanding_balance * daily_penalty_rate * days_overdue;
                }
            }
            
            // Calculate interest based on loan type
            let interest_amount = 0;
            if (loan_doc.interest_type === "Flat Rate") {
                // For flat rate, interest is calculated on original principal
                let monthly_interest = (flt(loan_doc.loan_amount) * flt(loan_doc.interest_rate) / 100) / 12;
                interest_amount = Math.min(monthly_interest, total_paid);
            } else {
                // For reducing balance, interest is calculated on current outstanding balance
                let monthly_rate = flt(loan_doc.interest_rate) / 100 / 12;
                interest_amount = Math.min(outstanding_balance * monthly_rate, total_paid);
            }
            
            // Calculate principal (remaining amount after interest and penalty)
            let amount_after_penalty = Math.max(0, total_paid - penalty_amount);
            let amount_after_interest = Math.max(0, amount_after_penalty - interest_amount);
            let principal_amount = amount_after_interest;
            
            // Set the calculated values
            frm.set_value("principal_amount", flt(principal_amount, 2));
            frm.set_value("interest_amount", flt(interest_amount, 2));
            frm.set_value("penalty_amount", flt(penalty_amount, 2));
            frm.set_value("outstanding_balance", flt(outstanding_balance, 2));
            frm.set_value("balance_after_payment", flt(balance_after_payment, 2));
            
            // Show summary in status bar
            this.update_payment_summary(frm, {
                principal: principal_amount,
                interest: interest_amount,
                penalty: penalty_amount,
                total: total_paid,
                balance_after: balance_after_payment
            });
        });
    },
    
    // Update payment summary in the form header
    update_payment_summary: function(frm, breakdown) {
        let summary_html = `
            <div class="payment-summary">
                <div class="row">
                    <div class="col-xs-3">
                        <strong>Principal:</strong><br>
                        ${this.format_currency(breakdown.principal)}
                    </div>
                    <div class="col-xs-3">
                        <strong>Interest:</strong><br>
                        ${this.format_currency(breakdown.interest)}
                    </div>
                    <div class="col-xs-3">
                        <strong>Penalty:</strong><br>
                        ${this.format_currency(breakdown.penalty)}
                    </div>
                    <div class="col-xs-3">
                        <strong>Total:</strong><br>
                        ${this.format_currency(breakdown.total)}
                    </div>
                </div>
                <div class="row" style="margin-top: 10px;">
                    <div class="col-xs-12">
                        <strong>Balance After Payment:</strong>
                        ${this.format_currency(breakdown.balance_after)}
                    </div>
                </div>
            </div>
        `;
        
        // Add to form header
        frm.dashboard.set_headline(summary_html);
    },
    
    // Validate installment allocation
    validate_installment_allocation: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        
        // Validate that amount to pay does not exceed unpaid balance
        if (flt(row.amount_to_pay) > flt(row.unpaid_balance)) {
            frappe.msgprint(__("Amount to pay cannot exceed unpaid balance ({0}).", [this.format_currency(row.unpaid_balance)]));
            frappe.model.set_value(cdt, cdn, "amount_to_pay", row.unpaid_balance);
            return false;
        }
        
        // Update status based on amount to pay
        if (flt(row.amount_to_pay) >= flt(row.unpaid_balance)) {
            frappe.model.set_value(cdt, cdn, "status", "Fully Paid");
        } else if (flt(row.amount_to_pay) > 0) {
            frappe.model.set_value(cdt, cdn, "status", "Partially Paid");
        } else {
            frappe.model.set_value(cdt, cdn, "status", "Unpaid");
        }
        
        return true;
    },
    
    // Recalculate total paid from installment allocations
    recalculate_total_paid: function(frm) {
        let total_paid = 0;
        
        // Calculate from repayment breakdown if it exists
        if (frm.doc.repayment_breakdown) {
            frm.doc.repayment_breakdown.forEach(installment => {
                total_paid += flt(installment.amount_to_pay);
            });
        }
        
        // Calculate from installment adjustment if it exists
        if (frm.doc.installment_adjustment) {
            frm.doc.installment_adjustment.forEach(installment => {
                total_paid += flt(installment.amount_to_pay);
            });
        }
        
        frm.set_value("total_paid", flt(total_paid, 2));
        return flt(total_paid, 2);
    },
    
    // Fetch unpaid installments with enhanced error handling
    fetch_unpaid_installments: function(frm) {
        if (!frm.doc.loan) {
            frappe.msgprint(__("Please select a loan first."));
            return;
        }
        
        frappe.call({
            method: "shg.shg.loan.repayment.get_unpaid_installments",
            args: {
                loan_name: frm.doc.loan
            },
            freeze: true,
            freeze_message: __("Fetching unpaid installments..."),
            callback: function(r) {
                if (r.message) {
                    // Clear existing rows
                    frappe.model.clear_table(frm.doc, "repayment_breakdown");
                    
                    // Add new rows
                    r.message.forEach(installment => {
                        let row = frappe.model.add_child(frm.doc, "SHG Repayment Breakdown", "repayment_breakdown");
                        row.installment_no = installment.installment_no;
                        row.due_date = installment.due_date;
                        row.emi_amount = installment.emi_amount;
                        row.principal_component = installment.principal_component;
                        row.interest_component = installment.interest_component;
                        row.unpaid_balance = installment.unpaid_balance;
                        row.amount_to_pay = 0; // User will edit this
                    });
                    
                    frm.refresh_field("repayment_breakdown");
                    frappe.show_alert(__("Unpaid installments loaded successfully."));
                }
            }
        });
    },
    
    // Apply repayment with confirmation
    apply_repayment: function(frm) {
        if (!frm.doc.total_paid || frm.doc.total_paid <= 0) {
            frappe.msgprint(__("Please enter a repayment amount first."));
            return;
        }
        
        frappe.confirm(
            __("Are you sure you want to apply this repayment of {0}?", [this.format_currency(frm.doc.total_paid)]),
            function() {
                // Submit the document
                frm.savesubmit();
            }
        );
    },
    
    // Show loan details in a modal
    show_loan_details: function(frm) {
        if (!frm.doc.loan) return;
        
        frappe.call({
            method: "shg.shg.loan.reporting.get_detailed_loan_statement",
            args: {
                loan_name: frm.doc.loan
            },
            callback: function(r) {
                if (r.message) {
                    let data = r.message;
                    let dialog = new frappe.ui.Dialog({
                        title: __("Loan Details: {0}", [data.loan_details.loan_id]),
                        fields: [
                            {
                                label: __("Member"),
                                fieldtype: "Data",
                                read_only: 1,
                                default: data.loan_details.member_name
                            },
                            {
                                label: __("Loan Amount"),
                                fieldtype: "Currency",
                                read_only: 1,
                                default: data.loan_details.loan_amount
                            },
                            {
                                label: __("Interest Rate"),
                                fieldtype: "Percent",
                                read_only: 1,
                                default: data.loan_details.interest_rate
                            },
                            {
                                label: __("Status"),
                                fieldtype: "Data",
                                read_only: 1,
                                default: data.loan_details.status
                            },
                            {
                                label: __("Financial Summary"),
                                fieldtype: "Section Break"
                            },
                            {
                                label: __("Total Payable"),
                                fieldtype: "Currency",
                                read_only: 1,
                                default: data.financial_summary.total_payable
                            },
                            {
                                label: __("Total Paid"),
                                fieldtype: "Currency",
                                read_only: 1,
                                default: data.financial_summary.total_paid
                            },
                            {
                                label: __("Outstanding Balance"),
                                fieldtype: "Currency",
                                read_only: 1,
                                default: data.financial_summary.total_outstanding
                            }
                        ]
                    });
                    dialog.show();
                }
            }
        });
    }
};

// Form event handlers
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
        // Add custom buttons
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Calculate Breakdown"), function() {
                shg.loan_repayment.calculate_payment_breakdown(frm);
            });
            
            frm.add_custom_button(__("Fetch Unpaid Installments"), function() {
                shg.loan_repayment.fetch_unpaid_installments(frm);
            });
            
            frm.add_custom_button(__("Loan Details"), function() {
                shg.loan_repayment.show_loan_details(frm);
            });
        }
        
        if (frm.doc.docstatus === 0 && !frm.custom_buttons_added) {
            frm.add_custom_button(__("Apply Repayment"), function() {
                shg.loan_repayment.apply_repayment(frm);
            });
            frm.custom_buttons_added = true;
        }
    },
    
    loan: function(frm) {
        if (frm.doc.loan) {
            // Clear cache for this loan
            delete shg.loan_repayment.loan_cache[frm.doc.loan];
            
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
        // Auto-calculate breakdown when total paid changes
        shg.loan_repayment.calculate_payment_breakdown(frm);
    },
    
    repayment_date: function(frm) {
        // Recalculate breakdown when repayment date changes (affects penalties)
        shg.loan_repayment.calculate_payment_breakdown(frm);
    }
});

// Handle changes in repayment breakdown table
frappe.ui.form.on("SHG Repayment Breakdown", {
    amount_to_pay: function(frm, cdt, cdn) {
        // Validate the allocation
        if (shg.loan_repayment.validate_installment_allocation(frm, cdt, cdn)) {
            frm.refresh_field("repayment_breakdown");
            
            // Recalculate total paid
            let total_paid = shg.loan_repayment.recalculate_total_paid(frm);
            
            // Auto-calculate breakdown when total paid changes
            if (frm.doc.loan && total_paid > 0) {
                shg.loan_repayment.calculate_payment_breakdown(frm);
            }
        }
    },
    
    repayment_breakdown_remove: function(frm) {
        // Recalculate total paid when an installment is removed
        shg.loan_repayment.recalculate_total_paid(frm);
    }
});

// Handle changes in installment adjustment table
frappe.ui.form.on("SHG Repayment Installment Adjustment", {
    amount_to_repay: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        
        // Validate that amount to repay does not exceed unpaid balance
        if (flt(row.amount_to_repay) > flt(row.unpaid_balance)) {
            frappe.msgprint(__("Amount to repay cannot exceed unpaid balance ({0}).", [shg.loan_repayment.format_currency(row.unpaid_balance)]));
            frappe.model.set_value(cdt, cdn, "amount_to_repay", row.unpaid_balance);
        }
        
        // Update status based on amount to repay
        if (flt(row.amount_to_repay) >= flt(row.unpaid_balance)) {
            frappe.model.set_value(cdt, cdn, "status", "Paid");
        } else if (flt(row.amount_to_repay) > 0) {
            frappe.model.set_value(cdt, cdn, "status", "Partially Paid");
        } else {
            frappe.model.set_value(cdt, cdn, "status", "Pending");
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