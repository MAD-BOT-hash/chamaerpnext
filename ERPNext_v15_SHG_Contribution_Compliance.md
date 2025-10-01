# ERPNext v15 SHG Contribution Compliance

## Overview
This document explains the changes made to ensure SHG Contributions are fully compatible with ERPNext v15 GL validation requirements.

## Problem
ERPNext v15 restricts valid `reference_type` values in GL Entries, Journal Entries, and Payment Entries. Using custom reference types like "SHG Contribution" causes validation errors:
```
Row #1: Reference Type cannot be "SHG Contribution"
```

## Solution
Refactored the SHG app to use ERPNext-native approaches with proper traceability:

### 1. Preferred Approach: Payment Entry Flow
For each SHG Contribution, auto-create a Payment Entry of type "Receive":
- Dr Cash/Bank
- Cr Contributions Income
- Supports reconciliation, party tracking, and reporting natively

### 2. Fallback Approach: Journal Entry Flow
If Payment Entry is not possible, create a Journal Entry:
- Dr Cash/Bank
- Cr Contributions Income
- Uses standard "Journal Entry" reference_type or leaves it blank

### 3. Traceability Without Invalid Reference Types
Added custom fields to maintain traceability:
- `custom_shg_contribution` field on Payment Entry
- `custom_shg_contribution` field on Journal Entry

## Implementation Details

### Files Modified:
1. [shg_settings.json](file:///c%3A/Users/user/Downloads/shg-erpnext/shg/shg/doctype/shg_settings/shg_settings.json) - Changed default contribution posting method to "Payment Entry"
2. [shg_contribution.py](file:///c%3A/Users/user/Downloads/shg-erpnext/shg/shg/doctype/shg_contribution/shg_contribution.py) - Updated accounting entry creation methods
3. [hooks.py](file:///c%3A/Users/user/Downloads/shg-erpnext/shg/hooks.py) - Added custom field definitions
4. [custom_field.json](file:///c%3A/Users/user/Downloads/shg-erpnext/shg/shg/custom/custom_field.json) - Custom field definitions

### Key Changes:

#### Payment Entry Creation:
```python
pe = frappe.new_doc("Payment Entry")
pe.payment_type = "Receive"
pe.party_type = "Customer"
pe.party = member_customer
pe.company = company
pe.paid_from = "Cash - PFG"  # or Bank
pe.paid_to = "Contributions Income - PFG"
pe.paid_amount = self.amount
pe.received_amount = self.amount
pe.custom_shg_contribution = self.name  # Custom field for traceability
pe.insert(ignore_permissions=True)
pe.submit()
```

#### Journal Entry Creation:
```python
je = frappe.new_doc("Journal Entry")
je.voucher_type = "Bank Entry"
je.company = company
je.posting_date = self.date
je.custom_shg_contribution = self.name  # Custom field for traceability
je.append("accounts", {
    "account": self.get_cash_account(company),
    "debit_in_account_currency": self.amount
})
je.append("accounts", {
    "account": self.get_contribution_account(company),
    "credit_in_account_currency": self.amount,
    "party_type": "Customer",
    "party": member_customer
})
je.insert(ignore_permissions=True)
je.submit()
```

### Validation Updates:
Enhanced validation to check custom field linking instead of reference_type/reference_name:
```python
# Verify custom field linking
if not je.custom_shg_contribution or je.custom_shg_contribution != self.name:
    frappe.throw(_("Journal Entry must be linked to this SHG Contribution."))
```

## Benefits:
1. ✅ Full ERPNext v15 compatibility - no more reference type errors
2. ✅ Native ERPNext functionality - Payment Entry and Journal Entry approaches
3. ✅ Proper traceability - custom fields link entries back to contributions
4. ✅ Member-Customer linking maintained
5. ✅ Proper GL postings with correct account flows
6. ✅ Support for reconciliation and reporting

## Testing:
Created comprehensive unit tests in [test_shg_contribution_erpnext15_compliance.py](file:///c%3A/Users/user/Downloads/shg-erpnext/tests/test_shg_contribution_erpnext15_compliance.py) that verify:
- Payment Entry creation with correct account flows
- Journal Entry creation without invalid reference types
- Custom field linking for traceability
- ERPNext v15 compatibility validation

## Conclusion:
The SHG app now fully complies with ERPNext v15 GL validation requirements while maintaining all functionality and traceability.