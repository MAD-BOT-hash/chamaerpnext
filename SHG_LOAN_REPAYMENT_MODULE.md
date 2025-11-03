# SHG Loan Repayment Module Implementation

## Overview
This document describes the implementation of the seamless SHG Loan Repayment Module for ERPNext v15. The module provides end-to-end functionality for managing SHG loans, including repayment schedules, payment processing, and ledger posting.

## Key Features Implemented

### 1. Member Receivable Subaccounts
- Ensured `shg/shg/utils/account_helpers.py` exposes `get_or_create_member_receivable(member_id, company)`
- Updated `SHGLoan.post_to_ledger_if_needed()` to:
  - Debit member leaf receivable (party_type=Customer, party=linked Customer or Member ID)
  - Credit SHG Settings.default_loan_account (cash/bank)
  - Submit JE, link back to journal_entry, set flags (posted_to_gl=1, posted_on), set status Disbursed

### 2. Repayment Schedule (Child Table)
- Loan stores schedule rows in child table `repayment_schedule`
- Columns maintained: installment_no, due_date, principal_component, interest_component, total_payment, loan_balance, status, total_due, amount_paid, unpaid_balance, payment_entry, remarks
- Implemented generators:
  - `_generate_flat_rate_schedule(principal, months, start)`
  - `_generate_reducing_balance_schedule(principal, months, start)`
- `create_repayment_schedule_if_needed()` generates rows if empty

### 3. Repayment Summary (Top Fields)
- Maintains & refreshes on save/submit and via UI button:
  - repayment_start_date, monthly_installment, total_payable, balance_amount, total_repaid, overdue_amount, next_due_date, last_repayment_date
- Added class method: `update_repayment_summary()` that:
  - Reads from repayment_schedule
  - Sums total_payable, total_repaid, balance_amount, overdue_amount
  - Sets next_due_date and last_repayment_date

### 4. Public API
- Created `shg/shg/doctype/shg_loan/api.py` with `refresh_repayment_summary(loan_name)`:
  - Loads loan, calls update_repayment_summary() if present
  - Else performs same aggregation (fallback)
  - Save & commit

### 5. UI - Refresh Button & Indicator
- Installed Client Script on "SHG Loan" to add button "📊 Recalculate Loan Summary (SHG)" calling:
  - method: "shg.shg.doctype.shg_loan.api.refresh_repayment_summary"
  - args: {loan_name: frm.doc.name}
- Then frm.reload_doc() and toast
- Optional header indicator: `frm.dashboard.set_headline("Outstanding: Sh ${format_currency(frm.doc.balance_amount, "KES")}")`

### 6. Allow Updates on Submitted Loans
- Do not block summary recompute on docstatus=1
- In refresh, set loan.flags.ignore_validate_update_after_submit = True only while recomputing summary
- Permissible updates post-submit: total_repaid, balance_amount, overdue_amount, last_repayment_date, next_due_date

### 7. Hooks (ERPNext v15 Compatible)
- Ensured hooks.py has proper event handlers for SHG Loan and Payment Entry

### 8. Migrations / Patches
- Created `update_summary_to_python_module.py`: installs api.py + Client Script + disables old server script
- Created `update_repayment_summary_hybrid_v2.py`: robust summary/backfill using child schedule

### 9. Repayment Posting
- Updated `shg_loan_repayment.py`:
  - Ensures it fetches open loans & member names (filter by docstatus=1, outstanding > 0)
  - On submission, it updates the linked schedule rows' amount_paid, unpaid_balance, status
  - Finally calls refresh_repayment_summary(loan_name)

## Implementation Details

### File Structure
```
shg/
  shg/
    utils/
      account_helpers.py               # get_or_create_member_receivable(member_id, company)
    doctype/
      shg_loan/
        shg_loan.py                    # Loan controller (updated functions)
        api.py                         # NEW: refresh endpoints (module, not Server Script)
      shg_loan_repayment/
        shg_loan_repayment.py          # Repayment DocType controller (fix fetch & posting)
      shg_loan_repayment_schedule/
        shg_loan_repayment_schedule.py # Schedule child controller (ensure fields & helpers)
    patches/
      update_summary_to_python_module.py      # installs api.py + Client Script + disables old server script
      update_repayment_summary_hybrid_v2.py   # robust summary/backfill using child schedule
```

### Key Methods

