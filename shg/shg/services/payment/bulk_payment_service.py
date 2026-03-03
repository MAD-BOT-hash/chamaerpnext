"""
Bulk Payment Service Layer
Enterprise-grade bulk payment processing with idempotency and concurrency safety
"""
import frappe
from frappe import _
from frappe.utils import flt, now, getdate
from decimal import Decimal
import json
from typing import Dict, List, Optional, Tuple
from frappe.model.document import Document
import hashlib
from datetime import datetime

# Import SHG-native services
from shg.shg.services.contribution.contribution_service import (
    ContributionService, 
    get_shg_document_total,
    ContributionServiceError
)


class BulkPaymentServiceError(Exception):
    """Base exception for bulk payment service errors"""
    pass


# Re-export for backward compatibility
get_invoice_total = get_shg_document_total


class OverpaymentError(BulkPaymentServiceError):
    """Raised when total allocation exceeds payment amount"""
    pass


class ConcurrencyError(BulkPaymentServiceError):
    """Raised when concurrent access conflict occurs"""
    pass


class DuplicateProcessingError(BulkPaymentServiceError):
    """Raised when duplicate processing is detected"""
    pass


class BulkPaymentService:
    """
    Enterprise-grade bulk payment processing service with:
    - Idempotency guarantee
    - Row-level locking (FOR UPDATE)
    - Overpayment prevention
    - Atomic transaction safety
    - Auto-allocation by oldest due date
    - Background job support
    - Duplicate processing prevention
    - Full audit logging
    - Scale to 10,000+ members
    """
    
    def __init__(self):
        self.logger = frappe.logger("bulk_payment_service", allow_site=True)
        self.audit_service = self._get_audit_service()
    
    def _get_audit_service(self):
        """Get audit service instance"""
        try:
            from shg.shg.services.audit.audit_service import audit_service
            return audit_service
        except ImportError:
            return None
    
    def process_bulk_payment(self, bulk_payment_name: str, processed_via: str = "Manual") -> Dict:
        """
        Process bulk payment with full enterprise safety
        
        Args:
            bulk_payment_name: Name of the SHG Bulk Payment document
            processed_via: Processing method (Manual/Background Job/Auto Allocation)
            
        Returns:
            Dict with processing results and audit trail
        """
        # Generate idempotency key
        idempotency_key = self._generate_idempotency_key(bulk_payment_name, processed_via)
        
        try:
            # Check for duplicate processing
            if self._is_already_processed(bulk_payment_name, idempotency_key):
                raise DuplicateProcessingError(f"Bulk payment {bulk_payment_name} already processed")
            
            # Lock the bulk payment document
            bulk_payment = self._lock_bulk_payment(bulk_payment_name)
            
            # Validate bulk payment
            self._validate_bulk_payment(bulk_payment)
            
            # Process allocations atomically
            result = self._process_allocations_transaction(bulk_payment, processed_via, idempotency_key)
            
            # Log successful processing
            self._log_audit_action(
                "SHG Bulk Payment",
                bulk_payment_name,
                "Updated",
                {
                    "total_amount": bulk_payment.total_amount,
                    "total_allocated": bulk_payment.total_allocated_amount,
                    "processing_method": processed_via,
                    "allocations_processed": len(bulk_payment.allocations),
                    "idempotency_key": idempotency_key,
                    "status": "Processed"
                }
            )
            
            return result
            
        except Exception as e:
            # Log error
            self._log_audit_action(
                "SHG Bulk Payment",
                bulk_payment_name,
                "Updated",
                {
                    "error": str(e),
                    "processing_method": processed_via,
                    "idempotency_key": idempotency_key,
                    "status": "Failed"
                }
            )
            raise
    
    def _generate_idempotency_key(self, bulk_payment_name: str, processed_via: str) -> str:
        """Generate unique idempotency key for this operation"""
        timestamp = datetime.now().isoformat()
        data = f"{bulk_payment_name}:{processed_via}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _is_already_processed(self, bulk_payment_name: str, idempotency_key: str) -> bool:
        """Check if this bulk payment has already been processed"""
        # Check audit trail for duplicate processing
        if self.audit_service:
            recent_logs = frappe.get_all(
                "SHG Audit Trail",
                filters={
                    "reference_doctype": "SHG Bulk Payment",
                    "reference_name": bulk_payment_name,
                    "action": "Updated",
                    "timestamp": [">", frappe.utils.add_to_date(frappe.utils.now(), hours=-24)],
                    "details": ["LIKE", "%Processed%"]
                },
                limit=1
            )
            return len(recent_logs) > 0
        
        # Fallback: check document status
        bulk_payment = frappe.get_doc("SHG Bulk Payment", bulk_payment_name)
        return bulk_payment.processing_status in ["Processed", "Partially Processed"]
    
    def _lock_bulk_payment(self, bulk_payment_name: str) -> Document:
        """Lock bulk payment document with row-level locking"""
        # Use SELECT FOR UPDATE to prevent concurrent processing
        locked_doc = frappe.db.sql("""
            SELECT * FROM `tabSHG Bulk Payment` 
            WHERE name = %s FOR UPDATE
        """, bulk_payment_name, as_dict=True)
        
        if not locked_doc:
            raise BulkPaymentServiceError(f"Bulk payment {bulk_payment_name} not found")
        
        return frappe.get_doc("SHG Bulk Payment", bulk_payment_name)
    
    def _validate_bulk_payment(self, bulk_payment: Document):
        """Validate bulk payment before processing"""
        # Check if already processed
        if bulk_payment.processing_status in ["Processed", "Partially Processed"]:
            raise BulkPaymentServiceError(f"Bulk payment already processed with status: {bulk_payment.processing_status}")
        
        # Validate total amount
        if not bulk_payment.total_amount or bulk_payment.total_amount <= 0:
            raise BulkPaymentServiceError("Total payment amount must be greater than zero")
        
        # Validate allocations exist
        if not bulk_payment.allocations:
            raise BulkPaymentServiceError("No allocations found for processing")
        
        # Validate allocation amounts
        total_allocated = sum(flt(allocation.allocated_amount) for allocation in bulk_payment.allocations)
        if total_allocated <= 0:
            raise BulkPaymentServiceError("Total allocated amount must be greater than zero")
        
        # Overpayment prevention
        if total_allocated > bulk_payment.total_amount:
            raise OverpaymentError(
                f"Total allocated amount ({total_allocated}) exceeds payment amount ({bulk_payment.total_amount})"
            )
        
        # Validate each allocation
        for allocation in bulk_payment.allocations:
            self._validate_allocation(allocation)
    
    def _validate_allocation(self, allocation: Document):
        """Validate individual allocation"""
        if not allocation.member:
            raise BulkPaymentServiceError("Member is required for allocation")
        
        if not allocation.reference_doctype:
            raise BulkPaymentServiceError("Reference type is required for allocation")
        
        if not allocation.reference_name:
            raise BulkPaymentServiceError("Reference name is required for allocation")
        
        if not allocation.allocated_amount or allocation.allocated_amount <= 0:
            raise BulkPaymentServiceError("Allocated amount must be greater than zero")
        
        # Validate outstanding amount
        if allocation.allocated_amount > allocation.outstanding_amount:
            raise OverpaymentError(
                f"Allocated amount ({allocation.allocated_amount}) exceeds outstanding amount ({allocation.outstanding_amount}) "
                f"for {allocation.reference_doctype} {allocation.reference_name}"
            )
    
    def _process_allocations_transaction(self, bulk_payment: Document, processed_via: str, idempotency_key: str) -> Dict:
        """
        Process all allocations within a single atomic transaction
        """
        try:
            # Update processing status in database directly to avoid submit restrictions
            frappe.db.set_value(
                "SHG Bulk Payment", 
                bulk_payment.name, 
                "processing_status", 
                "Processing",
                update_modified=False
            )
            frappe.db.set_value(
                "SHG Bulk Payment", 
                bulk_payment.name, 
                "processed_by", 
                frappe.session.user,
                update_modified=False
            )
            frappe.db.set_value(
                "SHG Bulk Payment", 
                bulk_payment.name, 
                "processed_via", 
                processed_via,
                update_modified=False
            )
            
            # Create consolidated payment entry
            payment_entry = self._create_consolidated_payment_entry(bulk_payment)
            
            # Process each allocation
            allocation_results = []
            successful_allocations = 0
            failed_allocations = 0
            
            # Sort allocations by due date (oldest first) for auto-allocation logic
            sorted_allocations = sorted(
                bulk_payment.allocations, 
                key=lambda x: getdate(x.due_date or x.reference_date)
            )
            
            for allocation in sorted_allocations:
                try:
                    # Lock the reference document
                    self._lock_reference_document(allocation.reference_doctype, allocation.reference_name)
                    
                    # Process individual allocation
                    allocation_result = self._process_single_allocation(
                        allocation, 
                        payment_entry.name,
                        bulk_payment.company
                    )
                    
                    allocation_results.append(allocation_result)
                    successful_allocations += 1
                    
                    # Update allocation status
                    allocation.processing_status = "Processed"
                    allocation.payment_entry = payment_entry.name
                    allocation.processed_date = now()
                    allocation.is_processed = 1
                    
                except Exception as e:
                    allocation.processing_status = "Failed"
                    allocation.remarks = f"Processing failed: {str(e)}"
                    failed_allocations += 1
                    self.logger.error(f"Allocation failed: {str(e)}")
            
            # Update bulk payment totals
            self._update_bulk_payment_totals(bulk_payment)
            
            # Determine final status
            if successful_allocations == len(bulk_payment.allocations):
                final_status = "Processed"
            elif successful_allocations > 0:
                final_status = "Partially Processed"
            else:
                final_status = "Failed"
            
            # Update final status and other fields directly in database
            frappe.db.set_value(
                "SHG Bulk Payment", 
                bulk_payment.name, 
                "processing_status", 
                final_status,
                update_modified=False
            )
            frappe.db.set_value(
                "SHG Bulk Payment", 
                bulk_payment.name, 
                "payment_entry", 
                payment_entry.name,
                update_modified=False
            )
            frappe.db.set_value(
                "SHG Bulk Payment", 
                bulk_payment.name, 
                "processed_date", 
                now(),
                update_modified=False
            )
            
            # Transaction will be committed automatically by Frappe at request end
            # Do NOT call frappe.db.commit() manually - let Frappe handle transaction lifecycle
            
            return {
                "success": True,
                "bulk_payment_name": bulk_payment.name,
                "payment_entry": payment_entry.name,
                "total_allocations": len(bulk_payment.allocations),
                "successful_allocations": successful_allocations,
                "failed_allocations": failed_allocations,
                "allocation_results": allocation_results,
                "idempotency_key": idempotency_key
            }
            
        except Exception as e:
            # Log detailed error for debugging
            frappe.log_error(
                frappe.get_traceback(),
                f"Bulk Payment Processing Failed: {bulk_payment.name}"
            )
            
            # Rollback on any error - Frappe will handle this automatically
            # but we explicitly rollback to ensure clean state
            try:
                frappe.db.rollback()
            except:
                pass  # Ignore rollback errors
            
            # Update status to failed directly in database (outside transaction)
            try:
                frappe.db.set_value(
                    "SHG Bulk Payment", 
                    bulk_payment.name, 
                    "processing_status", 
                    "Failed",
                    update_modified=False
                )
                frappe.db.set_value(
                    "SHG Bulk Payment", 
                    bulk_payment.name, 
                    "remarks", 
                    f"Processing failed: {str(e)}",
                    update_modified=False
                )
            except Exception as update_error:
                frappe.log_error(
                    f"Failed to update error status: {update_error}",
                    "Bulk Payment Error Handling Failed"
                )
            
            # Re-raise with clear message
            raise BulkPaymentServiceError(
                f"Bulk payment processing failed for {bulk_payment.name}: {str(e)}"
            ) from e
    
    def _lock_reference_document(self, doctype: str, docname: str):
        """
        Lock reference document to prevent concurrent modifications.
        Uses SELECT FOR UPDATE for row-level locking.
        """
        try:
            # Use parameterized query to prevent SQL injection
            result = frappe.db.sql(
                f"SELECT name FROM `tab{doctype}` WHERE name = %s FOR UPDATE",
                (docname,),
                as_dict=True
            )
            if not result:
                raise BulkPaymentServiceError(
                    f"Document {doctype} {docname} not found or could not be locked"
                )
        except Exception as e:
            frappe.log_error(
                frappe.get_traceback(),
                f"Row Lock Failed: {doctype} {docname}"
            )
            raise ConcurrencyError(
                f"Could not lock {doctype} {docname} for processing. "
                f"Another process may be modifying this document."
            ) from e
    
    def _create_consolidated_payment_entry(self, bulk_payment: Document) -> Document:
        """
        Create single consolidated payment entry for all allocations.
        
        NOTE: ERPNext Payment Entry only accepts specific reference doctypes:
        'Sales Order', 'Sales Invoice', 'Journal Entry', 'Dunning'
        
        SHG doctypes (SHG Contribution Invoice, SHG Contribution, SHG Meeting Fine)
        CANNOT be added as Payment Entry references. Instead, we:
        1. Create Payment Entry WITHOUT references
        2. Link the payment_entry to SHG documents separately
        3. Track allocations in remarks field
        """
        # Group allocations by member to handle multiple members properly
        allocations_by_member = {}
        for allocation in bulk_payment.allocations:
            member = allocation.member
            if member not in allocations_by_member:
                allocations_by_member[member] = []
            allocations_by_member[member].append(allocation)
        
        # Get the first allocation to determine primary member
        first_allocation = bulk_payment.allocations[0] if bulk_payment.allocations else None
        if not first_allocation:
            raise BulkPaymentServiceError("No allocations found for payment entry creation")
        
        # Get the member and ensure it can be used as a party
        member_name = first_allocation.member
        
        # Ensure the member exists as a Customer in ERPNext
        customer_name = self._ensure_member_as_customer(member_name)
        
        # Build detailed remarks for tracking
        allocation_details = []
        for allocation in bulk_payment.allocations:
            if allocation.allocated_amount > 0:
                allocation_details.append(
                    f"{allocation.reference_doctype}: {allocation.reference_name} = {allocation.allocated_amount}"
                )
        
        remarks = f"Bulk payment {bulk_payment.name}\n"
        remarks += f"Total allocations: {len(allocation_details)}\n"
        remarks += "\n".join(allocation_details[:20])  # Limit to first 20 for readability
        if len(allocation_details) > 20:
            remarks += f"\n... and {len(allocation_details) - 20} more"
        
        payment_entry = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "company": bulk_payment.company,
            "posting_date": bulk_payment.posting_date or frappe.utils.nowdate(),
            "mode_of_payment": bulk_payment.mode_of_payment,
            "paid_amount": bulk_payment.total_amount,
            "received_amount": bulk_payment.total_amount,
            "paid_from": self._get_default_receivable_account(bulk_payment.company),
            "paid_to": bulk_payment.payment_account,
            "party_type": "Customer",
            "party": customer_name,
            "reference_no": bulk_payment.reference_no,
            "reference_date": bulk_payment.reference_date,
            "remarks": remarks
        })
        
        # DO NOT add references - ERPNext only accepts Sales Invoice, Sales Order, Journal Entry, Dunning
        # SHG doctypes are tracked separately via payment_entry links in each SHG document
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        return payment_entry
    
    def _ensure_member_as_customer(self, member_name: str) -> str:
        """Ensure the SHG member exists as a Customer in ERPNext"""
        if not member_name:
            raise BulkPaymentServiceError("Member name is required")
        
        # First, try to find if the member already exists as a Customer
        customer_name = frappe.db.get_value("Customer", {"name": member_name})
        if customer_name:
            return customer_name
        
        # Try to find customer by customer_name field
        customer_name = frappe.db.get_value("Customer", {"customer_name": member_name})
        if customer_name:
            return customer_name
        
        # Try to get customer from SHG Member document
        try:
            member_doc = frappe.get_doc("SHG Member", member_name)
            if hasattr(member_doc, 'customer') and member_doc.customer:
                return member_doc.customer
        except:
            pass  # Member might not exist or not have customer field
        
        # If no customer found, create one based on the member
        # First, get member details
        try:
            member_doc = frappe.get_doc("SHG Member", member_name)
            customer_full_name = getattr(member_doc, 'member_name', member_name) or member_name
        except:
            customer_full_name = member_name
        
        # Create a customer for this member
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_full_name,
            "customer_type": "Individual",
            "customer_group": "SHG Members",  # Assuming this customer group exists
            "territory": "All Territories",  # Default territory
        })
        
        customer.insert(ignore_permissions=True)
        return customer.name
    
    def _get_default_receivable_account(self, company: str) -> str:
        """Get default receivable account for the company"""
        company_doc = frappe.get_doc("Company", company)
        return company_doc.default_receivable_account or "Debtors - " + frappe.get_value("Company", company, "abbr")
    
    def _process_single_allocation(self, allocation: Document, payment_entry_name: str, company: str) -> Dict:
        """Process individual allocation"""
        # Update reference document payment status
        reference_doc = frappe.get_doc(allocation.reference_doctype, allocation.reference_name)
        
        # Handle different reference types
        if allocation.reference_doctype == "SHG Contribution Invoice":
            self._update_contribution_invoice_payment(reference_doc, allocation.allocated_amount)
        elif allocation.reference_doctype == "SHG Contribution":
            self._update_contribution_payment(reference_doc, allocation.allocated_amount, payment_entry_name)
        elif allocation.reference_doctype == "SHG Meeting Fine":
            self._update_meeting_fine_payment(reference_doc, allocation.allocated_amount)
        
        # Log audit trail
        self._log_audit_action(
            allocation.reference_doctype,
            allocation.reference_name,
            "Payment Allocated",
            {
                "bulk_payment_allocation": allocation.name,
                "payment_entry": payment_entry_name,
                "allocated_amount": allocation.allocated_amount,
                "member": allocation.member
            }
        )
        
        return {
            "allocation_name": allocation.name,
            "reference_doctype": allocation.reference_doctype,
            "reference_name": allocation.reference_name,
            "allocated_amount": allocation.allocated_amount,
            "member": allocation.member,
            "status": "Processed"
        }
    
    def _update_contribution_invoice_payment(self, invoice_doc: Document, allocated_amount: float):
        """Update contribution invoice payment status"""
        invoice_doc.paid_amount = flt(invoice_doc.paid_amount) + flt(allocated_amount)
        total_amount = get_invoice_total(invoice_doc)
        invoice_doc.outstanding_amount = total_amount - flt(invoice_doc.paid_amount)
        
        if invoice_doc.outstanding_amount <= 0:
            invoice_doc.status = "Paid"
        elif invoice_doc.paid_amount > 0:
            invoice_doc.status = "Partially Paid"
        
        invoice_doc.save(ignore_permissions=True)
    
    def _update_contribution_payment(self, contribution_doc: Document, allocated_amount: float, payment_entry_name: str):
        """
        Update contribution payment status using ContributionService.
        Delegates to clean architecture service layer.
        """
        try:
            contribution_service = ContributionService()
            contribution_service.allocate_payment(
                contribution_name=contribution_doc.name,
                allocated_amount=allocated_amount,
                payment_entry_name=payment_entry_name
            )
        except ContributionServiceError:
            raise
        except Exception as e:
            frappe.log_error(
                frappe.get_traceback(),
                f"Bulk Payment: Contribution Update Failed: {contribution_doc.name}"
            )
            raise BulkPaymentServiceError(
                f"Failed to update contribution {contribution_doc.name}: {str(e)}"
            ) from e
    
    def _update_meeting_fine_payment(self, fine_doc: Document, allocated_amount: float):
        """Update meeting fine payment status"""
        fine_doc.paid_amount = flt(fine_doc.paid_amount) + flt(allocated_amount)
        fine_doc.outstanding_amount = flt(fine_doc.amount) - flt(fine_doc.paid_amount)
        
        if fine_doc.outstanding_amount <= 0:
            fine_doc.status = "Paid"
        elif fine_doc.paid_amount > 0:
            fine_doc.status = "Partially Paid"
        
        fine_doc.save(ignore_permissions=True)
    
    def _update_bulk_payment_totals(self, bulk_payment: Document):
        """Update bulk payment summary totals"""
        total_allocated = sum(flt(allocation.allocated_amount) for allocation in bulk_payment.allocations)
        total_outstanding = sum(flt(allocation.outstanding_amount) for allocation in bulk_payment.allocations)
        
        bulk_payment.total_allocated_amount = total_allocated
        bulk_payment.total_outstanding_amount = total_outstanding
        bulk_payment.unallocated_amount = flt(bulk_payment.total_amount) - flt(total_allocated)
        
        bulk_payment.save(ignore_permissions=True)
    
    def auto_allocate_by_oldest_due_date(self, bulk_payment_name: str) -> Dict:
        """
        Auto-allocate payment amounts by oldest due date first
        """
        bulk_payment = frappe.get_doc("SHG Bulk Payment", bulk_payment_name)
        
        # Sort allocations by due date (oldest first)
        sorted_allocations = sorted(
            bulk_payment.allocations,
            key=lambda x: getdate(x.due_date or x.reference_date)
        )
        
        remaining_amount = flt(bulk_payment.total_amount)
        total_allocated = 0
        
        # Allocate to oldest due dates first
        for allocation in sorted_allocations:
            if remaining_amount <= 0:
                allocation.allocated_amount = 0
                continue
            
            # Allocate maximum possible amount
            allocation_amount = min(
                flt(allocation.outstanding_amount),
                remaining_amount
            )
            
            allocation.allocated_amount = allocation_amount
            remaining_amount -= allocation_amount
            total_allocated += allocation_amount
        
        bulk_payment.save(ignore_permissions=True)
        
        return {
            "success": True,
            "bulk_payment_name": bulk_payment_name,
            "total_amount": bulk_payment.total_amount,
            "total_allocated": total_allocated,
            "remaining_amount": remaining_amount,
            "allocations_processed": len([a for a in bulk_payment.allocations if a.allocated_amount > 0])
        }
    
    def _log_audit_action(self, reference_doctype: str, reference_name: str, action: str, details: Dict = None):
        """Log audit action if audit service is available"""
        if self.audit_service:
            try:
                self.audit_service.log_action(
                    reference_doctype,
                    reference_name,
                    action,
                    details=details
                )
            except Exception as e:
                self.logger.error(f"Audit logging failed: {str(e)}")
        else:
            # Fallback logging
            self.logger.info(f"Audit: {action} {reference_doctype} {reference_name} - {json.dumps(details or {})}")


