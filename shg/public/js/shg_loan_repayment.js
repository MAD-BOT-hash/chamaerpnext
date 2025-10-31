frappe.ui.form.on('SHG Loan Repayment', {
    refresh: function(frm) {
        // Add dashboard indicators
        if (frm.doc.docstatus === 1 && frm.doc.journal_entry) {
            frm.dashboard.add_indicator(__('Posted to General Ledger'), 'green');
        }
        
        if (frm.doc.penalty_amount > 0) {
            frm.dashboard.add_indicator(__('Penalty Applied: {0}', [format_currency(frm.doc.penalty_amount, 'KES')]), 'red');
        }
        
        // Add print receipt button
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Print Receipt'), function() {
                frappe.utils.print(
                    frm.doc.doctype,
                    frm.doc.name,
                    'SHG Repayment Receipt'
                );
            });
            
            frm.add_custom_button(__('Send SMS Receipt'), function() {
                frappe.call({
                    method: 'send_payment_confirmation',
                    doc: frm.doc,
                    callback: function(r) {
                        frappe.msgprint(__('SMS receipt sent successfully'));
                    }
                });
            });
        }
        
        // Add button to fetch outstanding loans
        frm.add_custom_button(__('Fetch Outstanding Loans'), function() {
            frappe.prompt([
                {
                    fieldname: 'member',
                    label: 'Filter by Member (optional)',
                    fieldtype: 'Link',
                    options: 'SHG Member',
                    reqd: 0
                }
            ], function(values) {
                frappe.call({
                    method: 'shg.shg.doctype.shg_loan_repayment.shg_loan_repayment.get_outstanding_loans',
                    args: { member: values.member },
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            let list = r.message.map(l =>
                                `<b>${l.member_name}</b> → ${l.loan_id} (Balance: ${format_currency(l.balance_amount, 'KES')})`
                            ).join("<br>");
                            frappe.msgprint({
                                title: __("Outstanding Loans"),
                                message: list,
                                indicator: 'blue'
                            });
                        } else {
                            frappe.msgprint(__('No outstanding loans found.'));
                        }
                    }
                });
            }, __('Filter Outstanding Loans'));
        });
        
        // Add Refresh Loan Details button
        if (frm.doc.loan) {
            frm.add_custom_button(__('Refresh Loan Details'), function() {
                refresh_loan_details(frm);
            });
        }
    },
    
    loan: function(frm) {
        if (!frm.doc.loan) return;
        
        refresh_loan_details(frm);
    },
    
    total_paid: function(frm) {
        if (frm.doc.total_paid && frm.doc.loan) {
            // Trigger repayment breakdown calculation
            frappe.call({
                method: 'calculate_repayment_breakdown',
                doc: frm.doc,
                callback: function(r) {
                    frm.refresh_fields(['principal_amount', 'interest_amount', 'penalty_amount', 'balance_after_payment']);
                }
            });
        }
    },
    
    repayment_date: function(frm) {
        // Recalculate penalty if date changes
        if (frm.doc.total_paid && frm.doc.loan) {
            frappe.call({
                method: 'calculate_repayment_breakdown',
                doc: frm.doc,
                callback: function(r) {
                    frm.refresh_fields(['penalty_amount']);
                }
            });
        }
    },
    
    payment_method: function(frm) {
        // Make reference number required for certain payment methods
        if (frm.doc.payment_method === 'Mobile Money' || frm.doc.payment_method === 'Bank Transfer') {
            frm.toggle_reqd('reference_number', true);
        } else {
            frm.toggle_reqd('reference_number', false);
        }
    }
});

// Function to refresh loan details
function refresh_loan_details(frm) {
    if (!frm.doc.loan) return;

    frappe.call({
        method: 'shg.shg.doctype.shg_loan_repayment.shg_loan_repayment.get_repayment_details',
        args: { loan_id: frm.doc.loan },
        callback: function(r) {
            if (!r.message) return;

            const d = r.message;

            // Set all repayment-related fields
            frm.set_value('member', d.member);
            frm.set_value('member_name', d.member_name);
            frm.set_value('repayment_start_date', d.repayment_start_date);
            frm.set_value('monthly_installment', d.monthly_installment);
            frm.set_value('total_payable', d.total_payable);
            frm.set_value('outstanding_balance', d.balance_amount);
            frm.set_value('total_repaid', d.total_repaid);
            frm.set_value('overdue_amount', d.overdue_amount);

            // Set suggested repayment amount
            if (!frm.doc.total_paid && d.monthly_installment) {
                frm.set_value('total_paid', d.monthly_installment);
            }

            // Show loan status
            if (d.loan_status === 'Disbursed') {
                frm.dashboard.add_indicator(__('Loan Status: Active'), 'blue');
            }

            // Update progress bar
            update_progress_bar(frm, d);

            frm.refresh_fields();
        }
    });
}

// Function to update progress bar
function update_progress_bar(frm, loan_data) {
    if (!loan_data.total_payable || loan_data.total_payable <= 0) return;
    
    const paid_percentage = Math.round((loan_data.total_repaid / loan_data.total_payable) * 100);
    const balance_amount = loan_data.balance_amount || 0;
    const overdue_amount = loan_data.overdue_amount || 0;
    
    // Create progress bar HTML
    const progress_html = `
        <div style="margin-top: 10px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>Paid: ${paid_percentage}%</span>
                <span>Overdue: ${format_currency(overdue_amount, 'KES')}</span>
                <span>Balance: ${format_currency(balance_amount, 'KES')}</span>
            </div>
            <div style="width: 100%; background-color: #f0f0f0; border-radius: 4px; height: 20px;">
                <div style="width: ${paid_percentage}%; height: 100%; background-color: #4CAF50; border-radius: 4px; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px;">
                    ${paid_percentage}%
                </div>
            </div>
        </div>
    `;
    
    // Add progress bar to the form
    frm.dashboard.add_section(progress_html, 'Loan Progress');
    frm.dashboard.show();
}