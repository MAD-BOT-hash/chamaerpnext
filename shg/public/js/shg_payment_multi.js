// SHG Multi Payment Dialog
frappe.ui.form.on('SHG Contribution Invoice', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Receive Multiple Payments'), function() {
                open_multi_payment_dialog();
            }, __("Actions"));
        }
    }
});

function open_multi_payment_dialog() {
    const d = new frappe.ui.Dialog({
        title: "Receive Multiple Payments",
        size: "large",
        fields: [
            {
                label: "Filter by Member",
                fieldname: "member_filter",
                fieldtype: "Link",
                options: "SHG Member",
                reqd: 0,
                onchange: function() {
                    load_unpaid_invoices(d);
                }
            },
            {
                label: "Filter by Date Range",
                fieldname: "date_range",
                fieldtype: "DateRange",
                onchange: function() {
                    load_unpaid_invoices(d);
                }
            },
            { fieldtype: "Section Break", label: "Unpaid Invoices" },
            {
                fieldname: "invoice_table",
                fieldtype: "HTML",
                options: "<div id='invoice_table'></div>"
            },
            { fieldtype: "Section Break" },
            {
                label: "Payment Date",
                fieldname: "payment_date",
                fieldtype: "Date",
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                label: "Payment Method",
                fieldname: "payment_method",
                fieldtype: "Select",
                options: ["Cash", "Mpesa", "Bank Transfer", "Cheque"],
                default: "Cash",
                reqd: 1
            },
            {
                label: "Receiving Account",
                fieldname: "account",
                fieldtype: "Link",
                options: "Account",
                reqd: 1
            },
            {
                fieldtype: "Data",
                label: "Total Selected (KSh)",
                fieldname: "total_selected",
                read_only: 1
            }
        ],
        primary_action_label: "Submit Payments",
        primary_action(values) {
            const selected = [];
            $('#invoice_table input[type=checkbox]:checked').each(function() {
                const row = $(this).closest('tr');
                const invoice = {
                    name: row.data('name'),
                    paid_amount: parseFloat(row.find('.paid_amount').val()) || 0
                };
                if (invoice.paid_amount > 0) selected.push(invoice);
            });

            if (!selected.length) {
                frappe.msgprint("Please select at least one invoice to pay.");
                return;
            }

            frappe.call({
                method: "shg.api.payments.receive_multiple_payments",
                args: {
                    selected_invoices: JSON.stringify(selected),
                    payment_date: values.payment_date,
                    payment_method: values.payment_method,
                    account: values.account
                },
                freeze: true,
                freeze_message: __("Processing Payments..."),
                callback: (r) => {
                    frappe.msgprint(r.message || "Payments recorded successfully.");
                    d.hide();
                    frappe.reload_doc();
                }
            });
        }
    });

    load_unpaid_invoices(d);
    d.show();
}

function load_unpaid_invoices(dialog) {
    // Get filter values
    const member_filter = dialog.get_value("member_filter");
    const date_range = dialog.get_value("date_range");
    
    // Build filters
    const filters = {
        status: ["in", ["Unpaid", "Partially Paid"]]
    };
    
    if (member_filter) {
        filters.member = member_filter;
    }
    
    if (date_range && date_range.length === 2) {
        filters.invoice_date = ["between", [date_range[0], date_range[1]]];
    }
    
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "SHG Contribution Invoice",
            filters: filters,
            fields: ["name", "member", "member_name", "invoice_date", "due_date", "amount", "status"]
        },
        callback: (r) => {
            const data = r.message || [];
            let html = `
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Select</th>
                            <th>Invoice</th>
                            <th>Member</th>
                            <th>Invoice Date</th>
                            <th>Due Date</th>
                            <th>Status</th>
                            <th>Outstanding (KSh)</th>
                            <th>Pay Amount</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            data.forEach(inv => {
                // Calculate outstanding amount (for now, we'll use the full amount)
                // In a real implementation, this would need to account for partial payments
                const outstanding_amount = inv.amount || 0;
                html += `
                    <tr data-name="${inv.name}">
                        <td><input type="checkbox" class="invoice-check"></td>
                        <td>${inv.name}</td>
                        <td>${inv.member_name || inv.member}</td>
                        <td>${frappe.format_date(inv.invoice_date)}</td>
                        <td>${frappe.format_date(inv.due_date)}</td>
                        <td>${inv.status}</td>
                        <td>${format_currency(outstanding_amount, "KES")}</td>
                        <td><input type="number" class="form-control paid_amount" value="${outstanding_amount}" min="0" max="${outstanding_amount}"></td>
                    </tr>
                `;
            });

            html += "</tbody></table>";
            dialog.fields_dict.invoice_table.$wrapper.html(html);

            // Total calculation
            $('#invoice_table input').on('input change', function() {
                let total = 0;
                $('#invoice_table tr').each(function() {
                    if ($(this).find('.invoice-check').is(':checked')) {
                        const amt = parseFloat($(this).find('.paid_amount').val()) || 0;
                        total += amt;
                    }
                });
                dialog.set_value("total_selected", total.toFixed(2));
            });
        }
    });
}