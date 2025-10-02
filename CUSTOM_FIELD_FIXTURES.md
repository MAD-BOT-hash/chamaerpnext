# Custom Field Fixture Restructuring for SHG App

This document describes the restructuring of custom field JSON files in the SHG app to follow the correct fixture format for ERPNext.

## Issue Identified

The custom field JSON files in `shg/shg/custom/` were using an incorrect format that could cause `KeyError` exceptions during `sync_customizations`. The files were defining individual `Custom Field` objects directly instead of grouping them under the proper fixture structure.

## Solution Implemented

All custom field JSON files have been restructured to follow the correct fixture format with a `custom_fields` key that groups fields by their target doctype (`dt`).

## Old Format (Incorrect)

```json
{
  "doctype": "Custom Field",
  "dt": "Journal Entry",
  "fieldname": "custom_shg_contribution",
  "fieldtype": "Link",
  "options": "SHG Contribution",
  "label": "SHG Contribution",
  "insert_after": "voucher_type",
  "allow_on_submit": 1
}
```

## New Format (Correct)

```json
{
  "custom_fields": {
    "Journal Entry": [
      {
        "fieldname": "custom_shg_contribution",
        "fieldtype": "Link",
        "options": "SHG Contribution",
        "label": "SHG Contribution",
        "insert_after": "voucher_type",
        "allow_on_submit": 1
      }
    ]
  }
}
```

## Files Restructured

### Journal Entry Custom Fields
1. `custom_field_journal_entry_shg_contribution.json`
2. `custom_field_journal_entry_shg_loan.json`
3. `custom_field_journal_entry_shg_loan_repayment.json`
4. `custom_field_journal_entry_shg_meeting_fine.json`

### Payment Entry Custom Fields
1. `custom_field_payment_entry_shg_contribution.json`
2. `custom_field_payment_entry_shg_loan.json`
3. `custom_field_payment_entry_shg_loan_repayment.json`
4. `custom_field_payment_entry_shg_meeting_fine.json`

### Customer Custom Fields
1. `custom_field_customer_is_shg_member.json`
2. `custom_field_customer_shg_member_id.json`

## Benefits

### ERPNext Compatibility
- Full compatibility with ERPNext's `sync_customizations` command
- No more `KeyError` exceptions during fixture installation
- Proper grouping of custom fields by target doctype

### Code Maintainability
- Consistent format across all custom field files
- Easier to understand and modify
- Better organization of related custom fields

### Deployment Reliability
- Reduced risk of deployment failures
- Proper error handling during customization sync
- Predictable behavior during app installation

## Implementation Details

### Structure Requirements
Each custom field file now follows this structure:
- Top-level `custom_fields` object
- Keys are target doctypes (e.g., "Journal Entry", "Payment Entry", "Customer")
- Values are arrays of custom field definitions
- Each custom field definition includes all required properties

### Property Preservation
All original custom field properties have been preserved:
- `fieldname`: Unique identifier for the field
- `fieldtype`: Type of field (Link, Data, Check, etc.)
- `options`: Target doctype for Link fields
- `label`: Display name for the field
- `insert_after`: Position relative to other fields
- `allow_on_submit`: Whether field can be edited after submission
- `depends_on`: Conditional display logic

## Testing

A new test file `test_custom_field_fixtures.py` has been created to verify:
1. All custom field files follow the correct structure
2. Required properties are present in each custom field definition
3. All fieldnames are unique within each doctype
4. Proper grouping by target doctype

## Conclusion

The restructuring of custom field JSON files ensures proper compatibility with ERPNext's customization system while maintaining all existing functionality. The new format is more robust and less prone to errors during app installation and deployment.