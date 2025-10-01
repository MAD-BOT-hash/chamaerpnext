# ERPNext v15 Reference Type Rules for Financial Documents

## Overview

ERPNext v15 enforces strict validation rules for the `reference_type` field in financial documents like Journal Entries, Payment Entries, and GL Entries. These rules ensure data integrity and prevent invalid references that could cause accounting inconsistencies.

## Reference Type Validation Rules

### 1. GL Entry Reference Types

In ERPNext v15, GL Entries can only have the following valid reference types:
- Empty string (no reference)
- "Sales Invoice"
- "Purchase Invoice"
- "Journal Entry"
- "Sales Order"
- "Purchase Order"
- "Expense Claim"
- "Asset"
- "Loan"
- "Payroll Entry"
- "Employee Advance"
- "Exchange Rate Revaluation"
- "Invoice Discounting"
- "Fees"
- "Full and Final Statement"
- "Payment Entry"
- "Loan Interest Accrual"

### 2. Journal Entry Account Reference Types

For Journal Entry accounts, the same validation rules apply. Custom document types like "SHG Contribution" or "SHG Loan" are not allowed as reference types.

### 3. Payment Entry Reference Types

Payment Entries follow the same validation rules as other financial documents.

## Validation Implementation

The validation is implemented in the ERPNext core code and cannot be modified without changing the core ERPNext files, which is not recommended.

## Recommended Approach

To comply with ERPNext v15 reference type validation while maintaining traceability:

1. Use standard ERPNext document types as reference types (e.g., "Journal Entry", "Payment Entry")
2. Store the actual SHG document reference in the `reference_name` field
3. Create a link field on SHG documents to store the created Journal Entry or Payment Entry
4. Use `self.doctype` as the reference_type when creating Journal Entries from custom documents

## Best Practices

1. Always use standard ERPNext document types for reference_type
2. Maintain traceability through link fields rather than custom reference types
3. Implement idempotent posting operations to prevent duplicate entries
4. Use proper error handling and logging for failed postings
5. Ensure Party Type is correctly set to "Customer" or "Supplier" when applicable

## Example Implementation

```python
# Correct approach
je = frappe.get_doc({
    "doctype": "Journal Entry",
    "accounts": [
        {
            "account": debit_account,
            "debit_in_account_currency": amount,
            "reference_type": "Journal Entry",  # Standard ERPNext type
            "reference_name": self.name         # SHG document name
        },
        {
            "account": credit_account,
            "credit_in_account_currency": amount,
            "reference_type": "Journal Entry",  # Standard ERPNext type
            "reference_name": self.name         # SHG document name
        }
    ]
})
```

This approach ensures compliance with ERPNext v15 validation rules while maintaining full traceability between SHG documents and their corresponding financial entries.