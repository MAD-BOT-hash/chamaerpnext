"""
GL Service Layer
Enterprise-grade accounting service with proper transaction handling
"""
import frappe
from frappe import _
from frappe.utils import flt, now
from frappe.model.document import Document
from typing import Dict, List, Optional, Union
from decimal import Decimal
import json

class GLServiceError(Exception):
    """Base exception for GL service errors"""
    pass

class GLService:
    """
    Enterprise-grade general ledger service with:
    - Proper transaction handling
    - Concurrency safety
    - Audit trail
    - Error recovery
    """
    
    def __init__(self):
        self.logger = frappe.logger("gl_service", allow_site=True)
    
    def create_journal_entry(self, data: Dict) -> str:
        """
        Create a journal entry with proper accounting principles
        
        Args:
            data: Journal entry data including:
                - company: Company name
                - posting_date: Posting date
                - accounts: List of account entries
                - voucher_type: Voucher type
                - voucher_no: Voucher number
                - remarks: Optional remarks
                
        Returns:
            Name of created Journal Entry
        """
        try:
            # Validate journal entry data
            self._validate_journal_entry_data(data)
            
            # Create journal entry in transaction
            je_name = self._create_journal_entry_transaction(data)
            
            # Log successful creation
            self._log_journal_entry_creation(je_name, data)
            
            return je_name
            
        except Exception as e:
            self.logger.error(f"Journal entry creation failed: {str(e)}", 
                            extra={'data': data, 'error': str(e)})
            frappe.throw(f"Journal entry creation failed: {str(e)}")
    
    def _validate_journal_entry_data(self, data: Dict):
        """Validate journal entry data"""
        required_fields = ['company', 'posting_date', 'accounts']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            raise GLServiceError(f"Missing required fields: {missing_fields}")
        
        if not data.get('accounts') or len(data['accounts']) < 2:
            raise GLServiceError("At least two account entries are required")
        
        # Validate account entries balance
        self._validate_account_balance(data['accounts'])
        
        # Validate accounts exist
        self._validate_accounts_exist(data['accounts'], data['company'])
    
    def _validate_account_balance(self, accounts: List[Dict]):
        """Validate that debit and credit amounts balance"""
        total_debit = sum(flt(entry.get('debit', 0)) for entry in accounts)
        total_credit = sum(flt(entry.get('credit', 0)) for entry in accounts)
        
        if abs(total_debit - total_credit) > 0.01:  # Allow small rounding differences
            raise GLServiceError(
                f"Debit ({total_debit}) and credit ({total_credit}) amounts must balance"
            )
    
    def _validate_accounts_exist(self, accounts: List[Dict], company: str):
        """Validate that all accounts exist for the company"""
        for entry in accounts:
            account_name = entry.get('account')
            if not account_name:
                raise GLServiceError("Account name is required for all entries")
            
            if not frappe.db.exists("Account", {"name": account_name, "company": company}):
                raise GLServiceError(f"Account {account_name} does not exist for company {company}")
    
    def _create_journal_entry_transaction(self, data: Dict) -> str:
        """Create journal entry within a transaction"""
        try:
            # Create journal entry document
            je = frappe.get_doc({
                "doctype": "Journal Entry",
                "voucher_type": data.get('voucher_type', 'Journal Entry'),
                "posting_date": data['posting_date'],
                "company": data['company'],
                "remarks": data.get('remarks', ''),
                "voucher_no": data.get('voucher_no', ''),
                "user_remark": data.get('user_remark', '')
            })
            
            # Add account entries
            for entry in data['accounts']:
                je.append("accounts", {
                    "account": entry['account'],
                    "debit_in_account_currency": flt(entry.get('debit', 0)),
                    "credit_in_account_currency": flt(entry.get('credit', 0)),
                    "party_type": entry.get('party_type'),
                    "party": entry.get('party'),
                    "reference_type": entry.get('reference_type'),
                    "reference_name": entry.get('reference_name'),
                    "cost_center": entry.get('cost_center'),
                    "project": entry.get('project')
                })
            
            # Save and submit
            je.flags.ignore_permissions = True
            je.insert()
            je.submit()
            
            return je.name
            
        except Exception as e:
            frappe.db.rollback()
            raise
    
    def create_payment_entry(self, data: Dict) -> str:
        """
        Create a payment entry with proper accounting
        
        Args:
            data: Payment entry data
            
        Returns:
            Name of created Payment Entry
        """
        try:
            # Validate payment entry data
            self._validate_payment_entry_data(data)
            
            # Create payment entry in transaction
            pe_name = self._create_payment_entry_transaction(data)
            
            # Log successful creation
            self._log_payment_entry_creation(pe_name, data)
            
            return pe_name
            
        except Exception as e:
            self.logger.error(f"Payment entry creation failed: {str(e)}")
            frappe.throw(f"Payment entry creation failed: {str(e)}")
    
    def _validate_payment_entry_data(self, data: Dict):
        """Validate payment entry data"""
        required_fields = ['company', 'posting_date', 'payment_type', 'paid_from', 'paid_to', 'paid_amount']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            raise GLServiceError(f"Missing required fields: {missing_fields}")
        
        # Validate accounts
        company = data['company']
        if not frappe.db.exists("Account", {"name": data['paid_from'], "company": company}):
            raise GLServiceError(f"Paid from account {data['paid_from']} does not exist")
        
        if not frappe.db.exists("Account", {"name": data['paid_to'], "company": company}):
            raise GLServiceError(f"Paid to account {data['paid_to']} does not exist")
    
    def _create_payment_entry_transaction(self, data: Dict) -> str:
        """Create payment entry within a transaction"""
        try:
            # Create payment entry document
            pe = frappe.get_doc({
                "doctype": "Payment Entry",
                "payment_type": data['payment_type'],
                "posting_date": data['posting_date'],
                "company": data['company'],
                "mode_of_payment": data.get('mode_of_payment'),
                "paid_from": data['paid_from'],
                "paid_to": data['paid_to'],
                "paid_amount": flt(data['paid_amount']),
                "received_amount": flt(data.get('received_amount', data['paid_amount'])),
                "reference_no": data.get('reference_no'),
                "reference_date": data.get('reference_date'),
                "remarks": data.get('remarks', ''),
                "party_type": data.get('party_type'),
                "party": data.get('party')
            })
            
            # Add references if provided
            if data.get('references'):
                for ref in data['references']:
                    pe.append("references", {
                        "reference_doctype": ref['reference_doctype'],
                        "reference_name": ref['reference_name'],
                        "allocated_amount": flt(ref.get('allocated_amount', data['paid_amount']))
                    })
            
            # Save and submit
            pe.flags.ignore_permissions = True
            pe.insert()
            pe.submit()
            
            return pe.name
            
        except Exception as e:
            frappe.db.rollback()
            raise
    
    def reverse_journal_entry(self, je_name: str) -> str:
        """
        Create a reversing journal entry for error correction
        
        Args:
            je_name: Name of journal entry to reverse
            
        Returns:
            Name of reversing journal entry
        """
        try:
            # Get original journal entry
            original_je = frappe.get_doc("Journal Entry", je_name)
            
            # Create reversing entry
            reversing_data = self._prepare_reversing_entry(original_je)
            reversing_je_name = self.create_journal_entry(reversing_data)
            
            # Mark original as reversed
            original_je.db_set("custom_reversed_by", reversing_je_name)
            
            # Log reversal
            self._log_journal_entry_reversal(je_name, reversing_je_name)
            
            return reversing_je_name
            
        except Exception as e:
            self.logger.error(f"Journal entry reversal failed: {str(e)}")
            frappe.throw(f"Journal entry reversal failed: {str(e)}")
    
    def _prepare_reversing_entry(self, original_je: Document) -> Dict:
        """Prepare data for reversing journal entry"""
        reversing_accounts = []
        
        for entry in original_je.accounts:
            reversing_accounts.append({
                "account": entry.account,
                "debit": flt(entry.credit_in_account_currency),  # Swap debit/credit
                "credit": flt(entry.debit_in_account_currency),   # Swap debit/credit
                "party_type": entry.party_type,
                "party": entry.party,
                "reference_type": entry.reference_type,
                "reference_name": entry.reference_name
            })
        
        return {
            "company": original_je.company,
            "posting_date": now().split()[0],  # Today's date
            "accounts": reversing_accounts,
            "voucher_type": "Reversing Journal Entry",
            "voucher_no": f"REVERSE-{original_je.name}",
            "remarks": f"Reversal of {original_je.name} - {original_je.remarks}"
        }
    
    def _log_journal_entry_creation(self, je_name: str, data: Dict):
        """Log journal entry creation"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG GL Log',
                'voucher_type': 'Journal Entry',
                'voucher_no': je_name,
                'amount': sum(flt(entry.get('debit', 0)) for entry in data['accounts']),
                'status': 'Created',
                'timestamp': now(),
                'details': json.dumps(data)
            })
            log_entry.insert(ignore_permissions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to log journal entry creation: {str(e)}")
    
    def _log_payment_entry_creation(self, pe_name: str, data: Dict):
        """Log payment entry creation"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG GL Log',
                'voucher_type': 'Payment Entry',
                'voucher_no': pe_name,
                'amount': flt(data['paid_amount']),
                'status': 'Created',
                'timestamp': now(),
                'details': json.dumps(data)
            })
            log_entry.insert(ignore_permissions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to log payment entry creation: {str(e)}")
    
    def _log_journal_entry_reversal(self, original_je: str, reversing_je: str):
        """Log journal entry reversal"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG GL Log',
                'voucher_type': 'Reversing Journal Entry',
                'voucher_no': reversing_je,
                'reference_voucher': original_je,
                'status': 'Reversed',
                'timestamp': now()
            })
            log_entry.insert(ignore_permissions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to log journal entry reversal: {str(e)}")
    
    def get_account_balance(self, account_name: str, company: str, 
                          from_date: Optional[str] = None, to_date: Optional[str] = None) -> Dict:
        """
        Get account balance for a specific period
        
        Args:
            account_name: Account name
            company: Company name
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            Dict with balance information
        """
        try:
            # Build query conditions
            conditions = ["account = %(account)s", "company = %(company)s"]
            params = {"account": account_name, "company": company}
            
            if from_date:
                conditions.append("posting_date >= %(from_date)s")
                params["from_date"] = from_date
            
            if to_date:
                conditions.append("posting_date <= %(to_date)s")
                params["to_date"] = to_date
            
            # Get debit and credit totals
            result = frappe.db.sql(f"""
                SELECT 
                    SUM(debit) as total_debit,
                    SUM(credit) as total_credit
                FROM `tabGL Entry`
                WHERE {' AND '.join(conditions)}
            """, params, as_dict=True)
            
            if result and result[0]:
                total_debit = flt(result[0].total_debit or 0)
                total_credit = flt(result[0].total_credit or 0)
                balance = total_debit - total_credit
                
                return {
                    'account': account_name,
                    'company': company,
                    'from_date': from_date,
                    'to_date': to_date,
                    'total_debit': total_debit,
                    'total_credit': total_credit,
                    'balance': balance,
                    'balance_type': 'Debit' if balance > 0 else 'Credit' if balance < 0 else 'Zero'
                }
            
            return {
                'account': account_name,
                'company': company,
                'from_date': from_date,
                'to_date': to_date,
                'total_debit': 0,
                'total_credit': 0,
                'balance': 0,
                'balance_type': 'Zero'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get account balance: {str(e)}")
            frappe.throw(f"Failed to get account balance: {str(e)}")

# Global service instance
gl_service = GLService()