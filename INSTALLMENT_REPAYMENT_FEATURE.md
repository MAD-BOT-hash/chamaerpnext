# Installment-Based Repayment Feature

## Overview
This feature enhances the SHG Loan Repayment functionality to support paying multiple unpaid installments via an editable child table. Users can now select specific installments to pay and allocate amounts to each installment individually.

## Key Components

### 1. New Child DocType: SHG Repayment Installment Adjustment
- Fields:
  - `installment_no`: Installment number (read-only)
  - `due_date`: Due date (read-only)
  - `principal_amount`: Principal amount (read-only)
  - `interest_amount`: Interest amount (read-only)
  - `total_due`: Total due amount (read-only)
  - `amount_to_repay`: Amount to repay (editable)
  - `remaining`: Remaining balance (auto-calculated, read-only)
  - `schedule_row_id`: Link to the repayment schedule row (hidden)

### 2. Enhanced SHG Loan Repayment
- Added new child table field `installment_adjustment`
- New method `pull_unpaid_installments()` to populate the table
- Validation to ensure amounts don't exceed totals
- Logic to update repayment schedule based on installment adjustments

### 3. Server-Side Methods
- `recalculate_installment_balances()`: Recalculate remaining balances
- `refresh_installment_adjustment()`: Refresh with current unpaid installments

### 4. UI Enhancements
- "Pull Unpaid Installments" button
- "Recalculate Balances" button
- "Refresh Installments" button
- Auto-calculation of remaining balances when amounts change

## Implementation Details

### Database Changes
- Added new child DocType `SHG Repayment Installment Adjustment`
- Updated `SHG Loan Repayment` doctype with new child table field
- Added patch to ensure proper migration

### Code Changes
- Modified `SHG Loan Repayment` Python class with new methods
- Updated JavaScript to handle UI interactions
- Added server-side API methods for balance calculations

### Validation Rules
- Amount to repay cannot be negative
- Amount to repay cannot exceed total due
- Total installment payments must equal Total Paid field
- Proper handling of partial and full payments

## Usage

### Creating a New Repayment with Installment Adjustments
1. Create a new SHG Loan Repayment
2. Select a loan
3. Click "Pull Unpaid Installments" to populate the table
4. Enter amounts to repay for each installment
5. Submit the repayment

### Editing Existing Repayment
1. Open an existing draft repayment
2. Modify amounts in the installment adjustment table
3. Use "Recalculate Balances" to update remaining amounts
4. Submit the repayment

## Testing
Comprehensive test cases have been created to verify:
- Pulling unpaid installments
- Full installment repayment
- Partial installment repayment
- Multiple installment repayment
- Proper schedule updates
- Balance calculations

## Migration
Run the following command to apply the changes:
```bash
bench --site your-site-name migrate
```

The patch `add_repayment_installment_adjustment_doctype` will be executed automatically.