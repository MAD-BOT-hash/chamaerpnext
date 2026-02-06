// Copyright (c) 2026, SHG Solutions
// License: MIT

frappe.ui.form.on('SHG Multi Member Loan Repayment', {
    setup: function(frm) {
        // Set query for account field based on payment method
        frm.set_query('account', function() {
            if (frm.doc.payment_method === 'Cash') {
                return {
                    filters: {
                        'account_type': 'Cash',
                        'company': frm.doc.company
                    }
                };
            } else {
                return {
                    filters: {
                        'account_type': ['in', ['Bank', 'Cash']],
                        'company': frm.doc.company
                    }
                };
            }
        });
    },
    
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            // Add button to fetch members with active loans
            frm.add_custom_button(__('Fetch Members with Active Loans'), function() {
                fetch_members_with_active_loans_dialog(frm);
            });
            
            // Add validation for payment amounts
            validate_payment_amounts(frm);
        }
    },
    
    payment_method: function(frm) {
        // Clear account when payment method changes
        frm.set_value('account', '');
    },
    
    loans_remove: function(frm) {
        // Recalculate totals when rows are removed
        frm.trigger('calculate_totals');
    }
});

frappe.ui.form.on('SHG Multi Member Loan Repayment Item', {
    payment_amount: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        
        // Validate payment amount
        if (flt(row.payment_amount) > flt(row.outstanding_balance)) {
            frappe.msgprint({
                title: __('Invalid Amount'),
                message: __('Payment amount cannot exceed outstanding balance of {0}', [format_currency(row.outstanding_balance)]),
                indicator: 'red'
            });
            frappe.model.set_value(cdt, cdn, 'payment_amount', row.outstanding_balance);
            return;
        }
        
        if (flt(row.payment_amount) < 0) {
            frappe.msgprint({
                title: __('Invalid Amount'),
                message: __('Payment amount must be greater than zero'),
                indicator: 'red'
            });
            frappe.model.set_value(cdt, cdn, 'payment_amount', 0);
            return;
        }
        
        // Recalculate totals
        frm.trigger('calculate_totals');
    },
    
    loans_add: function(frm, cdt, cdn) {
        // Recalculate totals when new row is added
        frm.trigger('calculate_totals');
    }
});

// Function to fetch members with active loans in a dialog
function fetch_members_with_active_loans_dialog(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Multi-Member Loan Repayment Entry'),
        fields: [
            {
                label: __('Repayment Date'),
                fieldname: 'repayment_date',
                fieldtype: 'Date',
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                label: __('Company'),
                fieldname: 'company',
                fieldtype: 'Link',
                options: 'Company',
                default: frm.doc.company || frappe.defaults.get_user_default('Company'),
                reqd: 1
            },
            {
                fieldtype: 'Column Break'
            },
            {
                label: __('Payment Method'),
                fieldname: 'payment_method',
                fieldtype: 'Select',
                options: 'Cash\nMobile Money\nBank Transfer\nCheque',
                reqd: 1
            },
            {
                label: __('Account'),
                fieldname: 'account',
                fieldtype: 'Link',
                options: 'Account',
                get_query: function() {
                    let payment_method = dialog.get_value('payment_method');
                    if (payment_method === 'Cash') {
                        return {
                            filters: {
                                'account_type': 'Cash',
                                'company': dialog.get_value('company')
                            }
                        };
                    } else {
                        return {
                            filters: {
                                'account_type': ['in', ['Bank', 'Cash']],
                                'company': dialog.get_value('company')
                            }
                        };
                    }
                },
                reqd: 1
            },
            {
                fieldtype: 'Section Break',
                label: __('🧾 Members with Active Loans')
            },
            {
                fieldtype: 'HTML',
                fieldname: 'loans_table'
            }
        ],
        primary_action_label: __('Submit Repayments'),
        primary_action: function(values) {
            // Validate that at least one payment is entered
            let has_payments = false;
            let loan_data = [];
            
            // Collect loan data from table
            dialog.fields_dict.loans_table.$wrapper.find('tr[data-loan]').each(function() {
                let row = $(this);
                let payment_amount = flt(row.find('input.payment-amount').val());
                
                if (payment_amount > 0) {
                    has_payments = true;
                    loan_data.push({
                        member: row.data('member'),
                        member_name: row.data('member-name'),
                        loan: row.data('loan'),
                        loan_type: row.data('loan-type'),
                        outstanding_balance: flt(row.data('outstanding-balance')),
                        payment_amount: payment_amount,
                        status: 'Active'
                    });
                }
            });
            
            if (!has_payments) {
                frappe.msgprint({
                    title: __('No Payments'),
                    message: __('Please enter payment amounts for at least one member'),
                    indicator: 'orange'
                });
                return;
            }
            
            // Validate payment amounts
            let validation_errors = [];
            loan_data.forEach(loan => {
                if (loan.payment_amount > loan.outstanding_balance) {
                    validation_errors.push(`${loan.member_name}: Payment amount exceeds outstanding balance`);
                }
                if (loan.payment_amount <= 0) {
                    validation_errors.push(`${loan.member_name}: Payment amount must be greater than zero`);
                }
            });
            
            if (validation_errors.length > 0) {
                frappe.msgprint({
                    title: __('Validation Errors'),
                    message: validation_errors.join('<br>'),
                    indicator: 'red'
                });
                return;
            }
            
            // Show confirmation dialog
            frappe.confirm(
                __('Are you sure you want to post loan repayments for the selected members?<br>This action will update loan balances and generate repayment entries.'),
                function() {
                    // Process the repayments
                    process_multi_member_repayments({
                        repayment_date: values.repayment_date,
                        company: values.company,
                        payment_method: values.payment_method,
                        account: values.account,
                        loans: loan_data
                    }, frm, dialog);
                }
            );
        },
        secondary_action_label: __('Cancel')
    });
    
    // Show the dialog
    dialog.show();
    
    // Fetch and display members with active loans
    fetch_and_display_active_loans(dialog);
}

