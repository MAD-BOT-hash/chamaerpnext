# SHG Canonical Posting Mapping

This document provides the recommended canonical mapping between SHG document types and ERPNext posting objects (Journal Entry or Payment Entry).

## Overview

The new SHG implementation ensures compliance with ERPNext v15 reference type validation rules by using standard ERPNext document types as reference types while maintaining traceability through link fields.

## Canonical Mapping

### 1. SHG Contribution

**Recommended Posting Object:** Journal Entry (default) or Payment Entry

**Mapping Logic:**
- When `contribution_posting_method` in SHG Settings is "Journal Entry" (default):
  - Creates a Journal Entry with:
    - Debit: Bank/Cash Account
    - Credit: Member Account (with party_type="Customer")
- When `contribution_posting_method` is "Payment Entry":
  - Creates a Payment Entry (Receive) with:
    - Paid From: Bank/Cash Account
    - Paid To: Member Account
    - Party Type: Customer
    - Party: Linked Customer

**Use Cases:**
- **Journal Entry**: For record-only contributions or when using generic posting
- **Payment Entry**: For actual bank/C2B receipts

### 2. SHG Loan Disbursement

**Recommended Posting Object:** Journal Entry (default) or Payment Entry

**Mapping Logic:**
- When `loan_disbursement_posting_method` in SHG Settings is "Journal Entry" (default):
  - Creates a Journal Entry with:
    - Debit: Member Account (with party_type="Customer")
    - Credit: Loan Account
- When `loan_disbursement_posting_method` is "Payment Entry":
  - Creates a Payment Entry (Pay) with:
    - Paid From: Loan Account
    - Paid To: Bank Account
    - Party Type: Customer
    - Party: Linked Customer

**Use Cases:**
- **Journal Entry**: For internal loan records or when using generic posting
- **Payment Entry**: For actual bank payouts via M-Pesa or other payment methods

### 3. SHG Loan Repayment

**Recommended Posting Object:** Journal Entry (default) or Payment Entry

**Mapping Logic:**
- When `loan_repayment_posting_method` in SHG Settings is "Journal Entry" (default):
  - Creates a Journal Entry with:
    - Debit: Bank/Cash Account
    - Credit: Member Account (with party_type="Customer")
    - Credit: Interest Income Account (if applicable)
    - Credit: Penalty Income Account (if applicable)
- When `loan_repayment_posting_method` is "Payment Entry":
  - Creates a Payment Entry (Receive) with:
    - Paid From: Bank/Cash Account
    - Paid To: Member Account
    - Party Type: Customer
    - Party: Linked Customer

**Use Cases:**
- **Journal Entry**: For detailed accounting with multiple account allocations
- **Payment Entry**: For simple receipt tracking

### 4. SHG Meeting Fine

**Recommended Posting Object:** Journal Entry (default)

**Mapping Logic:**
- Creates a Journal Entry with:
  - Debit: Member Account (with party_type="Customer")
  - Credit: Penalty Income Account

**Use Cases:**
- **Journal Entry**: For internal adjustments and fine recording

## Traceability

Each SHG document maintains one-to-one traceability with the created posting object:

- SHG Contribution → journal_entry (Link to Journal Entry) or payment_entry (Link to Payment Entry)
- SHG Loan → disbursement_journal_entry (Link to Journal Entry) or disbursement_payment_entry (Link to Payment Entry)
- SHG Loan Repayment → journal_entry (Link to Journal Entry) or payment_entry (Link to Payment Entry)
- SHG Meeting Fine → journal_entry (Link to Journal Entry) or payment_entry (Link to Payment Entry)

Additional fields track the posting status:
- posted_to_gl (Check): Indicates if the document has been posted to GL
- posted_on (Datetime): Timestamp when the document was posted to GL

## Benefits of This Approach

1. **ERPNext v15 Compliance**: Uses only valid reference types approved by ERPNext
2. **Traceability**: Maintains clear links between SHG documents and financial entries
3. **Flexibility**: Supports both Journal Entry and Payment Entry based on business needs
4. **Idempotency**: Prevents duplicate postings through the posted_to_gl flag
5. **Party Compliance**: Properly uses Customer/Supplier party types as required
6. **Admin Control**: Allows configuration through SHG Settings
7. **Migration Support**: Provides tools to detect and handle legacy entries

## Configuration in SHG Settings

Administrators can control the default posting method for each transaction type:

- **Contribution Posting Method**: Journal Entry (default) or Payment Entry
- **Loan Disbursement Posting Method**: Journal Entry (default) or Payment Entry
- **Loan Repayment Posting Method**: Journal Entry (default) or Payment Entry

## Error Handling

The implementation includes robust error handling:

1. **Validation**: Checks for required accounts and party details
2. **Idempotency**: Prevents duplicate postings
3. **Graceful Failures**: Logs errors and provides helpful error messages
4. **Rollback Support**: Properly cancels associated entries when SHG documents are cancelled

This canonical mapping ensures that all SHG financial transactions are properly recorded in ERPNext while maintaining full compliance with v15 validation rules.