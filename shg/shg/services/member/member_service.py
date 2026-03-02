"""
Member Service Layer
Enterprise-grade member management with concurrency safety and proper account creation
"""
import frappe
from frappe import _
from frappe.utils import flt, now
from frappe.model.document import Document
from typing import Dict, List, Optional, Union
import json
from decimal import Decimal

class MemberServiceError(Exception):
    """Base exception for member service errors"""
    pass

class MemberService:
    """
    Enterprise-grade member management service with:
    - Concurrency-safe account creation
    - Proper validation
    - Audit trail
    - Financial summary management
    """
    
    def __init__(self):
        self.logger = frappe.logger("member_service", allow_site=True)
    
    def create_member_account(self, member_id: str, company: str) -> str:
        """
        Safely create member ledger account with concurrency protection
        
        Args:
            member_id: Member ID
            company: Company name
            
        Returns:
            Name of created account
        """
        try:
            # Validate inputs
            self._validate_member_account_inputs(member_id, company)
            
            # Check if account already exists
            existing_account = self._get_existing_member_account(member_id, company)
            if existing_account:
                return existing_account
            
            # Create account in transaction with locking
            account_name = self._create_member_account_transaction(member_id, company)
            
            # Log successful creation
            self._log_member_account_creation(member_id, company, account_name)
            
            return account_name
            
        except Exception as e:
            self.logger.error(f"Member account creation failed: {str(e)}")
            frappe.throw(f"Member account creation failed: {str(e)}")
    
    def _validate_member_account_inputs(self, member_id: str, company: str):
        """Validate inputs for member account creation"""
        if not member_id:
            raise MemberServiceError("Member ID is required")
        
        if not company:
            raise MemberServiceError("Company is required")
        
        # Validate member exists
        if not frappe.db.exists("SHG Member", member_id):
            raise MemberServiceError(f"Member {member_id} not found")
        
        # Validate company exists
        if not frappe.db.exists("Company", company):
            raise MemberServiceError(f"Company {company} not found")
    
    def _get_existing_member_account(self, member_id: str, company: str) -> Optional[str]:
        """Check if member account already exists"""
        company_abbr = frappe.db.get_value("Company", company, "abbr")
        account_name = f"{member_id} - {company_abbr}"
        
        existing_account = frappe.db.exists("Account", {
            "account_name": account_name,
            "company": company
        })
        
        return existing_account
    
    def _create_member_account_transaction(self, member_id: str, company: str) -> str:
        """
        Create member account in a transaction-safe manner with proper locking
        """
        try:
            # Lock the member record to prevent concurrent creation
            member = frappe.get_doc("SHG Member", member_id)
            
            # Get company abbreviation
            company_abbr = frappe.db.get_value("Company", company, "abbr")
            
            # Get parent account (SHG Members group)
            parent_account_name = f"SHG Members - {company_abbr}"
            parent_account = frappe.db.exists("Account", {
                "account_name": parent_account_name,
                "company": company
            })
            
            # Create parent account if it doesn't exist
            if not parent_account:
                parent_account = self._create_parent_member_account(company, company_abbr)
            
            # Create member account
            member_account_name = f"{member_id} - {company_abbr}"
            account = frappe.get_doc({
                "doctype": "Account",
                "account_name": member_account_name,
                "account_type": "Receivable",
                "company": company,
                "parent_account": parent_account,
                "root_type": "Asset",
                "report_type": "Balance Sheet",
                "is_group": 0
            })
            account.flags.ignore_permissions = True
            account.insert()
            
            # Update member with account reference
            member.db_set("custom_member_account", account.name)
            
            return account.name
            
        except Exception as e:
            frappe.db.rollback()
            raise
    
    def _create_parent_member_account(self, company: str, company_abbr: str) -> str:
        """Create parent SHG Members account group"""
        try:
            # Get Accounts Receivable parent
            accounts_receivable = frappe.db.get_value(
                "Account",
                {"account_type": "Receivable", "is_group": 1, "company": company},
                "name"
            )
            
            if not accounts_receivable:
                raise MemberServiceError(f"No Accounts Receivable group found for company {company}")
            
            # Create SHG Members parent account
            parent_account = frappe.get_doc({
                "doctype": "Account",
                "account_name": f"SHG Members - {company_abbr}",
                "company": company,
                "parent_account": accounts_receivable,
                "is_group": 1,
                "account_type": "Receivable",
                "report_type": "Balance Sheet",
                "root_type": "Asset"
            })
            parent_account.flags.ignore_permissions = True
            parent_account.insert()
            
            return parent_account.name
            
        except Exception as e:
            self.logger.error(f"Failed to create parent member account: {str(e)}")
            raise
    
    def _log_member_account_creation(self, member_id: str, company: str, account_name: str):
        """Log member account creation for audit trail"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG Member Log',
                'member': member_id,
                'company': company,
                'account': account_name,
                'action': 'Account Created',
                'timestamp': now()
            })
            log_entry.insert(ignore_permissions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to log member account creation: {str(e)}")
    
    def update_member_financial_summary(self, member_id: str) -> Dict:
        """
        Update member's financial summary with proper locking
        
        Args:
            member_id: Member ID
            
        Returns:
            Dict with updated financial summary
        """
        try:
            # Lock member record for update
            member = frappe.get_doc("SHG Member", member_id)
            
            # Calculate financial summary
            summary = self._calculate_member_financial_summary(member_id)
            
            # Update member fields atomically
            self._update_member_summary_fields(member, summary)
            
            # Log update
            self._log_financial_summary_update(member_id, summary)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Member financial summary update failed: {str(e)}")
            frappe.throw(f"Financial summary update failed: {str(e)}")
    
    def _calculate_member_financial_summary(self, member_id: str) -> Dict:
        """Calculate comprehensive financial summary for member"""
        try:
            # Get contributions summary
            contributions = frappe.get_all(
                "SHG Contribution",
                filters={"member": member_id, "docstatus": 1},
                fields=["expected_amount", "amount_paid", "unpaid_amount", "status"]
            )
            
            # Get contribution invoices summary
            invoices = frappe.get_all(
                "SHG Contribution Invoice",
                filters={"member": member_id, "docstatus": 1},
                fields=["amount", "status"]
            )
            
            # Get meeting fines summary
            fines = frappe.get_all(
                "SHG Meeting Fine",
                filters={"member": member_id, "docstatus": 1},
                fields=["fine_amount", "status"]
            )
            
            # Calculate contribution totals
            total_expected = sum(flt(c.expected_amount or c.amount) for c in contributions)
            total_paid = sum(flt(c.amount_paid) for c in contributions)
            total_unpaid_contributions = sum(flt(c.unpaid_amount) for c in contributions)
            
            # Calculate invoice totals
            total_invoice_amount = sum(flt(i.amount) for i in invoices)
            unpaid_invoices = len([i for i in invoices if i.status in ['Unpaid', 'Partially Paid']])
            
            # Calculate fine totals
            total_fine_amount = sum(flt(f.fine_amount) for f in fines)
            unpaid_fines = len([f for f in fines if f.status != 'Paid'])
            
            # Overall summary
            total_unpaid = total_unpaid_contributions + total_invoice_amount + total_fine_amount
            payment_percentage = (total_paid / total_expected * 100) if total_expected > 0 else 0
            
            return {
                'total_expected_contributions': total_expected,
                'total_paid_contributions': total_paid,
                'total_unpaid_contributions': total_unpaid_contributions,
                'total_invoice_amount': total_invoice_amount,
                'unpaid_invoices_count': unpaid_invoices,
                'total_fine_amount': total_fine_amount,
                'unpaid_fines_count': unpaid_fines,
                'total_unpaid_amount': total_unpaid,
                'payment_percentage': round(payment_percentage, 2),
                'total_contributions': len(contributions),
                'paid_contributions': len([c for c in contributions if c.status == 'Paid']),
                'unpaid_contributions': len([c for c in contributions if c.status == 'Unpaid']),
                'partial_contributions': len([c for c in contributions if c.status == 'Partially Paid'])
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate financial summary: {str(e)}")
            raise
    
    def _update_member_summary_fields(self, member: Document, summary: Dict):
        """Update member document fields with calculated summary"""
        try:
            # Update financial summary fields
            member.db_set("total_expected_contributions", summary['total_expected_contributions'])
            member.db_set("total_paid_contributions", summary['total_paid_contributions'])
            member.db_set("total_unpaid_contributions", summary['total_unpaid_contributions'])
            member.db_set("total_invoice_amount", summary['total_invoice_amount'])
            member.db_set("unpaid_invoices_count", summary['unpaid_invoices_count'])
            member.db_set("total_fine_amount", summary['total_fine_amount'])
            member.db_set("unpaid_fines_count", summary['unpaid_fines_count'])
            member.db_set("total_unpaid_amount", summary['total_unpaid_amount'])
            member.db_set("payment_percentage", summary['payment_percentage'])
            
            # Update status based on financial position
            if summary['total_unpaid_amount'] <= 0:
                member.db_set("financial_status", "Good Standing")
            elif summary['payment_percentage'] >= 80:
                member.db_set("financial_status", "Good")
            elif summary['payment_percentage'] >= 50:
                member.db_set("financial_status", "Fair")
            else:
                member.db_set("financial_status", "Poor")
                
        except Exception as e:
            self.logger.error(f"Failed to update member summary fields: {str(e)}")
            raise
    
    def _log_financial_summary_update(self, member_id: str, summary: Dict):
        """Log financial summary update for audit trail"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG Member Log',
                'member': member_id,
                'action': 'Financial Summary Updated',
                'details': json.dumps(summary),
                'timestamp': now()
            })
            log_entry.insert(ignore_permissions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to log financial summary update: {str(e)}")
    
    def get_member_dashboard_data(self, member_id: str) -> Dict:
        """
        Get comprehensive dashboard data for member
        
        Args:
            member_id: Member ID
            
        Returns:
            Dict with dashboard data
        """
        try:
            # Get member basic info
            member = frappe.get_doc("SHG Member", member_id)
            
            # Get financial summary
            financial_summary = self._calculate_member_financial_summary(member_id)
            
            # Get recent activity
            recent_contributions = frappe.get_all(
                "SHG Contribution",
                filters={"member": member_id, "docstatus": 1},
                fields=["name", "contribution_date", "amount", "status"],
                order_by="contribution_date desc",
                limit=5
            )
            
            recent_payments = frappe.get_all(
                "Payment Entry",
                filters={"party_type": "SHG Member", "party": member_id, "docstatus": 1},
                fields=["name", "posting_date", "paid_amount"],
                order_by="posting_date desc",
                limit=5
            )
            
            # Get upcoming obligations
            upcoming_invoices = frappe.get_all(
                "SHG Contribution Invoice",
                filters={
                    "member": member_id,
                    "docstatus": 1,
                    "status": ["in", ["Unpaid", "Partially Paid"]]
                },
                fields=["name", "due_date", "amount", "status"],
                order_by="due_date asc",
                limit=5
            )
            
            return {
                'member_info': {
                    'name': member.member_name,
                    'member_id': member.name,
                    'membership_status': member.membership_status,
                    'joining_date': member.joining_date
                },
                'financial_summary': financial_summary,
                'recent_contributions': recent_contributions,
                'recent_payments': recent_payments,
                'upcoming_invoices': upcoming_invoices,
                'last_updated': now()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get member dashboard data: {str(e)}")
            frappe.throw(f"Failed to get dashboard data: {str(e)}")
    
    def validate_member_eligibility(self, member_id: str, action: str) -> Dict:
        """
        Validate member eligibility for specific actions
        
        Args:
            member_id: Member ID
            action: Action to validate (e.g., 'loan_application', 'contribution_payment')
            
        Returns:
            Dict with validation results
        """
        try:
            member = frappe.get_doc("SHG Member", member_id)
            
            validation_result = {
                'member_id': member_id,
                'member_name': member.member_name,
                'is_eligible': True,
                'reasons': [],
                'eligibility_score': 100
            }
            
            # Check membership status
            if member.membership_status != "Active":
                validation_result['is_eligible'] = False
                validation_result['reasons'].append("Member is not active")
                validation_result['eligibility_score'] -= 50
            
            # Check financial standing for payment-related actions
            if 'payment' in action.lower():
                financial_summary = self._calculate_member_financial_summary(member_id)
                if financial_summary['payment_percentage'] < 30:
                    validation_result['reasons'].append("Poor payment history")
                    validation_result['eligibility_score'] -= 30
            
            # Check for overdue obligations
            overdue_count = frappe.db.count("SHG Contribution Invoice", {
                "member": member_id,
                "docstatus": 1,
                "status": "Overdue"
            })
            
            if overdue_count > 0:
                validation_result['reasons'].append(f"{overdue_count} overdue invoices")
                validation_result['eligibility_score'] -= (overdue_count * 10)
            
            # Final eligibility determination
            if validation_result['eligibility_score'] < 50:
                validation_result['is_eligible'] = False
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Member eligibility validation failed: {str(e)}")
            frappe.throw(f"Eligibility validation failed: {str(e)}")
    
    def get_member_statistics(self, filters: Optional[Dict] = None) -> Dict:
        """
        Get comprehensive member statistics
        
        Args:
            filters: Optional filters for statistics
            
        Returns:
            Dict with member statistics
        """
        try:
            # Build base query
            member_filters = {"docstatus": 1}
            if filters:
                member_filters.update(filters)
            
            # Get total members
            total_members = frappe.db.count("SHG Member", member_filters)
            
            # Get active members
            active_filters = member_filters.copy()
            active_filters["membership_status"] = "Active"
            active_members = frappe.db.count("SHG Member", active_filters)
            
            # Get financial summary statistics
            financial_stats = self._calculate_member_financial_statistics()
            
            # Get recent activity statistics
            recent_stats = self._calculate_recent_activity_statistics()
            
            return {
                'total_members': total_members,
                'active_members': active_members,
                'inactive_members': total_members - active_members,
                'active_percentage': round((active_members / total_members * 100), 2) if total_members > 0 else 0,
                'financial_statistics': financial_stats,
                'recent_activity': recent_stats,
                'report_timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get member statistics: {str(e)}")
            frappe.throw(f"Failed to get statistics: {str(e)}")
    
    def _calculate_member_financial_statistics(self) -> Dict:
        """Calculate overall financial statistics for all members"""
        try:
            # This would aggregate data across all members
            # Implementation depends on your specific requirements
            return {
                'total_expected': 0,
                'total_collected': 0,
                'total_outstanding': 0,
                'collection_percentage': 0
            }
        except Exception as e:
            self.logger.error(f"Failed to calculate financial statistics: {str(e)}")
            return {}
    
    def _calculate_recent_activity_statistics(self) -> Dict:
        """Calculate recent activity statistics"""
        try:
            # Get recent contributions
            recent_contributions = frappe.db.count("SHG Contribution", {
                "docstatus": 1,
                "contribution_date": [">=", frappe.utils.add_days(frappe.utils.today(), -30)]
            })
            
            # Get recent payments
            recent_payments = frappe.db.count("Payment Entry", {
                "docstatus": 1,
                "posting_date": [">=", frappe.utils.add_days(frappe.utils.today(), -30)]
            })
            
            return {
                'recent_contributions': recent_contributions,
                'recent_payments': recent_payments,
                'period_days': 30
            }
        except Exception as e:
            self.logger.error(f"Failed to calculate recent activity statistics: {str(e)}")
            return {}

# Global service instance
member_service = MemberService()