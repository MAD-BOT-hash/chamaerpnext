import frappe

def execute():
    """Enhance loan form UI with better layout and features"""
    
    # Add custom buttons for loan management
    enhance_loan_form_buttons()
    
    # Add dashboard indicators
    add_dashboard_indicators()
    
    frappe.msgprint("✅ Loan form UI enhanced with better layout and features")

def enhance_loan_form_buttons():
    """Add custom buttons for loan management"""
    
    client_script_content = """
frappe.ui.form.on("SHG Loan", {
    refresh: function(frm) {
        // Add status badges
        if (frm.doc.loan_status) {
            let status_colors = {
                "Active": "blue",
                "Completed": "green",
                "Overdue": "red",
                "Defaulted": "orange"
            };
            
            let color = status_colors[frm.doc.loan_status] || "gray";
            frm.page.set_indicator(__(frm.doc.loan_status), color);
        }
        
        // Add repayment history timeline button
        if (frm.doc.name && frm.doc.docstatus === 1) {
            frm.add_custom_button(__('View Repayment History'), function() {
                show_repayment_history(frm);
            });
        }
        
        // Add edit permissions for admins/treasurers
        if (frm.doc.docstatus === 1) {
            // Enable editing of certain fields for authorized users
            if (frappe.user.has_role(['SHG Admin', 'SHG Treasurer'])) {
                frm.set_df_property('disbursement_date', 'read_only', 0);
                frm.set_df_property('interest_rate', 'read_only', 0);
                frm.set_df_property('loan_period_months', 'read_only', 0);
            }
        }
    }
});

function show_repayment_history(frm) {
    // Create a dialog to show repayment history
    let dialog = new frappe.ui.Dialog({
        title: __('Repayment History for Loan {0}', [frm.doc.name]),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'history_html',
                options: '<div class="repayment-history-container" style="min-height: 400px; max-height: 600px; overflow-y: auto;"></div>'
            }
        ],
        primary_action_label: __('Close'),
        primary_action: function() {
            dialog.hide();
        }
    });
    
    // Load repayment history
    load_repayment_history(frm, dialog);
    
    dialog.show();
}

function load_repayment_history(frm, dialog) {
    // Get repayment schedule
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'SHG Loan Repayment Schedule',
            filters: {
                parent: frm.doc.name,
                parenttype: 'SHG Loan'
            },
            fields: ['*'],
            order_by: 'due_date asc'
        },
        callback: function(r) {
            if (r.message) {
                render_repayment_history(r.message, dialog);
            }
        }
    });
}

function render_repayment_history(schedule, dialog) {
    let html = `
        <div class="timeline" style="position: relative; padding-left: 30px;">
            <div style="position: absolute; left: 15px; top: 0; bottom: 0; width: 2px; background: #ddd;"></div>
    `;
    
    schedule.forEach(row => {
        let status_class = '';
        let status_icon = '';
        let status_text = '';
        
        switch(row.status) {
            case 'Paid':
                status_class = 'success';
                status_icon = '✅';
                status_text = 'Paid';
                break;
            case 'Partially Paid':
                status_class = 'warning';
                status_icon = '🔶';
                status_text = 'Partially Paid';
                break;
            case 'Overdue':
                status_class = 'danger';
                status_icon = '❌';
                status_text = 'Overdue';
                break;
            default:
                status_class = 'secondary';
                status_icon = '⏳';
                status_text = 'Pending';
        }
        
        let payment_date = row.actual_payment_date ? frappe.datetime.str_to_user(row.actual_payment_date) : 'Not paid';
        let due_date = frappe.datetime.str_to_user(row.due_date);
        
        html += `
            <div class="timeline-item" style="margin-bottom: 20px; position: relative;">
                <div style="position: absolute; left: -25px; top: 5px; width: 16px; height: 16px; border-radius: 50%; background: \${getStatusColor(status_class)}; border: 2px solid white;"></div>
                <div class="card" style="border-left: 3px solid \${getStatusColor(status_class)};">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <h6 class="card-title">Installment #\${row.installment_no} \${status_icon} \${status_text}</h6>
                            <span class="text-muted">\${due_date}</span>
                        </div>
                        <div class="row">
                            <div class="col-md-3">
                                <small class="text-muted">Principal</small>
                                <div>\${format_currency(row.principal_component)}</div>
                            </div>
                            <div class="col-md-3">
                                <small class="text-muted">Interest</small>
                                <div>\${format_currency(row.interest_component)}</div>
                            </div>
                            <div class="col-md-3">
                                <small class="text-muted">Total Due</small>
                                <div>\${format_currency(row.total_payment)}</div>
                            </div>
                            <div class="col-md-3">
                                <small class="text-muted">Paid</small>
                                <div>\${format_currency(row.amount_paid)}</div>
                            </div>
                        </div>
                        \${row.actual_payment_date ? \`<div class="mt-2"><small class="text-muted">Payment Date: \${payment_date}</small></div>\` : ''}
                        \${row.unpaid_balance > 0 ? \`<div class="mt-1"><small class="text-muted">Balance: \${format_currency(row.unpaid_balance)}</small></div>\` : ''}
                    </div>
                </div>
            </div>
        `;
    });
    
    html += `</div>`;
    
    dialog.fields_dict.history_html.$wrapper.html(html);
}

function getStatusColor(status_class) {
    const colors = {
        'success': '#28a745',
        'warning': '#ffc107',
        'danger': '#dc3545',
        'secondary': '#6c757d'
    };
    return colors[status_class] || '#6c757d';
}

function format_currency(amount) {
    return frappe.format(amount, { fieldtype: 'Currency' });
}
"""
    
    # Create or update the client script
    script_name = "SHG Loan - Enhanced UI"
    if frappe.db.exists("Client Script", script_name):
        script = frappe.get_doc("Client Script", script_name)
        script.script = client_script_content
        script.enabled = 1
        script.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": script_name,
            "dt": "SHG Loan",
            "view": "Form",
            "script": client_script_content,
            "enabled": 1
        }).insert(ignore_permissions=True)
    
    frappe.db.commit()

