frappe.ui.form.on('SHG Loan', {
    refresh(frm) {
        if (frm.is_new()) return;

        // add button column to grid
        frm.fields_dict.repayment_schedule.grid.add_custom_button("💰 Mark as Paid", () => {
            const selected = frm.fields_dict.repayment_schedule.grid.get_selected_children();
            if (!selected.length) {
                frappe.msgprint(__('Select at least one installment.'));
                return;
            }
            frappe.confirm(
                `Mark ${selected.length} installment(s) as Paid for Loan ${frm.doc.name}?`,
                () => {
                    selected.forEach(row => {
                        frappe.call({
                            method: 'shg.shg.doctype.shg_loan_repayment_schedule.shg_loan_repayment_schedule.mark_installment_paid',
                            args: {
                                loan_name: frm.doc.name,
                                installment_no: row.installment_no
                            },
                            callback() {
                                frm.reload_doc();
                            }
                        });
                    });
                }
            );
        });

        frm.fields_dict.repayment_schedule.grid.add_custom_button("↩️ Reverse Payment", () => {
            const selected = frm.fields_dict.repayment_schedule.grid.get_selected_children();
            if (!selected.length) {
                frappe.msgprint(__('Select at least one installment.'));
                return;
            }
            frappe.confirm(
                `Reverse payment for ${selected.length} installment(s)?`,
                () => {
                    selected.forEach(row => {
                        frappe.call({
                            method: 'shg.shg.doctype.shg_loan_repayment_schedule.shg_loan_repayment_schedule.reverse_installment_payment',
                            args: {
                                loan_name: frm.doc.name,
                                installment_no: row.installment_no
                            },
                            callback() {
                                frm.reload_doc();
                            }
                        });
                    });
                }
            );
        });
    }
});