# Client Calls to Server Functions in Frappe/ERPNext

This document explains how to properly expose server functions for client calls in Frappe/ERPNext and provides examples.

## 📋 Required Decorator

To expose a server function for client calls, you must add the `@frappe.whitelist()` decorator:

```python
import frappe

@frappe.whitelist()
def your_function(parameters):
    # Your logic here
    pass
```

## 📁 File Location

Server functions should be placed in the appropriate doctype Python file:
```
shg/shg/doctype/[doctype_name]/[doctype_name].py
```

## ✅ Example Implementation

### Server Side (Python)
File: `shg/shg/doctype/shg_member/shg_member.py`

```python
import frappe

@frappe.whitelist()
def update_financial_summary(member_id=None):
    """Update financial summary for a member"""
    if not member_id:
        frappe.throw("Member ID required")

    try:
        # Get the member document
        member = frappe.get_doc("SHG Member", member_id)
        
        # Update the financial summary
        member.update_financial_summary()
        
        # Return success message with updated information
        return {
            "status": "success",
            "message": "Financial summary updated successfully",
            "summary": {
                "total_contributions": member.total_contributions,
                "total_loans_taken": member.total_loans_taken,
                "current_loan_balance": member.current_loan_balance,
                "credit_score": member.credit_score
            }
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Member - Update Financial Summary Failed")
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_member_summary(member_id=None):
    """Get member summary information"""
    if not member_id:
        frappe.throw("Member ID required")

    try:
        # Get the member document
        member = frappe.get_doc("SHG Member", member_id)
        
        # Return member summary information
        return {
            "status": "success",
            "member_info": {
                "name": member.name,
                "member_name": member.member_name,
                "account_number": member.account_number,
                "total_contributions": member.total_contributions,
                "total_loans_taken": member.total_loans_taken,
                "current_loan_balance": member.current_loan_balance,
                "credit_score": member.credit_score,
                "last_contribution_date": member.last_contribution_date,
                "last_loan_date": member.last_loan_date,
                "membership_status": member.membership_status
            }
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Member - Get Member Summary Failed")
        return {
            "status": "error",
            "message": str(e)
        }
```

## 📞 Client Side (JavaScript)

### Method 1: Using frappe.call()
```javascript
// Update financial summary
frappe.call({
    method: "shg.shg.doctype.shg_member.shg_member.update_financial_summary",
    args: {
        member_id: cur_frm.doc.name
    },
    callback: function(r) {
        if(!r.exc) {
            if (r.message.status === "success") {
                frappe.msgprint("Financial summary updated: " + r.message.message);
                // Refresh the form to show updated values
                cur_frm.reload_doc();
            } else {
                frappe.msgprint("Error: " + r.message.message);
            }
        }
    }
});

// Get member summary
frappe.call({
    method: "shg.shg.doctype.shg_member.shg_member.get_member_summary",
    args: {
        member_id: cur_frm.doc.name
    },
    callback: function(r) {
        if(!r.exc) {
            if (r.message.status === "success") {
                console.log("Member Summary:", r.message.member_info);
                // Use the member information as needed
                let info = r.message.member_info;
                frappe.msgprint(`
                    Member: ${info.member_name}
                    Total Contributions: ${info.total_contributions}
                    Current Loan Balance: ${info.current_loan_balance}
                    Credit Score: ${info.credit_score}
                `);
            } else {
                frappe.msgprint("Error: " + r.message.message);
            }
        }
    }
});
```

### Method 2: In Form Scripts
File: `shg/public/js/shg_member.js`

```javascript
frappe.ui.form.on('SHG Member', {
    refresh: function(frm) {
        // Add custom button to update financial summary
        frm.add_custom_button(__('Update Financial Summary'), function() {
            frappe.call({
                method: "shg.shg.doctype.shg_member.shg_member.update_financial_summary",
                args: {
                    member_id: frm.doc.name
                },
                callback: function(r) {
                    if(!r.exc) {
                        if (r.message.status === "success") {
                            frappe.msgprint("Financial summary updated successfully");
                            frm.reload_doc();
                        } else {
                            frappe.msgprint("Error: " + r.message.message);
                        }
                    }
                }
            });
        });
    }
});
```

## 🔐 Security Considerations

1. **Always validate input parameters**:
```python
@frappe.whitelist()
def your_function(member_id=None):
    if not member_id:
        frappe.throw("Member ID required")
    
    # Validate that user has permission to access this member
    if not frappe.has_permission("SHG Member", "read", member_id):
        frappe.throw("Insufficient permissions")
```

2. **Use frappe.has_permission()** for access control:
```python
@frappe.whitelist()
def update_member_data(member_id, data):
    # Check if user has write permission
    if not frappe.has_permission("SHG Member", "write", member_id):
        frappe.throw("You do not have permission to update this member")
    
    # Proceed with update logic
```

3. **Log errors properly**:
```python
except Exception as e:
    frappe.log_error(frappe.get_traceback(), "Function Name - Error Description")
    return {"status": "error", "message": str(e)}
```

## 🧪 Testing Client Calls

You can test client calls using the Frappe Console or by creating custom buttons:

```javascript
// Test in Frappe Console
frappe.call({
    method: "shg.shg.doctype.shg_member.shg_member.get_member_summary",
    args: {
        member_id: "TEST-MEMBER-001"
    },
    callback: function(r) {
        console.log(r.message);
    }
});
```

## 📚 Best Practices

1. **Always use try-except blocks** in whitelisted functions
2. **Return structured responses** with status indicators
3. **Log errors** for debugging purposes
4. **Validate permissions** before performing operations
5. **Use meaningful function names** that describe their purpose
6. **Document your functions** with docstrings
7. **Group related functions** in the same file

The implementation in the SHG Member doctype now includes two whitelisted functions:
1. `update_financial_summary()` - Updates a member's financial summary
2. `get_member_summary()` - Retrieves a member's summary information

These functions can be called from the client side using `frappe.call()` with the appropriate method path.