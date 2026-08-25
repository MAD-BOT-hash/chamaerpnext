import frappe
from frappe import _
from frappe.utils import flt, getdate
from frappe.model.document import Document


class SHGBulkContributionInvoice(Document):
    """Generate multiple contribution invoices for selected members in one operation."""
    
    def validate(self):
        """Validate the bulk invoice document."""
        if not self.members:
            frappe.throw(_("Please select members to generate invoices"))
            
        self.calculate_totals()
    
    def calculate_totals(self):
        """Calculate total members and amount."""
        selected_count = sum(1 for row in self.members if row.selected)
        total_amt = sum(flt(row.amount) for row in self.members if row.selected)
        
        self.total_members = selected_count
        self.total_amount = total_amt
    
    def on_submit(self):
        """Not submittable - this is a utility DocType for generating invoices."""
        frappe.throw(_("This document cannot be submitted. Use 'Create Invoices' button to generate contribution invoices."))
    
    @frappe.whitelist()
    def get_active_members(self):
        """Fetch active SHG members and populate the members table."""
        # Get active members
        members = frappe.get_list(
            "SHG Member",
            filters={
                "status": "Active",
                "docstatus": 1
            },
            fields=["name", "member_name"],
            order_by="member_name"
        )
        
        if not members:
            frappe.msgprint(_("No active members found"))
            return
        
        # Clear existing rows
        self.members = []
        
        # Add members to table
        for member_doc in members:
            row = self.append("members", {
                "member": member_doc.name,
                "member_name": member_doc.member_name,
                "qty": self.default_qty or 1,
                "rate": self.default_rate or 0,
                "selected": 1,
                "status": "Pending"
            })
            # Calculate amount
            row.amount = flt(row.qty) * flt(row.rate)
        
        self.calculate_totals()
        frappe.msgprint(_("Loaded {0} active members").format(len(members)))
    
    @frappe.whitelist()
    def clear_members(self):
        """Clear all members from the table."""
        self.members = []
        self.calculate_totals()
        frappe.msgprint(_("Cleared all members"))
    
    @frappe.whitelist()
    def create_invoices(self):
        """Create individual contribution invoices for selected members."""
        if not self.members:
            frappe.throw(_("No members to create invoices for"))
        
        selected_members = [row for row in self.members if row.selected]
        if not selected_members:
            frappe.throw(_("Please select at least one member"))
        
        created_count = 0
        failed_count = 0
        errors = []
        
        for idx, row in enumerate(selected_members):
            try:
                # Check for duplicate invoice
                existing = frappe.get_value(
                    "SHG Contribution Invoice",
                    {
                        "member": row.member,
                        "invoice_date": self.invoice_date,
                        "contribution_type": self.contribution_type,
                        "docstatus": [">", "-1"]  # Not cancelled
                    },
                    "name"
                )
                
                if existing:
                    row.status = "Failed"
                    row.error_message = "Invoice already exists: " + existing
                    failed_count += 1
                    errors.append(f"{row.member_name}: Invoice already exists ({existing})")
                    continue
                
                # Create the contribution invoice
                invoice = frappe.new_doc("SHG Contribution Invoice")
                invoice.member = row.member
                invoice.member_name = row.member_name
                invoice.invoice_date = self.invoice_date
                invoice.due_date = self.due_date
                invoice.contribution_type = self.contribution_type
                invoice.qty = flt(row.qty)
                invoice.rate = flt(row.rate)
                invoice.amount = flt(row.amount)
                invoice.description = self.description
                invoice.payment_method = "Cash"  # Default payment method
                
                invoice.insert(ignore_permissions=True)
                
                # Update row with success
                row.generated_invoice = invoice.name
                row.status = "Created"
                row.error_message = ""
                created_count += 1
                
            except Exception as e:
                row.status = "Failed"
                row.error_message = str(e)[:500]  # Truncate error message
                failed_count += 1
                errors.append(f"{row.member_name}: {str(e)[:100]}")
        
        # Save the bulk invoice with updated status
        self.status = "Invoices Created"
        self.save()
        
        # Prepare result message
        msg = _("<b>Bulk Invoice Creation Result:</b><br/>")
        msg += _("Successfully created: <b>{0}</b> invoices<br/>").format(created_count)
        
        if failed_count > 0:
            msg += _("Failed: <b>{0}</b> invoices<br/>").format(failed_count)
            msg += "<b>Errors:</b><br/>"
            for error in errors[:10]:  # Show first 10 errors
                msg += f"• {error}<br/>"
            if len(errors) > 10:
                msg += f"• ... and {len(errors) - 10} more<br/>"
        
        frappe.msgprint(msg)
        
        return {
            "created": created_count,
            "failed": failed_count,
            "errors": errors
        }
