"""
SHG Allocation Engine
=====================
Centralized payment allocation logic for all SHG payment processing.

ALL payment allocation operations MUST use this engine:
- Bulk Payment Processing
- Mpesa Auto Reconciliation
- Manual Payment Entry
- API-based Payments

NO SEPARATE IMPLEMENTATIONS ALLOWED.
"""
import frappe
from frappe import _
from frappe.utils import flt, nowdate
from frappe.model.document import Document
from typing import Dict, List, Optional, Any, Tuple


# =============================================================================
# EXCEPTIONS
# =============================================================================

class AllocationError(Exception):
    """Base exception for allocation errors"""
    pass


class OverpaymentError(AllocationError):
    """Raised when payment exceeds outstanding amount"""
    pass


class InsufficientFundsError(AllocationError):
    """Raised when payment amount is insufficient"""
    pass


class DocumentNotFoundError(AllocationError):
    """Raised when reference document not found"""
    pass


class DocumentLockedError(AllocationError):
    """Raised when document is locked by another process"""
    pass


class AlreadyPaidError(AllocationError):
    """Raised when document is already fully paid"""
    pass


# =============================================================================
# STATUS CONSTANTS (SINGLE SOURCE OF TRUTH)
# =============================================================================

# Canonical status values for all SHG doctypes
STATUS_UNPAID = "Unpaid"
STATUS_PENDING = "Pending"  # Used by Meeting Fine
STATUS_PARTIALLY_PAID = "Partially Paid"
STATUS_PAID = "Paid"
STATUS_WAIVED = "Waived"
STATUS_CANCELLED = "Cancelled"
STATUS_OVERDUE = "Overdue"

# Status values that indicate document can receive payment
PAYABLE_STATUSES = [STATUS_UNPAID, STATUS_PENDING, STATUS_PARTIALLY_PAID, STATUS_OVERDUE]

# Status values that indicate document is fully settled
SETTLED_STATUSES = [STATUS_PAID, STATUS_WAIVED, STATUS_CANCELLED]


# =============================================================================
# FIELD MAPPING (SINGLE SOURCE OF TRUTH FOR ALL DOCTYPES)
# =============================================================================

# Defines field names for each doctype to handle inconsistencies
DOCTYPE_FIELD_MAP = {
    "SHG Contribution Invoice": {
        "total_field": "amount",           # Total amount due
        "paid_field": "paid_amount",       # Amount paid so far
        "outstanding_field": "outstanding_amount",  # Outstanding balance
        "date_field": "due_date",          # Due date field
        "reference_date_field": "invoice_date",  # Reference date
        "member_field": "member",          # Member link field
        "payment_entry_field": "payment_entry",  # Payment entry link
        "status_field": "status",          # Status field
    },
    "SHG Contribution": {
        "total_field": "expected_amount",  # Total amount due (NOT 'amount')
        "paid_field": "amount_paid",       # Amount paid so far
        "outstanding_field": "unpaid_amount",  # Outstanding balance
        "date_field": "contribution_date", # Reference date (NO due_date!)
        "reference_date_field": "contribution_date",
        "member_field": "member",
        "payment_entry_field": "payment_entry",
        "status_field": "status",
    },
    "SHG Meeting Fine": {
        "total_field": "fine_amount",      # Total fine amount
        "paid_field": "paid_amount",       # Amount paid so far
        "outstanding_field": "outstanding_amount",  # Outstanding balance
        "date_field": "fine_date",         # Fine date (NO due_date!)
        "reference_date_field": "fine_date",
        "member_field": "member",
        "payment_entry_field": "payment_entry",
        "status_field": "status",
    },
    "SHG Loan Repayment Schedule": {
        "total_field": "total_payment",    # Total installment amount
        "paid_field": "amount_paid",       # Amount paid so far (NOT actual_amount_paid)
        "outstanding_field": "unpaid_balance",  # Outstanding balance (NOT outstanding_amount)
        "date_field": "due_date",          # Due date
        "reference_date_field": "due_date",
        "member_field": None,              # Member from parent loan
        "payment_entry_field": "payment_entry",
        "status_field": "status",
    },
}


