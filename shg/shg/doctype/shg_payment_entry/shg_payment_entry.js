// Copyright (c) 2025
// License: MIT

frappe.ui.form.on('SHG Payment Entry', {
    setup: function(frm) {
        frm.set_query("reference_doctype", "references", function() {
            return {
                filters: {
                    "name": ["in", ["Sales Invoice", "Journal Entry", "SHG Loan", "SHG Loan Repayment"]]
                }
            };
        });
    },

    refresh: function(frm) {
        // Add custom buttons or modify UI as needed
    },

    payment_type: function(frm) {
        // Handle payment type changes
    },

    party: function(frm) {
        // Handle party changes
    }
});

frappe.ui.form.on('SHG Payment Entry Detail', {
    amount: function(frm, cdt, cdn) {
        frm.trigger('calculate_total');
    },
    
    invoice: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        if (row.invoice) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SHG Contribution Invoice',
                    name: row.invoice
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'invoice_date', r.message.invoice_date);
                        frappe.model.set_value(cdt, cdn, 'outstanding_amount', r.message.amount);
                        frappe.model.set_value(cdt, cdn, 'amount', r.message.amount);
                        frappe.model.set_value(cdt, cdn, 'description', r.message.description);
                        frm.trigger('calculate_total');
                    }
                }
            });
        }
    },
    
    invoice_type: function(frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        // Clear fields when invoice type changes
        frappe.model.set_value(cdt, cdn, 'invoice', '');
        frappe.model.set_value(cdt, cdn, 'reference_name', '');
        frappe.model.set_value(cdt, cdn, 'invoice_date', '');
        frappe.model.set_value(cdt, cdn, 'outstanding_amount', 0);
        frappe.model.set_value(cdt, cdn, 'description', '');
    }
});

function open_fine_payment_dialog(frm) {
    if (!frm.doc.member) {
        frappe.msgprint("Please select a Member first.");
        return;
    }

    frappe.call({
        method: "shg.shg.doctype.shg_payment_entry.shg_payment_entry.get_unpaid_fines",
        args: { member: frm.doc.member },
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                frappe.msgprint("No unpaid fines found for this member.");
                return;
            }

            let fines = r.message;
            let options_html = fines.map(f => `
                <tr>
                    <td><input type="checkbox" class="fine-check" data-name="${f.name}" data-amount="${f.fine_amount}"></td>
                    <td>${f.name}</td>
                    <td>${f.fine_date || ''}</td>
                    <td>${f.fine_reason || ''}</td>
                    <td>${f.fine_amount || 0}</td>
                    <td>${f.fine_description || ''}</td>
                </tr>
            `).join("");

            let dialog = new frappe.ui.Dialog({
                title: "Select Fines to Pay",
                fields: [
                    {
                        fieldname: "html",
                        fieldtype: "HTML",
                        options: `
                            <table class="table table-bordered">
                                <thead>
                                    <tr>
                                        <th>Select</th><th>Fine ID</th><th>Date</th><th>Type</th><th>Amount</th><th>Remarks</th>
                                    </tr>
                                </thead>
                                <tbody>${options_html}</tbody>
                            </table>
                        `
                    }
                ],
                primary_action_label: "Add to Payment",
                primary_action(values) {
                    let selected = [];
                    $(".fine-check:checked").each(function() {
                        selected.push({
                            invoice_type: "SHG Meeting Fine",
                            reference_doctype: "SHG Meeting Fine",
                            reference_name: $(this).data("name"),
                            amount: parseFloat($(this).data("amount")),
                            outstanding_amount: parseFloat($(this).data("amount"))
                        });
                    });

                    if (selected.length === 0) {
                        frappe.msgprint("No fines selected.");
                        return;
                    }

                    selected.forEach(s => {
                        let row = frm.add_child("payment_entries", s);
                    });

                    frm.refresh_field("payment_entries");
                    frm.trigger("calculate_total");
                    dialog.hide();
                }
            });

            dialog.show();
        }
    });
}