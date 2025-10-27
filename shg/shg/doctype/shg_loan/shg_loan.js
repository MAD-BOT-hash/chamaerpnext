frappe.ui.form.on("SHG Loan", {
    refresh(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.status !== "Paid") {
            frm.add_custom_button(
                __("Make Repayment"),
                () => open_repayment_dialog(frm),
                __("Actions")
            );
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