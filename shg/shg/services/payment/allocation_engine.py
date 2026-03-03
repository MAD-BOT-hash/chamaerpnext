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


# =============================================================================
# TOTAL AMOUNT RESOLVER (SINGLE SOURCE OF TRUTH)
# =============================================================================

def get_shg_document_total(doc: Document) -> float:
    """
    SHG-native document total resolver.
    
    FIELD PRIORITY (SHG fields first, ERPNext fields last):
    1. expected_amount - SHG Contribution
    2. amount - SHG Contribution Invoice, SHG Meeting Fine
    3. fine_amount - SHG Meeting Fine (alternative)
    4. total_amount - Generic fallback
    5. grand_total - ERPNext Sales Invoice (LAST RESORT)
    
    Args:
        doc: Any SHG or ERPNext document with amount fields
        
    Returns:
        float: The total amount (never negative)
        
    Raises:
        AllocationError: If no valid total field found
    """
    field_priority = [
        'expected_amount',  # SHG Contribution
        'amount',           # SHG Contribution Invoice, SHG Meeting Fine
        'fine_amount',      # SHG Meeting Fine (alternative name)
        'total_amount',     # Generic fallback
        'grand_total',      # ERPNext Sales Invoice (last resort)
    ]
    
    for field in field_priority:
        if hasattr(doc, field):
            value = getattr(doc, field)
            if value is not None and flt(value) > 0:
                return flt(value)
    
    # Detailed error for debugging
    raise AllocationError(
        f"Cannot determine total amount for {doc.doctype} {doc.name}. "
        f"No valid total field found. Checked: {', '.join(field_priority)}"
    )


def get_outstanding_amount(doc: Document) -> float:
    """
    Calculate outstanding amount for any SHG document.
    
    SINGLE FORMULA (no duplication):
    outstanding = total - paid
    
    Args:
        doc: SHG document (Contribution Invoice, Contribution, Meeting Fine)
        
    Returns:
        float: Outstanding amount (never negative)
    """
    total = get_shg_document_total(doc)
    paid = flt(getattr(doc, 'paid_amount', 0) or 0)
    outstanding = flt(total - paid)
    return max(0, outstanding)  # Never return negative


def get_paid_amount(doc: Document) -> float:
    """
    Get paid amount from any SHG document.
    
    Args:
        doc: SHG document
        
    Returns:
        float: Paid amount
    """
    return flt(getattr(doc, 'paid_amount', 0) or 0)


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
    ]
    
    def __init__(self):
        self.audit_log = []
    
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
        
        # Calculate amounts BEFORE allocation
        total = get_shg_document_total(doc)
        paid_before = get_paid_amount(doc)
        outstanding_before = get_outstanding_amount(doc)
        
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
        
        # Update document fields
        doc.paid_amount = flt(paid_after, 2)
        
        # Update outstanding_amount if field exists
        if hasattr(doc, 'outstanding_amount'):
            doc.outstanding_amount = flt(outstanding_after, 2)
        
        # Update status
        if outstanding_after <= 0:
            doc.status = "Paid"
        elif paid_after > 0:
            doc.status = "Partially Paid"
        
        # Link payment entry if provided
        if payment_entry_name:
            if hasattr(doc, 'payment_entry'):
                doc.payment_entry = payment_entry_name
            if hasattr(doc, 'payment_reference'):
                doc.payment_reference = payment_entry_name
        
        # Save document
        if auto_save:
            doc.save(ignore_permissions=True)
        
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
            "status": doc.status,
            "payment_entry": payment_entry_name,
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
