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
    },
    
    loan: function(frm) {
        if (frm.doc.loan) {
            // Get loan details and calculate suggested repayment
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SHG Loan',
                    name: frm.doc.loan
                },
                callback: function(r) {
                    if (r.message) {
                        let loan = r.message;
                        
                        frm.set_value('member', loan.member);
                        frm.set_value('member_name', loan.member_name);
                        frm.set_value('outstanding_balance', loan.balance_amount);
                        
                        // Set suggested repayment amount
                        if (!frm.doc.total_paid && loan.monthly_installment) {
                            frm.set_value('total_paid', loan.monthly_installment);
                        }
                        
                        // Show loan status
                        if (loan.status === 'Disbursed') {
                            frm.dashboard.add_indicator(__('Loan Status: Active'), 'blue');
                        }
                        
                        // Show overdue warning if applicable
                        if (loan.next_due_date && frappe.datetime.get_diff(loan.next_due_date, frappe.datetime.get_today()) < 0) {
                            let overdue_days = Math.abs(frappe.datetime.get_diff(loan.next_due_date, frappe.datetime.get_today()));
                            frappe.msgprint({
                                title: __('Overdue Payment'),
                                message: __('This loan is {0} days overdue. A penalty may be applied.', [overdue_days]),
                                indicator: 'red'
                            });
                        }
                    }
                }
            });
        }
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