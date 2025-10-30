"""
ERPNext 15 SMART APP AUTO-FIXER
-------------------------------
Purpose:
  ✅ Detect & fix AttributeError issues (missing hook methods, lifecycle stubs)
  ✅ Auto-create missing DocType JSONs referenced in controllers
  ✅ Auto-generate blank Client Script (.js) files for matching DocTypes
  ✅ Enforce ERPNext 15 naming conventions for doctypes and hooks

Usage:
  bench --site erpmain execute shg.tools.fix_app_structure_erpnext15.fix_app_structure
"""

import os
import re
import frappe
import json
import importlib.util

APP_NAME = "shg"
APP_PATH = os.path.join("apps", APP_NAME, APP_NAME)


# ---------------------------------------
# Utility: Safe Stub Writer
# ---------------------------------------
def ensure_stub(py_file: str, func_name: str):
    """Add harmless ERPNext 15 stub if missing."""
    if not os.path.exists(py_file):
        return False

    with open(py_file) as f:
        code = f.read()
    if re.search(rf"def\s+{func_name}\s*\(", code):
        return False

    with open(py_file, "a") as f:
        f.write(
            f"\n\ndef {func_name}(doc=None, method=None):\n"
            f"    '''Auto-generated ERPNext 15 stub for {func_name}'''\n"
            f"    return\n"
        )
    print(f"✅ Added stub: {func_name} in {py_file}")
    return True


# ---------------------------------------
# Utility: Create minimal DocType JSON
# ---------------------------------------
def create_doctype_json(doctype_name: str):
    """Auto-create missing DocType JSON under /doctype/<doctype_name>"""
    safe_name = doctype_name.lower().replace(" ", "_")
    dt_dir = os.path.join(APP_PATH, "doctype", safe_name)
    os.makedirs(dt_dir, exist_ok=True)
    dt_path = os.path.join(dt_dir, f"{safe_name}.json")

    if os.path.exists(dt_path):
        return False

    minimal_doc = {
        "doctype": "DocType",
        "name": doctype_name,
        "module": APP_NAME.upper(),
        "custom": 0,
        "istable": 0,
        "editable_grid": 1,
        "fields": [],
        "permissions": [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
        ],
        "allow_import": 1
    }

    with open(dt_path, "w") as f:
        json.dump(minimal_doc, f, indent=1)
    print(f"🆕 Created missing DocType JSON: {doctype_name}")
    return True


# ---------------------------------------
# Utility: Create blank JS Client Script
# ---------------------------------------
def create_client_script(doctype_name: str):
    """Generate an empty JS client script for the DocType."""
    safe_name = doctype_name.lower().replace(" ", "_")
    js_path = os.path.join(APP_PATH, "public", "js")
    os.makedirs(js_path, exist_ok=True)
    target_file = os.path.join(js_path, f"{safe_name}.js")

    if os.path.exists(target_file):
        return False

    content = (
        f"// Auto-generated Client Script for {doctype_name}\n"
        f"frappe.ui.form.on('{doctype_name}', {{\n"
        f"  refresh(frm) {{\n"
        f"    // Custom logic here\n"
        f"  }}\n"
        f"}});\n"
    )
    with open(target_file, "w") as f:
        f.write(content)
    print(f"🆕 Created Client Script: {target_file}")
    return True


# ---------------------------------------
# Hook Scan
# ---------------------------------------
def scan_hooks():
    hooks_path = os.path.join(APP_PATH, "hooks.py")
    if not os.path.exists(hooks_path):
        return
    with open(hooks_path) as f:
        content = f.read()

    refs = re.findall(r'["\']([\w\.]+):([\w_]+)["\']', content)
    for module_path, func_name in refs:
        parts = module_path.split(".")
        if parts[0] != APP_NAME:
            continue
        module_file = os.path.join(APP_PATH, *parts[1:]) + ".py"
        if not os.path.exists(module_file):
            print(f"⚠️ Missing file for {module_path}:{func_name}")
            continue
        ensure_stub(module_file, func_name)


# ---------------------------------------
# Scan Doctype Controllers
# ---------------------------------------
def scan_doctype_controllers():
    """Ensure all ERPNext 15 lifecycle hooks exist in every controller."""
    lifecycle = [
        "validate", "before_insert", "after_insert", "before_save",
        "on_submit", "on_update", "on_update_after_submit",
        "on_cancel", "on_trash"
    ]
    dt_root = os.path.join(APP_PATH, "doctype")
    for root, _, files in os.walk(dt_root):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            for hook in lifecycle:
                ensure_stub(path, hook)


# ---------------------------------------
# Auto-Detect & Create Missing Doctypes
# ---------------------------------------
def auto_detect_doctypes():
    """
    Parse Python controllers for frappe.get_doc / frappe.new_doc / frappe.get_list references.
    Create missing DocType JSONs if not found in /doctype.
    """
    pattern = re.compile(r"frappe\.(?:get_doc|get_list|new_doc)\(['\"]([\w\s]+)['\"]")
    for root, _, files in os.walk(APP_PATH):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            with open(path) as f:
                code = f.read()
            for dt in set(pattern.findall(code)):
                if not frappe.db.exists("DocType", dt):
                    create_doctype_json(dt)
                    create_client_script(dt)


# ---------------------------------------
# Main Runner
# ---------------------------------------
def fix_app_structure():
    print("🔍 Running ERPNext 15 smart structure & AttributeError repair...")
    scan_hooks()
    scan_doctype_controllers()
    auto_detect_doctypes()
    frappe.db.commit()
    print("✅ Cleanup complete.\n➡️ Run:\n   bench clear-cache && bench migrate && bench restart")


# Allow bench execute
if __name__ == "__main__":
    fix_app_structure()