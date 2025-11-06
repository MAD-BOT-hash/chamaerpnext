# Repayment Balance Calculation Fix

## Problem
The repayment validation logic in the SHG Loan module had several issues:

1. **Incomplete Balance Calculation**: The `get_loan_balance` function only calculated principal balance, not including interest components
2. **Incorrect Validation**: The repayment validation was using cached values instead of real-time calculations
3. **Missing Synchronization**: Loan-level fields were not properly synchronized with schedule-level fields
4. **No Proper API**: There was no backend method to get accurate remaining balance information

## Solution Implemented

### 1. Enhanced Balance Calculation Functions

#### New `get_remaining_balance` Function
Added a new whitelisted function that calculates the remaining loan balance by summing unpaid balances from the repayment schedule, including both principal and interest components:

```python
@frappe.whitelist()
def get_remaining_balance(loan_name):
    """
    Calculate remaining loan balance by summing unpaid balances from repayment schedule.
    This includes both principal and interest components.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        
    Returns:
        dict: Contains total_balance, principal_balance, and interest_balance
    """
    # Implementation that sums unpaid_balance, principal_component, and interest_component
    # from all repayment schedule rows
```

#### Improved `get_loan_balance` Function
Updated the existing function to ensure proper error handling and logging.

### 2. Fixed Repayment Validation Logic

#### Enhanced `calculate_outstanding_balance` Method
Updated the method in `SHGLoanRepayment` class to properly calculate outstanding balance:

```python
def calculate_outstanding_balance(self, loan_doc):
    """
    Calculate outstanding balance by summing unpaid balances from repayment schedule.
    This ensures we're using real-time data instead of potentially stale cached values.
    Includes both principal and interest components.
    """
    # Get all repayment schedule rows
    schedule_rows = frappe.get_all(
        "SHG Loan Repayment Schedule",
        filters={
            "parent": loan_doc.name,
            "parenttype": "SHG Loan"
        },
        fields=["unpaid_balance"]
    )
    
    # Sum all unpaid balances
    outstanding_balance = sum(flt(row.get("unpaid_balance", 0)) for row in schedule_rows)
    
    return outstanding_balance
```

### 3. Improved Loan Summary Synchronization

#### Enhanced `update_loan_summary` Method
Added proper synchronization between loan-level fields and schedule-level fields:

```python
def update_loan_summary(self, loan_doc):
    """
    Update loan summary fields after repayment.
    This ensures loan-level fields are synchronized with schedule-level fields.
    """
    try:
        # Recalculate repayment summary
        loan_doc.update_repayment_summary()
        
        # Also update using the new get_remaining_balance function
        from shg.shg.doctype.shg_loan.shg_loan import get_remaining_balance
        balance_info = get_remaining_balance(loan_doc.name)
        
        # Update loan fields with computed values
        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.balance_amount = flt(balance_info["total_balance"], 2)
        loan_doc.save(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to update loan summary for {loan_doc.name}")
```

### 4. Fixed Repayment Schedule Updates

Enhanced the schedule update methods to properly update all relevant fields:
- `amount_paid`
- `unpaid_balance` 
- `status`
- `actual_payment_date`
- `payment_entry`

### 5. Improved Error Messages

The error message "Repayment (x) exceeds remaining balance (y)" now reflects accurate numbers by using real-time calculations instead of cached values.

## Benefits

1. **Accurate Balance Calculation**: Both principal and interest components are included in balance calculations
2. **Real-time Validation**: Validation uses dynamic calculations instead of cached values
3. **Proper Synchronization**: Loan-level fields are consistently updated with schedule-level fields
4. **Enhanced API**: New `get_remaining_balance` function provides detailed balance information
5. **Better Error Handling**: More accurate error messages help users understand validation failures
6. **Partial Payment Support**: Logic properly handles partial payments at both installment and loan levels

## Testing

Created comprehensive test cases in `tests/test_repayment_balance_calculation.py` to verify:
- `get_remaining_balance` function returns correct values
- Repayment validation uses correct balance calculation
- Repayment schedule updates properly after payment
- Loan summary fields are synchronized with schedule
- Validation correctly rejects amounts exceeding balance

## How to Test the Fix

1. Create a loan with a repayment schedule
2. Check that the initial balance includes both principal and interest
3. Make a partial repayment
4. Verify that the remaining balance is correctly calculated
5. Try to make another repayment - it should be accepted if within the remaining balance
6. Try to make a repayment that exceeds the balance - it should be rejected with an appropriate error message
7. Check that all schedule rows are properly updated after payments
8. Verify that loan-level fields are synchronized with schedule-level fields