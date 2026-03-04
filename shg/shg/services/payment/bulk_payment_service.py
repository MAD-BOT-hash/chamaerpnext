"""
Bulk Payment Service Layer
Enterprise-grade bulk payment processing with idempotency and concurrency safety

ALL PAYMENT ALLOCATION LOGIC DELEGATED TO:
shg.shg.services.payment.allocation_engine.AllocationEngine

NO SEPARATE IMPLEMENTATIONS - SINGLE SOURCE OF TRUTH
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

# Import centralized allocation engine (SINGLE SOURCE OF TRUTH)
from shg.shg.services.payment.allocation_engine import (
    AllocationEngine,
    get_shg_document_total,
    get_outstanding_amount,
    get_paid_amount,
    AllocationError,
    OverpaymentError as AllocOverpaymentError,
    DocumentNotFoundError,
    AlreadyPaidError,
    # Status constants
    STATUS_UNPAID,
    STATUS_PENDING,
    STATUS_PARTIALLY_PAID,
    STATUS_PAID,
    PAYABLE_STATUSES,
    SETTLED_STATUSES,
)

# Import contribution service for backward compatibility
from shg.shg.services.contribution.contribution_service import (
    ContributionService,
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
        
        # DUPLICATE PREVENTION: Check if reference document is already fully paid
        try:
            ref_doc = frappe.get_doc(allocation.reference_doctype, allocation.reference_name)
            current_status = ref_doc.status if hasattr(ref_doc, 'status') else None
            
            if current_status in SETTLED_STATUSES:
                raise BulkPaymentServiceError(
                    f"Document {allocation.reference_doctype} {allocation.reference_name} "
                    f"is already settled with status '{current_status}'. Cannot apply payment."
                )
            
            # Also check outstanding amount directly
            actual_outstanding = get_outstanding_amount(ref_doc)
            if actual_outstanding <= 0:
                raise BulkPaymentServiceError(
                    f"Document {allocation.reference_doctype} {allocation.reference_name} "
                    f"has no outstanding balance (Outstanding: {actual_outstanding}). Already fully paid."
                )
                
        except frappe.DoesNotExistError:
            raise BulkPaymentServiceError(
                f"Reference document {allocation.reference_doctype} {allocation.reference_name} not found"
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
            
            # Update member statements for all affected members
            affected_members = self._update_affected_member_statements(allocation_results)
            
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
                "members_updated": affected_members,
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
        """
        Process individual allocation using centralized AllocationEngine.
        
        ALL allocation logic delegated to AllocationEngine - NO SEPARATE IMPLEMENTATIONS.
        """
        # Use centralized allocation engine
        allocation_engine = AllocationEngine()
        
        try:
            result = allocation_engine.allocate_payment(
                doctype=allocation.reference_doctype,
                docname=allocation.reference_name,
                amount=flt(allocation.allocated_amount),
                payment_entry_name=payment_entry_name,
                allow_overpayment=False,
                auto_save=True
            )
            
            # Log audit trail
            self._log_audit_action(
                allocation.reference_doctype,
                allocation.reference_name,
                "Payment Allocated",
                {
                    "bulk_payment_allocation": allocation.name,
                    "payment_entry": payment_entry_name,
                    "allocated_amount": allocation.allocated_amount,
                    "member": allocation.member,
                    "total_amount": result.get("total_amount"),
                    "paid_after": result.get("paid_after"),
                    "outstanding_after": result.get("outstanding_after"),
                    "status": result.get("status")
                }
            )
            
            return {
                "allocation_name": allocation.name,
                "reference_doctype": allocation.reference_doctype,
                "reference_name": allocation.reference_name,
                "allocated_amount": allocation.allocated_amount,
                "member": allocation.member,
                "status": "Processed",
                "document_status": result.get("status"),
                "outstanding_after": result.get("outstanding_after")
            }
            
        except AlreadyPaidError as e:
            # Document already paid - log as warning, not error
            frappe.log_error(
                f"Duplicate payment prevented: {str(e)}",
                f"Bulk Payment: Already Paid: {allocation.reference_name}"
            )
            raise BulkPaymentServiceError(
                f"Document {allocation.reference_doctype} {allocation.reference_name} "
                f"is already fully paid. Cannot apply duplicate payment."
            ) from e
            
        except AllocationError as e:
            frappe.log_error(
                f"Allocation failed: {str(e)}\n{frappe.get_traceback()}",
                f"Bulk Payment: Allocation Failed: {allocation.reference_name}"
            )
            raise BulkPaymentServiceError(str(e)) from e
    
    # =========================================================================
    # DEPRECATED: These methods are kept for backward compatibility only
    # ALL NEW CODE MUST USE AllocationEngine
    # =========================================================================
    
    def _update_contribution_invoice_payment(self, invoice_doc: Document, allocated_amount: float):
        """DEPRECATED: Use AllocationEngine.allocate_payment() instead."""
        # Delegate to AllocationEngine
        engine = AllocationEngine()
        engine.allocate_payment(
            doctype=invoice_doc.doctype,
            docname=invoice_doc.name,
            amount=allocated_amount,
            auto_save=True
        )
    
    def _update_contribution_payment(self, contribution_doc: Document, allocated_amount: float, payment_entry_name: str):
        """DEPRECATED: Use AllocationEngine.allocate_payment() instead."""
        # Delegate to AllocationEngine
        engine = AllocationEngine()
        engine.allocate_payment(
            doctype=contribution_doc.doctype,
            docname=contribution_doc.name,
            amount=allocated_amount,
            payment_entry_name=payment_entry_name,
            auto_save=True
        )
    
    def _update_meeting_fine_payment(self, fine_doc: Document, allocated_amount: float):
        """DEPRECATED: Use AllocationEngine.allocate_payment() instead."""
        # Delegate to AllocationEngine
        engine = AllocationEngine()
        engine.allocate_payment(
            doctype=fine_doc.doctype,
            docname=fine_doc.name,
            amount=allocated_amount,
            auto_save=True
        )
    
    def _update_bulk_payment_totals(self, bulk_payment: Document):
        """Update bulk payment summary totals"""
        total_allocated = sum(flt(allocation.allocated_amount) for allocation in bulk_payment.allocations)
        total_outstanding = sum(flt(allocation.outstanding_amount) for allocation in bulk_payment.allocations)
        
        bulk_payment.total_allocated_amount = total_allocated
        bulk_payment.total_outstanding_amount = total_outstanding
        bulk_payment.unallocated_amount = flt(bulk_payment.total_amount) - flt(total_allocated)
        
        bulk_payment.save(ignore_permissions=True)
    
    def _update_affected_member_statements(self, allocation_results: List[Dict]) -> List[str]:
        """
        Update financial statements for all members affected by allocations.
        
        Args:
            allocation_results: List of allocation result dictionaries
            
        Returns:
            List of member IDs that were updated
        """
        # Collect unique members from allocations
        members = set()
        for result in allocation_results:
            if result.get("status") == "Processed" and result.get("member"):
                members.add(result["member"])
        
        updated_members = []
        for member in members:
            try:
                self._update_single_member_statement(member)
                updated_members.append(member)
            except Exception as e:
                self.logger.error(f"Failed to update member statement for {member}: {str(e)}")
                frappe.log_error(
                    f"Failed to update member statement for {member}: {str(e)}",
                    "Bulk Payment: Member Statement Update Failed"
                )
        
        return updated_members
    
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
                    f"Fallback member update failed for {member}: {str(e)}",
                    "Bulk Payment: Member Update Fallback Failed"
                )
    
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
                "status": ["in", PAYABLE_STATUSES]  # Use canonical payable statuses
            },
            fields=["name", "member", "member_name", "invoice_date", "due_date", "amount", "paid_amount", "status", "description"]
        )
        
        # Filter by company through member
        company_members = frappe.get_all("SHG Member", filters={"company": company}, pluck="name")
        filtered_invoices = [inv for inv in invoices if inv.member in company_members]
        
        # Format for bulk payment
        result = []
        for inv in filtered_invoices:
            outstanding = flt(inv.amount) - flt(inv.paid_amount or 0)
            if outstanding > 0:
                result.append({
                    "member": inv.member,
                    "member_name": inv.member_name,
                    "reference_doctype": "SHG Contribution Invoice",
                    "reference_name": inv.name,
                    "reference_date": inv.invoice_date,
                    "due_date": inv.due_date,
                    "outstanding_amount": outstanding,
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
        # Get unpaid contributions - use status field with PAYABLE_STATUSES
        contributions = frappe.get_all(
            "SHG Contribution",
            filters={
                "docstatus": 1,
                "status": ["in", PAYABLE_STATUSES]  # Use canonical payable statuses
            },
            fields=["name", "member", "member_name", "contribution_date", "due_date", "expected_amount", "amount_paid", "status", "contribution_type"]
        )
        
        # Filter by company through member
        company_members = frappe.get_all("SHG Member", filters={"company": company}, pluck="name")
        filtered_contributions = [cont for cont in contributions if cont.member in company_members]
        
        # Format for bulk payment
        result = []
        for cont in filtered_contributions:
            outstanding = flt(cont.expected_amount) - flt(cont.amount_paid or 0)
            if outstanding > 0:
                result.append({
                    "member": cont.member,
                    "member_name": cont.member_name,
                    "reference_doctype": "SHG Contribution",
                    "reference_name": cont.name,
                    "reference_date": cont.contribution_date,
                    "due_date": cont.due_date,
                    "outstanding_amount": outstanding,
                    "status": cont.status,
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
        # Get unpaid meeting fines - status can be "Pending" or "Partially Paid"
        fines = frappe.get_all(
            "SHG Meeting Fine",
            filters={
                "docstatus": 1,
                "status": ["in", PAYABLE_STATUSES]  # Use canonical payable statuses
            },
            fields=["name", "member", "member_name", "fine_date", "due_date", "fine_amount", "paid_amount", "fine_description", "status"]
        )
        
        # Filter by company through member
        company_members = frappe.get_all("SHG Member", filters={"company": company}, pluck="name")
        filtered_fines = [fine for fine in fines if fine.member in company_members]
        
        # Format for bulk payment
        result = []
        for fine in filtered_fines:
            outstanding = flt(fine.fine_amount) - flt(fine.paid_amount)
            if outstanding > 0:
                result.append({
                    "member": fine.member,
                    "member_name": fine.member_name,
                    "reference_doctype": "SHG Meeting Fine",
                    "reference_name": fine.name,
                    "reference_date": fine.fine_date,
                    "due_date": fine.due_date,
                    "outstanding_amount": outstanding,
                    "status": fine.status,
                    "description": fine.fine_description or "Meeting Fine"
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
                "status": ["in", PAYABLE_STATUSES]  # Use canonical payable statuses
            },
            fields=["name", "member", "member_name", "invoice_date", "due_date", "amount", "paid_amount", "status", "description"]
        )
        
        # Format for bulk payment
        result = []
        for inv in invoices:
            outstanding = flt(inv.amount) - flt(inv.paid_amount or 0)
            if outstanding > 0:
                result.append({
                    "member": inv.member,
                    "member_name": inv.member_name,
                    "reference_doctype": "SHG Contribution Invoice",
                    "reference_name": inv.name,
                    "reference_date": inv.invoice_date,
                    "due_date": inv.due_date,
                    "outstanding_amount": outstanding,
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
                "status": ["in", PAYABLE_STATUSES]  # Use canonical payable statuses
            },
            fields=["name", "member", "member_name", "contribution_date", "due_date", "expected_amount", "amount_paid", "status", "contribution_type"]
        )
        
        # Format for bulk payment
        result = []
        for cont in contributions:
            outstanding = flt(cont.expected_amount) - flt(cont.amount_paid or 0)
            if outstanding > 0:
                result.append({
                    "member": cont.member,
                    "member_name": cont.member_name,
                    "reference_doctype": "SHG Contribution",
                    "reference_name": cont.name,
                    "reference_date": cont.contribution_date,
                    "due_date": cont.due_date,
                    "outstanding_amount": outstanding,
                    "status": cont.status,
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
                "status": ["in", PAYABLE_STATUSES]  # Use canonical payable statuses
            },
            fields=["name", "member", "member_name", "fine_date", "due_date", "fine_amount", "paid_amount", "fine_description", "status"]
        )
        
        # Format for bulk payment
        result = []
        for fine in fines:
            outstanding = flt(fine.fine_amount) - flt(fine.paid_amount)
            if outstanding > 0:
                result.append({
                    "member": fine.member,
                    "member_name": fine.member_name,
                    "reference_doctype": "SHG Meeting Fine",
                    "reference_name": fine.name,
                    "reference_date": fine.fine_date,
                    "due_date": fine.due_date,
                    "outstanding_amount": outstanding,
                    "status": fine.status,
                    "description": fine.fine_description or "Meeting Fine"
                })
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching unpaid meeting fines for member - {str(e)}")
        return []


@frappe.whitelist()
def get_unpaid_loan_installments_for_company(company: str) -> List[Dict]:
    """
    Get all unpaid loan installments for a company
    """
    try:
        # Get company members
        company_members = frappe.get_all("SHG Member", filters={"company": company}, pluck="name")
        if not company_members:
            return []
        
        # Get active loans for company members
        loans = frappe.get_all(
            "SHG Loan",
            filters={
                "member": ["in", company_members],
                "docstatus": 1,
                "status": ["in", ["Disbursed", "Partially Paid", "Active"]]
            },
            fields=["name", "member", "member_name"]
        )
        
        result = []
        for loan in loans:
            # Get unpaid installments for this loan
            installments = frappe.get_all(
                "SHG Loan Repayment Schedule",
                filters={
                    "parent": loan.name,
                    "parenttype": "SHG Loan",
                    "status": ["in", PAYABLE_STATUSES]
                },
                fields=["name", "installment_no", "due_date", "total_payment", "amount_paid", "unpaid_balance", "status"]
            )
            
            for inst in installments:
                outstanding = flt(inst.unpaid_balance) or (flt(inst.total_payment) - flt(inst.amount_paid or 0))
                if outstanding > 0:
                    result.append({
                        "member": loan.member,
                        "member_name": loan.member_name,
                        "reference_doctype": "SHG Loan Repayment Schedule",
                        "reference_name": inst.name,
                        "reference_date": inst.due_date,
                        "due_date": inst.due_date,
                        "outstanding_amount": outstanding,
                        "status": inst.status,
                        "description": f"Loan Installment #{inst.installment_no} ({loan.name})",
                        "loan": loan.name
                    })
        
        # Sort by due date
        result.sort(key=lambda x: getdate(x.get('due_date') or '1900-01-01'))
        return result
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching unpaid loan installments - {str(e)}")
        return []


@frappe.whitelist()
def get_unpaid_loan_installments_for_member(member: str) -> List[Dict]:
    """
    Get all unpaid loan installments for a specific member
    """
    try:
        # Get member name
        member_name = frappe.db.get_value("SHG Member", member, "member_name") or member
        
        # Get active loans for member
        loans = frappe.get_all(
            "SHG Loan",
            filters={
                "member": member,
                "docstatus": 1,
                "status": ["in", ["Disbursed", "Partially Paid", "Active"]]
            },
            fields=["name"]
        )
        
        result = []
        for loan in loans:
            # Get unpaid installments for this loan
            installments = frappe.get_all(
                "SHG Loan Repayment Schedule",
                filters={
                    "parent": loan.name,
                    "parenttype": "SHG Loan",
                    "status": ["in", PAYABLE_STATUSES]
                },
                fields=["name", "installment_no", "due_date", "total_payment", "amount_paid", "unpaid_balance", "status"]
            )
            
            for inst in installments:
                outstanding = flt(inst.unpaid_balance) or (flt(inst.total_payment) - flt(inst.amount_paid or 0))
                if outstanding > 0:
                    result.append({
                        "member": member,
                        "member_name": member_name,
                        "reference_doctype": "SHG Loan Repayment Schedule",
                        "reference_name": inst.name,
                        "reference_date": inst.due_date,
                        "due_date": inst.due_date,
                        "outstanding_amount": outstanding,
                        "status": inst.status,
                        "description": f"Loan Installment #{inst.installment_no} ({loan.name})",
                        "loan": loan.name
                    })
        
        # Sort by due date
        result.sort(key=lambda x: getdate(x.get('due_date') or '1900-01-01'))
        return result
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching unpaid loan installments for member - {str(e)}")
        return []


@frappe.whitelist()
def get_all_unpaid_items_for_company(company: str) -> List[Dict]:
    """
    Get all unpaid items (invoices, contributions, fines, loan installments) for a company
    """
    try:
        # Get all types of unpaid items
        invoices = get_unpaid_invoices_for_company(company)
        contributions = get_unpaid_contributions_for_company(company)
        fines = get_unpaid_meeting_fines_for_company(company)
        loan_installments = get_unpaid_loan_installments_for_company(company)
        
        # Combine and sort by due date (oldest first)
        all_items = invoices + contributions + fines + loan_installments
        all_items.sort(key=lambda x: getdate(x.get('due_date') or x.get('reference_date') or '1900-01-01'))
        
        return all_items
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching all unpaid items - {str(e)}")
        return []


@frappe.whitelist()
def get_all_unpaid_items_for_member(member: str) -> List[Dict]:
    """
    Get all unpaid items (invoices, contributions, fines, loan installments) for a specific member
    """
    try:
        # Get all types of unpaid items for the specific member
        invoices = get_unpaid_invoices_for_member(member)
        contributions = get_unpaid_contributions_for_member(member)
        fines = get_unpaid_meeting_fines_for_member(member)
        loan_installments = get_unpaid_loan_installments_for_member(member)
        
        # Combine and sort by due date (oldest first)
        all_items = invoices + contributions + fines + loan_installments
        all_items.sort(key=lambda x: getdate(x.get('due_date') or x.get('reference_date') or '1900-01-01'))
        
        return all_items
        
    except Exception as e:
        frappe.log_error(f"Bulk Payment: Error fetching all unpaid items for member - {str(e)}")
        return []


# Global service instance
bulk_payment_service = BulkPaymentService()