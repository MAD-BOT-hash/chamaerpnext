# SHG Member Fields - Editable on Submit Patch

This patch enables specific fields in the SHG Member DocType to be editable even after the document is submitted.

## Fields Enabled for Editing on Submit

1. `membership_date`
2. `id_number`
3. `phone_number`
4. `email` (corresponds to email_address in the objective)
5. `member_id`

## Implementation Details

The patch uses Property Setters to modify field properties without changing the core doctype structure. This approach is safer and more maintainable than directly modifying the JSON files.

For the `member_id` field, which was previously marked as `read_only`, the patch also removes the read-only restriction to allow editing on submit.

## Usage

To apply this patch, run:

```bash
bench --site erpmain execute shg.patches.custom.allow_edit_member_fields.execute
```

After running the patch, clear the cache:

```bash
bench --site erpmain clear-cache
```

## Verification

After applying the patch, you can verify the changes by:

1. Opening an existing submitted SHG Member record
2. Trying to edit the specified fields
3. Saving the changes

The fields should now be editable even for submitted documents.

## Notes

- This patch is designed to be safe and will not overwrite existing configurations
- Property Setters are used to ensure changes persist through updates
- The patch handles both standard and custom fields appropriately