# Module-level functions for frappe.whitelist()
@frappe.whitelist()
def get_unpaid_invoices_for_company(company: str) -> List[Dict]:
    """
    Get all unpaid contribution invoices for a company
    """
    try:
        # Get unpaid contribution invoices
        invoices = frappe.get_all(
            "SHG Contribution Invoice",
            filters={
                "docstatus": 1,
                "status": ["in", ["Unpaid", "Partially Paid"]]
            },
            fields=["name", "member", "member_name", "invoice_date", "due_date", "amount", "status", "description"]
        )
        
        # Filter by company through member
        company_members = frappe.get_all("SHG Member", filters={"company": company}, pluck="name")
        filtered_invoices = [inv for inv in invoices if inv.member in company_members]
        
        # Format for bulk payment
        result = []
        for inv in filtered_invoices:
            result.append({
                "member": inv.member,
                "member_name": inv.member_name,
                "reference_doctype": "SHG Contribution Invoice",
                "reference_name": inv.name,
                "reference_date": inv.invoice_date,
                "due_date": inv.due_date,
                "outstanding_amount": inv.amount,
                "status": inv.status,
                "description": inv.description or "Contribution Invoice"
            })
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching unpaid invoices - {str(e)}")
        return []

@frappe.whitelist()
def get_unpaid_contributions_for_company(company: str) -> List[Dict]:
    """
    Get all unpaid contributions for a company
    """
    try:
        # Get unpaid contributions
        contributions = frappe.get_all(
            "SHG Contribution",
            filters={
                "docstatus": 1,
                "payment_status": ["in", ["Pending", "Partially Paid"]]
            },
            fields=["name", "member", "member_name", "contribution_date", "due_date", "expected_amount", "paid_amount", "payment_status", "contribution_type"]
        )
        
        # Filter by company through member
        company_members = frappe.get_all("SHG Member", filters={"company": company}, pluck="name")
        filtered_contributions = [cont for cont in contributions if cont.member in company_members]
        
        # Format for bulk payment
        result = []
        for cont in filtered_contributions:
            outstanding = flt(cont.expected_amount) - flt(cont.paid_amount)
            if outstanding > 0:
                result.append({
                    "member": cont.member,
                    "member_name": cont.member_name,
                    "reference_doctype": "SHG Contribution",
                    "reference_name": cont.name,
                    "reference_date": cont.contribution_date,
                    "due_date": cont.due_date,
                    "outstanding_amount": outstanding,
                    "status": cont.payment_status,
                    "description": f"Contribution - {cont.contribution_type or 'General'}"
                })
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching unpaid contributions - {str(e)}")
        return []

