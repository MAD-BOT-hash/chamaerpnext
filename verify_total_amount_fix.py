"""
Quick test to verify the Total Payment Amount field fix
"""
def verify_field_fix():
    """Verify that the total_amount field is properly configured"""
    print("🔍 Verifying Total Payment Amount Field Configuration...")
    
    # Read the JSON file
    import json
    with open('shg/shg/doctype/shg_bulk_payment/shg_bulk_payment.json', 'r') as f:
        data = json.load(f)
    
    # Find the total_amount field
    total_amount_field = None
    for field in data.get('fields', []):
        if field.get('fieldname') == 'total_amount':
            total_amount_field = field
            break
    
    if total_amount_field:
        print("✅ Found total_amount field")
        print(f"   Label: {total_amount_field.get('label')}")
        print(f"   Fieldtype: {total_amount_field.get('fieldtype')}")
        print(f"   Required: {total_amount_field.get('reqd')}")
        print(f"   Read-only: {total_amount_field.get('read_only', False)}")
        
        # Check if it's now editable (not read-only)
        if not total_amount_field.get('read_only'):
            print("✅ Field is now editable (not read-only) - Fix applied successfully!")
            return True
        else:
            print("❌ Field is still read-only - Fix not applied")
            return False
    else:
        print("❌ total_amount field not found")
        return False

if __name__ == "__main__":
    verify_field_fix()