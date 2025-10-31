frappe.ui.form.on('SHG Loan', {
    refresh: function(frm) {
        // --- 1️⃣ Detect group loan ---
        const is_group_loan = (frm.doc.loan_members && frm.doc.loan_members.length > 0);

        // Clear default ERPNext "Submit this document to confirm" helper
        frm.page.clear_indicator();

        // --- 2️⃣ If group loan, show banner & disable submit ---
        if (is_group_loan) {
            frm.dashboard.clear_headline();
            frm.dashboard.set_headline_alert(
                "📢 This is a <b>Group Loan Container</b>. <br>" +
                "👉 Please <b>create and submit individual member loans</b> below instead.",
                "orange"
            );

            // Disable submit to prevent errors
            frm.disable_save();

            // --- 3️⃣ Add button to generate individual loans ---
            frm.add_custom_button("👥 Create Individual Member Loans", function() {
                frappe.call({
                    method: "shg.shg.doctype.shg_loan.shg_loan.generate_individual_loans",
                    args: { parent_loan: frm.doc.name },
                    freeze: true,
                    freeze_message: "Generating individual member loans...",
                    callback: function(r) {
                        if (r.message && r.message.created && r.message.created.length > 0) {
                            frappe.msgprint(
                                `✅ Created ${r.message.created.length} individual loans:<br>` +
                                r.message.created.join(", ")
                            );
                            frm.reload_doc();
                        } else {
                            frappe.msgprint("⚠️ No individual loans were created (check members list).");
                        }
                    }
                });
            }).addClass("btn-primary");

            // --- 4️⃣ Hide standard "Submit" and "Disburse" actions for container ---
            frm.page.set_primary_action("Submit", null);
        }

        // --- 5️⃣ For individual loans (normal flow) ---
        else {
            frm.dashboard.clear_headline();
            frm.enable_save();
            
            // Add custom buttons based on status
            if (frm.doc.docstatus === 1) {
                if (frm.doc.status === 'Applied') {
                    frm.add_custom_button(__('Approve Loan'), function() {
                        frm.set_value('status', 'Approved');
                        frm.save();
                    }).addClass('btn-primary');
                }
                
                if (frm.doc.status === 'Approved') {
                    frm.add_custom_button(__('Disburse Loan'), function() {
                        frappe.call({
                            method: 'frappe.client.submit',
                            args: { doctype: "SHG Loan", name: frm.doc.name },
                            callback: function(r) {
                                if (!r.exc) {
                                    frm.reload_doc();
                                    frappe.msgprint(__('Loan disbursed successfully'));
                                }
                            }
                        });
                    }).addClass('btn-primary');
                }
                
                if (frm.doc.status === 'Disbursed') {
                    frm.add_custom_button(__('Record Repayment'), function() {
                        frappe.new_doc('SHG Loan Repayment', {
                            loan: frm.doc.name,
                            member: frm.doc.member,
                            member_name: frm.doc.member_name
                        });
                    });
                    
                    // Add Refresh Repayment Summary button
                    frm.add_custom_button(__('🔄 Refresh Repayment Summary'), function() {
                        if (!frm.doc.name) {
                            frappe.msgprint(__('Please save the Loan first.'));
                            return;
                        }

                        frappe.call({
                            method: 'shg.shg.doctype.shg_loan.shg_loan.update_repayment_summary',
                            args: { loan_id: frm.doc.name },
                            callback: function(r) {
                                frm.reload_doc();
                                frappe.show_alert({
                                    message: __('Repayment summary refreshed successfully.'),
                                    indicator: 'green'
                                });
                            }
                        });
                    }).addClass('btn-primary');
                    
                    frm.add_custom_button(__('View Repayment Schedule'), function() {
                        // Use the accurate repayment schedule from the server-side method
                        frappe.call({
                            method: 'shg.shg.doctype.shg_loan.shg_loan.get_member_loan_statement',
                            args: { docname: frm.doc.name },
                            callback: function(r) {
                                if (r.message) {
                                    // Create a dialog to display the repayment schedule
                                    let schedule_data = r.message.repayment_schedule;
                                    let loan_details = r.message.loan_details;
                                    let summary = r.message.summary;
                                    
                                    // Format data for the grid
                                    let formatted_data = schedule_data.map(row => {
                                        return [
                                            row.installment_no,
                                            frappe.datetime.str_to_user(row.due_date),
                                            format_currency(row.total_due, 'KES'),
                                            format_currency(row.amount_paid, 'KES'),
                                            format_currency(row.unpaid_balance, 'KES'),
                                            row.status
                                        ];
                                    });
                                    
                                    let dialog = new frappe.ui.Dialog({
                                        title: __('Repayment Schedule for Loan {0}', [frm.doc.name]),
                                        fields: [
                                            {
                                                label: __('Loan Details'),
                                                fieldtype: 'Section Break',
                                                collapsible: 1
                                            },
                                            {
                                                label: __('Member'),
                                                fieldtype: 'Data',
                                                default: loan_details.member_name,
                                                read_only: 1
                                            },
                                            {
                                                label: __('Loan Amount'),
                                                fieldtype: 'Currency',
                                                default: loan_details.loan_amount,
                                                read_only: 1
                                            },
                                            {
                                                label: __('Interest Rate'),
                                                fieldtype: 'Percent',
                                                default: loan_details.interest_rate,
                                                read_only: 1
                                            },
                                            {
                                                label: __('Loan Period'),
                                                fieldtype: 'Int',
                                                default: loan_details.loan_period_months,
                                                read_only: 1
                                            },
                                            {
                                                label: __('Repayment Schedule'),
                                                fieldtype: 'Section Break'
                                            },
                                            {
                                                label: __('Schedule Summary'),
                                                fieldtype: 'HTML',
                                                options: `
                                                    <div class="row">
                                                        <div class="col-xs-4">
                                                            <b>Total Due:</b> ${format_currency(summary.total_due, 'KES')}
                                                        </div>
                                                        <div class="col-xs-4">
                                                            <b>Total Paid:</b> ${format_currency(summary.total_paid, 'KES')}
                                                        </div>
                                                        <div class="col-xs-4">
                                                            <b>Outstanding:</b> ${format_currency(summary.outstanding_balance, 'KES')}
                                                        </div>
                                                    </div>
                                                    <div class="row" style="margin-top: 10px;">
                                                        <div class="col-xs-4">
                                                            <b>Overdue Installments:</b> ${summary.overdue_count}
                                                        </div>
                                                    </div>
                                                `
                                            },
                                            {
                                                label: '',
                                                fieldtype: 'Table',
                                                fields: [
                                                    {
                                                        label: __('Installment'),
                                                        fieldname: 'installment_no',
                                                        fieldtype: 'Int',
                                                        width: '100px'
                                                    },
                                                    {
                                                        label: __('Due Date'),
                                                        fieldname: 'due_date',
                                                        fieldtype: 'Date',
                                                        width: '150px'
                                                    },
                                                    {
                                                        label: __('Total Due'),
                                                        fieldname: 'total_due',
                                                        fieldtype: 'Currency',
                                                        width: '150px'
                                                    },
                                                    {
                                                        label: __('Amount Paid'),
                                                        fieldname: 'amount_paid',
                                                        fieldtype: 'Currency',
                                                        width: '150px'
                                                    },
                                                    {
                                                        label: __('Unpaid Balance'),
                                                        fieldname: 'unpaid_balance',
                                                        fieldtype: 'Currency',
                                                        width: '150px'
                                                    },
                                                    {
                                                        label: __('Status'),
                                                        fieldname: 'status',
                                                        fieldtype: 'Data',
                                                        width: '120px'
                                                    }
                                                ],
                                                data: formatted_data,
                                                get_data: () => formatted_data
                                            }
                                        ],
                                        primary_action_label: 'Close',
                                        primary_action() {
                                            dialog.hide();
                                        }
                                    });
                                    
                                    dialog.show();
                                }
                            }
                        });
                    });
                    
                    // On refresh: if submitted & schedule exists, show quick actions
                    if (frm.doc.repayment_schedule && frm.doc.repayment_schedule.length > 0) {
                        frm.add_custom_button(__('Mark all due as paid today'), function() {
                            frappe.confirm(
                                'Are you sure you want to mark all due installments as paid?',
                                function() {
                                    // Call server-side method to mark all due installments as paid
                                    frappe.call({
                                        method: 'shg.shg.doctype.shg_loan.shg_loan.mark_all_due_as_paid',
                                        args: {
                                            loan_name: frm.doc.name
                                        },
                                        callback: function(r) {
                                            if (!r.exc) {
                                                frm.reload_doc();
                                                frappe.msgprint(__('All due installments marked as paid'));
                                            }
                                        }
                                    });
                                }
                            );
                        }, __('Quick Actions'));
                    }
                }
                
                // Print loan agreement
                frm.add_custom_button(__('Print Agreement'), function() {
                    frappe.utils.print(
                        frm.doc.doctype,
                        frm.doc.name,
                        'SHG Loan Agreement'
                    );
                });
            }
            else {
                // Add "Select Multiple Members" button for new loans
                frm.add_custom_button(__('Select Multiple Members'), () => {
                    const d = new frappe.ui.Dialog({
                        title: __('Select Members for Loan'),
                        fields: [
                            {
                                label: 'Filter by Group',
                                fieldname: 'group_filter',
                                fieldtype: 'Link',
                                options: 'SHG Group',
                                onchange: function() {
                                    const group = d.get_value('group_filter');
                                    if (group) {
                                        frappe.db.get_list('SHG Member', {
                                            filters: { group: group, membership_status: 'Active' },
                                            fields: ['name', 'member_name', 'total_contributions']
                                        }).then(members => {
                                            const member_list = members.map(m => ({
                                                label: `${m.member_name} (${m.name})`,
                                                value: m.name
                                            }));

                                            d.fields_dict.member_select.df.options = member_list;
                                            d.fields_dict.member_select.refresh();
                                        });
                                    }
                                }
                            },
                            {
                                label: 'Select Members',
                                fieldname: 'member_select',
                                fieldtype: 'MultiCheck',
                                options: []
                            },
                            {
                                label: 'Distribute Amount Equally',
                                fieldname: 'distribute_equally',
                                fieldtype: 'Check',
                                default: 1
                            }
                        ],
                        primary_action_label: 'Add to Loan',
                        primary_action(values) {
                            const selected = values.member_select;
                            if (!selected || selected.length === 0) {
                                frappe.msgprint(__('Please select at least one member.'));
                                return;
                            }

                            const per_member = flt(frm.doc.loan_amount) / selected.length;

                            selected.forEach(member_id => {
                                frappe.db.get_doc('SHG Member', member_id).then(m => {
                                    frm.add_child('loan_members', {
                                        member: m.name,
                                        member_name: m.member_name,
                                        allocated_amount: values.distribute_equally ? per_member : 0
                                    });
                                    frm.refresh_field('loan_members');
                                });
                            });
                            d.hide();
                        }
                    });
                    
                    // Fetch all active members
                    frappe.db.get_list('SHG Member', {
                        filters: { membership_status: 'Active' },
                        fields: ['name', 'member_name', 'total_contributions']
                    }).then(members => {
                        const member_list = members.map(m => ({
                            label: `${m.member_name} (${m.name})`,
                            value: m.name
                        }));

                        d.fields_dict.member_select.df.options = member_list;
                        d.fields_dict.member_select.refresh();
                        d.show();
                    });
                }, 'Actions');
            }
        }
        
        // Add dashboard indicators
        if (frm.doc.docstatus === 1) {
            frm.dashboard.add_indicator(__('Status: {0}', [frm.doc.status]), 
                frm.doc.status === 'Disbursed' ? 'green' : 
                frm.doc.status === 'Approved' ? 'blue' : 
                frm.doc.status === 'Applied' ? 'orange' : 'grey');
                
            if (frm.doc.balance_amount > 0) {
                frm.dashboard.add_indicator(__('Balance: {0}', [format_currency(frm.doc.balance_amount, 'KES')]), 'orange');
            }
        }
    },
    
    member: function(frm) {
        if (frm.doc.member) {
            // Auto-populate member name
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'SHG Member',
                    filters: { name: frm.doc.member },
                    fieldname: 'member_name'
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('member_name', r.message.member_name);
                    }
                }
            });
            
            // Check member eligibility
            frappe.call({
                method: 'check_member_eligibility',
                doc: frm.doc,
                callback: function(r) {
                    if (r.message && !r.message.eligible) {
                        frappe.msgprint({
                            title: __('Not Eligible'),
                            message: r.message.reason,
                            indicator: 'orange'
                        });
                    }
                }
            });
        }
    },
    
    loan_type: function(frm) {
        if (frm.doc.loan_type) {
            // Auto-populate loan type details
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SHG Loan Type',
                    name: frm.doc.loan_type
                },
                callback: function(r) {
                    if (r.message) {
                        let loan_type = r.message;
                        
                        // Set default values if not already set
                        if (loan_type.interest_rate && !frm.doc.interest_rate) {
                            frm.set_value('interest_rate', loan_type.interest_rate);
                        }
                        if (loan_type.interest_type && !frm.doc.interest_type) {
                            frm.set_value('interest_type', loan_type.interest_type);
                        }
                        if (loan_type.default_tenure_months && !frm.doc.loan_period_months) {
                            frm.set_value('loan_period_months', loan_type.default_tenure_months);
                        }
                        if (loan_type.repayment_frequency && !frm.doc.repayment_frequency) {
                            frm.set_value('repayment_frequency', loan_type.repayment_frequency);
                        }
                    }
                }
            });
        }
    },
    
    loan_amount: function(frm) {
        if (frm.doc.loan_amount) {
            // Validate against maximum loan amount setting
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'SHG Settings',
                    fieldname: 'maximum_loan_amount'
                },
                callback: function(r) {
                    if (r.message && r.message.maximum_loan_amount) {
                        let max_amount = r.message.maximum_loan_amount;
                        if (frm.doc.loan_amount > max_amount) {
                            frappe.msgprint({
                                title: __('Exceeds Limit'),
                                message: __('Loan amount exceeds the maximum allowed amount of KES {0}', [format_currency(max_amount, 'KES')]),
                                indicator: 'orange'
                            });
                        }
                    }
                }
            });
            
            // Also check against loan type limits
            if (frm.doc.loan_type) {
                frappe.call({
                    method: 'frappe.client.get',
                    args: {
                        doctype: 'SHG Loan Type',
                        name: frm.doc.loan_type
                    },
                    callback: function(r) {
                        if (r.message) {
                            let loan_type = r.message;
                            if (loan_type.minimum_amount && frm.doc.loan_amount < loan_type.minimum_amount) {
                                frappe.msgprint({
                                    title: __('Below Minimum'),
                                    message: __('Loan amount is below the minimum of KES {0} for this loan type', [format_currency(loan_type.minimum_amount, 'KES')]),
                                    indicator: 'orange'
                                });
                            }
                            if (loan_type.maximum_amount && frm.doc.loan_amount > loan_type.maximum_amount) {
                                frappe.msgprint({
                                    title: __('Exceeds Limit'),
                                    message: __('Loan amount exceeds the maximum of KES {0} for this loan type', [format_currency(loan_type.maximum_amount, 'KES')]),
                                    indicator: 'orange'
                                });
                            }
                        }
                    }
                });
            }
        }
        // Recalculate repayment details
        frm.trigger('calculate_repayment_details');
    },
    
    interest_rate: function(frm) {
        // Recalculate repayment details
        frm.trigger('calculate_repayment_details');
    },
    
    loan_period_months: function(frm) {
        // Recalculate repayment details
        frm.trigger('calculate_repayment_details');
    },
    
    calculate_repayment_details: function(frm) {
        if (frm.doc.loan_amount && frm.doc.interest_rate && frm.doc.loan_period_months) {
            frappe.call({
                method: 'calculate_repayment_details',
                doc: frm.doc,
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('monthly_installment', r.message.monthly_installment);
                        frm.set_value('total_payable', r.message.total_payable);
                    }
                }
            });
        }
    },
    
    status: function(frm) {
        if (frm.doc.status === 'Approved' && !frm.doc.approved_date) {
            frm.set_value('approved_date', frappe.datetime.get_today());
            frm.set_value('approved_by', frappe.session.user);
        }
        
        if (frm.doc.status === 'Disbursed' && !frm.doc.disbursement_date) {
            frm.set_value('disbursement_date', frappe.datetime.get_today());
        }
    }
});

