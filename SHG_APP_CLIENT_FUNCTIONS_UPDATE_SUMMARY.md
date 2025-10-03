# SHG App Client Functions Update Summary

This document summarizes all the updates made to add `@frappe.whitelist()` decorators to functions in the SHG app that are called from the client side.

## Overview

All functions in the SHG app that are called from client-side code (frappe.call, button actions, REST API calls, or form triggers) have been updated with the `@frappe.whitelist()` decorator to ensure they are accessible in ERPNext v15.

Functions that are internal hook functions or private methods have been marked with comments indicating they should NOT have the `@frappe.whitelist()` decorator.

## Files Updated

### 1. SHG Loan (shg/shg/doctype/shg_loan/shg_loan.py)

**Functions with @frappe.whitelist() added:**
- `check_member_eligibility()`: Check if a member is eligible for a loan

**Hook functions (marked as NOT to have @frappe.whitelist()):**
- `validate_loan()`
- `post_to_general_ledger()`
- `generate_repayment_schedule()`

### 2. SHG Loan Repayment (shg/shg/doctype/shg_loan_repayment/shg_loan_repayment.py)

**Functions with @frappe.whitelist() (already had it):**
- `send_payment_confirmation()`: Send SMS confirmation for loan repayment

**Hook functions (marked as NOT to have @frappe.whitelist()):**
- `validate_repayment()`
- `post_to_general_ledger()`

### 3. SHG Contribution (shg/shg/doctype/shg_contribution/shg_contribution.py)

**Functions with @frappe.whitelist() (already had it):**
- `get_suggested_amount()`: Get suggested contribution amount based on type and member
- `send_payment_confirmation()`: Send payment confirmation SMS
- `initiate_mpesa_stk_push()`: Initiate Mpesa STK Push for contribution payment

Fixed duplicate @frappe.whitelist() decorators that were present in the file.

**Hook functions (marked as NOT to have @frappe.whitelist()):**
- `validate_contribution()`
- `post_to_general_ledger()`

### 4. SHG Notification Log (shg/shg/doctype/shg_notification_log/shg_notification_log.py)

**Functions with @frappe.whitelist() added:**
- `mark_as_sent()`: Mark notification as sent
- `mark_as_failed(error_message)`: Mark notification as failed

### 5. SHG Meeting Fine (shg/shg/doctype/shg_meeting_fine/shg_meeting_fine.py)

**Functions with @frappe.whitelist() added:**
- `send_fine_notification()`: Send fine notification to member

**Hook functions (marked as NOT to have @frappe.whitelist()):**
- `validate_fine()`
- `post_to_general_ledger()`

### 5. SHG Meeting (shg/shg/doctype/shg_meeting/shg_meeting.py)

**Functions with @frappe.whitelist() added:**
- `get_member_list()`: Get all active members for attendance

**Hook functions (marked as NOT to have @frappe.whitelist()):**
- `process_attendance_fines()`

### 6. SHG Member (shg/shg/doctype/shg_member/shg_member.py)

**Functions with @frappe.whitelist() (already had it):**
- `update_financial_summary(member_id)`: Update financial summary for a member
- `get_member_summary(member_id)`: Get member summary information

**Hook functions (marked as NOT to have @frappe.whitelist()):**
- `validate_member()`
- `create_member_ledger()`
- `handle_member_amendment()`
- `handle_member_update_after_submit()`

## Implementation Notes

1. All functions decorated with `@frappe.whitelist()` maintain their original signatures and business logic.

2. Return values from these functions are JSON serializable (dict, str, int, list) as required by the Frappe framework.

3. Hook functions that are called internally by the Frappe framework through hooks.py are NOT decorated with `@frappe.whitelist()` as they don't need to be accessible from the client side.

4. Comments have been added to all hook functions to indicate they should NOT have the `@frappe.whitelist()` decorator.

5. Duplicate decorators were removed from the SHG Contribution file.

## Testing

All updated functions should now be accessible from client-side code in ERPNext v15. The functions can be called using:

```javascript
frappe.call({
    method: "shg.shg.doctype.shg_loan.shg_loan.check_member_eligibility",
    args: {
        // function arguments
    },
    callback: function(r) {
        // handle response
    }
});
```

Replace the method path with the appropriate path for each function.

## Files Created

1. `CLIENT_CALLABLE_FUNCTIONS_SUMMARY.md` - Summary of all client callable functions
2. `SHG_APP_CLIENT_FUNCTIONS_UPDATE_SUMMARY.md` - This file with detailed update information