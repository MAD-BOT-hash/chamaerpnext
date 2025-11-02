import os
import json
import frappe
from frappe import _
from frappe.utils import flt, getdate, today

# ---------- Helpers ----------

def _write_file(rel_path: str, content: str):
    """Create/overwrite a file under the 'shg' app folder."""
    app_path = frappe.get_app_path("shg")
    abs_path = os.path.join(app_path, *rel_path.split("/"))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
    return abs_path

def _disable_server_script_by_name(name: str):
    if frappe.db.exists("Server Script", name):
        doc = frappe.get_doc("Server Script", name)
        if not doc.disabled:
            doc.disabled = 1
            doc.save()
            frappe.db.commit()

def _ensure_client_script(name: str, doctype: str, script: str):
    """Create/Update a Client Script document."""
    if frappe.db.exists("Client Script", name):
        cs = frappe.get_doc("Client Script", name)
        cs.script = script
        cs.dt = doctype
        cs.enabled = 1
        cs.save()
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": name,
            "dt": doctype,
            "script": script,
            "enabled": 1,
        }).insert()
    frappe.db.commit()

# ---------- Module code we're installing ----------

MODULE_CODE = """# -*- coding: utf-8 -*-
import frappe
from frappe.utils import flt, getdate, today

@frappe.whitelist()
def refresh_repayment_summary(loan_name: str):
    \"\"\"Recalculate and persist loan summary from child-table schedule.
    Works on submitted loans via db_set, and emits form alerts on client side.
    \"\"\"
    if not loan_name:
        frappe.throw('Loan name is required.')

    loan = frappe.get_doc('SHG Loan', loan_name)
    loan.flags.ignore_validate_update_after_submit = True

    # pull schedule rows from child table
    rows = frappe.get_all(
        'SHG Loan Repayment Schedule',
        filters={'parent': loan.name, 'parenttype': 'SHG Loan'},
        fields=['name','due_date','total_payment','amount_paid','unpaid_balance',
                'status','actual_payment_date','loan_balance'],
        order_by='due_date asc'
    )

    total_paid = 0.0
    total_payment_sum = 0.0
    overdue_amt = 0.0
    next_due = None
    last_paid_date = None
    outstanding = None

    today_d = getdate(today())
    for r in rows:
        tp = flt(r.get('total_payment') or 0)
        ap = flt(r.get('amount_paid') or 0)
        ub = flt(r.get('unpaid_balance') or 0)
        total_payment_sum += tp
        total_paid += ap

        # overdue: unpaid portion of past-due rows
        if r.get('due_date') and getdate(r['due_date']) < today_d and ub > 0:
            overdue_amt += ub

        # next due: first unpaid future/present
        if ub > 0:
            if not next_due:
                next_due = r.get('due_date')

        # last repayment date (actual payments)
        if ap > 0 and r.get('actual_payment_date'):
            last_paid_date = r['actual_payment_date']

        # prefer schedule's running balance if present
        if r.get('loan_balance') is not None:
            outstanding = r['loan_balance']

    # fallback outstanding if schedule didn't provide a running balance
    if outstanding is None:
        outstanding = max(flt(loan.loan_amount or 0), 0) - total_paid

    # derive total_payable if missing
    total_payable = flt(loan.total_payable or 0)
    if not total_payable:
        # try: sum of scheduled totals
        total_payable = total_payment_sum or (flt(loan.loan_amount or 0) + flt(loan.total_interest_payable or 0))

    # persist via db_set to allow update-after-submit
    loan.db_set('total_repaid', round(total_paid, 2))
    loan.db_set('overdue_amount', round(overdue_amt, 2))
    loan.db_set('balance_amount', round(outstanding, 2))
    if next_due:
        loan.db_set('next_due_date', next_due)
    if last_paid_date:
        loan.db_set('last_repayment_date', last_paid_date)
    if total_payable and not flt(loan.total_payable):
        loan.db_set('total_payable', round(total_payable, 2))

    # Optional UX nudge for header indicator (consumed by Client Script)
    frappe.response['message'] = {
        'ok': True,
        'total_repaid': round(total_paid, 2),
        'overdue_amount': round(overdue_amt, 2),
        'balance_amount': round(outstanding, 2),
        'next_due_date': next_due
    }
    return frappe.response['message']
"""

# ---------- Client Script with CUSTOM BUTTON LABEL ----------

CUSTOM_BUTTON_LABEL = "📊 Recalculate Loan Summary (SHG)"  # Your custom label (Option 5)

CLIENT_SCRIPT = f"""frappe.ui.form.on('SHG Loan', {{
    refresh(frm) {{
        // Always show the custom refresh button
        frm.add_custom_button('{CUSTOM_BUTTON_LABEL}', async () => {{
            if (!frm.doc.name) {{
                frappe.msgprint('Please save the document first.');
                return;
            }}
            frappe.call({{
                method: 'shg.shg.api.repayment_refresh.refresh_repayment_summary',
                args:  {{loan_name: frm.doc.name}} ,
                callback: (r) => {{
                    frm.reload_doc();
                    if (r && r.message) {{
                        const m = r.message;
                        frappe.show_alert({{
                            message: `✅ Summary refreshed — Outstanding: Sh ${{m.balance_amount}}`,
                            indicator: 'green'
                        }});
                        // Tiny header indicator
                        frm.page.set_title(_(frm.doc.name + " · Outstanding: Sh " + m.balance_amount));
                    }} else {{
                        frappe.show_alert({{message: 'Summary refreshed', indicator: 'green'}});
                    }}
                }}
            }});
        }});
    }}
}});"""

# ---------- Patch entry ----------

def execute():
    """
    Install the repayment refresh module, disable old server script, and add a client-side button.
    Also safe on reruns.
    """
    # 1) Write/overwrite the python module
    rel_py = "shg/api/repayment_refresh.py"
    _write_file(rel_py, MODULE_CODE)

    # 2) Disable any old server script with same idea (avoid sandbox NameError issues)
    _disable_server_script_by_name("SHG Loan | refresh_repayment_summary")

    # 3) Install Client Script with your custom label
    _ensure_client_script(
        name="SHG Loan | Refresh Summary Button",
        doctype="SHG Loan",
        script=CLIENT_SCRIPT,
    )

    frappe.clear_cache()
    frappe.msgprint(_("✅ Installed repayment refresh module + client button."))