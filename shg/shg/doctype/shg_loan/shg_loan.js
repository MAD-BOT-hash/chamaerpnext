frappe.ui.form.on("SHG Loan", {
    setup: function(frm) {
        frm.set_query("group", function() {
            return {
                filters: { status: "Active" },
            };
        });
    },
    validate(frm) {
        if (frm.doc.is_group_loan) {
            (frm.doc.loan_members || []).forEach(row => {
                if (!row.member) {
                    frappe.throw(__('All Loan Members must have a Member selected before saving.'));
                }
            });
        }
    },
    
    refresh(frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(
                __("View Repayment Schedule"),
                () => {
                    frappe.route_options = {
                        "loan": frm.doc.name
                    };
                    frappe.set_route("query-report", "Loan Repayment Schedule");
                },
                __("View")
            );
        }
        
        if (frm.doc.docstatus === 1 && frm.doc.status !== "Paid") {
            frm.add_custom_button(
                __("Make Repayment"),
                () => open_repayment_dialog(frm),
                __("Actions")
            );
        }
        
        // Add "Select Multiple Members" button for new loans
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Select Multiple Members'), () => {
                const d = new frappe.ui.Dialog({
                    title: __('Select Members for Loan'),
                    fields: [
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
                        // 🧠 Enhancement: show contributions next to each member
                        label: `${m.member_name} (${m.name}) — KES ${format_currency(m.total_contributions || 0, 'KES')}`,
                        value: m.name
                    }));
                    d.fields_dict.member_select.df.options = member_list;
                    d.fields_dict.member_select.refresh();
                    d.show();
                });
            }, 'Actions');
        }
        
        // Add "Get Active Members" button to the loan_members grid
        // Optional: disable Add Members until repayment_start_date is set
        frm.fields_dict.loan_members.grid.add_custom_button(__('Get Active Members'), () => {
            if (!frm.doc.repayment_start_date) {
                frappe.msgprint(__('Please set the Repayment Start Date first.'));
                return;
            }

            // Filter for active members only
            const filters = { membership_status: 'Active' };

            frappe.db.get_list('SHG Member', {
                filters: filters,
                fields: ['name', 'member_name', 'total_contributions']
            }).then(members => {
                if (!members.length) {
                    frappe.msgprint(__('No active members found.'));
                    return;
                }

                members.forEach(m => {
                    // Avoid duplicates
                    const exists = frm.doc.loan_members.some(row => row.member === m.name);
                    if (!exists) {
                        frm.add_child('loan_members', {
                            member: m.name,
                            member_name: `${m.member_name} — KES ${format_currency(m.total_contributions || 0, 'KES')}`,
                            // Optional: set initial allocation or zero
                            allocated_amount: 0
                        });
                    }
                });

                frm.refresh_field('loan_members');
                frappe.msgprint(__(`${members.length} active members loaded.`));
            });
        });
        
        // Add "Generate Individual Loans" button
        if (!frm.is_new() && frm.doc.loan_members && frm.doc.loan_members.length > 0) {
            frm.add_custom_button(__('Generate Individual Loans'), function() {
                frappe.call({
                    method: "shg.shg.doctype.shg_loan.shg_loan.generate_individual_loans",
                    args: { parent_loan: frm.doc.name },
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.msgprint(__("Individual loans created for all members successfully."));
                            frm.reload_doc();
                        }
                    }
                });
            }, __('Actions'));
        }
    }
});

function open_repayment_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: "Record Loan Repayment",
        size: "large",
        fields: [
            {
                label: "Member",
                fieldname: "member",
                fieldtype: "Link",
                options: "SHG Member",
                reqd: 1,
                get_query: () => ({
                    filters: { status: "Active" },
                }),
                onchange: function () {
                    const member = d.get_value("member");
                    if (member) {
                        frappe.call({
                            method: "shg.api.get_active_loans",
                            args: { member },
                            callback: function (r) {
                                if (r.message && r.message.length) {
                                    d.fields_dict.loan_df.df.options = r.message.map(
                                        (loan) =>
                                            `${loan.name} | Balance: ${loan.balance_amount}`
                                    );
                                    d.fields_dict.loan_df.refresh();
                                } else {
                                    frappe.msgprint("No active loans found for this member.");
                                    d.fields_dict.loan_df.df.options = [];
                                    d.fields_dict.loan_df.refresh();
                                }
                            },
                        });
                    }
                },
            },
            {
                label: "Select Loan",
                fieldname: "loan_df",
                fieldtype: "Select",
                options: [],
                reqd: 1,
            },
            {
                label: "Amount Paid",
                fieldname: "amount_paid",
                fieldtype: "Currency",
                reqd: 1,
            },
            {
                label: "Posting Date",
                fieldname: "posting_date",
                fieldtype: "Date",
                default: frappe.datetime.get_today(),
                reqd: 1,
            },
            {
                label: "Remarks",
                fieldname: "remarks",
                fieldtype: "Small Text",
            },
        ],
        primary_action_label: "Submit Repayment",
        primary_action(values) {
            if (!values.member || !values.loan_df || !values.amount_paid) {
                frappe.msgprint("Please fill in all required fields.");
                return;
            }

            const loan_name = values.loan_df.split("|")[0].trim();

            frappe.call({
                method: "shg.api.create_repayment",
                args: {
                    loan: loan_name,
                    member: values.member,
                    amount_paid: values.amount_paid,
                    posting_date: values.posting_date,
                    remarks: values.remarks,
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.msgprint(
                            `✅ Repayment ${r.message} successfully recorded for Loan ${loan_name}`
                        );
                        d.hide();
                        frm.reload_doc();
                    }
                },
            });
        },
    });

    d.show();
}