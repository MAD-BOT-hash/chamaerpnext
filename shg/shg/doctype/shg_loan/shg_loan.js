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
        
        // Add "Get Active Members" button for group loans
        if (frm.doc.docstatus === 0 && frm.doc.loan_members) {
            frm.add_custom_button(__("Get Active Members"), function() {
                frappe.call({
                    method: "shg.shg.doctype.shg_loan.shg_loan.get_active_group_members",
                    doc: frm.doc,
                    callback: function(r) {
                        if (r.message) {
                            // Clear existing loan members
                            frm.clear_table('loan_members');
                            
                            // Add active members to loan members table
                            r.message.forEach(function(member) {
                                var row = frm.add_child('loan_members');
                                row.member = member.member;
                                row.member_name = member.member_name;
                                row.allocated_amount = member.allocated_amount || 0.0;
                            });
                            
                            frm.refresh_field('loan_members');
                            frappe.msgprint(__('Loan members list populated with active members'));
                            
                            // Auto-sync allocated total with loan amount if needed
                            sync_allocated_total_with_loan_amount(frm);
                        }
                    }
                });
            }, __("Actions"));
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
    },
    
    // Auto-sync allocated total with loan amount
    loan_amount: function(frm) {
        sync_allocated_total_with_loan_amount(frm);
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

function sync_allocated_total_with_loan_amount(frm) {
    // Only sync for group loans
    if (!frm.doc.loan_members || frm.doc.loan_members.length === 0) return;
    
    // Calculate total allocated amount
    var total_allocated = 0;
    frm.doc.loan_members.forEach(function(row) {
        total_allocated += flt(row.allocated_amount);
    });
    
    // If loan amount is not set or is zero, set it to total allocated
    if (!frm.doc.loan_amount || frm.doc.loan_amount === 0) {
        frm.set_value('loan_amount', total_allocated);
    }
}