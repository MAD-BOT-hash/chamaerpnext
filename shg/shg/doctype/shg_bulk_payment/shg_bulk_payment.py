import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, now, nowdate


class SHGBulkPayment(Document):
    """
    SHG Bulk Payment Document
    Enterprise-grade bulk payment processing with full safety guarantees
    Provides ERPNext-compatible properties for Payment Entry integration.
    """
    
    # ========================================================================
    # ERPNext Payment Entry Compatibility Properties
    # ========================================================================
    
    @property
    def grand_total(self):
        """ERPNext compatibility - returns total_amount."""
        return flt(self.total_amount or 0)
    
    @property
    def base_grand_total(self):
        """ERPNext compatibility - returns total_amount."""
        return flt(self.total_amount or 0)
    
    @property
    def rounded_total(self):
        """ERPNext compatibility - returns total_amount."""
        return flt(self.total_amount or 0)
    
    @property
    def outstanding_amount(self):
        """ERPNext compatibility - returns unallocated_amount."""
        return flt(getattr(self, 'unallocated_amount', 0) or 0)
    
    @property
    def currency(self):
        """ERPNext compatibility - returns company currency."""
        if hasattr(self, 'company') and self.company:
            return frappe.db.get_value("Company", self.company, "default_currency") or "KES"
        return "KES"
    
    @property
    def conversion_rate(self):
        """ERPNext compatibility - returns 1.0."""
        return 1.0
    
    @property
    def advance_paid(self):
        """ERPNext compatibility - returns 0."""
        return 0.0
    
    @property
    def is_return(self):
        """ERPNext compatibility - returns False."""
        return False
    
    @property
    def customer(self):
        """ERPNext compatibility - returns member's customer."""
        if hasattr(self, 'member') and self.member:
            customer = frappe.db.get_value("SHG Member", self.member, "customer")
            return customer or self.member
        return None
    
    # ========================================================================
    # End ERPNext Compatibility Properties
    # ========================================================================
    
    def __getattr__(self, name):
        """Fallback for ERPNext attributes not explicitly defined."""
        common_financial_attrs = {
            "total_advance": 0.0, "base_total": 0.0, "net_total": 0.0,
            "base_net_total": 0.0, "total_taxes_and_charges": 0.0,
            "base_total_taxes_and_charges": 0.0, "discount_amount": 0.0,
            "base_discount_amount": 0.0, "write_off_amount": 0.0,
            "base_write_off_amount": 0.0, "rounding_adjustment": 0.0,
            "base_rounding_adjustment": 0.0, "paid_amount": 0.0,
            "base_paid_amount": 0.0, "change_amount": 0.0,
            "base_change_amount": 0.0, "loyalty_amount": 0.0,
            "in_words": "", "base_in_words": "", "total_qty": 1.0,
            "is_internal_customer": 0, "is_internal_supplier": 0,
            "group_same_items": 0, "disable_rounded_total": 0,
            "apply_discount_on": "", "additional_discount_percentage": 0.0,
        }
        if name in common_financial_attrs:
            return common_financial_attrs[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def before_validate(self):
        """Auto-calculate totals and set company before validation"""
        self.set_company()
        self.calculate_totals()
    
    def set_company(self):
        """Set company from SHG Settings if not already set"""
        if not self.company:
            company = frappe.db.get_single_value("SHG Settings", "company")
            if not company:
                # Fallback to user default company
                company = frappe.defaults.get_user_default("Company")
            if not company:
                # Final fallback to global default company
                company = frappe.db.get_single_value("Global Defaults", "default_company")
            if not company:
                # Get first available company
                companies = frappe.get_all("Company", limit=1)
                if companies:
                    company = companies[0].name
            if company:
                self.company = company
            else:
                frappe.throw("No default Company found. Please set a company in SHG Settings, Global Defaults, or create a Company.")
    
    def calculate_totals(self):
        """Calculate and set total amounts based on allocations"""
        total_allocated = 0.0
        total_outstanding = 0.0
        
        if self.allocations:
            for row in self.allocations:
                total_allocated += flt(row.allocated_amount or 0)
                total_outstanding += flt(row.outstanding_amount or 0)
        
        self.total_allocated_amount = total_allocated
        self.total_outstanding_amount = total_outstanding
        self.unallocated_amount = flt(self.total_amount) - flt(total_allocated)
    
    def validate(self):
        """Validate bulk payment document"""
        self.validate_required_fields()
        self.validate_amounts()
        self.validate_allocations()
        self.update_totals()
    
    def validate_required_fields(self):
        """Validate all required fields are present"""
        if not self.company:
            frappe.throw(_("Company is required"))
        
        if not self.posting_date:
            frappe.throw(_("Posting Date is required"))
        
        if not self.mode_of_payment:
            frappe.throw(_("Mode of Payment is required"))
        
        if not self.payment_account:
            frappe.throw(_("Payment Account is required"))
        
        if not self.reference_no:
            frappe.throw(_("Reference No is required"))
        
        if not self.reference_date:
            frappe.throw(_("Reference Date is required"))
    
    def validate_amounts(self):
        """Validate payment amounts"""
        if flt(self.total_amount) <= 0:
            frappe.throw(_("Total Amount must be greater than zero"))
        
        # Validate allocations exist
        if not self.allocations:
            frappe.throw(_("At least one allocation is required"))
        
        # Validate allocation amounts
        total_allocated = sum(flt(allocation.allocated_amount) for allocation in self.allocations)
        if total_allocated <= 0:
            frappe.throw(_("Total allocated amount must be greater than zero"))
        
        # Overpayment prevention
        if total_allocated > flt(self.total_amount):
            frappe.throw(
                _("Total allocated amount ({0}) cannot exceed total payment amount ({1})").format(
                    total_allocated, self.total_amount
                )
            )
    
    def validate_allocations(self):
        """Validate each allocation"""
        for allocation in self.allocations:
            self.validate_single_allocation(allocation)
    
    def validate_single_allocation(self, allocation):
        """Validate individual allocation"""
        if not allocation.member:
            frappe.throw(_("Member is required for allocation {0}").format(allocation.idx))
        
        if not allocation.reference_doctype:
            frappe.throw(_("Reference Type is required for allocation {0}").format(allocation.idx))
        
        if not allocation.reference_name:
            frappe.throw(_("Reference Name is required for allocation {0}").format(allocation.idx))
        
        if flt(allocation.allocated_amount) <= 0:
            frappe.throw(_("Allocated Amount must be greater than zero for allocation {0}").format(allocation.idx))
        
        # Validate outstanding amount
        if flt(allocation.allocated_amount) > flt(allocation.outstanding_amount):
            frappe.throw(
                _("Allocated amount ({0}) cannot exceed outstanding amount ({1}) for {2} {3}").format(
                    allocation.allocated_amount,
                    allocation.outstanding_amount,
                    allocation.reference_doctype,
                    allocation.reference_name
                )
            )
    
    def update_totals(self):
        """Update document totals"""
        total_allocated = sum(flt(allocation.allocated_amount) for allocation in self.allocations)
        total_outstanding = sum(flt(allocation.outstanding_amount) for allocation in self.allocations)
        
        self.total_allocated_amount = total_allocated
        self.total_outstanding_amount = total_outstanding
        self.unallocated_amount = flt(self.total_amount) - flt(total_allocated)
    
    def before_submit(self):
        """Validate before submission"""
        if self.processing_status not in ["Draft", "Failed"]:
            frappe.throw(_("Only Draft or Failed bulk payments can be submitted"))
        
        # Ensure all required fields are populated
        self.validate()
    
    def on_submit(self):
        """Process bulk payment on submission"""
        # Update processed_by and processed_via before processing
        frappe.db.set_value(
            "SHG Bulk Payment", 
            self.name, 
            "processed_by", 
            frappe.session.user,
            update_modified=False
        )
        frappe.db.set_value(
            "SHG Bulk Payment", 
            self.name, 
            "processed_via", 
            "Manual",
            update_modified=False
        )
        
        # Process the payment (this will update the status internally)
        self.process_bulk_payment()
    
    def on_cancel(self):
        """
        Reverse bulk payment on cancellation.
        - Reverse status of all allocated items back to Unpaid/Pending
        - Update member statements to reflect the reversal
        """
        self._reverse_allocations()
        self._update_member_statements_on_cancel()
        
        # Update processing status
        frappe.db.set_value(
            "SHG Bulk Payment",
            self.name,
            "processing_status",
            "Cancelled",
            update_modified=False
        )
        
        frappe.msgprint(
            _("Bulk payment cancelled. All allocations have been reversed."),
            alert=True,
            indicator="orange"
        )
    
    def _reverse_allocations(self):
        """
        Reverse all payment allocations back to unpaid status.
        """
        reversed_count = 0
        errors = []
        
        for allocation in self.allocations:
            if not allocation.is_processed:
                continue
                
            try:
                self._reverse_single_allocation(allocation)
                reversed_count += 1
            except Exception as e:
                errors.append(f"{allocation.reference_name}: {str(e)}")
                frappe.log_error(
                    title="Reverse Allocation",
                    message=f"Failed: {allocation.reference_name}: {str(e)}"
                )
        
        if errors:
            frappe.msgprint(
                _("Some allocations could not be reversed: {0}").format(", ".join(errors[:5])),
                indicator="red"
            )
        
        if reversed_count > 0:
            frappe.msgprint(
                _("Reversed {0} allocation(s)").format(reversed_count),
                alert=True
            )
    
    def _reverse_single_allocation(self, allocation):
        """
        Reverse a single allocation back to unpaid status.
        
        Args:
            allocation: SHG Bulk Payment Allocation row
        """
        doctype = allocation.reference_doctype
        docname = allocation.reference_name
        allocated_amount = allocation.allocated_amount
        
        try:
            doc = frappe.get_doc(doctype, docname)
            
            # Handle based on doctype
            if doctype == "SHG Loan Repayment Schedule":
                self._reverse_loan_installment(doc, allocated_amount)
            else:
                self._reverse_standard_allocation(doc, doctype, allocated_amount)
            
            # Update allocation status
            frappe.db.set_value(
                "SHG Bulk Payment Allocation",
                allocation.name,
                {
                    "processing_status": "Reversed",
                    "is_processed": 0,
                    "remarks": f"Reversed on {frappe.utils.now()}"
                },
                update_modified=False
            )
            
        except Exception as e:
            raise Exception(f"Failed to reverse {doctype} {docname}: {str(e)}")
    
    def _reverse_standard_allocation(self, doc, doctype, allocated_amount):
        """
        Reverse allocation for standard doctypes (Contribution Invoice, Contribution, Fine).
        """
        # Determine field names based on doctype
        if doctype == "SHG Contribution":
            paid_field = "amount_paid"
            outstanding_field = "unpaid_amount"
        else:
            paid_field = "paid_amount"
            outstanding_field = "outstanding_amount"
        
        # Get current values
        current_paid = flt(getattr(doc, paid_field, 0) or 0)
        current_outstanding = flt(getattr(doc, outstanding_field, 0) or 0)
        
        # Reverse the payment
        new_paid = max(0, current_paid - allocated_amount)
        new_outstanding = current_outstanding + allocated_amount
        
        # Determine new status
        if new_paid <= 0:
            new_status = "Pending" if doctype == "SHG Meeting Fine" else "Unpaid"
        else:
            new_status = "Partially Paid"
        
        # Update document
        update_values = {
            paid_field: new_paid,
            outstanding_field: new_outstanding,
            "status": new_status
        }
        
        # Clear payment entry reference if fully reversed
        if new_paid <= 0 and hasattr(doc, 'payment_entry'):
            update_values["payment_entry"] = None
        
        frappe.db.set_value(doctype, doc.name, update_values, update_modified=False)
        
        # If this is a Contribution Invoice, also reverse the linked Contribution
        if doctype == "SHG Contribution Invoice":
            self._reverse_linked_contribution(doc, allocated_amount)
    
    def _reverse_linked_contribution(self, invoice_doc, allocated_amount):
        """
        Reverse the linked SHG Contribution when a Contribution Invoice is reversed.
        
        Args:
            invoice_doc: SHG Contribution Invoice document
            allocated_amount: Amount to reverse
        """
        linked_contribution = getattr(invoice_doc, 'linked_shg_contribution', None)
        if not linked_contribution:
            return
        
        try:
            contribution = frappe.get_doc("SHG Contribution", linked_contribution)
            
            # Get current values
            total_amount = flt(contribution.total_amount or 0)
            current_paid = flt(getattr(contribution, 'amount_paid', 0) or 0)
            
            # Reverse the payment
            new_paid = max(0, current_paid - allocated_amount)
            new_unpaid = total_amount - new_paid
            
            # Determine new status
            if new_paid <= 0:
                new_status = "Unpaid"
            elif new_paid < total_amount:
                new_status = "Partially Paid"
            else:
                new_status = "Paid"
            
            # Update the contribution
            update_values = {
                "amount_paid": flt(new_paid, 2),
                "unpaid_amount": flt(new_unpaid, 2),
                "status": new_status
            }
            
            # Clear payment entry if fully reversed
            if new_paid <= 0:
                update_values["payment_entry"] = None
            
            frappe.db.set_value(
                "SHG Contribution",
                linked_contribution,
                update_values,
                update_modified=False
            )
            
        except Exception as e:
            frappe.log_error(
                title="Contribution Reversal",
                message=f"Failed to reverse {linked_contribution}: {str(e)}"
            )
    
    def _reverse_loan_installment(self, schedule_row, allocated_amount):
        """
        Reverse allocation for loan repayment schedule installment.
        """
        # Get current values
        current_paid = flt(schedule_row.actual_amount_paid or 0)
        total_amount = flt(schedule_row.total_amount or 0)
        
        # Reverse the payment
        new_paid = max(0, current_paid - allocated_amount)
        new_outstanding = total_amount - new_paid
        
        # Determine new status
        if new_paid <= 0:
            new_status = "Unpaid"
        elif new_paid < total_amount:
            new_status = "Partially Paid"
        else:
            new_status = "Paid"
        
        # Update schedule row
        frappe.db.set_value(
            "SHG Loan Repayment Schedule",
            schedule_row.name,
            {
                "actual_amount_paid": new_paid,
                "outstanding_amount": new_outstanding,
                "status": new_status,
                "payment_entry": None if new_paid <= 0 else schedule_row.payment_entry
            },
            update_modified=False
        )
        
        # Update parent loan balance
        self._update_parent_loan_on_reversal(schedule_row)
    
    def _update_parent_loan_on_reversal(self, schedule_row):
        """Update parent loan document after installment reversal."""
        try:
            if not schedule_row.parent:
                return
            
            # Recalculate total outstanding from all installments
            total_outstanding = frappe.db.sql("""
                SELECT SUM(COALESCE(outstanding_amount, total_amount - COALESCE(actual_amount_paid, 0))) as total
                FROM `tabSHG Loan Repayment Schedule`
                WHERE parent = %s
            """, (schedule_row.parent,), as_dict=True)[0].total or 0.0
            
            # Determine loan status
            if total_outstanding <= 0:
                loan_status = "Fully Paid"
            else:
                # Check if any payments made
                total_paid = frappe.db.sql("""
                    SELECT SUM(COALESCE(actual_amount_paid, 0)) as total
                    FROM `tabSHG Loan Repayment Schedule`
                    WHERE parent = %s
                """, (schedule_row.parent,), as_dict=True)[0].total or 0.0
                
                loan_status = "Partially Paid" if total_paid > 0 else "Disbursed"
            
            frappe.db.set_value(
                "SHG Loan",
                schedule_row.parent,
                {
                    "loan_balance": flt(total_outstanding),
                    "status": loan_status
                },
                update_modified=False
            )
        except Exception as e:
            frappe.log_error(
                title="Parent Loan Update",
                message=f"Failed: {schedule_row.parent}: {str(e)}"
            )
    
    def _update_member_statements_on_cancel(self):
        """
        Update financial statements for all members after cancellation.
        """
        # Collect unique members from allocations
        members = set()
        for allocation in self.allocations:
            if allocation.member:
                members.add(allocation.member)
        
        updated_count = 0
        for member in members:
            try:
                self._update_single_member_statement(member)
                updated_count += 1
            except Exception as e:
                frappe.log_error(
                    title="Member Statement",
                    message=f"Cancel update failed for {member}: {str(e)}"
                )
        
        if updated_count > 0:
            frappe.msgprint(
                _("Updated financial statements for {0} member(s) after cancellation").format(updated_count),
                alert=True,
                indicator="blue"
            )
    
    def process_bulk_payment(self):
        """Process the bulk payment using service layer"""
        try:
            from shg.shg.services.payment.bulk_payment_service import bulk_payment_service
            
            # Process using service layer
            result = bulk_payment_service.process_bulk_payment(
                self.name,
                processed_via="Manual"
            )
            
            # The service layer will have updated the database directly
            # No need to update self here as document is already submitted
            
            # Explicitly update member statements for all affected members
            self._update_member_statements_on_submit()
            
            frappe.msgprint(
                _("Bulk payment processed successfully. Payment Entry: {0}").format(result["payment_entry"]),
                alert=True
            )
            
        except Exception as e:
            # Update status to failed directly in database since doc is submitted
            frappe.db.set_value(
                "SHG Bulk Payment",
                self.name,
                "processing_status",
                "Failed",
                update_modified=False
            )
            frappe.db.set_value(
                "SHG Bulk Payment",
                self.name,
                "remarks",
                f"Processing failed: {str(e)}",
                update_modified=False
            )
            
            frappe.throw(_("Bulk payment processing failed: {0}").format(str(e)))
    
    def _update_member_statements_on_submit(self):
        """
        Update financial statements for all members in this bulk payment.
        Called after successful bulk payment processing.
        """
        # Collect unique members from allocations
        members = set()
        for allocation in self.allocations:
            if allocation.member:
                members.add(allocation.member)
        
        updated_count = 0
        for member in members:
            try:
                self._update_single_member_statement(member)
                updated_count += 1
            except Exception as e:
                frappe.log_error(
                    title="Member Statement",
                    message=f"Update failed for {member}: {str(e)}"
                )
        
        if updated_count > 0:
            frappe.msgprint(
                _("Updated financial statements for {0} member(s)").format(updated_count),
                alert=True,
                indicator="green"
            )
    
    def _update_single_member_statement(self, member: str):
        """
        Update financial statement for a single member.
        
        Args:
            member: Member ID
        """
        try:
            # Try using the member statement utility
            from shg.shg.utils.member_statement_utils import populate_member_statement
            populate_member_statement(member)
        except ImportError:
            # Fallback: update member document directly
            try:
                member_doc = frappe.get_doc("SHG Member", member)
                if hasattr(member_doc, 'update_financial_summary'):
                    member_doc.update_financial_summary()
                elif hasattr(member_doc, 'update_member_statement'):
                    member_doc.update_member_statement()
            except Exception as e:
                frappe.log_error(
                    title="Member Update",
                    message=f"Fallback failed for {member}: {str(e)}"
                )
    
    @frappe.whitelist()
    def auto_allocate_by_oldest_due_date(self):
        """Auto-allocate by oldest due date"""
        try:
            from shg.shg.services.payment.bulk_payment_service import bulk_payment_service
            
            result = bulk_payment_service.auto_allocate_by_oldest_due_date(self.name)
            
            # Refresh the document
            self.reload()
            
            return result
            
        except Exception as e:
            frappe.throw(_("Auto-allocation failed: {0}").format(str(e)))
    
    @frappe.whitelist()
    def process_in_background(self):
        """Process payment in background"""
        try:
            from shg.shg.jobs.bulk_payment_jobs import schedule_bulk_payment_processing
            
            # Schedule background processing
            schedule_bulk_payment_processing(self.name)
            
            self.processing_status = "Processing"
            self.processed_via = "Background Job"
            self.save(ignore_permissions=True)
            
            frappe.msgprint(
                _("Bulk payment scheduled for background processing"),
                alert=True
            )
            
        except Exception as e:
            frappe.throw(_("Failed to schedule background processing: {0}").format(str(e)))
    
    @frappe.whitelist()
    def get_processing_status(self):
        """Get current processing status"""
        try:
            from shg.shg.jobs.bulk_payment_jobs import get_bulk_payment_processing_status
            return get_bulk_payment_processing_status(self.name)
        except Exception as e:
            frappe.throw(_("Failed to get processing status: {0}").format(str(e)))
    
    @frappe.whitelist()
    def validate_integrity(self):
        """Validate document integrity"""
        try:
            from shg.shg.jobs.bulk_payment_jobs import validate_bulk_payment_integrity
            return validate_bulk_payment_integrity(self.name)
        except Exception as e:
            frappe.throw(_("Integrity validation failed: {0}").format(str(e)))
    
    @frappe.whitelist()
    def retry_processing(self):
        """Retry failed processing"""
        try:
            from shg.shg.jobs.bulk_payment_jobs import retry_failed_bulk_payment
            return retry_failed_bulk_payment(self.name)
        except Exception as e:
            frappe.throw(_("Retry failed: {0}").format(str(e)))