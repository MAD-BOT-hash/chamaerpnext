# SHG Contribution Status Synchronization

## Overview

This feature ensures that SHG Contribution documents stay in sync with their related SHG Contribution Invoices. When an invoice is marked as "Paid" and "Closed", the corresponding contribution is automatically marked as "Paid".

## How It Works

### 1. Automatic Status Updates

When a SHG Contribution Invoice is:
- Marked as `status = "Paid"`
- Marked as `is_closed = 1`

The system automatically:
- Finds the linked SHG Contribution (using the `invoice_reference` field)
- Updates the contribution's `status` field to "Paid"
- Updates the contribution's `posted_on` timestamp

### 2. Reversal on Cancellation

When a SHG Contribution Invoice is:
- Reopened (status changed from "Paid" or is_closed = 0)

The system automatically:
- Finds the linked SHG Contribution
- Updates the contribution's `status` field back to "Unpaid"

### 3. Integration Points

The synchronization happens in multiple places:

1. **SHG Payment Entry Submission** - When a payment is processed, all linked invoices are marked as Paid and Closed, which triggers contribution status updates.

2. **SHG Payment Entry Cancellation** - When a payment is cancelled, all linked invoices are reopened, which triggers contribution status reversals.

3. **Direct Invoice Updates** - When an invoice status is manually changed, the linked contribution is updated accordingly.

## Implementation Details

### Key Methods

- `mark_linked_contribution_as_paid()` - Marks the linked contribution as Paid when invoice is Paid and Closed
- `reopen_linked_contribution()` - Reopens the linked contribution when invoice is reopened
- `update_linked_invoices()` - In SHG Payment Entry, updates invoice status and calls contribution methods
- `reopen_linked_invoices()` - In SHG Payment Entry, reopens invoices and calls contribution methods

### Safety Features

- Checks for document existence before accessing
- Uses `db_set()` with `update_modified=False` to avoid unnecessary timestamp changes
- Handles cases where the `is_closed` field might not exist
- Comprehensive error logging with `frappe.log_error()`

## Field Relationships

- SHG Contribution Invoice has an `is_closed` field (added via custom field)
- SHG Contribution has an `invoice_reference` field linking to the invoice
- Both documents have synchronized `status` fields

## Testing

The feature includes unit tests in `test_contribution_invoice_status_sync.py` that verify:
- Invoice submission creates linked contributions
- Paid and Closed invoices mark contributions as Paid
- Reopened invoices revert contribution status to Unpaid