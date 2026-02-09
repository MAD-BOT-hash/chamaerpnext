# SHG Multi Member Loan Repayment

## Overview
This doctype enables bulk processing of loan repayments for multiple SHG members in a single transaction.

## Fields

### Parent Document Fields
- posting_date: 'YYYY-MM-DD' (required)
- payment_mode: 'Cash/Bank Transfer/Cheque/Mobile Money' (required)
- payment_account: 'Account Link' (required)
- company: 'Company Link' (required)
- batch_number: 'Reference/Batch Number' (required)
- description: 'Text field for additional information'
- total_repayment_amount: 'Currency field (auto-calculated)'
- total_selected_loans: 'Integer field (auto-calculated)'

### Child Table Fields (SHG Multi Member Loan Repayment Item)
- member: 'SHG Member Link' (required)
- member_name: 'Member Name' (auto-fetched, read-only)
- loan: 'SHG Loan Link' (required)
- loan_type: 'Loan Type' (auto-fetched, read-only)
- installment_due_date: 'Date' (auto-fetched, read-only)
- outstanding_amount: 'Currency' (auto-fetched, read-only, required)
- repayment_amount: 'Currency' (user editable, required)
- status: 'Data field' (system managed)

## Workflow
1. User creates new SHG Multi Member Loan Repayment document
2. Selects posting date, payment mode, payment account, and company
3. Enters batch number and optional description
4. Clicks "Get Active Loans" to populate child table with active loans
5. Reviews and adjusts repayment amounts as needed
6. Submits document to process all loan repayments

## Validation Rules
- All parent-level mandatory fields must be filled
- Each child table row must have all required fields
- Repayment amount cannot exceed outstanding amount
- No duplicate loans allowed in same batch
- Only active members and loans in "Disbursed" or "Partially Paid" status can be processed

## API Methods
- fetch_active_loans(member=None): Get active loans for member or all members
- recalculate_totals(): Recalculate total amounts and loan count
