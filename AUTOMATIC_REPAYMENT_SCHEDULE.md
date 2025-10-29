# Automatic Loan Repayment Schedule

This document describes the implementation of automatic loan repayment schedule generation in the SHG app.

## Overview

The system automatically generates a repayment schedule table when a loan is created. The schedule includes all necessary details for tracking loan repayments and supports both flat interest and reducing balance calculation methods.

## Features Implemented

### 1. Automatic Schedule Generation

When a loan is created and submitted, the system automatically generates a repayment schedule with the following fields:
- `installment_no`: Sequential installment number
- `due_date`: Date when the installment is due
- `principal_amount`: Principal component of the installment
- `interest_amount`: Interest component of the installment
- `total_due`: Total amount due for the installment
- `amount_paid`: Amount already paid
- `unpaid_balance`: Remaining balance for the installment
- `status`: Current status (Pending/Paid/Overdue)

### 2. Interest Calculation Methods

The system supports two interest calculation methods:

#### Flat Interest Rate
- Interest is calculated on the original principal amount throughout the loan period
- Principal and interest components remain constant for each installment
- Formula: Total Interest = Principal × Rate × Time

#### Reducing Balance Method
- Interest is calculated on the outstanding principal balance
- Interest component decreases with each payment
- Principal component increases with each payment
- Uses EMI (Equated Monthly Installment) calculation

### 3. Dynamic Schedule Updates

When loan terms are edited:
- The repayment schedule is automatically regenerated
- An audit log is created to track changes
- Previous payment information is preserved where possible

### 4. Audit Trail

All changes to loan terms that affect the repayment schedule are logged:
- Detailed comments are added to the loan document
- Changes to key parameters are recorded (loan amount, interest rate, period, etc.)
- Timestamps and user information are captured

## Technical Implementation

### SHG Loan Controller Enhancements

#### New Methods Added:
1. `_generate_flat_rate_schedule()`: Generates schedule using flat interest method
2. `_generate_reducing_balance_schedule()`: Generates schedule using reducing balance method
3. `update_repayment_schedule()`: Updates schedule when loan terms change
4. `_check_and_update_repayment_schedule()`: Checks for term changes and triggers updates

#### Modified Methods:
1. `validate()`: Added logic to check for term changes in draft loans
2. `create_repayment_schedule_if_needed()`: Enhanced to support both calculation methods

### Data Structure

The repayment schedule is stored in the `repayment_schedule` child table with the following fields:
- `installment_no` (Int)
- `due_date` (Date)
- `principal_amount` (Currency)
- `interest_amount` (Currency)
- `total_due` (Currency)
- `amount_paid` (Currency)
- `unpaid_balance` (Currency)
- `status` (Select: Pending/Paid/Partially Paid/Overdue)

## Usage

### Creating a Loan with Automatic Schedule

1. Create a new SHG Loan document
2. Fill in loan details including:
   - Member information
   - Loan amount
   - Interest rate
   - Loan period (months)
   - Interest type (Flat Rate or Reducing Balance)
   - Repayment start date
3. Submit the loan
4. The system automatically generates the repayment schedule

### Modifying Loan Terms

1. Edit a draft loan or modify allowed fields in a submitted loan
2. Change any key parameters (amount, rate, period, etc.)
3. Save the loan
4. The system automatically regenerates the repayment schedule
5. An audit comment is added to the document

## Testing

Unit tests have been created to verify:
- Correct calculation for both interest methods
- Proper schedule generation
- Dynamic updates when terms change
- Audit logging functionality

## Future Enhancements

1. Support for different repayment frequencies (weekly, bi-weekly, etc.)
2. Advanced penalty calculations for overdue payments
3. Integration with automated payment processing
4. Enhanced reporting on repayment performance