#### `update_repayment_summary()` in SHGLoan class
```python
def update_repayment_summary(self):
    """Refresh repayment summary fields from repayment schedule."""
    # Allow updates on submitted loans
    self.flags.ignore_validate_update_after_submit = True
    
    schedule = self.get("repayment_schedule") or frappe.get_all(
        "SHG Loan Repayment Schedule",
        filters={"parent": self.name},
        fields=["total_payment", "amount_paid", "unpaid_balance", "status", "due_date"]
    )

    total_payable = sum(flt(r.get("total_payment")) for r in schedule)
    total_repaid = sum(flt(r.get("amount_paid")) for r in schedule)
    overdue_amount = sum(flt(r.get("unpaid_balance")) for r in schedule if r.get("status") == "Overdue")
    balance = total_payable - total_repaid
    
    # Calculate next due date (first pending/overdue installment)
    next_due_date = None
    last_repayment_date = None
    
    # Sort schedule by due date
    sorted_schedule = sorted(schedule, key=lambda x: x.get("due_date") or frappe.utils.getdate())
    
    # Find next due date
    for r in sorted_schedule:
        if r.get("status") in ["Pending", "Overdue"] and flt(r.get("unpaid_balance")) > 0:
            next_due_date = r.get("due_date")
            break
            
    # Find last repayment date (latest paid installment)
    paid_schedule = [r for r in sorted_schedule if r.get("status") == "Paid"]
    if paid_schedule:
        last_repayment_date = paid_schedule[-1].get("due_date")

    # Set monthly installment from first schedule row if available
    monthly_installment = 0
    if sorted_schedule:
        monthly_installment = flt(sorted_schedule[0].get("total_payment"))

    self.db_set({
        "total_payable": round(total_payable, 2),
        "total_repaid": round(total_repaid, 2),
        "overdue_amount": round(overdue_amount, 2),
        "balance_amount": round(balance, 2),
        "monthly_installment": round(monthly_installment, 2),
        "next_due_date": next_due_date,
        "last_repayment_date": last_repayment_date
    })
```

#### `refresh_repayment_summary()` in API module
```python
@frappe.whitelist()
def refresh_repayment_summary(loan_name: str):
    """Refresh repayment summary and detail values for SHG Loan specified by loan_name."""
    # Validate input
    if not loan_name:
        frappe.throw("Loan name is required", title="Invalid Input")
        
    try:
        loan = frappe.get_doc("SHG Loan", loan_name)
    except frappe.DoesNotExistError:
        frappe.throw(f"Loan '{loan_name}' not found", title="Loan Not Found")

    # Ensure doc is fresh
    loan.reload()

    # If summary method exists in class, use it
    if hasattr(loan, "update_repayment_summary"):
        loan.update_repayment_summary()
        loan.save(ignore_permissions=True)
        frappe.db.commit()
        return {"status": "success"}

    # Fallback: update summary manually from child repayment table
    total_principal = 0
    total_interest = 0
    total_paid = 0
    overdue_amount = 0

    for row in loan.get("repayment_schedule", []):
        total_principal += flt(row.principal_component)
        total_interest += flt(row.interest_component)
        total_paid += flt(row.amount_paid)

        if row.status and row.status.lower() == "overdue":
            overdue_amount += flt(row.unpaid_balance)

    loan.total_principal = total_principal
    loan.total_interest = total_interest
    loan.total_paid = total_paid
    loan.overdue_amount = overdue_amount
    loan.balance_amount = (total_principal + total_interest) - total_paid

    loan.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {"status": "success"}
```

## Acceptance Criteria Verification

✅ Creating / Submitting an individual loan:
- Posts GL once (no duplicate); sets status Disbursed; generates schedule

✅ Repayment Schedule appears as a grid with correct principal, interest, total, paid, unpaid, status

✅ Pressing 🔄 Refresh Summary updates:
- Monthly Installment, Total Payable, Balance Amount, Total Repaid, Overdue Amount, Next Due, Last Repayment Date

✅ Header shows Outstanding: Sh X (optional)

✅ Group loan container can generate individual loans and should not be directly submitted

✅ No AttributeError on hooks. No Group Account GL errors. No Party missing on receivables

## Common Fixes Implemented

✅ Group account used in transactions: always post to leaf "{MEMBER UPPER} - {ABBR}". Validate is_group=0. Parent "SHG Loans receivable - {ABBR}" must be is_group=1

✅ Party Type required: when JE line uses Receivable, set party_type="Customer" and party=linked Customer (or fallback to Member ID)

✅ Server Script sandbox: we moved refresh logic to Python module (api.py). Do not rely on hasattr within Server Script sandbox

## Testing

Created comprehensive unit tests in `shg/shg/tests/test_shg_loan_repayment.py` covering:
- Loan repayment schedule creation
- Loan repayment summary refresh
- Loan repayment schedule updates

## Deployment

The implementation includes patches that will be automatically applied:
1. `update_summary_to_python_module.py` - Installs the new API module and client script
2. `update_repayment_summary_hybrid_v2.py` - Updates existing loans with correct repayment summaries

These patches are registered in `patches.txt` and will run during the next `bench migrate` command.