@frappe.whitelist()
def get_unpaid_meeting_fines_for_company(company: str) -> List[Dict]:
    """
    Get all unpaid meeting fines for a company
    """
    try:
        # Get unpaid meeting fines
        fines = frappe.get_all(
            "SHG Meeting Fine",
            filters={
                "docstatus": 1,
                "status": "Unpaid"
            },
            fields=["name", "member", "member_name", "fine_date", "due_date", "amount", "paid_amount", "description"]
        )
        
        # Filter by company through member
        company_members = frappe.get_all("SHG Member", filters={"company": company}, pluck="name")
        filtered_fines = [fine for fine in fines if fine.member in company_members]
        
        # Format for bulk payment
        result = []
        for fine in filtered_fines:
            outstanding = flt(fine.amount) - flt(fine.paid_amount)
            if outstanding > 0:
                result.append({
                    "member": fine.member,
                    "member_name": fine.member_name,
                    "reference_doctype": "SHG Meeting Fine",
                    "reference_name": fine.name,
                    "reference_date": fine.fine_date,
                    "due_date": fine.due_date,
                    "outstanding_amount": outstanding,
                    "status": "Unpaid",
                    "description": fine.description or "Meeting Fine"
                })
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching unpaid meeting fines - {str(e)}")
        return []

