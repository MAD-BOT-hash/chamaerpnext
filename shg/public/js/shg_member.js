frappe.ui.form.on('SHG Member', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Amend'), function() {
                frm.amend_doc();
            }, __('Actions'));
            
            frm.add_custom_button(__('View Statement'), function() {
                frappe.route_options = {
                    "member": frm.doc.name
                };
                frappe.set_route("query-report", "Member Statement");
            });
            
            frm.add_custom_button(__('Record Contribution'), function() {
                frappe.new_doc('SHG Contribution', {
                    member: frm.doc.name
                });
            });
            
            frm.add_custom_button(__('Apply for Loan'), function() {
                frappe.new_doc('SHG Loan', {
                    member: frm.doc.name
                });
            });
            
            frm.add_custom_button(__('Update Financial Summary'), function() {
                frappe.call({
                    method: 'update_financial_summary',
                    doc: frm.doc,
                    callback: function(r) {
                        frm.refresh();
                        frappe.msgprint('Financial summary updated');
                    }
                });
            });
        }
        
        // Add dashboard indicators
        if (frm.doc.docstatus === 1) {
            frm.dashboard.add_indicator(__('Total Contributions: {0}', [format_currency(frm.doc.total_contributions || 0, 'KES')]), 'blue');
            frm.dashboard.add_indicator(__('Loan Balance: {0}', [format_currency(frm.doc.current_loan_balance || 0, 'KES')]), frm.doc.current_loan_balance > 0 ? 'orange' : 'green');
            frm.dashboard.add_indicator(__('Credit Score: {0}', [frm.doc.credit_score || 0]), get_credit_score_color(frm.doc.credit_score));
        }
    },
    
    phone_number: function(frm) {
        if (frm.doc.phone_number) {
            // Format phone number
            let phone = frm.doc.phone_number;
            if (phone.startsWith('07') || phone.startsWith('01')) {
                frm.set_value('phone_number', '+254' + phone.substring(1));
            }
        }
    },
    
    id_number: function(frm) {
        if (frm.doc.id_number) {
            // Clean the ID number by removing non-digit characters
            let cleanId = frm.doc.id_number.replace(/\D/g, '');
            
            // If the cleaned ID is different from the current value, update it
            if (cleanId !== frm.doc.id_number) {
                frm.set_value('id_number', cleanId);
            }
            
            // Only validate when we have 8 digits
            if (cleanId.length === 8) {
                // Valid - do nothing
            } else if (cleanId.length > 8) {
                // Too long - show warning
                frappe.msgprint(__('Kenyan ID Number must be exactly 8 digits'));
            }
            // If less than 8 digits, we're still typing - don't interfere
        }
    },
    
    membership_status: function(frm) {
        if (frm.doc.membership_status === 'Exited') {
            frappe.confirm(__('Are you sure you want to mark this member as exited?'), function() {
                frm.save();
            }, function() {
                frm.set_value('membership_status', 'Active');
            });
        }
    }
});

function get_credit_score_color(score) {
    if (!score) return 'grey';
    if (score >= 80) return 'green';
    if (score >= 60) return 'yellow';
    if (score >= 40) return 'orange';
    return 'red';
}