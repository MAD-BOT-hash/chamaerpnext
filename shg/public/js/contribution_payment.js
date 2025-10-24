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
    let d = new frappe.ui.Dialog({
        title: 'Receive Multiple Payments',
        fields: [
            {
                label: 'Filter by Member',
                fieldname: 'member_filter',
                fieldtype: 'Link',
                options: 'SHG Member',
                reqd: 0,
            },
            {
                fieldtype: 'Section Break'
            },
            {
                label: 'Unpaid Invoices',
                fieldname: 'invoice_list',
                fieldtype: 'HTML'
            }
        ],
        primary_action_label: 'Process Payments',
        primary_action(values) {
            const selected = [];
            $('#invoice-table input.invoice-checkbox:checked').each(function() {
                const row = $(this).closest('tr');
                selected.push({
                    name: row.data('name'),
                    paid_amount: parseFloat(row.find('.paid_amount').val()) || 0
                });
            });
            console.log("Selected invoices:", JSON.stringify(selected));

            if (!selected.length) {
                frappe.msgprint("Please select at least one invoice to pay.");
                return;
            }

            frappe.call({
                method: "shg.shg.utils.payment_utils.receive_multiple_payments",
                args: {
                    selected_invoices: JSON.stringify(selected),
                    payment_date: frappe.datetime.get_today(),
                    payment_method: "Cash"
                },
                callback: function(r) {
                    if (r.message && r.message.processed !== undefined) {
                        frappe.msgprint(__("Processed {0} payment(s) successfully", [r.message.processed]));
                    } else {
                        frappe.msgprint(r.message || "Payments recorded successfully.");
                    }
                    d.hide();
                    frappe.reload_doc();
                }
            });
        }
    });

    // Load unpaid invoices dynamically
    frappe.call({
        method: "shg.shg.utils.payment_utils.get_unpaid_invoices",
        args: { member: d.get_value('member_filter') },
        callback: function(r) {
            let html = `<table class="table table-bordered" id="invoice-table">
                <tr><th>Select</th><th>Invoice</th><th>Member</th><th>Unpaid Amount</th><th>Pay Now</th></tr>`;
            (r.message || []).forEach(inv => {
                html += `<tr data-name="${inv.name}">
                    <td><input type="checkbox" class="invoice-checkbox"></td>
                    <td>${inv.name}</td>
                    <td>${inv.member}</td>
                    <td>${inv.unpaid_amount}</td>
                    <td><input type="number" class="form-control paid_amount" value="${inv.unpaid_amount}"></td>
                </tr>`;
            });
            html += `</table>`;
            d.fields_dict.invoice_list.$wrapper.html(html);
        }
    });

    d.show();
}
