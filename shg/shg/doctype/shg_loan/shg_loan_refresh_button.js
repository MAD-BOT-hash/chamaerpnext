frappe.ui.form.on("SHG Loan", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("🔄 Refresh Summary", () => {
                frappe.call({
                    method: "shg.shg.doctype.shg_loan.api.refresh_repayment_summary",
                    args: { loan_name: frm.doc.name },
                    callback(r) {
                        if (r.message && r.message.status === "success") {
                            frm.reload_doc();
                            frappe.msgprint("📊 Repayment Summary Refreshed Successfully");
                        }
                    }
                });
            }, "Actions");
            
            // Optional: small header indicator on refresh
            if (frm.doc.balance_amount) {
                frm.dashboard.set_headline(
                    `Outstanding: ${format_currency(frm.doc.balance_amount, "KES")}`
                );
            }
        }
    }
});