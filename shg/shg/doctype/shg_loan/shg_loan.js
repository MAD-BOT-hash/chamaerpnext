frappe.ui.form.on("SHG Loan", {
    setup: function(frm) {
        // Set query for member field to only show active members
        frm.set_query("member", function() {
            return {
                filters: {
                    membership_status: "Active"
                }
            };
        });
    },
    
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Generate Schedule"), function() {
                frappe.call({
                    method: "shg.shg.api.loan.generate_schedule",
                    args: {
                        loan_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint(r.message.message);
                            frm.reload_doc();
                        }
                    }
                });
            });
            
            frm.add_custom_button(__("Refresh Summary"), function() {
                frappe.call({
                    method: "shg.shg.api.loan.refresh_repayment_summary",
                    args: {
                        loan_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint("Repayment summary refreshed successfully");
                            frm.reload_doc();
                            // Update dashboard headline after reload
                            setTimeout(function() {
                                set_loan_header_indicator(frm);
                            }, 1000);
                        }
                    }
                });
            });
            
            frm.add_custom_button(__("Create Repayment"), function() {
                frappe.route_options = {
                    "loan": frm.doc.name,
                    "member": frm.doc.member,
                    "total_paid": frm.doc.monthly_installment || 0
                };
                frappe.new_doc("SHG Loan Repayment");
            });
            
            frm.add_custom_button(__("View Statement"), function() {
                frappe.set_route("query-report", "SHG Loan Statement", {"loan": frm.doc.name});
            });
        }
        
        // Set header indicator
        set_loan_header_indicator(frm);
    },
    
    balance_amount: function(frm) {
        // Update header indicator when balance changes
        set_loan_header_indicator(frm);
    },
    
    overdue_amount: function(frm) {
        // Update header indicator when overdue amount changes
        set_loan_header_indicator(frm);
    }
});

function set_loan_header_indicator(frm) {
    if (!frm.doc.balance_amount) return;
    
    var indicator = [];
    var balance = flt(frm.doc.balance_amount);
    var overdue = flt(frm.doc.overdue_amount);
    
    if (balance === 0) {
        indicator = [__("Fully Paid"), "green", "balance_amount,=,0"];
    } else if (overdue > 0) {
        indicator = [__("Overdue: Sh {0}", [format_currency(overdue)]), "red", "overdue_amount,>,0"];
    } else {
        indicator = [__("Outstanding: Sh {0}", [format_currency(balance)]), "orange", "balance_amount,>,0"];
    }
    
    frm.dashboard.set_headline_indicator(indicator[0], indicator[1]);
}