# Client Callable Functions Summary

This document summarizes all the functions in the SHG app that have been decorated with `@frappe.whitelist()` to make them callable from the client side.

## SHG Loan (shg_loan.py)

### Class Methods
- `check_member_eligibility()`: Check if a member is eligible for a loan

## SHG Loan Repayment (shg_loan_repayment.py)

### Class Methods
- `send_payment_confirmation()`: Send SMS confirmation for loan repayment

## SHG Contribution (shg_contribution.py)

### Class Methods
- `get_suggested_amount()`: Get suggested contribution amount based on type and member
- `send_payment_confirmation()`: Send payment confirmation SMS
- `initiate_mpesa_stk_push()`: Initiate Mpesa STK Push for contribution payment

## SHG Meeting Fine (shg_meeting_fine.py)

### Class Methods
- `send_fine_notification()`: Send fine notification to member

## SHG Meeting (shg_meeting.py)

### Class Methods
- `get_member_list()`: Get all active members for attendance

## SHG Member (shg_member.py)

### Standalone Functions
- `update_financial_summary(member_id)`: Update financial summary for a member
- `get_member_summary(member_id)`: Get member summary information

## SHG Notification Log (shg_notification_log.py)

### Class Methods
- `mark_as_sent()`: Mark notification as sent
- `mark_as_failed(error_message)`: Mark notification as failed

## Hook Functions (Should NOT have @frappe.whitelist)

All hook functions in the doctype files have been marked with comments indicating they should NOT have the @frappe.whitelist() decorator since they are called internally by the Frappe framework.

## Implementation Notes

1. All functions that are called from client-side code (frappe.call, button actions, REST API calls, or form triggers) now have the @frappe.whitelist() decorator.

2. Hook functions that are called by the Frappe framework through hooks.py are NOT decorated with @frappe.whitelist() as they don't need to be accessible from the client side.

3. All decorated functions maintain their original signatures and business logic.

4. Return values from these functions are JSON serializable (dict, str, int, list) as required by the Frappe framework.