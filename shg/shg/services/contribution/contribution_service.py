"""
Contribution Service Layer
Enterprise-grade contribution management with proper service layer separation
"""
import frappe
from frappe import _
from frappe.utils import flt, now
from frappe.model.document import Document
from typing import Dict, List, Optional, Union
from decimal import Decimal
import json
from .payment_service import payment_service

class ContributionServiceError(Exception):
    """Base exception for contribution service errors"""
    pass

class DuplicateContributionError(ContributionServiceError):
    """Raised when attempting to create duplicate contribution"""
    pass

class ContributionService:
    """
    Enterprise-grade contribution management service with:
    - Proper separation of concerns
    - Transaction safety
    - Concurrency protection
    - Audit trail
    - Idempotency
    """
    
    def __init__(self):
        self.logger = frappe.logger("contribution_service", allow_site=True)
        self.payment_service = payment_service
    
    def create_contribution(self, data: Dict) -> Dict:
        """
        Create a new contribution with proper validation and service layer separation
        
        Args:
            data: Contribution data dictionary
            
        Returns:
            Dict with created contribution details
        """
        try:
            # Validate required fields
            self._validate_contribution_data(data)
            
            # Check for duplicates
            self._check_duplicate_contribution(data)
            
            # Create contribution in transaction
            contribution_data = self._create_contribution_transaction(data)
            
            # Log successful creation
            self._log_contribution_creation(contribution_data)
            
            return contribution_data
            
        except Exception as e:
            self.logger.error(f"Contribution creation failed: {str(e)}", 
                            extra={'data': data, 'error': str(e)})
            frappe.throw(f"Contribution creation failed: {str(e)}")
    
    def _validate_contribution_data(self, data: Dict):
        """Validate contribution data before creation"""
        required_fields = ['member', 'contribution_date', 'amount']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            raise ContributionServiceError(f"Missing required fields: {missing_fields}")
        
        # Validate member exists and is active
        member = frappe.db.get_value("SHG Member", data['member'], ["name", "membership_status"], as_dict=True)
        if not member:
            raise ContributionServiceError(f"Member {data['member']} not found")
        
        if member.membership_status != "Active":
            raise ContributionServiceError(f"Member {data['member']} is not active")
        
        # Validate amount
        amount = flt(data['amount'])
        if amount <= 0:
            raise ContributionServiceError("Contribution amount must be greater than zero")
        
        # Validate expected amount if provided
        if 'expected_amount' in data:
            expected_amount = flt(data['expected_amount'])
            if expected_amount <= 0:
                raise ContributionServiceError("Expected amount must be greater than zero")
    
    def _check_duplicate_contribution(self, data: Dict):
        """Check for duplicate contributions to prevent duplication"""
        # Check for existing contribution with same member and date
        existing = frappe.db.exists("SHG Contribution", {
            "member": data['member'],
            "contribution_date": data['contribution_date'],
            "docstatus": 1,
            "status": ["!=", "Cancelled"]
        })
        
        if existing:
            raise DuplicateContributionError(
                f"Contribution already exists for member {data['member']} on {data['contribution_date']}"
            )
        
        # Check for invoice reference uniqueness if provided
        if data.get('invoice_reference'):
            existing_invoice = frappe.db.exists("SHG Contribution", {
                "invoice_reference": data['invoice_reference'],
                "docstatus": ["!=", 2]  # Not cancelled
            })
            
            if existing_invoice:
                raise DuplicateContributionError(
                    f"Contribution already exists with invoice reference {data['invoice_reference']}"
                )
    
    def _create_contribution_transaction(self, data: Dict) -> Dict:
        """Create contribution within a database transaction"""
        try:
            # Prepare contribution data
            contribution_data = {
                "doctype": "SHG Contribution",
                "member": data['member'],
                "member_name": frappe.db.get_value("SHG Member", data['member'], "member_name"),
                "contribution_date": data['contribution_date'],
                "posting_date": data.get('posting_date', data['contribution_date']),
                "amount": flt(data['amount']),
                "expected_amount": flt(data.get('expected_amount', data['amount'])),
                "payment_method": data.get('payment_method', 'Mpesa'),
                "contribution_type": data.get('contribution_type'),
                "description": data.get('description'),
                "invoice_reference": data.get('invoice_reference'),
                "status": "Unpaid",
                "amount_paid": 0,
                "unpaid_amount": flt(data.get('expected_amount', data['amount']))
            }
            
            # Create contribution document
            contribution = frappe.get_doc(contribution_data)
            contribution.flags.ignore_permissions = True
            contribution.insert()
            
            # Submit if auto-submit is enabled
            if data.get('auto_submit', False):
                contribution.submit()
            
            # Update member financial summary
            self._update_member_summary(data['member'])
            
            return {
                'name': contribution.name,
                'member': contribution.member,
                'amount': contribution.amount,
                'expected_amount': contribution.expected_amount,
                'status': contribution.status,
                'docstatus': contribution.docstatus,
                'timestamp': now()
            }
            
        except Exception as e:
            frappe.db.rollback()
            raise
    
    def update_payment_status(self, contribution_name: str, payment_amount: float, 
                            payment_entry_name: Optional[str] = None) -> Dict:
        """
        Safely update contribution payment status with concurrency protection
        
        Args:
            contribution_name: Name of the contribution
            payment_amount: Amount being paid
            payment_entry_name: Optional payment entry reference
            
        Returns:
            Dict with updated payment status
        """
        try:
            # Lock contribution for update to prevent race conditions
            locked_contribution = self._lock_contribution(contribution_name)
            
            # Validate payment amount doesn't cause overpayment
            self._validate_payment_amount(locked_contribution, payment_amount)
            
            # Update payment status atomically
            updated_contribution = self._update_payment_status_transaction(
                contribution_name, 
                payment_amount, 
                payment_entry_name
            )
            
            # Log payment update
            self._log_payment_update(contribution_name, payment_amount, payment_entry_name)
            
            return updated_contribution
            
        except Exception as e:
            self.logger.error(f"Payment status update failed: {str(e)}")
            frappe.throw(f"Payment status update failed: {str(e)}")
    
    def _lock_contribution(self, contribution_name: str) -> Dict:
        """Lock contribution for concurrent access protection"""
        contribution_data = frappe.db.sql("""
            SELECT name, member, amount, expected_amount, amount_paid, unpaid_amount, status
            FROM `tabSHG Contribution`
            WHERE name = %s AND docstatus = 1
            FOR UPDATE
        """, (contribution_name,), as_dict=True)
        
        if not contribution_data:
            raise ContributionServiceError(f"Contribution {contribution_name} not found or not submitted")
        
        return contribution_data[0]
    
    def _validate_payment_amount(self, contribution_data: Dict, payment_amount: float):
        """Validate that payment amount doesn't exceed expected amount"""
        current_paid = flt(contribution_data.amount_paid or 0)
        expected_amount = flt(contribution_data.expected_amount or contribution_data.amount or 0)
        new_total_paid = current_paid + payment_amount
        
        if new_total_paid > expected_amount:
            raise ContributionServiceError(
                f"Payment of {payment_amount} would overpay contribution. "
                f"Expected: {expected_amount}, Current Paid: {current_paid}, New Total: {new_total_paid}"
            )
    
    def _update_payment_status_transaction(self, contribution_name: str, payment_amount: float, 
                                         payment_entry_name: Optional[str] = None) -> Dict:
        """Update payment status in a transaction-safe manner"""
        try:
            # Get fresh contribution data
            contribution = frappe.get_doc("SHG Contribution", contribution_name)
            
            # Validate payment amount again
            current_paid = flt(contribution.amount_paid or 0)
            expected_amount = flt(contribution.expected_amount or contribution.amount or 0)
            new_paid = current_paid + payment_amount
            new_unpaid = max(0, expected_amount - new_paid)
            
            if new_paid > expected_amount:
                raise ContributionServiceError("Overpayment detected")
            
            # Update payment fields
            contribution.amount_paid = new_paid
            contribution.unpaid_amount = new_unpaid
            
            # Update status based on payment
            if new_unpaid <= 0:
                contribution.status = "Paid"
            elif new_paid > 0:
                contribution.status = "Partially Paid"
            else:
                contribution.status = "Unpaid"
            
            # Update payment entry reference if provided
            if payment_entry_name:
                contribution.payment_entry = payment_entry_name
            
            # Save with proper flags
            contribution.flags.ignore_permissions = True
            contribution.save()
            
            # Update member financial summary
            self._update_member_summary(contribution.member)
            
            return {
                'contribution': contribution_name,
                'member': contribution.member,
                'amount_paid': new_paid,
                'unpaid_amount': new_unpaid,
                'status': contribution.status,
                'payment_entry': payment_entry_name,
                'timestamp': now()
            }
            
        except Exception as e:
            frappe.db.rollback()
            raise
    
    def _update_member_summary(self, member_id: str):
        """Update member financial summary"""
        try:
            member = frappe.get_doc("SHG Member", member_id)
            member.update_financial_summary()
        except Exception as e:
            self.logger.error(f"Failed to update member summary for {member_id}: {str(e)}")
    
    def _log_contribution_creation(self, contribution_data: Dict):
        """Log contribution creation for audit trail"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG Contribution Log',
                'contribution': contribution_data['name'],
                'member': contribution_data['member'],
                'amount': contribution_data['amount'],
                'expected_amount': contribution_data['expected_amount'],
                'status': contribution_data['status'],
                'action': 'Created',
                'timestamp': contribution_data['timestamp']
            })
            log_entry.insert(ignore_permissions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to log contribution creation: {str(e)}")
    
    def _log_payment_update(self, contribution_name: str, payment_amount: float, 
                          payment_entry_name: Optional[str] = None):
        """Log payment update for audit trail"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG Contribution Log',
                'contribution': contribution_name,
                'amount': payment_amount,
                'payment_entry': payment_entry_name,
                'action': 'Payment Updated',
                'timestamp': now()
            })
            log_entry.insert(ignore_permissions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to log payment update: {str(e)}")
    
    def get_member_contributions(self, member_id: str, status: Optional[str] = None) -> List[Dict]:
        """
        Get contributions for a member with optional status filter
        
        Args:
            member_id: Member ID
            status: Optional status filter
            
        Returns:
            List of contribution dictionaries
        """
        try:
            filters = {"member": member_id, "docstatus": 1}
            if status:
                filters["status"] = status
            
            contributions = frappe.get_all(
                "SHG Contribution",
                filters=filters,
                fields=["name", "contribution_date", "amount", "expected_amount", 
                       "amount_paid", "unpaid_amount", "status", "payment_method"],
                order_by="contribution_date desc"
            )
            
            return contributions
            
        except Exception as e:
            self.logger.error(f"Failed to fetch member contributions: {str(e)}")
            frappe.throw(f"Failed to fetch contributions: {str(e)}")
    
    def calculate_contribution_summary(self, member_id: str) -> Dict:
        """
        Calculate contribution summary for a member
        
        Args:
            member_id: Member ID
            
        Returns:
            Dict with contribution summary statistics
        """
        try:
            contributions = self.get_member_contributions(member_id)
            
            total_expected = sum(flt(c.expected_amount or c.amount) for c in contributions)
            total_paid = sum(flt(c.amount_paid) for c in contributions)
            total_unpaid = sum(flt(c.unpaid_amount) for c in contributions)
            
            paid_count = len([c for c in contributions if c.status == "Paid"])
            unpaid_count = len([c for c in contributions if c.status == "Unpaid"])
            partial_count = len([c for c in contributions if c.status == "Partially Paid"])
            
            return {
                'member': member_id,
                'total_expected': total_expected,
                'total_paid': total_paid,
                'total_unpaid': total_unpaid,
                'paid_contributions': paid_count,
                'unpaid_contributions': unpaid_count,
                'partial_contributions': partial_count,
                'total_contributions': len(contributions),
                'payment_percentage': (total_paid / total_expected * 100) if total_expected > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate contribution summary: {str(e)}")
            frappe.throw(f"Failed to calculate summary: {str(e)}")

# Global service instance
contribution_service = ContributionService()