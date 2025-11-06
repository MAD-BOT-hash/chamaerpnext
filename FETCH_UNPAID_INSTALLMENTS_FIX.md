# Fetch Unpaid Installments Fix

## Overview
This fix addresses the issue where the "Fetch Unpaid Installments" button in the SHG Loan Repayment form was not properly displaying data in the child table. The root cause was that the client-side JavaScript was not properly handling the data returned from the server and the child table was missing required fields.

## Changes Made

### 1. Updated SHG Repayment Installment Adjustment Doctype
**File**: `shg/shg/doctype/shg_repayment_installment_adjustment/shg_repayment_installment_adjustment.json`

**Changes**:
- Added `principal_amount` field (Currency, read-only)
- Added `interest_amount` field (Currency, read-only)
- Kept existing fields: `installment_no`, `due_date`, `total_due`, `unpaid_balance`, `amount_to_repay`, `status`, `schedule_row_id`

### 2. Updated SHG Loan Repayment Python Method
**File**: `shg/shg/doctype/shg_loan_repayment/shg_loan_repayment.py`

**Changes**:
- Modified `get_unpaid_installments()` method to include `principal_component` and `interest_component` fields from the repayment schedule
- Updated the method to populate `principal_amount` and `interest_amount` fields in the child table

### 3. Updated SHG Loan Repayment JavaScript
**File**: `shg/shg/doctype/shg_loan_repayment/shg_loan_repayment.js`

**Changes**:
- Ensured proper refresh of the `installment_adjustment` field after fetching data
- Simplified the callback to directly refresh the field instead of relying on the server method to return data

### 4. Created Database Migration Patch
**File**: `shg/shg/patches/update_repayment_installment_adjustment_fields.py`

**Purpose**:
- Updates the database schema to include the new fields
- Reloads the doctypes to ensure proper field mapping

## Root Cause Analysis

The issue was caused by two main problems:

1. **Missing Fields**: The SHG Repayment Installment Adjustment doctype was missing the `principal_amount` and `interest_amount` fields that the client script was expecting.

2. **Improper Data Handling**: The client script was not properly refreshing the child table field after receiving data from the server.

## Solution Implementation

### Server-Side Changes
The `get_unpaid_installments()` method was updated to:
1. Fetch additional fields from the repayment schedule: `principal_component` and `interest_component`
2. Map these fields to the child table fields: `principal_amount` and `interest_amount`
3. Return the populated child table data

### Client-Side Changes
The JavaScript was updated to:
1. Properly refresh the `installment_adjustment` field after the server call
2. Ensure the UI updates correctly by calling `frm.refresh_field('installment_adjustment')`

## Testing
Created test cases in `tests/test_fetch_unpaid_installments.py` to verify:
- Fetching unpaid installments populates the child table correctly
- All required fields are populated in each row
- The client script properly handles the data

## Migration
The patch `update_repayment_installment_adjustment_fields` will be automatically executed during the next migration to update the database schema.