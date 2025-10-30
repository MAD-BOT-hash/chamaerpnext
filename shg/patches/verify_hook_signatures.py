import frappe
import inspect

def execute():
    """Verify that all hook functions have the correct signatures (doc, method=None)."""
    
    # List of modules and expected hook functions
    hook_modules = {
        "shg.shg.doctype.shg_loan.shg_loan": [
            "validate_loan",
            "post_to_general_ledger",
            "after_insert_or_update",
            "on_submit"
        ],
        "shg.shg.doctype.shg_contribution.shg_contribution": [
            "validate_contribution",
            "post_to_general_ledger"
        ],
        "shg.shg.doctype.shg_loan_repayment.shg_loan_repayment": [
            "validate_repayment",
            "post_to_general_ledger"
        ]
    }
    
    issues_found = []
    
    for module_path, functions in hook_modules.items():
        try:
            module = frappe.get_module(module_path)
            for func_name in functions:
                if hasattr(module, func_name):
                    func = getattr(module, func_name)
                    sig = inspect.signature(func)
                    params = list(sig.parameters.keys())
                    
                    # Check if function has correct signature (doc, method=None)
                    if len(params) < 1:
                        issues_found.append(f"{module_path}.{func_name} has no parameters")
                    elif len(params) == 1:
                        # Only doc parameter - this is acceptable
                        pass
                    elif len(params) >= 2:
                        # Should have doc and method parameters
                        if params[0] != 'doc':
                            issues_found.append(f"{module_path}.{func_name} first parameter should be 'doc', got '{params[0]}'")
                        if params[1] != 'method':
                            issues_found.append(f"{module_path}.{func_name} second parameter should be 'method', got '{params[1]}'")
                        # Check if method has default value of None
                        method_param = sig.parameters.get('method')
                        if method_param and method_param.default != None and method_param.default != inspect.Parameter.empty:
                            issues_found.append(f"{module_path}.{func_name} 'method' parameter should have default value of None")
                else:
                    issues_found.append(f"{module_path}.{func_name} function not found")
        except Exception as e:
            issues_found.append(f"Error checking {module_path}: {str(e)}")
    
    if issues_found:
        print("Hook signature issues found:")
        for issue in issues_found:
            print(f"  - {issue}")
    else:
        print("✅ All hook functions have correct signatures")
    
    return issues_found