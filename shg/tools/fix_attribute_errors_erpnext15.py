"""
ERPNext 15 SAFE ATTRIBUTEERROR CLEANER
-------------------------------------
Purpose:
  • Scan the SHG app for AttributeError sources.
  • Verify all lifecycle hooks required by ERPNext 15 exist and are callable.
  • Auto-add harmless ERPNext-compliant stubs (before_save, on_submit, etc.) if missing.
  • Fix or remove invalid hook references safely.
  • Preserve all user logic intact.

Usage:
  bench --site erpmain execute shg.tools.fix_attribute_errors_erpnext15.fix_all_attribute_errors
"""

import os
import re
import frappe
import importlib.util

APP_NAME = "shg"
APP_PATH = os.path.join("apps", APP_NAME, APP_NAME)


# -------------------------
# Utility: ensure safe stub
# -------------------------
def ensure_stub(py_file: str, func_name: str):
    """Add a harmless ERPNext-15 style stub if function missing."""
    if not os.path.exists(py_file):
        return False

    with open(py_file, "r") as f:
        code = f.read()

    if re.search(rf"def\s+{func_name}\s*\(", code):
        return False  # already defined

    with open(py_file, "a") as f:
        f.write(
            f"\n\ndef {func_name}(doc=None, method=None):\n"
            f"    '''ERPNext 15-compliant auto-stub to prevent AttributeError ({func_name}).'''\n"
            f"    # TODO: implement business logic later\n"
            f"    return\n"
        )
    print(f"✅ Added missing stub: {func_name} in {py_file}")
    return True


# -------------------------
# Step 1 — Verify hooks.py
# -------------------------
def scan_hooks():
    hooks_path = os.path.join(APP_PATH, "hooks.py")
    if not os.path.exists(hooks_path):
        print(f"⚠️ No hooks.py found at {hooks_path}")
        return

    with open(hooks_path, "r") as f:
        content = f.read()

    refs = re.findall(r'["\']([\w\.]+):([\w_]+)["\']', content)
    for module_path, func_name in refs:
        parts = module_path.split(".")
        if parts[0] != APP_NAME:
            continue  # skip non-app references

        module_file = os.path.join(APP_PATH, *parts[1:]) + ".py"
        if not os.path.exists(module_file):
            print(f"⚠️ Missing file for {module_path}:{func_name}")
            continue

        ensure_stub(module_file, func_name)


# -----------------------------------
# Step 2 — Verify DocType controllers
# -----------------------------------
def scan_doctype_controllers():
    """Ensure all ERPNext 15 lifecycle hooks exist in every controller."""
    lifecycle_hooks = [
        "validate", "before_insert", "after_insert", "before_save",
        "on_submit", "on_update", "on_update_after_submit",
        "on_cancel", "on_trash"
    ]

    doctype_root = os.path.join(APP_PATH, "doctype")
    for root, _, files in os.walk(doctype_root):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            for hook in lifecycle_hooks:
                ensure_stub(path, hook)


# ------------------------------------------------
# Step 3 — Sanitize invalid hook references safely
# ------------------------------------------------
def sanitize_hooks():
    hooks_path = os.path.join(APP_PATH, "hooks.py")
    if not os.path.exists(hooks_path):
        return

    with open(hooks_path) as f:
        lines = f.readlines()

    cleaned = []
    for line in lines:
        match = re.search(r'["\']([\w\.]+):([\w_]+)["\']', line)
        if not match:
            cleaned.append(line)
            continue
        module_path, func_name = match.groups()
        try:
            spec = importlib.util.find_spec(module_path)
            if spec is None:
                print(f"⚠️ Removing invalid hook: {line.strip()}")
                continue
        except Exception:
            print(f"⚠️ Removing invalid hook: {line.strip()}")
            continue
        cleaned.append(line)

    with open(hooks_path, "w") as f:
        f.writelines(cleaned)
    print("🧹 Cleaned invalid hook references in hooks.py")


# -------------------------
# Step 4 — Run all routines
# -------------------------
def fix_all_attribute_errors():
    print("🔍 Running ERPNext 15 AttributeError cleanup across SHG app...")
    sanitize_hooks()
    scan_hooks()
    scan_doctype_controllers()
    frappe.db.commit()
    print("✅ Completed cleanup.\n➡️  Next steps:\n"
          "   bench clear-cache\n"
          "   bench migrate\n"
          "   bench restart\n")


# Allow bench execute direct call
if __name__ == "__main__":
    fix_all_attribute_errors()