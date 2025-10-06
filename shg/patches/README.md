# ERPNext SHG App - Posting Date Field Fix

This patch fixes the `pymysql.err.OperationalError: (1054, "Unknown column 'posting_date' in 'SELECT'")` error by adding a `posting_date` field to all transactional doctypes in the SHG app.

## Changes Made

1. **Added `posting_date` field to the following doctypes:**
   - SHG Loan
   - SHG Contribution
   - SHG Loan Repayment

2. **Field specifications:**
   - Field Label: **Posting Date**
   - Fieldname: `posting_date`
   - Fieldtype: **Date**
   - Default: `Today`
   - Mandatory: Yes
   - Position: Inserted just after the `member` field

3. **Created patch scripts:**
   - `add_posting_date_field.py` - Adds the field via Custom Field if not already present
   - `update_date_filters.py` - Documentation for updating code references
   - `reload_and_migrate.sh` - Commands to reload doctypes and run migrations

## Implementation Steps

1. Run the patch to add the posting_date field:
   ```bash
   bench --site erpmain execute shg.patches.add_posting_date_field.execute
   ```

2. Reload the doctypes:
   ```bash
   bench --site erpmain reload-doc shg doctype shg_loan
   bench --site erpmain reload-doc shg doctype shg_contribution
   bench --site erpmain reload-doc shg doctype shg_loan_repayment
   ```

3. Run migrations:
   ```bash
   bench --site erpmain migrate
   ```

4. Clear cache:
   ```bash
   bench --site erpmain clear-cache
   ```

5. Update your code to use posting_date in filters:
   ```python
   # Replace this:
   filters={"date": ["between", [from_date, to_date]]}
   
   # With this:
   filters={"posting_date": ["between", [from_date, to_date]]}
   ```

## Verification

After applying the patch, you can verify the changes by:

1. Checking that the posting_date field appears in each doctype form
2. Running a simple query to ensure no more "Unknown column 'posting_date'" errors:
   ```python
   frappe.get_all("SHG Loan", filters={"posting_date": ["between", ["2025-01-01", "2025-12-31"]]})
   ```

## Notes

- The patch is designed to be safe and will not overwrite existing fields
- The posting_date field will automatically default to today's date when creating new records
- Existing records will need to have their posting_date populated manually or via a separate data migration script