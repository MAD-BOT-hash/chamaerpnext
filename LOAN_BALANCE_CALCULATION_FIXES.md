# SHG Loan Balance Calculation Fixes

## Overview
This document describes the comprehensive fixes implemented for SHG Loan balance and repayment calculations to ensure all key computed fields update correctly and reflect the full outstanding amount (principal + interest).

## Issues Fixed

1. **Balance Amount always shows 0.00 even before repayment**
2. **Loan Balance only shows principal instead of principal + interest**
3. **Total Payable is calculated but not tied to real-time schedule updates**
4. **Repayments do not decrease loan balance or schedule balances properly**
5. **Partial repayments fail validation even when there IS a balance**
6. **Repayment schedule status and loan header summary fields are not synchronized**

## Key Changes Implemented

### 1. New Server-Side Functions

#### `get_outstanding_balance(loan_name)`
Returns detailed breakdown of loan balance:
```json
{
  "remaining_principal": x,
  "remaining_interest": y,
  "total_outstanding": x + y
}
```

#### `get_loan_balance(loan_name)`
Returns total outstanding balance (principal + interest)

#### `update_loan_summary(loan_name)`
Updates all loan summary fields to ensure synchronization with repayment schedule

#### `debug_loan_balance(loan_name)` (API endpoint)
Debug endpoint that returns detailed loan balance information including:
- Loan details
- Repayment schedule
- Repayments posted
- Computed remaining amounts

### 2. Enhanced Loan Repayment Logic

#### Partial Installment Payments
- Removed hard stop validation for partial payments
- Allow spreading payments across multiple installments
- Properly update schedule rows with partial payments

#### Real-Time Balance Calculation
- Calculate outstanding balance by summing unpaid balances from repayment schedule
- Include both principal and interest components
- Ensure synchronization between schedule-level and loan-level fields

#### Improved Validation
- Allow partial payments
- Only reject payments that exceed total outstanding balance
- Proper error messages with accurate numbers

### 3. Field Mapping Updates

| Field | Should Display |
|-------|----------------|
| Loan Balance | Total outstanding (principal + interest) |
| Balance Amount | Same as above |
| Total Repaid | Sum of all repayments posted |
| Total Payable | Total principal + total interest |
| Overdue Amount | Sum of past due schedule rows |

### 4. Synchronization Fixes

#### After Each Repayment:
1. Update `amount_paid` on schedule row
2. Update `unpaid_balance` on schedule row
3. Update `status` on schedule row (Unpaid → Partially Paid → Paid)
4. Refresh loan-level fields:
   - `total_repaid`
   - `loan_balance`
   - `overdue_amount`
   - `total_payable`

### 5. Database Changes

#### New Patch: `fix_loan_balance_calculations`
- Reloads SHG Loan and SHG Loan Repayment doctypes
- Updates all existing loans to recalculate balances
- Ensures proper synchronization of all fields

## API Endpoints

### Debug Loan Balance
```
GET /api/method/shg.shg.api.loan.debug_loan_balance?loan=LOAN-0001
```

Returns:
```json
{
  "loan": {
    "name": "LOAN-0001",
    "member": "MEMBER-001",
    "loan_amount": 10000,
    "total_payable": 11200,
    "total_repaid": 1000,
    "balance_amount": 10200,
    "loan_balance": 10200,
    "overdue_amount": 0
  },
  "schedule": [...],
  "repayments": [...],
  "outstanding": {
    "remaining_principal": 9000,
    "remaining_interest": 1200,
    "total_outstanding": 10200
  }
}
```

## Testing

Comprehensive test cases have been created in `tests/test_loan_balance_calculations.py` covering:
- `get_outstanding_balance` function
- `get_loan_balance` function
- Partial repayment updates
- Repayment schedule synchronization
- Loan summary updates
- Debug endpoint functionality

## Implementation Files

1. `shg/shg/doctype/shg_loan/shg_loan.py` - Added new functions and updated existing ones
2. `shg/shg/doctype/shg_loan_repayment/shg_loan_repayment.py` - Enhanced repayment logic
3. `shg/shg/api/loan.py` - Added debug endpoint
4. `shg/shg/patches/fix_loan_balance_calculations.py` - Database migration patch
5. `shg/patches.txt` - Updated with new patch
6. `tests/test_loan_balance_calculations.py` - Test cases