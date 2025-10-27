frappe.ui.form.on("SHG Contribution Invoice", {
    refresh(frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(
                __("Multi Member Payment"),
                () => open_multi_payment_dialog(frm),
                __("Actions")
            );
        }
    },
});

function open_multi_payment_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: "Multi Member Payment",
        size: "extra-large",
        fields: [
            {
                label: "Filter by Member",
                fieldname: "member_filter",
                fieldtype: "Link",
                options: "SHG Member",
                onchange: function () {
                    frappe.call({
                        method: "shg.api.get_unpaid_invoices_by_member",
                        args: {
                            member: d.get_value("member_filter")
                        },
                        freeze: true,
                        freeze_message: "Fetching unpaid invoices...",
                        callback: function (r) {
                            if (r.message && r.message.length) {
                                render_invoice_table(d, r.message);
                            } else {
                                d.fields_dict.invoice_html.$wrapper.html("<p>No unpaid invoices found for this member.</p>");
                            }
                        }
                    });
                },
            },
            {
                fieldname: "invoice_html",
                fieldtype: "HTML",
            },
            {
                label: "Total Selected (KES)",
                fieldname: "total_selected",
                fieldtype: "Currency",
                read_only: 1,
                default: 0,
            },
            {
                label: "Payment Mode",
                fieldname: "mode_of_payment",
                fieldtype: "Select",
                options: ["Cash", "Mobile Money", "Mpesa", "Bank Transfer", "Cheque"],
                reqd: 1,
            },
            {
                label: "Posting Date",
                fieldname: "posting_date",
                fieldtype: "Date",
                default: frappe.datetime.get_today(),
                reqd: 1,
            },
        ],
        primary_action_label: "Submit Payment",
        primary_action(values) {
            let selected_invoices = [];
            d.$wrapper.find("input.invoice-check:checked").each(function () {
                selected_invoices.push($(this).data("name"));
            });

            if (selected_invoices.length === 0) {
                frappe.msgprint("Please select at least one invoice.");
                return;
            }

            frappe.call({
                method: "shg.api.process_multi_member_payment",
                args: {
                    invoices: selected_invoices,
                    mode_of_payment: values.mode_of_payment,
                    posting_date: values.posting_date,
                },
                freeze: true,
                freeze_message: "Processing payments...",
                callback: function (r) {
                    if (r.message) {
                        frappe.msgprint(`✅ Payment Entries Created: ${r.message.join(", ")}`);
                        d.hide();
                        frm.reload_doc();
                    }
                },
            });
        },
    });

    d.show();
}

// Render HTML invoice list with checkboxes
function render_invoice_table(d, invoices) {
    let html = `
        <table class="table table-bordered table-hover">
            <thead>
                <tr>
                    <th>Select</th>
                    <th>Member</th>
                    <th>Invoice</th>
                    <th>Date</th>
                    <th>Amount</th>
                    <th>Outstanding</th>
                </tr>
            </thead>
            <tbody>
    `;
    invoices.forEach(inv => {
        html += `
            <tr>
                <td><input type="checkbox" class="invoice-check" data-name="${inv.name}" data-outstanding="${inv.outstanding_amount}" /></td>
                <td>${inv.member_name}</td>
                <td>${inv.name}</td>
                <td>${inv.posting_date}</td>
                <td>${format_currency(inv.grand_total, "KES")}</td>
                <td>${format_currency(inv.outstanding_amount, "KES")}</td>
            </tr>
        `;
    });
    html += "</tbody></table>";

    d.fields_dict.invoice_html.$wrapper.html(html);

    // Auto-update total on selection
    d.$wrapper.find(".invoice-check").on("change", function () {
        let total = 0;
        d.$wrapper.find("input.invoice-check:checked").each(function () {
            total += flt($(this).data("outstanding"));
        });
        d.set_value("total_selected", total);
    });
}