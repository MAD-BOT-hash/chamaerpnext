import os
import json

def validate_json_files(base_path):
    """Validate all JSON files in the given directory and subdirectories."""
    count = 0
    fixed = 0
    
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith('.json'):
                path = os.path.join(root, file)
                count += 1
                try:
                    with open(path, 'r') as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    print(f"🛠 Fixing invalid JSON: {path}")
                    # Read the file content
                    with open(path, 'r') as f:
                        text = f.read()
                    
                    # Fix common JSON syntax issues
                    # Replace single quotes with double quotes (simple approach)
                    text = text.replace("'", '"')
                    # Replace Python literals with JSON equivalents
                    text = text.replace('None', 'null').replace('True', 'true').replace('False', 'false')
                    # Remove trailing commas before closing braces/brackets
                    text = text.replace(',\n}', '\n}').replace(',\n]', '\n]')
                    
                    # Try to load the fixed JSON
                    try:
                        data = json.loads(text)
                        # Write the fixed JSON back to file with proper indentation
                        with open(path, 'w') as f:
                            json.dump(data, f, indent=4)
                        print(f"✅ Fixed and validated: {path}")
                        fixed += 1
                    except Exception as e2:
                        print(f"❌ Still invalid {path}: {e2}")
    
    print(f"Total JSON files checked: {count}, Fixed: {fixed}")

if __name__ == "__main__":
    base_path = r"c:\Users\user\Downloads\shg-erpnext\shg\shg\doctype"
    validate_json_files(base_path)