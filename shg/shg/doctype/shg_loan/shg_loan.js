frappe.ui.form.on("SHG Loan", {
    refresh(frm) {
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
                            label: 'Filter by Group',
                            fieldname: 'group_filter',
                            fieldtype: 'Select',
                            options: [],
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

                // 🧠 Dynamically load distinct group names from SHG Member records
                frappe.db.get_list('SHG Member', {
                    fields: ['group'],
                    filters: { membership_status: 'Active' },
                    distinct: true
                }).then(groups => {
                    const group_names = groups.map(g => g.group).filter(g => !!g);
                    d.fields_dict.group_filter.df.options = [''].concat(group_names);
                    d.fields_dict.group_filter.refresh();
                });

                d.show();
            }, 'Actions');
        }
    },
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