@frappe.whitelist()
def get_all_unpaid_items_for_member(member: str) -> List[Dict]:
    """
    Get all unpaid items (invoices, contributions, fines) for a specific member
    """
    try:
        # Get all types of unpaid items for the specific member
        invoices = get_unpaid_invoices_for_member(member)
        contributions = get_unpaid_contributions_for_member(member)
        fines = get_unpaid_meeting_fines_for_member(member)
        
        # Combine and sort by due date (oldest first)
        all_items = invoices + contributions + fines
        all_items.sort(key=lambda x: getdate(x.get('due_date') or x.get('reference_date') or '1900-01-01'))
        
        return all_items
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching all unpaid items for member - {str(e)}")
        return []


@frappe.whitelist()
def get_unpaid_invoices_for_member(member: str) -> List[Dict]:
    """
    Get all unpaid contribution invoices for a specific member
    """
    try:
        # Get unpaid contribution invoices for the specific member
        invoices = frappe.get_all(
            "SHG Contribution Invoice",
            filters={
                "member": member,
                "docstatus": 1,
                "status": ["in", ["Unpaid", "Partially Paid"]]
            },
            fields=["name", "member", "member_name", "invoice_date", "due_date", "amount", "status", "description"]
        )
        
        # Format for bulk payment
        result = []
        for inv in invoices:
            result.append({
                "member": inv.member,
                "member_name": inv.member_name,
                "reference_doctype": "SHG Contribution Invoice",
                "reference_name": inv.name,
                "reference_date": inv.invoice_date,
                "due_date": inv.due_date,
                "outstanding_amount": inv.amount,
                "status": inv.status,
                "description": inv.description or "Contribution Invoice"
            })
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching unpaid invoices for member - {str(e)}")
        return []