// Add custom buttons to the Repayment Schedule grid
frappe.ui.form.on('SHG Loan Repayment Schedule', {
    refresh: function(frm, cdt, cdn) {
        // Add Mark as Paid and Reverse Payment buttons to each row
        frm.fields_dict.repayment_schedule.grid.add_custom_button(__('Mark as Paid'), function() {
            let row = frm.fields_dict.repayment_schedule.grid.get_selected_children();
            if (row.length > 0) {
                let d = row[0];
                frappe.call({
                    method: 'shg.shg.doctype.shg_loan_repayment_schedule.shg_loan_repayment_schedule.mark_as_paid',
                    args: {
                        docname: d.name,
                        payment_amount: d.unpaid_balance
                    },
                    callback: function(r) {
                        if (!r.exc) {
                            frm.reload_doc();
                            frappe.msgprint(__('Installment marked as paid'));
                        }
                    }
                });
            } else {
                frappe.msgprint(__('Please select a row first'));
            }
        });
        
        frm.fields_dict.repayment_schedule.grid.add_custom_button(__('Reverse Payment'), function() {
            let row = frm.fields_dict.repayment_schedule.grid.get_selected_children();
            if (row.length > 0) {
                let d = row[0];
                frappe.call({
                    method: 'shg.shg.doctype.shg_loan_repayment_schedule.shg_loan_repayment_schedule.reverse_payment',
                    args: {
                        docname: d.name
                    },
                    callback: function(r) {
                        if (!r.exc) {
                            frm.reload_doc();
                            frappe.msgprint(__('Payment reversed'));
                        }
                    }
                });
            } else {
                frappe.msgprint(__('Please select a row first'));
            }
        });
    }
});