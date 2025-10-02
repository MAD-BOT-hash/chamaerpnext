import unittest
import json
import os

class TestCustomFieldFixtures(unittest.TestCase):
    def setUp(self):
        """Set up test dependencies."""
        self.custom_dir = os.path.join(os.path.dirname(__file__), '..', 'shg', 'shg', 'custom')
        
    def test_journal_entry_custom_fields_structure(self):
        """Test that Journal Entry custom fields follow the correct fixture format."""
        files = [
            'custom_field_journal_entry_shg_contribution.json',
            'custom_field_journal_entry_shg_loan.json',
            'custom_field_journal_entry_shg_loan_repayment.json',
            'custom_field_journal_entry_shg_meeting_fine.json'
        ]
        
        for filename in files:
            with open(os.path.join(self.custom_dir, filename), 'r') as f:
                data = json.load(f)
                
            # Check that the file has the correct structure
            self.assertIn('custom_fields', data, f"{filename} should have 'custom_fields' key")
            self.assertIn('Journal Entry', data['custom_fields'], f"{filename} should have 'Journal Entry' key")
            self.assertIsInstance(data['custom_fields']['Journal Entry'], list, f"{filename} 'Journal Entry' should be a list")
            self.assertGreater(len(data['custom_fields']['Journal Entry']), 0, f"{filename} should have at least one custom field")
            
            # Check the first custom field
            field = data['custom_fields']['Journal Entry'][0]
            self.assertIn('fieldname', field, f"{filename} custom field should have 'fieldname'")
            self.assertIn('fieldtype', field, f"{filename} custom field should have 'fieldtype'")
            self.assertIn('options', field, f"{filename} custom field should have 'options'")
            self.assertIn('label', field, f"{filename} custom field should have 'label'")
            self.assertIn('insert_after', field, f"{filename} custom field should have 'insert_after'")
            
            print(f"✓ {filename} has correct structure")

    def test_payment_entry_custom_fields_structure(self):
        """Test that Payment Entry custom fields follow the correct fixture format."""
        files = [
            'custom_field_payment_entry_shg_contribution.json',
            'custom_field_payment_entry_shg_loan.json',
            'custom_field_payment_entry_shg_loan_repayment.json',
            'custom_field_payment_entry_shg_meeting_fine.json'
        ]
        
        for filename in files:
            with open(os.path.join(self.custom_dir, filename), 'r') as f:
                data = json.load(f)
                
            # Check that the file has the correct structure
            self.assertIn('custom_fields', data, f"{filename} should have 'custom_fields' key")
            self.assertIn('Payment Entry', data['custom_fields'], f"{filename} should have 'Payment Entry' key")
            self.assertIsInstance(data['custom_fields']['Payment Entry'], list, f"{filename} 'Payment Entry' should be a list")
            self.assertGreater(len(data['custom_fields']['Payment Entry']), 0, f"{filename} should have at least one custom field")
            
            # Check the first custom field
            field = data['custom_fields']['Payment Entry'][0]
            self.assertIn('fieldname', field, f"{filename} custom field should have 'fieldname'")
            self.assertIn('fieldtype', field, f"{filename} custom field should have 'fieldtype'")
            self.assertIn('options', field, f"{filename} custom field should have 'options'")
            self.assertIn('label', field, f"{filename} custom field should have 'label'")
            self.assertIn('insert_after', field, f"{filename} custom field should have 'insert_after'")
            
            print(f"✓ {filename} has correct structure")

    def test_customer_custom_fields_structure(self):
        """Test that Customer custom fields follow the correct fixture format."""
        files = [
            'custom_field_customer_is_shg_member.json',
            'custom_field_customer_shg_member_id.json'
        ]
        
        for filename in files:
            with open(os.path.join(self.custom_dir, filename), 'r') as f:
                data = json.load(f)
                
            # Check that the file has the correct structure
            self.assertIn('custom_fields', data, f"{filename} should have 'custom_fields' key")
            self.assertIn('Customer', data['custom_fields'], f"{filename} should have 'Customer' key")
            self.assertIsInstance(data['custom_fields']['Customer'], list, f"{filename} 'Customer' should be a list")
            self.assertGreater(len(data['custom_fields']['Customer']), 0, f"{filename} should have at least one custom field")
            
            # Check the first custom field
            field = data['custom_fields']['Customer'][0]
            self.assertIn('fieldname', field, f"{filename} custom field should have 'fieldname'")
            self.assertIn('fieldtype', field, f"{filename} custom field should have 'fieldtype'")
            self.assertIn('label', field, f"{filename} custom field should have 'label'")
            self.assertIn('insert_after', field, f"{filename} custom field should have 'insert_after'")
            
            print(f"✓ {filename} has correct structure")

    def test_all_custom_fields_have_unique_fieldnames(self):
        """Test that all custom fields have unique fieldnames within their doctype."""
        doctype_fields = {}
        
        # Read all custom field files
        for filename in os.listdir(self.custom_dir):
            if filename.endswith('.json') and filename != 'property_setter.json':
                with open(os.path.join(self.custom_dir, filename), 'r') as f:
                    data = json.load(f)
                    
                if 'custom_fields' in data:
                    for doctype, fields in data['custom_fields'].items():
                        if doctype not in doctype_fields:
                            doctype_fields[doctype] = []
                        
                        for field in fields:
                            if 'fieldname' in field:
                                doctype_fields[doctype].append(field['fieldname'])
        
        # Check for duplicates
        for doctype, fieldnames in doctype_fields.items():
            duplicates = [name for name in fieldnames if fieldnames.count(name) > 1]
            self.assertEqual(len(duplicates), 0, f"Duplicate fieldnames found in {doctype}: {set(duplicates)}")
            
        print("✓ All custom fields have unique fieldnames")

if __name__ == '__main__':
    unittest.main()