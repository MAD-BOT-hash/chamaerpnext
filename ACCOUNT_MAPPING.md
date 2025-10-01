# SHG Account Mapping Documentation

This document explains how the account mapping functionality works in the SHG ERPNext application to avoid the `AttributeError: 'SHGContribution' object has no attribute 'posted_to_gl'` error.

## Problem Solved

The original error occurred because:
1. The `posted_to_gl` field was removed from the doctype definitions
2. But JavaScript files were still referencing this field
3. This caused runtime errors when trying to access non-existent fields

## Solution Implemented

We implemented a flexible account mapping system using child tables that allows:

1. **Dynamic Account Configuration**: Each contribution or loan can have custom account mappings
2. **No Hardcoded Field References**: Eliminates dependency on specific field names
3. **Flexible Accounting**: Different accounts can be used for different transactions

## Components

### 1. SHG Contribution Account (Child Table)

Fields:
- `account_type`: Select from Member Account, Contribution Account, Bank Account, Cash Account
- `account`: Link to the actual Account doctype
- `percentage`: Percentage of the amount to allocate
- `amount`: Fixed amount to allocate

### 2. SHG Loan Account (Child Table)

Fields:
- `account_type`: Select from Member Account, Loan Account, Interest Income Account, Penalty Income Account, Bank Account, Cash Account
- `account`: Link to the actual Account doctype
- `percentage`: Percentage of the amount to allocate
- `amount`: Fixed amount to allocate

### 3. Parent Doctypes Integration

Both `SHG Contribution` and `SHG Loan` doctypes now include:
- An `account_mapping` field of type Table
- Logic in Python files to process these mappings when creating Journal Entries

## How It Works

### For Contributions:

1. When a contribution is submitted, the system checks for account mappings
2. If mappings exist, it uses those accounts for the Journal Entry
3. If no mappings exist, it falls back to default accounts from SHG Settings

### For Loans:

1. When a loan is disbursed, the system checks for account mappings
2. If mappings exist, it uses those accounts for the disbursement Journal Entry
3. If no mappings exist, it falls back to default accounts

## Benefits

1. **No More AttributeError**: Eliminates references to non-existent fields
2. **Flexible Configuration**: Each transaction can have custom account mappings
3. **Backward Compatibility**: Falls back to default behavior when no mappings are defined
4. **Extensible**: Easy to add new account types without code changes

## Usage Examples

### Creating a Contribution with Account Mapping:

```javascript
// In JavaScript
frm.doc.account_mapping = [
    {
        account_type: "Member Account",
        account: "Member Receivable - TSC",
        percentage: 100,
        amount: 1000
    },
    {
        account_type: "Contribution Account",
        account: "SHG Contributions - TSC",
        percentage: 100,
        amount: 1000
    }
];
```

### In Python (Backend):

```python
# In shg_contribution.py
if self.account_mapping:
    for mapping in self.account_mapping:
        if mapping.account_type == "Bank Account":
            debit_account = mapping.account
        elif mapping.account_type == "Member Account":
            credit_account = mapping.account
```

## Testing

Run the test script to verify functionality:

```bash
python test_account_mapping.py
```

This will:
1. Create test accounts
2. Create a contribution with account mapping
3. Create a loan with account mapping
4. Verify Journal Entries are created correctly

## Error Prevention

The new system prevents the original error by:
1. Removing all references to `posted_to_gl` field
2. Using `journal_entry` field instead to track accounting status
3. Providing clear dashboard indicators in the UI
4. Using robust field existence checks in JavaScript