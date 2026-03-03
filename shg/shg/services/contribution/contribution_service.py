"""
SHG Contribution Service
Clean architecture service for contribution-related operations.
Separates contribution logic from bulk payment processing.
"""
import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document
from typing import Optional, Dict, Any


class ContributionServiceError(Exception):
    """Base exception for contribution service errors"""
    pass


class OverpaymentError(ContributionServiceError):
    """Raised when payment exceeds outstanding amount"""
    pass


class DocumentLockError(ContributionServiceError):
    """Raised when document cannot be locked for processing"""
    pass


def get_shg_document_total(doc: Document) -> float:
    """
    SHG-native document total resolver.
    Prioritizes SHG Contribution fields over ERPNext Sales Invoice fields.
    
    Field priority for SHG documents:
    1. expected_amount (SHG Contribution)
    2. amount (SHG Contribution Invoice, SHG Meeting Fine)
    3. total_amount (generic fallback)
    4. grand_total (ERPNext Sales Invoice - last resort)
    
    Args:
        doc: Any SHG or ERPNext document with amount fields
        
    Returns:
        float: The total amount
        
    Raises:
        frappe.ValidationError: If no valid total field found
    """
    field_priority = [
        'expected_amount',  # SHG Contribution primary field
        'amount',           # SHG Contribution Invoice, SHG Meeting Fine
        'total_amount',     # Generic fallback
        'grand_total',      # ERPNext Sales Invoice (last resort)
    ]
    
    for field in field_priority:
        if hasattr(doc, field):
            value = getattr(doc, field)
            if value is not None and flt(value) > 0:
                return flt(value)
    
    # Log detailed error for debugging
    available_fields = [f for f in dir(doc) if not f.startswith('_') 
                       and not callable(getattr(doc, f, None))]
    frappe.log_error(
        f"No valid total field found in {doc.doctype} {doc.name}. "
        f"Checked fields: {field_priority}. "
        f"Available fields: {available_fields[:20]}...",
        "SHG Document Total Field Missing"
    )
    frappe.throw(
        f"Cannot determine total amount for {doc.doctype} {doc.name}. "
        f"No recognized total field found. Expected one of: {', '.join(field_priority)}"
    )


class ContributionService:
    """
    Service class for SHG Contribution operations.
    Handles payment allocation, status updates, and document locking.
    """
    
    def __init__(self):
        self.logger = frappe.logger("contribution_service", allow_site=True)
    
    def allocate_payment(self, contribution_name: str, allocated_amount: float, 
                        payment_entry_name: str) -> Dict[str, Any]:
        """
        Allocate payment to a contribution with full safety checks.
        
        Args:
            contribution_name: Name of SHG Contribution
            allocated_amount: Amount to allocate
            payment_entry_name: Reference to Payment Entry
            
        Returns:
            Dict with allocation result
            
        Raises:
            OverpaymentError: If allocated amount exceeds outstanding
            DocumentLockError: If document cannot be locked
        """
        try:
            # Lock document for concurrent access
            self._lock_contribution(contribution_name)
            
            # Get contribution document
            contribution = frappe.get_doc("SHG Contribution", contribution_name)
            
            # Calculate totals using SHG-native fields
            total_amount = get_shg_document_total(contribution)
            current_paid = flt(contribution.paid_amount or 0)
            outstanding = total_amount - current_paid
            
            # Overpayment protection
            if flt(allocated_amount) > outstanding:
                raise OverpaymentError(
                    f"Allocated amount ({allocated_amount}) exceeds outstanding ({outstanding}) "
                    f"for contribution {contribution_name}"
                )
            
            # Update payment amounts
            new_paid = current_paid + flt(allocated_amount)
            new_outstanding = total_amount - new_paid
            
            # Determine status
            if new_outstanding <= 0:
                new_status = "Paid"
            elif new_paid > 0:
                new_status = "Partially Paid"
            else:
                new_status = "Unpaid"
            
            # Update document
            contribution.paid_amount = new_paid
            contribution.outstanding_amount = new_outstanding
            contribution.payment_status = new_status
            
            if not contribution.payment_entry:
                contribution.payment_entry = payment_entry_name
            
            contribution.save(ignore_permissions=True)
            
            self.logger.info(
                f"Payment allocated to contribution {contribution_name}: "
                f"amount={allocated_amount}, new_status={new_status}"
            )
            
            return {
                "success": True,
                "contribution": contribution_name,
                "allocated_amount": allocated_amount,
                "new_paid_amount": new_paid,
                "new_outstanding": new_outstanding,
                "new_status": new_status,
                "payment_entry": payment_entry_name
            }
            
        except OverpaymentError:
            raise
        except Exception as e:
            frappe.log_error(
                frappe.get_traceback(),
                f"Contribution Payment Allocation Failed: {contribution_name}"
            )
            raise ContributionServiceError(
                f"Failed to allocate payment to contribution {contribution_name}: {str(e)}"
            ) from e
    
    def _lock_contribution(self, contribution_name: str):
        """
        Lock contribution document for concurrent access.
        Uses SELECT FOR UPDATE for row-level locking.
        """
        try:
            result = frappe.db.sql(
                "SELECT name FROM `tabSHG Contribution` WHERE name = %s FOR UPDATE",
                (contribution_name,),
                as_dict=True
            )
            if not result:
                raise DocumentLockError(
                    f"Contribution {contribution_name} not found or could not be locked"
                )
        except Exception as e:
            frappe.log_error(
                frappe.get_traceback(),
                f"Contribution Lock Failed: {contribution_name}"
            )
            raise DocumentLockError(
                f"Could not lock contribution {contribution_name}. "
                f"Another process may be modifying this document."
            ) from e
    
    def get_outstanding_amount(self, contribution_name: str) -> float:
        """
        Get current outstanding amount for a contribution.
        
        Args:
            contribution_name: Name of SHG Contribution
            
        Returns:
            float: Outstanding amount
        """
        contribution = frappe.get_doc("SHG Contribution", contribution_name)
        total = get_shg_document_total(contribution)
        paid = flt(contribution.paid_amount or 0)
        return total - paid
    
    def update_contribution_status(self, contribution_name: str) -> str:
        """
        Recalculate and update contribution status based on paid amount.
        
        Args:
            contribution_name: Name of SHG Contribution
            
        Returns:
            str: New status
        """
        contribution = frappe.get_doc("SHG Contribution", contribution_name)
        
        total = get_shg_document_total(contribution)
        paid = flt(contribution.paid_amount or 0)
        outstanding = total - paid
        
        if outstanding <= 0:
            new_status = "Paid"
        elif paid > 0:
            new_status = "Partially Paid"
        else:
            new_status = "Unpaid"
        
        if contribution.payment_status != new_status:
            contribution.payment_status = new_status
            contribution.outstanding_amount = outstanding
            contribution.save(ignore_permissions=True)
            
        return new_status


# Singleton instance for use across the application
contribution_service = ContributionService()