def get_field_name(doctype: str, field_type: str) -> Optional[str]:
    """
    Get the correct field name for a doctype.
    
    Args:
        doctype: Document type name
        field_type: Type of field (total_field, paid_field, etc.)
        
    Returns:
        Field name or None if not mapped
    """
    mapping = DOCTYPE_FIELD_MAP.get(doctype, {})
    return mapping.get(field_type)


def safe_get_field(doc: Document, field_type: str, default: Any = None) -> Any:
    """
    Safely get a field value from a document using the field mapping.
    
    Args:
        doc: Document object
        field_type: Type of field to get
        default: Default value if field not found
        
    Returns:
        Field value or default
    """
    field_name = get_field_name(doc.doctype, field_type)
    if field_name and hasattr(doc, field_name):
        return getattr(doc, field_name, default)
    return default


# =============================================================================
# STATUS HELPERS
# =============================================================================

def get_status_field_name(doc: Document) -> str:
    """Get the correct status field name for a document."""
    return get_field_name(doc.doctype, "status_field") or "status"


def get_document_status(doc: Document) -> str:
    """Get current payment status from any SHG document."""
    status_field = get_status_field_name(doc)
    return getattr(doc, status_field, STATUS_UNPAID) or STATUS_UNPAID


def set_document_status(doc: Document, status: str):
    """
    Set payment status on any SHG document.
    
    Args:
        doc: SHG document
        status: New status value
    """
    # All SHG doctypes use 'status' field
    if hasattr(doc, 'status'):
        doc.status = status


def is_document_payable(doc: Document) -> bool:
    """
    Check if document can receive payments.
    
    Args:
        doc: SHG document
        
    Returns:
        bool: True if document can receive payment
    """
    current_status = get_document_status(doc)
    return current_status in PAYABLE_STATUSES


def is_document_settled(doc: Document) -> bool:
    """
    Check if document is fully settled (paid/waived/cancelled).
    
    Args:
        doc: SHG document
        
    Returns:
        bool: True if document is settled
    """
    current_status = get_document_status(doc)
    return current_status in SETTLED_STATUSES


# =============================================================================
# TOTAL AMOUNT RESOLVER (SINGLE SOURCE OF TRUTH)
# =============================================================================

def get_shg_document_total(doc: Document) -> float:
    """
    Get total amount from any SHG document using field mapping.
    
    Args:
        doc: Any SHG document with amount fields
        
    Returns:
        float: The total amount (never negative)
        
    Raises:
        AllocationError: If no valid total field found
    """
    # First try using the field mapping
    total_field = get_field_name(doc.doctype, "total_field")
    if total_field and hasattr(doc, total_field):
        value = getattr(doc, total_field)
        if value is not None and flt(value) > 0:
            return flt(value)
    
    # Fallback: check common field names
    fallback_fields = [
        'total_payment',    # SHG Loan Repayment Schedule
        'total_due',        # Alternative
        'expected_amount',  # SHG Contribution
        'amount',           # SHG Contribution Invoice
        'fine_amount',      # SHG Meeting Fine
        'total_amount',     # Generic
        'grand_total',      # ERPNext
    ]
    
    for field in fallback_fields:
        if hasattr(doc, field):
            value = getattr(doc, field)
            if value is not None and flt(value) > 0:
                return flt(value)
    
    raise AllocationError(
        f"Cannot determine total amount for {doc.doctype} {doc.name}. "
        f"Expected field: {total_field}"
    )


def get_outstanding_amount(doc: Document) -> float:
    """
    Calculate outstanding amount for any SHG document.
    
    SINGLE FORMULA: outstanding = total - paid
    
    Args:
        doc: SHG document
        
    Returns:
        float: Outstanding amount (never negative)
    """
    total = get_shg_document_total(doc)
    paid = get_paid_amount(doc)
    outstanding = flt(total - paid)
    return max(0, outstanding)


