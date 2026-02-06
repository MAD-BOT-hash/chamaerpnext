# SHG Multi Member Loan Repayment

This doctype allows processing loan repayments from multiple SHG members in a single entry, similar to the existing Multi-Member Payment functionality but specifically for loans.

## Features

1. **Multi-Loan Selection**: Select multiple members with active loans and outstanding balances
2. **Batch Repayment Processing**: Process repayments for all selected loans in one go
3. **Automatic Accounting**: Creates proper accounting entries with debit to bank/cash account and credit to member ledger accounts
4. **Loan Schedule Updates**: Automatically updates loan repayment schedules with actual payment dates and amounts
5. **Validation**: Prevents invalid payments and validates payment amounts against outstanding balances

## Fields

### Main Document
- **Repayment Date**: Date of the repayment
- **Company**: Company for which the repayment is being recorded
- **Payment Method**: Method of payment (Cash, Mobile Money, Bank Transfer, Cheque)
- **Account**: Bank/Cash account to debit
- **Total Payment Amount**: Total repayment amount (auto-calculated)
- **Total Selected Loans**: Number of loans with payments (auto-calculated)
- **Description**: Optional description

### Loans Table
- **Member ID**: ID of the member
- **Member Name**: Name of the member
- **Loan Number**: Loan document number
- **Loan Type**: Type of loan
- **Outstanding Balance**: Current outstanding balance (read-only)
- **Payment Amount**: Amount being repaid (editable)
- **Status**: Current loan status (read-only)

## Workflow

1. Create a new SHG Multi Member Loan Repayment
2. Click "Fetch Members with Active Loans" to get all members with outstanding loan balances
3. Enter payment amounts for members making repayments (leave blank for no payment)
4. Select payment method and account
5. Submit the document
6. System automatically:
   - Creates individual SHG Loan Repayment documents for each payment
   - Updates loan repayment schedules with actual payment data
   - Creates Payment Entry for accounting
   - Updates loan summary fields

## API Endpoints

### Get Members with Active Loans
```javascript
frappe.call({
    method: 'shg.shg.doctype.shg_multi_member_loan_repayment.shg_multi_member_loan_repayment.get_members_with_active_loans',
    args: {
        company: 'Company Name'  // Optional
    },
    callback: function(r) {
        // Handle response
    }
});
```

### Create Multi-Member Loan Repayment
```javascript
frappe.call({
    method: 'shg.shg.doctype.shg_multi_member_loan_repayment.shg_multi_member_loan_repayment.create_multi_member_loan_repayment',
    args: {
        repayment_data: {
            repayment_date: 'YYYY-MM-DD',
            company: 'Company Name',
            payment_method: 'Cash',
            account: 'Account Name',
            loans: [
                {
                    member: 'Member ID',
                    member_name: 'Member Name',
                    loan: 'Loan Number',
                    loan_type: 'Loan Type',
                    outstanding_balance: 5000,
                    payment_amount: 2000
                }
                // ... more loans
            ]
        }
    },
    callback: function(r) {
        // Handle response
    }
});
```

## Validation Rules

- Payment amount must be greater than zero
- Payment amount cannot exceed outstanding balance
- At least one loan must have a payment amount greater than zero
- Members with zero payment amounts are ignored
- Payment method and account must be selected

## Permissions

- **SHG Admin**: Full access
- **SHG Treasurer**: Full access
- **System Manager**: Full access

## Integration Points

- Links to SHG Loan and SHG Loan Repayment doctypes
- Creates Payment Entry documents for accounting
- Updates loan repayment schedules
- Integrates with member account mapping
- Follows company and account settings from SHG Settings