def add_dashboard_indicators():
    """Add dashboard indicators to loan form"""
    
    dashboard_script = """
frappe.ui.form.on("SHG Loan", {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1) {
            // Add dashboard indicators
            frm.dashboard.add_indicator(__('Total Payable: {0}', [format_currency(frm.doc.total_payable_amount || 0)]), 'blue');
            frm.dashboard.add_indicator(__('Total Paid: {0}', [format_currency(frm.doc.total_amount_paid || 0)]), 'green');
            frm.dashboard.add_indicator(__('Outstanding: {0}', [format_currency(frm.doc.outstanding_amount || 0)]), frm.doc.outstanding_amount > 0 ? 'orange' : 'green');
            
            if (frm.doc.overdue_amount > 0) {
                frm.dashboard.add_indicator(__('Overdue: {0}', [format_currency(frm.doc.overdue_amount || 0)]), 'red');
            }
            
            // Add progress bar
            if (frm.doc.total_payable_amount > 0) {
                let percent_paid = (frm.doc.total_amount_paid / frm.doc.total_payable_amount) * 100;
                frm.dashboard.add_progress(__('Repayment Progress'), percent_paid);
            }
        }
    }
});

function format_currency(amount) {
    return frappe.format(amount, { fieldtype: 'Currency' });
}
"""
    
    # Create or update the dashboard script
    script_name = "SHG Loan - Dashboard Indicators"
    if frappe.db.exists("Client Script", script_name):
        script = frappe.get_doc("Client Script", script_name)
        script.script = dashboard_script
        script.enabled = 1
        script.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": script_name,
            "dt": "SHG Loan",
            "view": "Form",
            "script": dashboard_script,
            "enabled": 1
        }).insert(ignore_permissions=True)
    
    frappe.db.commit()