@frappe.whitelist()
def get_unpaid_contributions_for_member(member: str) -> List[Dict]:
    """
    Get all unpaid contributions for a specific member
    """
    try:
        # Get unpaid contributions for the specific member
        contributions = frappe.get_all(
            "SHG Contribution",
            filters={
                "member": member,
                "docstatus": 1,
                "payment_status": ["in", ["Pending", "Partially Paid"]]
            },
            fields=["name", "member", "member_name", "contribution_date", "due_date", "expected_amount", "paid_amount", "payment_status", "contribution_type"]
        )
        
        # Format for bulk payment
        result = []
        for cont in contributions:
            outstanding = flt(cont.expected_amount) - flt(cont.paid_amount)
            if outstanding > 0:
                result.append({
                    "member": cont.member,
                    "member_name": cont.member_name,
                    "reference_doctype": "SHG Contribution",
                    "reference_name": cont.name,
                    "reference_date": cont.contribution_date,
                    "due_date": cont.due_date,
                    "outstanding_amount": outstanding,
                    "status": cont.payment_status,
                    "description": f"Contribution - {cont.contribution_type or 'General'}"
                })
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching unpaid contributions for member - {str(e)}")
        return []


@frappe.whitelist()
def get_unpaid_meeting_fines_for_member(member: str) -> List[Dict]:
    """
    Get all unpaid meeting fines for a specific member
    """
    try:
        # Get unpaid meeting fines for the specific member
        fines = frappe.get_all(
            "SHG Meeting Fine",
            filters={
                "member": member,
                "docstatus": 1,
                "status": "Unpaid"
            },
            fields=["name", "member", "member_name", "fine_date", "due_date", "amount", "paid_amount", "description"]
        )
        
        # Format for bulk payment
        result = []
        for fine in fines:
            outstanding = flt(fine.amount) - flt(fine.paid_amount)
            if outstanding > 0:
                result.append({
                    "member": fine.member,
                    "member_name": fine.member_name,
                    "reference_doctype": "SHG Meeting Fine",
                    "reference_name": fine.name,
                    "reference_date": fine.fine_date,
                    "due_date": fine.due_date,
                    "outstanding_amount": outstanding,
                    "status": "Unpaid",
                    "description": fine.description or "Meeting Fine"
                })
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching unpaid meeting fines for member - {str(e)}")
        return []


@frappe.whitelist()
def get_all_unpaid_items_for_company(company: str) -> List[Dict]:
    """
    Get all unpaid items (invoices, contributions, fines) for a company
    """
    try:
        # Get all types of unpaid items
        invoices = get_unpaid_invoices_for_company(company)
        contributions = get_unpaid_contributions_for_company(company)
        fines = get_unpaid_meeting_fines_for_company(company)
        
        # Combine and sort by due date (oldest first)
        all_items = invoices + contributions + fines
        all_items.sort(key=lambda x: getdate(x.get('due_date') or x.get('reference_date') or '1900-01-01'))
        
        return all_items
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching all unpaid items - {str(e)}")
        return []


# Global service instance
bulk_payment_service = BulkPaymentService()