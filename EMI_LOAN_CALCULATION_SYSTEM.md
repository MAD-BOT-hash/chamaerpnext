# EMI Loan Calculation System

## Overview
This document describes the implementation of an EMI-based loan calculation system for SHG loans that correctly handles principal + interest calculations, enables partial payments, and keeps all data synchronized.

## Key Components

### 1. Loan Utilities Module (`shg/shg/loan_utils.py`)

#### Functions:
- `get_schedule(loan_name)`: Retrieves repayment schedule with all relevant fields
- `compute_totals(schedule_rows)`: Computes loan totals including principal, interest, payable, repaid, balance, and overdue amounts
- `update_loan_summary(loan_name)`: Updates loan header fields with computed totals
- `allocate_payment_to_schedule(loan_name, paying_amount, posting_date)`: Allocates payments across installments using EMI logic
- `debug_loan_balance(loan)`: Debug endpoint for troubleshooting

### 2. API Endpoints (`shg/shg/api/loan.py`)

#### New Functions:
- `get_unpaid_installments(loan)`: Returns list of unpaid installments
- `post_repayment_allocation(loan, amount)`: Processes repayment allocation

### 3. Loan Repayment Doctype Handler (`shg/shg/doctype/shg_loan_repayment/shg_loan_repayment.py`)

#### Updated Logic:
- Simplified validation to only check for positive amounts
- On submit: Calls `allocate_payment_to_schedule` and `update_loan_summary`
- On cancel: Recomputes from ledger to maintain data integrity

### 4. Client Script (`shg/shg/doctype/shg_loan_repayment/shg_loan_repayment.js`)

#### Features:
- "Fetch Unpaid Installments" button that populates a child table
- Automatic summing of partial payments into total amount

### 5. Database Patch (`shg/shg/patches/recompute_loan_summaries_emi.py`)

#### Function:
- Normalizes all existing loan schedules
- Ensures `remaining_amount` and `status` fields are correctly populated
- Updates all loan summary fields

### 6. Test Suite (`tests/test_emi_loan_calculations.py`)

#### Coverage:
- Schedule retrieval
- Total computation
- Loan summary updates
- Payment allocation
- API endpoint testing

## Implementation Details

### EMI Allocation Logic
Payments are allocated across the earliest unpaid/partially paid installments:
1. Sort installments by due date
2. For each installment with remaining balance:
   - Allocate minimum of payment amount or remaining balance
   - Update amount paid, remaining amount, and status
   - Continue to next installment if payment amount remains

### Field Mapping
| Field | Value |
|-------|-------|
| `loan_balance` | Total outstanding (principal + interest) |
| `balance_amount` | Same as loan_balance for UI consistency |
| `total_payable` | Total principal + total interest |
| `total_repaid` | Sum of all payments made |
| `overdue_amount` | Sum of past due amounts |

### Partial Payment Handling
- Removed hard validation against single installments
- Payments can be any amount up to total outstanding balance
- Excess amounts automatically spread to next installments

### Data Synchronization
After each payment:
1. Update schedule row fields: `amount_paid`, `remaining_amount`, `status`
2. Update loan header fields: `total_payable`, `total_repaid`, `loan_balance`, `balance_amount`, `overdue_amount`

## Reports
Updated SQL queries to use:
```sql
SUM(sch.total_payment) AS total_payable,
SUM(sch.amount_paid) AS total_repaid,
(SUM(sch.total_payment) - SUM(sch.amount_paid)) AS loan_balance
```

For overdue amounts:
```sql
SUM(CASE WHEN sch.due_date < CURDATE() AND sch.status <> 'Paid'
         THEN (sch.total_payment - IFNULL(sch.amount_paid,0)) ELSE 0 END) AS overdue_amount
```

## Safety Measures
- Removed old validation logic that computed balances from principal only
- Added comprehensive error handling
- Implemented ledger-based recomputation for cancellations
- Ensured all field updates use `update_modified=False` for performance

## Files Created/Modified

1. `shg/shg/loan_utils.py` - New module with core calculation functions
2. `shg/shg/api/loan.py` - Updated with new API endpoints
3. `shg/shg/doctype/shg_loan_repayment/shg_loan_repayment.py` - Simplified repayment logic
4. `shg/shg/doctype/shg_loan_repayment/shg_loan_repayment.js` - Client-side UI enhancements
5. `shg/shg/patches/recompute_loan_summaries_emi.py` - Database migration patch
6. `shg/patches.txt` - Updated with new patch
7. `tests/test_emi_loan_calculations.py` - Test suite