# SHG Multi Member Payment

This doctype allows processing payments for multiple SHG Contribution Invoices in a single entry.

## Features

1. **Multi-Invoice Selection**: Select multiple unpaid contribution invoices from different members
2. **Batch Payment Processing**: Process payments for all selected invoices in one go
3. **Automatic Accounting**: Creates proper accounting entries with debit to bank/cash account and credit to member ledger accounts
4. **Status Updates**: Automatically updates invoice and contribution statuses
5. **Validation**: Prevents duplicate payments and validates payment amounts

## Fields

### Main Document
- **Payment Date**: Date of the payment
- **Payment Method**: Method of payment (Cash, Mpesa, Bank Transfer, etc.)
- **Company**: Company for which the payment is being recorded
- **Account**: Bank/Cash account to debit
- **Total Amount**: Total payment amount
- **Description**: Optional description

### Invoices Table
- **Invoice**: Link to SHG Contribution Invoice
- **Member**: Member associated with the invoice
- **Member Name**: Name of the member
- **Contribution Type**: Type of contribution
- **Invoice Date**: Date of the invoice
- **Due Date**: Due date of the invoice
- **Outstanding Amount**: Amount still owed on the invoice
- **Payment Amount**: Amount being paid (editable)
- **Status**: Current status of the invoice

## Workflow

1. Create a new SHG Multi Member Payment
2. Select unpaid invoices using the "Get Unpaid Invoices" button
3. Review and adjust payment amounts if needed
4. Select payment method and account
5. Submit the document
6. System automatically:
   - Creates Payment Entry documents for each invoice
   - Updates invoice statuses
   - Updates linked contribution statuses
   - Posts accounting entries

## API Endpoints

### Get Unpaid Invoices
```
frappe.call({
    method: 'shg.shg.doctype.shg_multi_member_payment.shg_multi_member_payment.get_unpaid_invoices',
    callback: function(r) {
        // Handle response
    }
});
```

### Create Multi-Member Payment
```
frappe.call({
    method: 'shg.shg.api.create_multi_member_payment',
    args: {
        invoice_data: [...],
        payment_date: 'YYYY-MM-DD',
        payment_method: 'Cash',
        account: 'Account Name',
        company: 'Company Name',
        description: 'Optional description'
    },
    callback: function(r) {
        // Handle response
    }
});
```

## Permissions

- **SHG Admin**: Full access
- **SHG Treasurer**: Full access

## Reports

- **SHG Multi Member Payment Summary**: Shows payment summaries with filters

## Dashboard

The workspace includes:
- Payment trend charts
- Daily payment counts and amounts
- Quick links to related documents