// Function to fetch and display active loans
function fetch_and_display_active_loans(dialog) {
    let company = dialog.get_value('company');
    
    frappe.call({
        method: 'shg.shg.doctype.shg_multi_member_loan_repayment.shg_multi_member_loan_repayment.get_members_with_active_loans',
        args: {
            company: company
        },
        freeze: true,
        freeze_message: __('Fetching members with active loans...'),
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                render_loans_table(dialog, r.message);
            } else {
                dialog.fields_dict.loans_table.$wrapper.html(
                    '<div class="text-center text-muted" style="padding: 20px;">' +
                    '<i class="fa fa-info-circle fa-2x"></i><br>' +
                    __('No members with active loans found') +
                    '</div>'
                );
            }
        }
    });
}

// Function to render loans table in dialog
function render_loans_table(dialog, loans_data) {
    let html = `
        <div class="table-responsive">
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>${__('Member ID')}</th>
                        <th>${__('Member Name')}</th>
                        <th>${__('Loan Number')}</th>
                        <th>${__('Loan Type')}</th>
                        <th class="text-right">${__('Outstanding Balance')}</th>
                        <th class="text-right">${__('Payment Amount')}</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    loans_data.forEach(loan => {
        html += `
            <tr data-member="${loan.member}" 
                data-member-name="${loan.member_name}" 
                data-loan="${loan.loan}" 
                data-loan-type="${loan.loan_type}" 
                data-outstanding-balance="${loan.outstanding_balance}">
                <td>${loan.member}</td>
                <td>${loan.member_name}</td>
                <td>${loan.loan}</td>
                <td>${loan.loan_type}</td>
                <td class="text-right">${format_currency(loan.outstanding_balance)}</td>
                <td class="text-right">
                    <input type="number" 
                           class="form-control payment-amount text-right" 
                           min="0" 
                           step="0.01" 
                           placeholder="0.00"
                           style="width: 120px; display: inline-block;">
                </td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
        <div class="text-muted small" style="margin-top: 10px;">
            ${__('Enter the amount being paid by each member. Leave the amount blank or zero for members not making a payment.')}
        </div>
    `;
    
    dialog.fields_dict.loans_table.$wrapper.html(html);
    
    // Add event listeners for payment amount inputs
    dialog.fields_dict.loans_table.$wrapper.find('input.payment-amount').on('input', function() {
        validate_payment_input($(this));
    });
}

// Function to validate payment input
function validate_payment_input(input_element) {
    let row = input_element.closest('tr');
    let payment_amount = flt(input_element.val());
    let outstanding_balance = flt(row.data('outstanding-balance'));
    
    // Clear any existing validation classes
    input_element.removeClass('is-invalid is-valid');
    
    if (payment_amount > 0) {
        if (payment_amount > outstanding_balance) {
            input_element.addClass('is-invalid');
            show_input_error(input_element, __('Payment cannot exceed outstanding balance'));
        } else if (payment_amount <= 0) {
            input_element.addClass('is-invalid');
            show_input_error(input_element, __('Payment must be greater than zero'));
        } else {
            input_element.addClass('is-valid');
            hide_input_error(input_element);
        }
    }
}

// Function to show input error
function show_input_error(element, message) {
    // Remove existing error tooltip
    hide_input_error(element);
    
    // Add error tooltip
    element.tooltip({
        title: message,
        placement: 'top',
        trigger: 'manual'
    }).tooltip('show');
}

// Function to hide input error
function hide_input_error(element) {
    if (element.data('bs.tooltip')) {
        element.tooltip('hide').tooltip('dispose');
    }
}

// Function to process multi-member repayments
function process_multi_member_repayments(repayment_data, frm, dialog) {
    frappe.call({
        method: 'shg.shg.doctype.shg_multi_member_loan_repayment.shg_multi_member_loan_repayment.create_multi_member_loan_repayment',
        args: {
            repayment_data: repayment_data
        },
        freeze: true,
        freeze_message: __('Processing loan repayments...'),
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frappe.msgprint({
                    title: __('Success'),
                    message: r.message.message,
                    indicator: 'green'
                });
                
                // Close dialog
                dialog.hide();
                
                // Refresh the form
                if (frm && frm.doc.__islocal) {
                    frappe.set_route('Form', 'SHG Multi Member Loan Repayment', r.message.repayment_name);
                } else {
                    frm.reload_doc();
                }
            }
        }
    });
}

// Function to validate payment amounts on main form
function validate_payment_amounts(frm) {
    if (frm.doc.loans) {
        let errors = [];
        
        frm.doc.loans.forEach(row => {
            if (flt(row.payment_amount) > flt(row.outstanding_balance)) {
                errors.push(`Row ${row.idx}: Payment amount exceeds outstanding balance`);
            }
            if (flt(row.payment_amount) < 0) {
                errors.push(`Row ${row.idx}: Payment amount must be greater than zero`);
            }
        });
        
        if (errors.length > 0) {
            frm.set_df_property('loans', 'description', errors.join('; '));
        } else {
            frm.set_df_property('loans', 'description', '');
        }
    }
}

// Utility function for formatting currency
function format_currency(amount, currency = 'KES') {
    return frappe.format(amount, { fieldtype: 'Currency', options: currency });
}