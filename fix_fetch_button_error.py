"""
Fix instructions for the fetch button error
"""

fix_instructions = """
🔧 FIX INSTRUCTIONS FOR FETCH BUTTON ERROR

The error "module 'shg.shg.services.payment.bulk_payment_service' has no attribute 'get_unpaid_invoices_for_company'" 
occurs because Frappe needs to reload the module to recognize the new methods.

SOLUTIONS (try in order):

1. **Restart the Frappe Server** (Most Effective)
   - Stop your Frappe development server (Ctrl+C)
   - Start it again with: `bench start`
   - This will reload all modules including the updated service

2. **Clear Python Cache**
   - Delete __pycache__ folders:
     ```bash
     find . -name "__pycache__" -type d -exec rm -rf {} +
     ```
   - Then restart the server

3. **Force Module Reload** (Development only)
   - In your Python console or script:
     ```python
     import importlib
     import shg.shg.services.payment.bulk_payment_service
     importlib.reload(shg.shg.services.payment.bulk_payment_service)
     ```

4. **Verify Installation**
   - After restart, test the fetch buttons again
   - The methods should now be accessible

The methods are properly defined in the file, this is purely a module loading/caching issue that resolves with a server restart.
"""

print(fix_instructions)