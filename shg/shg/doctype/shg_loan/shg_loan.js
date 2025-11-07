frappe.ui.form.on('SHG Loan', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1) {
            // Add Recalculate Loan Summary button
            frm.add_custom_button(__('Recalculate Loan Summary'), function() {
                frappe.call({
                    method: 'shg.shg.loan_utils.update_loan_summary',
                    args: {
                        loan_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message && r.message.status === 'success') {
                            frm.reload_doc();
                            frappe.show_alert(__('Loan summary recalculated successfully'));
                        } else {
                            frappe.msgprint(__('Failed to recalculate loan summary'));
                        }
                    }
                });
            });

            // Add Get Active Members button for group loans
            if (frm.doc.is_group_loan) {
                frm.add_custom_button(__('Get Active Members'), function() {
                    frappe.call({
                        method: 'shg.shg.doctype.shg_loan.shg_loan.get_active_group_members',
                        args: {
                            loan_name: frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message) {
                                frm.clear_table('loan_members');
                                r.message.forEach(function(member) {
                                    var row = frm.add_child('loan_members');
                                    row.member = member.member;
                                    row.member_name = member.member_name;
                                    row.allocated_amount = member.allocated_amount;
                                });
                                frm.refresh_field('loan_members');
                                frappe.show_alert(__('Active members added'));
                            }
                        }
                    });
                });
                
                // Add Generate Individual Loans button
                if (frm.doc.loan_members && frm.doc.loan_members.length > 0) {
                    frm.add_custom_button(__('Generate Individual Loans'), function() {
                        frappe.call({
                            method: 'shg.shg.doctype.shg_loan.shg_loan.generate_individual_loans',
                            args: {
                                parent_loan: frm.doc.name
                            },
                            callback: function(r) {
                                if (r.message && r.message.status === 'success') {
                                    frappe.show_alert(__('{0} individual loans generated', [r.message.created.length]));
                                } else {
                                    frappe.msgprint(__('Failed to generate individual loans'));
                                }
                            }
                        });
                    });
                }
            }
        }
    }
});
