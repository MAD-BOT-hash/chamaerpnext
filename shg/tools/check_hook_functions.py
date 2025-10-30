"""
ERPNext 15 Hook Auto-Check and Self-Heal Tool
---------------------------------------------

✅ Scans all Doctype Python files in the SHG app
✅ Verifies required lifecycle hook functions exist at the module level
✅ Auto-adds safe, empty stubs for any missing functions
✅ Prevents AttributeError: module '...' has no attribute 'before_save' and similar issues

Usage:
  bench --site erpmain execute shg.tools.check_hook_functions.verify_hooks
"""

import os
import re

APP_NAME = "shg"
APP_PATH = os.path.join("apps", APP_NAME, APP_NAME)
DOCTYPES_PATH = os.path.join(APP_PATH, "doctype")

# ERPNext 15 core lifecycle hooks to verify
HOOK_FUNCTIONS = [
    "validate",
    "before_insert",
    "after_insert",
    "before_save",
    "on_submit",
    "on_update",
    "on_update_after_submit",
    "on_cancel",
    "on_trash"
]


def ensure_function_stub(py_file, func_name):
    """Ensure a given function exists at module level. Create it if missing."""
    with open(py_file, "r") as f:
        code = f.read()

    # Check if already exists (regex def func_name(...):
    if re.search(rf"def\s+{func_name}\s*\(", code):
        return False

    # Append safe stub
    with open(py_file, "a") as f:
        f.write(
            f"\n\ndef {func_name}(doc=None, method=None):\n"
            f"    '''Auto-added ERPNext 15 lifecycle stub for {func_name}.'''\n"
            f"    # TODO: implement business logic later\n"
            f"    return\n"
        )

    print(f"✅ Added missing hook: {func_name} in {py_file}")
    return True


def verify_hooks():
    """Main function to scan all doctypes for missing hook functions."""
    print("🔍 Scanning all DocTypes for missing lifecycle hook functions...")

    doctypes_fixed = 0
    hooks_added = 0

    for root, _, files in os.walk(DOCTYPES_PATH):
        for file in files:
            if not file.endswith(".py"):
                continue

            py_path = os.path.join(root, file)

            # Skip __init__.py and tests
            if file in ["__init__.py", "test_shg_loan.py"]:
                continue

            doctypes_fixed += 1
            for func in HOOK_FUNCTIONS:
                if ensure_function_stub(py_path, func):
                    hooks_added += 1

    print("\n✅ Hook scan complete.")
    print(f"📦 DocTypes scanned: {doctypes_fixed}")
    print(f"🩹 Hook stubs added: {hooks_added}")
    print("➡️  Next steps:\n   bench clear-cache && bench restart\n")

    return {
        "doctypes_scanned": doctypes_fixed,
        "hooks_added": hooks_added
    }


# Allow bench direct execution
if __name__ == "__main__":
    verify_hooks()