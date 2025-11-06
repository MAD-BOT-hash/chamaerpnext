# "Get Active Members" Button Fix for SHG Loan

## Problem
The "Get Active Members" button was missing from the SHG Loan form for group loans, making it difficult to quickly populate the loan_members child table with all active SHG members.

## Solution Implemented
Added the missing functionality to restore the "Get Active Members" button in the SHG Loan DocType.

## Code Changes

### 1. Backend Method (`shg/shg/doctype/shg_loan/shg_loan.py`)

Added a new whitelisted method `get_active_group_members()` that:
- Fetches all SHG members with `membership_status = "Active"`
- Returns member data with `member`, `member_name`, and default `allocated_amount = 0.0`

```python
@frappe.whitelist()
def get_active_group_members(self):
    """
    Get all active members for group loan population.
    
    Returns:
        list: List of active SHG members with name and member_name
    """
    active_members = frappe.get_all(
        "SHG Member", 
        filters={"membership_status": "Active"},
        fields=["name", "member_name"]
    )
    
    return [
        {
            "member": m.name,
            "member_name": m.member_name,
            "allocated_amount": 0.0
        }
        for m in active_members
    ]
```

### 2. Frontend Implementation (`shg/shg/doctype/shg_loan/shg_loan.js`)

Added the "Get Active Members" button that:
- Appears only for group loans (when `loan_members` table exists) and in draft status
- Calls the backend method to fetch active members
- Populates the `loan_members` child table
- Includes auto-sync functionality to update loan amount based on allocated amounts

```javascript
// Add "Get Active Members" button for group loans
if (frm.doc.docstatus === 0 && frm.doc.loan_members) {
    frm.add_custom_button(__("Get Active Members"), function() {
        frappe.call({
            method: "shg.shg.doctype.shg_loan.shg_loan.get_active_group_members",
            doc: frm.doc,
            callback: function(r) {
                if (r.message) {
                    // Clear existing loan members
                    frm.clear_table('loan_members');
                    
                    // Add active members to loan members table
                    r.message.forEach(function(member) {
                        var row = frm.add_child('loan_members');
                        row.member = member.member;
                        row.member_name = member.member_name;
                        row.allocated_amount = member.allocated_amount || 0.0;
                    });
                    
                    frm.refresh_field('loan_members');
                    frappe.msgprint(__('Loan members list populated with active members'));
                    
                    // Auto-sync allocated total with loan amount if needed
                    sync_allocated_total_with_loan_amount(frm);
                }
            }
        });
    }, __("Actions"));
}
```

### 3. Auto-Sync Feature

Added functionality to automatically sync the total allocated amount with the loan amount:
- When loan amount changes, it checks if it should be updated based on allocated amounts
- When members are added, it can update the loan amount to match the total allocations

### 4. Patch File

Created a patch file to ensure the changes are properly applied during migrations:
- `shg/shg/patches/add_get_active_members_functionality.py`

## Benefits
1. **Ease of Use**: One-click population of active members for group loans
2. **Accuracy**: Only includes members with "Active" status
3. **Efficiency**: Eliminates manual entry of each member
4. **Auto-Sync**: Automatically updates loan amount based on allocations
5. **User Experience**: Follows the same pattern as other doctypes like SHG Meeting

## Testing
Created test cases in `tests/test_get_active_members.py` to verify:
- Only active members are returned by the backend method
- Inactive members are excluded
- The loan_members child table is properly populated
- The data structure is correct

## How to Test the Fix
1. Create a new SHG Loan with a loan_members child table
2. Ensure you have both active and inactive SHG members
3. Click the "Get Active Members" button in the Actions section
4. Verify that only active members are added to the loan_members table
5. Check that the allocated_amount is set to 0.0 for each member
6. Verify that the loan amount is automatically updated if it was 0