# SHG Payment Entry

This doctype is used to record payments received from SHG members for their contribution invoices.

## Features

- Record payments for multiple contribution invoices in a single entry
- Automatically update invoice statuses (Paid/Partially Paid)
- Update member financial summaries
- Send automatic payment receipts via email
- Filter invoices by member
- Support for multiple payment methods

## Fields

### Main Fields
- **Member**: Link to the SHG Member making the payment
- **Payment Date**: Date when the payment was received
- **Payment Method**: Method of payment (Cash, Bank Transfer, Mobile Money, Cheque)
- **Total Amount**: Total amount being paid (calculated automatically)
- **Reference Number**: Optional reference number for the payment
- **Description**: Optional description of the payment

### Accounting Fields
- **Debit Account**: Account to debit (typically cash/bank account)
- **Credit Account**: Account to credit (typically receivable account)

### Payment Entries
- **Invoice Type**: Type of invoice (currently only SHG Contribution Invoice)
- **Invoice**: Link to the specific invoice
- **Invoice Date**: Date of the invoice
- **Outstanding Amount**: Current outstanding amount on the invoice
- **Amount**: Amount being paid for this invoice
- **Description**: Description of the invoice

## Workflow

1. Create a new SHG Payment Entry
2. Select the member making the payment
3. Click "Get Unpaid Invoices" to fetch all unpaid invoices for the member
4. Adjust payment amounts as needed
5. Select payment method and accounts
6. Submit the payment entry
7. System automatically:
   - Updates invoice statuses
   - Updates member financial summaries
   - Sends payment receipt (if enabled in settings)

## Settings

Payment defaults can be configured in SHG Settings:
- Default Payment Method
- Default Debit Account
- Default Credit Account
- Auto Email Receipt