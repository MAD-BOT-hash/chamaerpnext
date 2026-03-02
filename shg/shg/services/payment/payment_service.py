"""
Payment Service Layer
Enterprise-grade payment processing with overpayment protection and concurrency safety
"""
import frappe
from frappe import _
from frappe.utils import flt, now
from decimal import Decimal
import json
from typing import Dict, List, Optional, Tuple
from frappe.model.document import Document

class PaymentServiceError(Exception):
    """Base exception for payment service errors"""
    pass

class OverpaymentError(PaymentServiceError):
    """Raised when payment exceeds expected amount"""
    pass

class ConcurrencyError(PaymentServiceError):
    """Raised when concurrent access conflict occurs"""
    pass

class PaymentService:
    """
    Enterprise-grade payment allocation service with:
    - Overpayment protection
    - Concurrency safety
    - Audit trail
    - Atomic operations
    """
    
    def __init__(self):
        self.logger = frappe.logger("payment_service", allow_site=True)
    
    def allocate_payment(self, payment_entry_name: str, contributions_data: List[Dict]) -> Dict:
        """
        Safely allocate payment to contributions
        
        Args:
            payment_entry_name: Name of the Payment Entry
            contributions_data: List of {'contribution': name, 'amount': amount} dicts
            
        Returns:
            Dict with allocation results and audit trail
        """
        try:
            # Validate payment entry
            payment_entry = frappe.get_doc("Payment Entry", payment_entry_name)
            self._validate_payment_entry(payment_entry)
            
            # Calculate total payment amount
            total_payment = self._calculate_payment_amount(payment_entry, contributions_data)
            
            # Start transaction with proper locking
            allocation_result = self._allocate_payment_transaction(
                payment_entry, 
                contributions_data, 
                total_payment
            )
            
            # Log successful allocation
            self._log_payment_allocation(
                payment_entry_name, 
                allocation_result, 
                total_payment
            )
            
            return allocation_result
            
        except Exception as e:
            self.logger.error(f"Payment allocation failed: {str(e)}", 
                            extra={'payment_entry': payment_entry_name, 
                                  'error': str(e),
                                  'stacktrace': frappe.get_traceback()})
            frappe.throw(f"Payment allocation failed: {str(e)}")
    
    def _validate_payment_entry(self, payment_entry: Document):
        """Validate payment entry before processing"""
        if payment_entry.docstatus != 1:
            raise PaymentServiceError("Payment entry must be submitted")
        
        if payment_entry.payment_type != "Receive":
            raise PaymentServiceError("Only 'Receive' payments are supported")
    
    def _calculate_payment_amount(self, payment_entry: Document, contributions_data: List[Dict]) -> float:
        """Calculate total payment amount to be allocated"""
        total_allocated = sum(flt(item.get('amount', 0)) for item in contributions_data)
        
        if total_allocated > flt(payment_entry.paid_amount):
            raise PaymentServiceError(
                f"Total allocated amount ({total_allocated}) exceeds payment amount ({payment_entry.paid_amount})"
            )
        
        return total_allocated
    
    def _allocate_payment_transaction(self, payment_entry: Document, contributions_data: List[Dict], total_payment: float) -> Dict:
        """Execute payment allocation in a transaction-safe manner"""
        try:
            # Lock all contributions to prevent race conditions
            locked_contributions = self._lock_contributions(contributions_data)
            
            # Validate overpayment protection
            self._validate_overpayment(locked_contributions, contributions_data)
            
            # Process each contribution allocation
            allocation_results = []
            for item in contributions_data:
                contribution_name = item['contribution']
                payment_amount = flt(item['amount'])
                
                result = self._allocate_to_contribution(
                    contribution_name, 
                    payment_amount, 
                    payment_entry.name
                )
                allocation_results.append(result)
            
            # Update payment entry with allocation reference
            self._update_payment_entry_reference(payment_entry, allocation_results)
            
            return {
                'status': 'success',
                'payment_entry': payment_entry.name,
                'total_allocated': total_payment,
                'allocations': allocation_results,
                'timestamp': now()
            }
            
        except Exception as e:
            frappe.db.rollback()
            raise
    
    def _lock_contributions(self, contributions_data: List[Dict]) -> List[Dict]:
        """Lock contributions for concurrent access protection"""
        contribution_names = [item['contribution'] for item in contributions_data]
        
        # Use SELECT FOR UPDATE to lock rows
        locked_data = frappe.db.sql("""
            SELECT name, member, expected_amount, amount_paid, unpaid_amount, status
            FROM `tabSHG Contribution` 
            WHERE name IN %s AND docstatus = 1
            FOR UPDATE
        """, (tuple(contribution_names),), as_dict=True)
        
        if len(locked_data) != len(contribution_names):
            missing = set(contribution_names) - {item.name for item in locked_data}
            raise PaymentServiceError(f"Contributions not found or not submitted: {missing}")
        
        return locked_data
    
    def _validate_overpayment(self, locked_contributions: List[Dict], contributions_data: List[Dict]):
        """Validate that no contribution will be overpaid"""
        contribution_dict = {item.name: item for item in locked_contributions}
        
        for item in contributions_data:
            contribution_name = item['contribution']
            payment_amount = flt(item['amount'])
            
            contribution = contribution_dict[contribution_name]
            current_paid = flt(contribution.amount_paid or 0)
            expected_amount = flt(contribution.expected_amount or contribution.amount or 0)
            new_total_paid = current_paid + payment_amount
            
            if new_total_paid > expected_amount:
                raise OverpaymentError(
                    f"Payment of {payment_amount} would overpay contribution {contribution_name}. "
                    f"Expected: {expected_amount}, Current Paid: {current_paid}, New Total: {new_total_paid}"
                )
    
    def _allocate_to_contribution(self, contribution_name: str, payment_amount: float, payment_entry_name: str) -> Dict:
        """Allocate payment to a single contribution"""
        try:
            # Get fresh contribution data to ensure consistency
            contribution = frappe.get_doc("SHG Contribution", contribution_name)
            
            # Double-check overpayment protection
            current_paid = flt(contribution.amount_paid or 0)
            expected_amount = flt(contribution.expected_amount or contribution.amount or 0)
            new_total_paid = current_paid + payment_amount
            
            if new_total_paid > expected_amount:
                raise OverpaymentError(
                    f"Overpayment detected for contribution {contribution_name}"
                )
            
            # Update contribution payment status
            contribution.amount_paid = new_total_paid
            contribution.unpaid_amount = max(0, expected_amount - new_total_paid)
            
            # Update status
            if contribution.unpaid_amount <= 0:
                contribution.status = "Paid"
            elif new_total_paid > 0:
                contribution.status = "Partially Paid"
            else:
                contribution.status = "Unpaid"
            
            # Save with audit trail
            contribution.flags.ignore_permissions = True
            contribution.save()
            
            # Update member financial summary
            self._update_member_summary(contribution.member)
            
            return {
                'contribution': contribution_name,
                'member': contribution.member,
                'amount_allocated': payment_amount,
                'new_status': contribution.status,
                'new_paid_amount': new_total_paid,
                'new_unpaid_amount': contribution.unpaid_amount
            }
            
        except Exception as e:
            self.logger.error(f"Contribution allocation failed: {str(e)}")
            raise
    
    def _update_member_summary(self, member_id: str):
        """Update member financial summary"""
        try:
            member = frappe.get_doc("SHG Member", member_id)
            member.update_financial_summary()
        except Exception as e:
            self.logger.error(f"Failed to update member summary for {member_id}: {str(e)}")
    
    def _update_payment_entry_reference(self, payment_entry: Document, allocation_results: List[Dict]):
        """Update payment entry with contribution references"""
        try:
            # Store allocation data as JSON
            allocation_data = {
                'allocations': allocation_results,
                'total_allocated': sum(item['amount_allocated'] for item in allocation_results)
            }
            
            payment_entry.db_set('custom_contribution_allocation', json.dumps(allocation_data))
            payment_entry.db_set('custom_allocation_status', 'Processed')
            
        except Exception as e:
            self.logger.error(f"Failed to update payment entry reference: {str(e)}")
    
    def _log_payment_allocation(self, payment_entry_name: str, allocation_result: Dict, total_payment: float):
        """Log payment allocation for audit trail"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG Payment Log',
                'payment_entry': payment_entry_name,
                'allocation_data': json.dumps(allocation_result),
                'total_amount': total_payment,
                'status': 'Success',
                'timestamp': now()
            })
            log_entry.insert(ignore_permissions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to log payment allocation: {str(e)}")
    
    def reverse_payment_allocation(self, payment_entry_name: str) -> Dict:
        """
        Safely reverse a payment allocation
        
        Args:
            payment_entry_name: Name of the Payment Entry to reverse
            
        Returns:
            Dict with reversal results
        """
        try:
            # Get allocation data
            payment_entry = frappe.get_doc("Payment Entry", payment_entry_name)
            allocation_data = json.loads(payment_entry.custom_contribution_allocation or '{}')
            
            if not allocation_data.get('allocations'):
                raise PaymentServiceError("No allocation data found for reversal")
            
            # Reverse each allocation
            reversal_results = []
            for allocation in allocation_data['allocations']:
                result = self._reverse_contribution_allocation(
                    allocation['contribution'], 
                    allocation['amount_allocated']
                )
                reversal_results.append(result)
            
            # Update payment entry status
            payment_entry.db_set('custom_allocation_status', 'Reversed')
            
            # Log reversal
            self._log_payment_reversal(payment_entry_name, reversal_results)
            
            return {
                'status': 'success',
                'payment_entry': payment_entry_name,
                'reversals': reversal_results,
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"Payment reversal failed: {str(e)}")
            frappe.throw(f"Payment reversal failed: {str(e)}")
    
    def _reverse_contribution_allocation(self, contribution_name: str, amount_to_reverse: float) -> Dict:
        """Reverse payment allocation for a single contribution"""
        try:
            contribution = frappe.get_doc("SHG Contribution", contribution_name)
            
            current_paid = flt(contribution.amount_paid or 0)
            new_paid = max(0, current_paid - amount_to_reverse)
            expected_amount = flt(contribution.expected_amount or contribution.amount or 0)
            new_unpaid = max(0, expected_amount - new_paid)
            
            # Update contribution
            contribution.amount_paid = new_paid
            contribution.unpaid_amount = new_unpaid
            
            # Update status
            if new_unpaid <= 0:
                contribution.status = "Paid"
            elif new_paid > 0:
                contribution.status = "Partially Paid"
            else:
                contribution.status = "Unpaid"
            
            contribution.flags.ignore_permissions = True
            contribution.save()
            
            # Update member summary
            self._update_member_summary(contribution.member)
            
            return {
                'contribution': contribution_name,
                'amount_reversed': amount_to_reverse,
                'new_paid_amount': new_paid,
                'new_unpaid_amount': new_unpaid,
                'new_status': contribution.status
            }
            
        except Exception as e:
            self.logger.error(f"Contribution reversal failed: {str(e)}")
            raise
    
    def _log_payment_reversal(self, payment_entry_name: str, reversal_results: List[Dict]):
        """Log payment reversal for audit trail"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG Payment Log',
                'payment_entry': payment_entry_name,
                'allocation_data': json.dumps({
                    'reversals': reversal_results,
                    'total_reversed': sum(item['amount_reversed'] for item in reversal_results)
                }),
                'total_amount': -sum(item['amount_reversed'] for item in reversal_results),
                'status': 'Reversed',
                'timestamp': now()
            })
            log_entry.insert(ignore_permissions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to log payment reversal: {str(e)}")

# Global service instance
payment_service = PaymentService()