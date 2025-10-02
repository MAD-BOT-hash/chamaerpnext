# Voucher Type Fixes for SHG App

This document describes the fixes implemented to resolve voucher type issues in the SHG (Self Help Group) app for ERPNext.

## Issues Identified and Fixed

### 1. Custom Voucher Type Problem

**Issue**: SHG doctypes were not using valid ERPNext voucher types, causing compatibility issues.

**Fix**: Implemented a mapping of valid voucher types for each SHG doctype:

```python
valid_voucher_type = {
    "SHG Contribution": "Bank Entry",
    "SHG Loan": "Journal Entry",
    "SHG Loan Repayment": "Cash Entry",
    "SHG Meeting Fine": "Journal Entry"
}
je.voucher_type = valid_voucher_type.get(doc_type, "Journal Entry")
```

**Changes Made**:
- Updated JSON schema files to use correct default voucher types
- Modified gl_utils.py to use the valid voucher type mapping
- Ensured all Journal Entries use appropriate voucher types

### 2. Payment Entry Direction Reversed

**Issue**: Payment Entry direction was incorrect for contributions. Members bring cash to the group, but the accounting entries were reversed.

**Fix**: Corrected the payment direction in Payment Entries:

```python
# For Contributions:
pe.paid_from = get_or_create_member_account(member, company)  # Member's account
pe.paid_to = _get_cash_account(doc, company)                 # Cash/Bank account
```

**Changes Made**:
- Updated `_create_payment_entry` function in gl_utils.py
- Corrected payment direction for all SHG transaction types
- Ensured proper accounting flow: Member pays from their account to group's cash/bank

### 3. Member Party Type Mismatch

**Issue**: Party Type was set to "Customer" but should be "SHG Member" to match the actual party type.

**Fix**: 
1. Registered "SHG Member" as a valid party type in ERPNext
2. Updated all accounting entries to use "SHG Member" as party type

**Changes Made**:
- Added `register_party_types()` function in install.py
- Updated gl_utils.py to use "SHG Member" as party_type
- Ensured proper party linking in all GL entries

### 4. _update_document_with_entry Hook Issue

**Issue**: Using `doc.save()` in `_update_document_with_entry` was re-triggering on_update hooks and causing loops.

**Fix**: Changed to use `doc.db_set()` with `update_modified=False` to avoid triggering hooks:

```python
def _update_document_with_entry(doc, entry_field, entry_name):
    """Update document with created entry reference without triggering hooks"""
    doc.db_set({
        entry_field: entry_name,
        "posted_to_gl": 1,
        "posted_on": frappe.utils.now()
    }, update_modified=False)
```

**Changes Made**:
- Updated `_update_document_with_entry` function in gl_utils.py
- Added `update_modified=False` parameter to prevent hook triggering
- Ensured document updates don't cause recursive calls

### 5. Bank Entry Reference Fields Missing

**Issue**: ERPNext requires Bank Entry and Cash Entry voucher types to have reference_no and reference_date fields populated.

**Fix**: Added reference fields for Bank Entry and Cash Entry voucher types with proper fallback handling:

```python
# Add reference_no and reference_date for Bank and Cash entries
if je.voucher_type in ["Bank Entry", "Cash Entry"]:
    # Ensure we have reference values, fallback to doc name and today if not set
    je.reference_no = reference_no or doc.name
    je.reference_date = reference_date or today()
```

**Changes Made**:
- Updated `_create_journal_entry` function in gl_utils.py
- Added reference_no and reference_date for Bank Entry (Contributions)
- Added reference_no and reference_date for Cash Entry (Loan Repayments)
- Used document name as reference_no and document date as reference_date
- Added fallback handling to prevent undefined variable errors

## Detailed Changes by File

### shg/shg/utils/gl_utils.py
- **Voucher Type Mapping**: Added valid voucher type mapping for all SHG doctypes
- **Party Type Correction**: Changed from "Customer" to "SHG Member" for all entries
- **Payment Direction Fix**: Corrected paid_from/paid_to directions for all transactions
- **Hook Prevention**: Changed `doc.save()` to `doc.db_set()` with `update_modified=False`
- **Reference Fields**: Added reference_no and reference_date for Bank Entry and Cash Entry voucher types
- **Fallback Handling**: Added proper fallback for reference fields to prevent undefined variable errors

### shg/shg/doctype/*/ *.json (All 4 doctypes)
- **Default Voucher Types**: Updated default values to match valid ERPNext voucher types
- **SHG Contribution**: Changed from "Contribution Entry" to "Bank Entry"
- **SHG Loan**: Changed from "Loan Entry" to "Journal Entry"
- **SHG Loan Repayment**: Changed from "Repayment Entry" to "Cash Entry"
- **SHG Meeting Fine**: Changed from "Fine Entry" to "Journal Entry"

### shg/install.py
- **Party Type Registration**: Added function to register "SHG Member" as a valid party type
- **Installation Hook**: Added call to register party types during installation

## Testing

New test files were created to verify all fixes:

1. **test_voucher_type_fixes.py**: Tests voucher types, payment directions, party types, and hook prevention
2. **test_bank_entry_references.py**: Tests that Bank Entry and Cash Entry have required reference fields

## Benefits

### ERPNext Compatibility
- Full compatibility with ERPNext's voucher type system
- No more invalid reference type errors
- Proper integration with ERPNext's accounting workflows

### Correct Accounting Flow
- Members pay from their accounts to group's cash/bank accounts
- Proper party type usage for accurate reporting
- Correct voucher types for appropriate transaction classification

### System Stability
- Prevention of recursive hook calls
- More efficient document updates
- Reduced risk of data corruption

### Compliance
- Adherence to ERPNext's party type system
- Proper accounting standards compliance
- Audit-ready transaction records

## Implementation Notes

### Party Type Registration
The SHG Member party type is registered during app installation:
```python
{
    "doctype": "Party Type",
    "party_type": "SHG Member",
    "account_type": "Receivable"
}
```

### Voucher Type Mapping
All Journal Entries now use appropriate voucher types:
- **Contributions**: Bank Entry
- **Loan Disbursements**: Journal Entry
- **Loan Repayments**: Cash Entry
- **Meeting Fines**: Journal Entry

### Payment Flow
Corrected payment flow for all transactions:
```
Member Account (SHG Member) → Cash/Bank Account
```

### Reference Fields
Bank Entry and Cash Entry voucher types now include required reference fields:
- **reference_no**: Set to document name (with fallback to document name)
- **reference_date**: Set to document date (with fallback to today)

## Conclusion

These fixes ensure the SHG app is fully compatible with ERPNext's voucher type system while maintaining proper accounting practices. The changes improve system stability, ensure correct financial reporting, and provide a better user experience.