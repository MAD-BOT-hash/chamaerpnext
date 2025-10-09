# Billable Contributions Features

This document describes the new billable contributions features added to the SHG ERPNext application.

## New Fields in SHG Contribution Type

The following fields have been added to the SHG Contribution Type doctype:

1. **Is Billable** (Check) - Marks the contribution as billable
2. **Billing Frequency** (Select) - Options: Monthly, Weekly, Quarterly, Annually, Bi monthly
3. **Due Day** (Int) - Day of month when payment becomes due (e.g., 5 means due every 5th)
4. **Grace Period** (Int) - Optional days before the invoice is marked overdue
5. **Auto Invoice** (Check) - If enabled, ERPNext automatically creates invoices for each active member
6. **Item Code** (Link) - Item to use for invoicing this contribution type

## Scheduled Tasks

The following scheduled tasks have been added:

1. **Daily Task**: `generate_billable_contribution_invoices` - Identifies contributions that are billable and due, then generates Sales Invoices for each active member
2. **Monthly Task**: `send_monthly_member_statements` - Automatically sends a monthly statement PDF to all members' emails at month-end

## Invoice Generation Logic

For each active SHG Member, the system creates a new Sales Invoice with:

- Customer = Member Name
- Posting Date = Due Date
- Item = Contribution Type
- Amount = Defined Contribution Amount
- Reference = Contribution Period (e.g., "October 2025 Contribution")

The invoice is submitted automatically.

## Email Notification

When an invoice is generated, an email is sent to the member:

- Subject: "Your [Month] SHG Contribution Invoice"
- Body: Contains member name, amount due, due date, and attached invoice PDF

## Automated Statements

The Member Statement Report has been enhanced with:

- Filtering by date range
- Filtering by transaction type (Contribution / Loan / Repayment / Fine)

## Dashboard Enhancement

The SHG Dashboard has been enhanced with:

- Pending Invoices section showing:
  - Total Due Amount
  - Overdue Invoices
  - Paid Contributions This Month
- Invoice Status Overview chart

## Implementation Details

The implementation includes:

1. Custom fields added to Sales Invoice doctype
2. New number cards for dashboard metrics
3. New dashboard chart for invoice status
4. Updated scheduler events in hooks.py
5. New patch file for database migrations