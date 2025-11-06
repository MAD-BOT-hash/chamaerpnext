# Inline SHG Loan Repayment Implementation

## Overview
This document describes the implementation of an inline partial repayment system for SHG loans with full EMI logic support. The system allows users to fetch unpaid installments, make partial payments per installment, and see real-time updates of totals directly within the SHG Loan form.

## Key Components

### 1. Schema Patches (`shg/shg/patches/add_inline_repayment_fields.py`)

#### Added Fields to SHG Loan Repayment Schedule:
- `pay_now` (Check) - Select installment for payment
- `amount_to_pay` (Currency) - Amount to pay for selected installment
- `remaining_amount` (Currency, Read Only) - Remaining balance for installment

#### Added Fields to SHG Loan:
- `inline_repayment_section` (Section Break) - Section for inline repayment controls
- `emi_breakdown` (HTML) - Display EMI summary information
- `inline_total_selected` (Currency, Read Only) - Total amount selected for payment
- `inline_overdue` (Currency, Read Only) - Total overdue amount
- `inline_outstanding` (Currency, Read Only) - Total outstanding amount

### 2. API Module (`shg/shg/api/loan_inline.py`)

#### Functions:
- `pull_unpaid_installments(loan_name)` - Fetch unpaid or partially paid installments
- `compute_inline_totals(loan_name)` - Calculate dynamic totals
- `post_inline_repayments(loan_name, repayments)` - Process selected payments
- `get_installment_remaining_balance(schedule_row)` - Calculate remaining balance for installment
- `compute_aggregate_totals(loan_name)` - Compute principal + interest unpaid totals

### 3. Client-Side JavaScript (`shg/public/js/shg_loan.js`)

#### Features:
- Custom buttons: "Pull Unpaid Installments" and "Post Selected Payments"
- Live recalculation of totals when:
  - Table rows are added/removed
  - `pay_now` checkbox is toggled
  - `amount_to_pay` is modified
- EMI breakdown display with formatted totals
- Highlighting of selected installments
- Real-time updates without save/refresh

### 4. Hooks Configuration (`shg/hooks.py`)

#### Updated:
- Added `SHG Loan: "public/js/shg_loan.js"` to `doctype_js` configuration

### 5. Test Suite (`tests/test_inline_repayment.py`)

#### Coverage:
- Pulling unpaid installments
- Computing inline totals
- Posting inline repayments
- Calculating installment remaining balances
- Computing aggregate totals

## Implementation Details

### Field Mapping
| Field | Purpose |
|-------|---------|
| `pay_now` | Checkbox to select installment for payment |
| `amount_to_pay` | Currency field for payment amount |
| `remaining_amount` | Read-only display of unpaid balance |
| `inline_total_selected` | Sum of all selected payment amounts |
| `inline_overdue` | Sum of unpaid balances for past due installments |
| `inline_outstanding` | Total outstanding balance (principal + interest) |

### EMI Logic
- Supports partial payments per installment
- Automatically closes rows when fully paid
- Maintains proper status tracking (Pending, Partially Paid, Paid, Overdue)
- Updates loan-level totals in real-time

### User Experience
- No standalone "repayment schedule" List View - kept as child table
- Inline editing within SHG Loan form
- Real-time total calculations
- Confirmation dialogs for payment posting
- Visual EMI breakdown display

### Compatibility
- ERPNext version 15 compatible
- Removes deprecated field references
- Maintains backward compatibility with existing data

## Files Created/Modified

1. `shg/shg/patches/add_inline_repayment_fields.py` - Schema patch for new fields
2. `shg/patches.txt` - Updated with new patch
3. `shg/shg/api/loan_inline.py` - API module with core logic
4. `shg/public/js/shg_loan.js` - Client-side JavaScript enhancements
5. `shg/hooks.py` - Updated doctype_js configuration
6. `tests/test_inline_repayment.py` - Test suite

## Workflow

1. User opens submitted SHG Loan form
2. Clicks "Pull Unpaid Installments" to fetch outstanding schedule rows
3. Selects installments to pay by checking `pay_now` checkboxes
4. Enters payment amounts in `amount_to_pay` fields
5. Sees live updates of totals in EMI breakdown
6. Clicks "Post Selected Payments" to process payments
7. System validates amounts, updates schedule rows, and recalculates loan totals

## Benefits

- ✅ Inline editing without form jumps
- ✅ Real-time total calculations
- ✅ Support for partial payments per installment
- ✅ Automatic row closure when fully paid
- ✅ Accurate loan aging and overdue calculations
- ✅ Improved user experience
- ✅ Full EMI math (Principal + Interest breakdown)
- ✅ Compatible with ERPNext v15