def get_paid_amount(doc: Document) -> float:
    """
    Get paid amount from any SHG document using field mapping.
    
    Args:
        doc: SHG document
        
    Returns:
        float: Paid amount
    """
    # First try using the field mapping
    paid_field = get_field_name(doc.doctype, "paid_field")
    if paid_field and hasattr(doc, paid_field):
        value = getattr(doc, paid_field, 0)
        if value is not None:
            return flt(value)
    
    # Fallback: check common field names
    for field in ['paid_amount', 'amount_paid', 'actual_amount_paid']:
        if hasattr(doc, field):
            value = getattr(doc, field, 0)
            if value is not None:
                return flt(value)
    
    return 0.0


def get_member_from_doctype(doc: Document) -> Optional[str]:
    """
    Get member ID from any SHG document.
    
    Args:
        doc: SHG document
        
    Returns:
        Member ID or None
    """
    # Use field mapping
    member_field = get_field_name(doc.doctype, "member_field")
    if member_field and hasattr(doc, member_field):
        return getattr(doc, member_field)
    
    # For loan repayment schedule, get member from parent loan
    if doc.doctype == "SHG Loan Repayment Schedule" and hasattr(doc, 'parent'):
        try:
            return frappe.db.get_value("SHG Loan", doc.parent, "member")
        except:
            pass
    
    return None


# =============================================================================
# ALLOCATION ENGINE
# =============================================================================

