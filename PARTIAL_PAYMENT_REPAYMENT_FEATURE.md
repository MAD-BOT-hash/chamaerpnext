# Partial Payment & Full Balance Management Feature

## Overview
This feature enhances the SHG Loan Repayment functionality to support partial payments and full balance management. Users can now select specific installments to pay, allocate amounts to each installment individually, and track loan balances accurately.

## Key Components

### 1. Updated Child Table: SHG Repayment Installment Adjustment
Updated fields to include:
- `installment_no`: Installment number (read-only)
- `due_date`: Due date (read-only)
- `total_due`: Total due amount (read-only)
- `unpaid_balance`: Unpaid balance (read-only)
- `amount_to_repay`: Amount to repay (editable)
- `status`: Status (Pending, Partially Paid, Paid) (auto-updated)

### 2. Enhanced SHG Loan Repayment
- Added new method `get_unpaid_installments()` to populate the table
- Updated validation to ensure amounts don't exceed unpaid balances
- Logic to update repayment schedule based on installment adjustments
- Support for partial and full installment payments

### 3. SHG Loan Repayment Schedule Updates
- Ensure `total_due` is computed as `principal_component + interest_component`
- Proper handling of status updates (Pending, Partially Paid, Paid)

### 4. UI Enhancements
- "Fetch Unpaid Installments" button replaces "Pull Unpaid Installments"
- Real-time status updates when amounts change
- Validation to prevent overpayments

## Implementation Details

### Database Changes
- Updated `SHG Repayment Installment Adjustment` doctype with new fields
- Updated `SHG Loan Repayment Schedule` to ensure `total_due` is computed correctly
- Added patch to migrate existing data

### Code Changes
- Modified `SHG Loan Repayment` Python class with new methods
- Updated JavaScript to handle UI interactions
- Updated schedule math utilities to compute `total_due` correctly
- Updated member summary report to compute loan balances accurately

### Validation Rules
- Amount to repay cannot be negative
- Amount to repay cannot exceed unpaid balance
- Total installment payments must equal Total Paid field
- Proper handling of partial and full payments

## Usage

### Creating a New Repayment with Installment Adjustments
1. Create a new SHG Loan Repayment
2. Select a loan
3. Click "Fetch Unpaid Installments" to populate the table
4. Enter amounts to repay for each installment
5. Submit the repayment

### Editing Existing Repayment
1. Open an existing draft repayment
2. Modify amounts in the installment adjustment table
3. Submit the repayment

## Testing
Comprehensive test cases have been created to verify:
- Fetching unpaid installments
- Partial installment repayment
- Full installment repayment
- Multiple installment repayment
- Proper schedule updates
- Balance calculations

## Migration
Run the following command to apply the changes:
```bash
bench --site your-site-name migrate
```

The patch `add_child_table_repayment_installment_adjustment` will be executed automatically.