class AllocationEngine:
    """
    Central allocation engine for all SHG payments.
    
    Usage:
        engine = AllocationEngine()
        result = engine.allocate_payment(
            doctype="SHG Contribution Invoice",
            docname="SHGCI-00001",
            amount=1000.0,
            payment_entry_name="PE-00001"
        )
    """
    
    # Supported SHG document types for allocation
    SUPPORTED_DOCTYPES = [
        "SHG Contribution Invoice",
        "SHG Contribution",
        "SHG Meeting Fine",
        "SHG Loan Repayment Schedule",  # Loan installment payments
    ]
    
    def __init__(self):
        self.audit_log = []
        self._member_updates = set()  # Track members to update statements
    
    def allocate_payment(
        self,
        doctype: str,
        docname: str,
        amount: float,
        payment_entry_name: Optional[str] = None,
        allow_overpayment: bool = False,
        auto_save: bool = True
    ) -> Dict[str, Any]:
        """
        Allocate payment to a single SHG document.
        
        Args:
            doctype: Document type (SHG Contribution Invoice, etc.)
            docname: Document name
            amount: Amount to allocate
            payment_entry_name: Optional Payment Entry reference
            allow_overpayment: Allow allocation beyond outstanding
            auto_save: Automatically save the document
            
        Returns:
            dict: Allocation result with before/after amounts
            
        Raises:
            DocumentNotFoundError: Document doesn't exist
            OverpaymentError: Amount exceeds outstanding (if not allowed)
            AlreadyPaidError: Document is already fully paid
        """
        if doctype not in self.SUPPORTED_DOCTYPES:
            raise AllocationError(f"Unsupported doctype: {doctype}")
        
        if flt(amount) <= 0:
            raise AllocationError(f"Invalid allocation amount: {amount}")
        
        # Load document
        try:
            doc = frappe.get_doc(doctype, docname)
        except frappe.DoesNotExistError:
            raise DocumentNotFoundError(f"{doctype} {docname} not found")
        
        # DUPLICATE PREVENTION: Check if document is already fully paid
        current_status = get_document_status(doc)
        if is_document_settled(doc):
            raise AlreadyPaidError(
                f"{doctype} {docname} is already settled with status '{current_status}'. "
                f"Cannot apply additional payment."
            )
        
        # Calculate amounts BEFORE allocation
        total = get_shg_document_total(doc)
        paid_before = get_paid_amount(doc)
        outstanding_before = get_outstanding_amount(doc)
        
        # DUPLICATE PREVENTION: Check if there's any outstanding amount
        if outstanding_before <= 0:
            raise AlreadyPaidError(
                f"{doctype} {docname} has no outstanding balance. "
                f"Total: {total}, Already Paid: {paid_before}, Outstanding: {outstanding_before}"
            )
        
        # Validate allocation amount
        allocation_amount = flt(amount)
        if not allow_overpayment and allocation_amount > outstanding_before:
            raise OverpaymentError(
                f"Attempted payment of {allocation_amount} exceeds "
                f"outstanding balance of {outstanding_before} for {doctype} {docname}. "
                f"Total: {total}, Already Paid: {paid_before}"
            )
        
        # Cap allocation to outstanding if not allowing overpayment
        if not allow_overpayment:
            allocation_amount = min(allocation_amount, outstanding_before)
        
        # Apply allocation
        paid_after = paid_before + allocation_amount
        outstanding_after = max(0, total - paid_after)
        
        # Determine new status
        if outstanding_after <= 0:
            new_status = STATUS_PAID
        elif paid_after > 0:
            new_status = STATUS_PARTIALLY_PAID
        else:
            new_status = current_status  # Keep current status
        
        # Build update values dict for db_set using field mapping
        update_values = {"status": new_status}
        
        # Get field names from mapping
        paid_field = get_field_name(doctype, "paid_field")
        outstanding_field = get_field_name(doctype, "outstanding_field")
        payment_entry_field = get_field_name(doctype, "payment_entry_field")
        
        # Set paid amount using correct field name
        if paid_field:
            update_values[paid_field] = flt(paid_after, 2)
        
        # Set outstanding amount using correct field name  
        if outstanding_field:
            update_values[outstanding_field] = flt(outstanding_after, 2)
        
        # Link payment entry if provided
        if payment_entry_name and payment_entry_field:
            update_values[payment_entry_field] = payment_entry_name
        
        # Use db_set for submitted documents (ERPNext compliant)
        if auto_save:
            if doc.docstatus == 1:
                # Submitted document - use db_set (no .save())
                frappe.db.set_value(doctype, docname, update_values, update_modified=False)
            else:
                # Draft document - can use save
                for key, value in update_values.items():
                    if hasattr(doc, key):
                        setattr(doc, key, value)
                doc.save(ignore_permissions=True)
        
        # Track member for statement update
        member = self._get_member_from_document(doc, doctype)
        if member:
            self._member_updates.add(member)
        
        # Handle loan-specific updates
        if doctype == "SHG Loan Repayment Schedule":
            self._update_parent_loan(doc)
        
        # Handle Contribution Invoice - sync linked contribution
        if doctype == "SHG Contribution Invoice":
            self._sync_linked_contribution(doc, allocation_amount, payment_entry_name)
        
        # Build result
        result = {
            "doctype": doctype,
            "docname": docname,
            "total_amount": total,
            "paid_before": paid_before,
            "allocated_amount": allocation_amount,
            "paid_after": paid_after,
            "outstanding_before": outstanding_before,
            "outstanding_after": outstanding_after,
            "status_before": current_status,
            "status": new_status,
            "payment_entry": payment_entry_name,
            "member": member,
            "success": True
        }
        
        # Add to audit log
        self._log_allocation(result)
        
        return result
    
    def allocate_bulk(
        self,
        allocations: List[Dict[str, Any]],
        payment_entry_name: Optional[str] = None,
        stop_on_error: bool = False
    ) -> Dict[str, Any]:
        """
        Allocate payments to multiple documents.
        
        Args:
            allocations: List of dicts with doctype, docname, amount
            payment_entry_name: Optional Payment Entry reference
            stop_on_error: Stop processing on first error
            
        Returns:
            dict: Summary of all allocations
        """
        results = []
        success_count = 0
        error_count = 0
        total_allocated = 0.0
        
        for alloc in allocations:
            try:
                result = self.allocate_payment(
                    doctype=alloc.get("doctype") or alloc.get("reference_doctype"),
                    docname=alloc.get("docname") or alloc.get("reference_name"),
                    amount=flt(alloc.get("amount") or alloc.get("allocated_amount")),
                    payment_entry_name=payment_entry_name,
                    allow_overpayment=alloc.get("allow_overpayment", False)
                )
                results.append(result)
                success_count += 1
                total_allocated += result["allocated_amount"]
                
            except AllocationError as e:
                error_result = {
                    "doctype": alloc.get("doctype") or alloc.get("reference_doctype"),
                    "docname": alloc.get("docname") or alloc.get("reference_name"),
                    "error": str(e),
                    "success": False
                }
                results.append(error_result)
                error_count += 1
                
                if stop_on_error:
                    break
        
        return {
            "results": results,
            "success_count": success_count,
            "error_count": error_count,
            "total_allocated": total_allocated,
            "payment_entry": payment_entry_name
        }
    
    def validate_allocation(
        self,
        doctype: str,
        docname: str,
        amount: float
    ) -> Tuple[bool, str]:
        """
        Validate if allocation is possible without applying it.
        
        Args:
            doctype: Document type
            docname: Document name
            amount: Amount to validate
            
        Returns:
            tuple: (is_valid, message)
        """
        try:
            doc = frappe.get_doc(doctype, docname)
            outstanding = get_outstanding_amount(doc)
            
            if flt(amount) <= 0:
                return False, f"Invalid amount: {amount}"
            
            if flt(amount) > outstanding:
                return False, (
                    f"Amount {amount} exceeds outstanding {outstanding}"
                )
            
            return True, "Allocation is valid"
            
        except frappe.DoesNotExistError:
            return False, f"Document {doctype} {docname} not found"
        except Exception as e:
            return False, str(e)
    
    def get_allocation_summary(self, doctype: str, docname: str) -> Dict[str, Any]:
        """
        Get current allocation status for a document.
        
        Args:
            doctype: Document type
            docname: Document name
            
        Returns:
            dict: Current allocation status
        """
        try:
            doc = frappe.get_doc(doctype, docname)
            return {
                "doctype": doctype,
                "docname": docname,
                "total_amount": get_shg_document_total(doc),
                "paid_amount": get_paid_amount(doc),
                "outstanding_amount": get_outstanding_amount(doc),
                "status": getattr(doc, 'status', 'Unknown'),
                "payment_entry": getattr(doc, 'payment_entry', None)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _log_allocation(self, result: Dict[str, Any]):
        """Add allocation to audit log."""
        self.audit_log.append({
            "timestamp": nowdate(),
            **result
        })
    
    def _get_member_from_document(self, doc: Document, doctype: str) -> Optional[str]:
        """
        Extract member ID from any SHG document.
        
        Args:
            doc: SHG document
            doctype: Document type
            
        Returns:
            str: Member ID or None
        """
        # Direct member field
        if hasattr(doc, 'member') and doc.member:
            return doc.member
        
        # For loan repayment schedule, get from parent loan
        if doctype == "SHG Loan Repayment Schedule":
            if hasattr(doc, 'parent') and doc.parent:
                try:
                    return frappe.db.get_value("SHG Loan", doc.parent, "member")
                except:
                    pass
        
        return None
    
    def _update_parent_loan(self, schedule_row: Document):
        """
        Update parent loan summary after repayment schedule payment.
        
        Args:
            schedule_row: SHG Loan Repayment Schedule row
        """
        if not hasattr(schedule_row, 'parent') or not schedule_row.parent:
            return
        
        try:
            # Import loan utils to update loan summary
            from shg.shg.loan_utils import update_loan_summary
            update_loan_summary(schedule_row.parent)
        except ImportError:
            # Fallback: update directly
            try:
                loan = frappe.get_doc("SHG Loan", schedule_row.parent)
                if hasattr(loan, 'update_loan_summary'):
                    loan.update_loan_summary()
            except Exception as e:
                frappe.log_error(
                    title="Loan Summary Update",
                    message=f"Failed to update loan {schedule_row.parent}: {str(e)}"
                )
    
    def _sync_linked_contribution(
        self,
        invoice_doc: Document,
        allocated_amount: float,
        payment_entry_name: Optional[str] = None
    ):
        """
        Sync payment status to the linked SHG Contribution when an invoice is paid.
        
        When SHG Contribution Invoice is paid via bulk payment:
        1. Update the linked SHG Contribution's paid/unpaid amounts
        2. Update the linked SHG Contribution's status
        3. Track member for statement update
        
        Args:
            invoice_doc: SHG Contribution Invoice document
            allocated_amount: Amount allocated to the invoice
            payment_entry_name: Optional Payment Entry reference
        """
        # Check if invoice has a linked contribution
        linked_contribution = getattr(invoice_doc, 'linked_shg_contribution', None)
        if not linked_contribution:
            return
        
        try:
            # Get the linked contribution document
            contribution = frappe.get_doc("SHG Contribution", linked_contribution)
            
            # Use field mapping to get correct field names for SHG Contribution
            total_field = get_field_name("SHG Contribution", "total_field")  # expected_amount
            paid_field = get_field_name("SHG Contribution", "paid_field")     # amount_paid
            outstanding_field = get_field_name("SHG Contribution", "outstanding_field")  # unpaid_amount
            
            # Get current values using correct field names
            total_amount = flt(getattr(contribution, total_field, 0) or 0)
            current_paid = flt(getattr(contribution, paid_field, 0) or 0)
            
            # Calculate new values
            new_paid = min(current_paid + allocated_amount, total_amount)
            new_unpaid = max(total_amount - new_paid, 0)
            
            # Determine new status
            if new_unpaid <= 0:
                new_status = STATUS_PAID
            elif new_paid > 0:
                new_status = STATUS_PARTIALLY_PAID
            else:
                new_status = getattr(contribution, 'status', STATUS_UNPAID)
            
            # Update the contribution document using db_set (ERPNext compliant)
            update_values = {
                paid_field: flt(new_paid, 2),
                outstanding_field: flt(new_unpaid, 2),
                "status": new_status
            }
            
            # Link payment entry if provided
            payment_entry_field = get_field_name("SHG Contribution", "payment_entry_field")
            if payment_entry_name and payment_entry_field:
                update_values[payment_entry_field] = payment_entry_name
            
            frappe.db.set_value(
                "SHG Contribution",
                linked_contribution,
                update_values,
                update_modified=False
            )
            
            # Track member for statement update
            member_field = get_field_name("SHG Contribution", "member_field")
            if member_field and hasattr(contribution, member_field):
                member = getattr(contribution, member_field)
                if member:
                    self._member_updates.add(member)
                
        except Exception as e:
            frappe.log_error(
                title="Contribution Sync",
                message=f"Failed to sync contribution {linked_contribution} for invoice {invoice_doc.name}: {str(e)}"
            )
    
    def update_member_statements(self):
        """
        Update financial statements for all members affected by allocations.
        Call this after bulk allocations are complete.
        """
        updated_members = []
        
        for member in self._member_updates:
            try:
                self._update_single_member_statement(member)
                updated_members.append(member)
            except Exception as e:
                frappe.log_error(
                    title="Member Statement",
                    message=f"Failed to update statement for {member}: {str(e)}"
                )
        
        # Clear the update set
        self._member_updates.clear()
        
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
                    title="Member Update",
                    message=f"Fallback update failed for {member}: {str(e)}"
                )


# =============================================================================
# CONVENIENCE FUNCTIONS (WRAPPERS)
# =============================================================================

def allocate_payment_to_document(
    doctype: str,
    docname: str,
    amount: float,
    payment_entry_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function for single allocation.
    
    Usage:
        from shg.shg.services.payment.allocation_engine import allocate_payment_to_document
        
        result = allocate_payment_to_document(
            "SHG Contribution Invoice",
            "SHGCI-00001",
            1000.0,
            "PE-00001"
        )
    """
    engine = AllocationEngine()
    return engine.allocate_payment(
        doctype=doctype,
        docname=docname,
        amount=amount,
        payment_entry_name=payment_entry_name
    )


def get_document_outstanding(doctype: str, docname: str) -> float:
    """
    Get outstanding amount for any SHG document.
    
    Usage:
        from shg.shg.services.payment.allocation_engine import get_document_outstanding
        
        outstanding = get_document_outstanding("SHG Contribution Invoice", "SHGCI-00001")
    """
    doc = frappe.get_doc(doctype, docname)
    return get_outstanding_amount(doc)


# Alias for backward compatibility
get_invoice_total = get_shg_document_total
