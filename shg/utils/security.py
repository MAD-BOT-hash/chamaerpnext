import frappe
import hashlib
import secrets
from cryptography.fernet import Fernet
from typing import Optional, Dict, Any
import json

class SHGSecurity:
    """
    Security module for SHG ERPNext application
    Handles encryption, data protection, and GDPR compliance
    """
    
    def __init__(self):
        self.settings = frappe.get_single("SHG Settings")
    
    def encrypt_data(self, data: str) -> str:
        """
        Encrypt sensitive data using Fernet symmetric encryption
        
        Args:
            data: String data to encrypt
            
        Returns:
            Encrypted data as string
        """
        try:
            # Get or generate encryption key
            encryption_key = self._get_encryption_key()
            cipher_suite = Fernet(encryption_key.encode())
            
            encrypted_data = cipher_suite.encrypt(data.encode())
            return encrypted_data.decode()
        except Exception as e:
            frappe.log_error(f"Encryption failed: {str(e)}", "SHG Security Error")
            raise
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive data
        
        Args:
            encrypted_data: Encrypted data as string
            
        Returns:
            Decrypted data as string
        """
        try:
            # Get encryption key
            encryption_key = self._get_encryption_key()
            cipher_suite = Fernet(encryption_key.encode())
            
            decrypted_data = cipher_suite.decrypt(encrypted_data.encode())
            return decrypted_data.decode()
        except Exception as e:
            frappe.log_error(f"Decryption failed: {str(e)}", "SHG Security Error")
            raise
    
    def _get_encryption_key(self) -> str:
        """
        Get or generate encryption key from settings
        """
        # Check if encryption key exists in settings
        if not hasattr(self.settings, 'encryption_key') or not self.settings.encryption_key:
            # Generate a new key
            key = Fernet.generate_key().decode()
            
            # Store in settings (this would typically be in a secure field)
            # For now, we'll use a custom field approach
            self.settings.encryption_key = key
            self.settings.save(ignore_permissions=True)
            
            return key
        else:
            return self.settings.encryption_key
    
    def hash_data(self, data: str, algorithm: str = 'sha256') -> str:
        """
        Hash data using specified algorithm
        
        Args:
            data: String data to hash
            algorithm: Hash algorithm ('sha256', 'sha512', 'md5')
            
        Returns:
            Hashed data as hex string
        """
        if algorithm == 'sha256':
            return hashlib.sha256(data.encode()).hexdigest()
        elif algorithm == 'sha512':
            return hashlib.sha512(data.encode()).hexdigest()
        elif algorithm == 'md5':
            return hashlib.md5(data.encode()).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generate a cryptographically secure token
        
        Args:
            length: Length of the token in bytes (default 32)
            
        Returns:
            Secure token as hex string
        """
        return secrets.token_hex(length)
    
    def mask_sensitive_data(self, data: str, mask_char: str = '*', 
                           visible_chars: int = 2, position: str = 'middle') -> str:
        """
        Mask sensitive data like phone numbers or ID numbers
        
        Args:
            data: String to mask
            mask_char: Character to use for masking
            visible_chars: Number of characters to keep visible
            position: Where to show visible chars ('start', 'end', 'middle')
            
        Returns:
            Masked string
        """
        if len(data) <= visible_chars * 2:
            return mask_char * len(data)
        
        if position == 'start':
            return data[:visible_chars] + (mask_char * (len(data) - visible_chars))
        elif position == 'end':
            return (mask_char * (len(data) - visible_chars)) + data[-visible_chars:]
        elif position == 'middle':
            mid_point = len(data) // 2
            start_visible = max(0, mid_point - visible_chars // 2)
            end_visible = min(len(data), start_visible + visible_chars)
            
            result = list(mask_char * len(data))
            result[:visible_chars] = list(data[:visible_chars])
            result[-visible_chars:] = list(data[-visible_chars:])
            
            return ''.join(result)
        else:
            raise ValueError(f"Invalid position: {position}")

class DataPrivacyManager:
    """
    Manager for GDPR and data privacy compliance
    """
    
    def __init__(self):
        self.security = SHGSecurity()
    
    def anonymize_member_data(self, member_id: str) -> Dict[str, Any]:
        """
        Anonymize member data for privacy compliance
        
        Args:
            member_id: ID of the member to anonymize
            
        Returns:
            Dictionary with anonymization results
        """
        try:
            member = frappe.get_doc("SHG Member", member_id)
            
            # Store original data temporarily for restoration if needed
            original_data = {
                'member_name': member.member_name,
                'phone_number': getattr(member, 'phone_number', ''),
                'id_number': getattr(member, 'id_number', ''),
                'email': getattr(member, 'email', ''),
                'address': getattr(member, 'address', '')
            }
            
            # Anonymize data
            masked_phone = self.security.mask_sensitive_data(original_data['phone_number'])
            masked_id = self.security.mask_sensitive_data(original_data['id_number'])
            masked_email = self._mask_email(original_data['email'])
            
            # Update member with anonymized data
            member.member_name = f"Anonymized Member {member.name[-4:]}"
            if hasattr(member, 'phone_number'):
                member.phone_number = masked_phone
            if hasattr(member, 'id_number'):
                member.id_number = masked_id
            if hasattr(member, 'email'):
                member.email = masked_email
            if hasattr(member, 'address'):
                member.address = "Anonymized Address"
            
            member.anonymized = 1  # Assuming we add this field
            member.save(ignore_permissions=True)
            
            return {
                "status": "success",
                "member_id": member_id,
                "original_data_masked": True,
                "fields_anonymized": list(original_data.keys()),
                "timestamp": frappe.utils.now()
            }
            
        except Exception as e:
            frappe.log_error(f"Anonymization failed for member {member_id}: {str(e)}", 
                           "SHG Data Privacy Error")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _mask_email(self, email: str) -> str:
        """
        Mask email address
        
        Args:
            email: Email address to mask
            
        Returns:
            Masked email address
        """
        if '@' not in email:
            return self.security.mask_sensitive_data(email)
        
        local_part, domain = email.split('@', 1)
        masked_local = self.security.mask_sensitive_data(local_part, visible_chars=2)
        return f"{masked_local}@{domain}"
    
    def delete_member_data(self, member_id: str, retention_period_days: int = 30) -> Dict[str, Any]:
        """
        Delete member data after retention period
        
        Args:
            member_id: ID of the member to delete
            retention_period_days: Days to retain data before permanent deletion
            
        Returns:
            Dictionary with deletion results
        """
        try:
            # Check if retention period has passed
            member = frappe.get_doc("SHG Member", member_id)
            
            # Instead of immediate deletion, mark as deleted and schedule actual deletion
            member.data_retention_end = frappe.utils.add_days(frappe.utils.nowdate(), retention_period_days)
            member.deleted_flag = 1  # Assuming we add this field
            member.save(ignore_permissions=True)
            
            # Also mark related records
            related_docs = [
                "SHG Contribution",
                "SHG Loan", 
                "SHG Loan Repayment",
                "SHG Meeting Attendance",
                "SHG Meeting Fine",
                "SHG Notification Log"
            ]
            
            for doctype in related_docs:
                try:
                    doc_list = frappe.get_all(doctype, filters={"member": member_id})
                    for doc in doc_list:
                        try:
                            doc_obj = frappe.get_doc(doctype, doc.name)
                            doc_obj.data_retention_end = frappe.utils.add_days(
                                frappe.utils.nowdate(), retention_period_days
                            )
                            doc_obj.deleted_flag = 1
                            doc_obj.save(ignore_permissions=True)
                        except:
                            continue  # Skip if document doesn't have these fields
                except:
                    continue  # Skip if doctype doesn't exist
            
            return {
                "status": "success",
                "member_id": member_id,
                "retention_period": retention_period_days,
                "scheduled_for_deletion": frappe.utils.add_days(frappe.utils.nowdate(), retention_period_days),
                "timestamp": frappe.utils.now()
            }
            
        except Exception as e:
            frappe.log_error(f"Data deletion failed for member {member_id}: {str(e)}", 
                           "SHG Data Privacy Error")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def export_member_data(self, member_id: str) -> Dict[str, Any]:
        """
        Export member data for GDPR compliance
        
        Args:
            member_id: ID of the member to export data for
            
        Returns:
            Dictionary with member data
        """
        try:
            member = frappe.get_doc("SHG Member", member_id)
            
            # Collect all related data
            member_data = {
                "member_info": {
                    "name": member.name,
                    "member_name": member.member_name,
                    "phone_number": getattr(member, 'phone_number', ''),
                    "id_number": getattr(member, 'id_number', ''),
                    "email": getattr(member, 'email', ''),
                    "membership_status": getattr(member, 'membership_status', ''),
                    "date_of_registration": getattr(member, 'date_of_registration', ''),
                    "created": member.creation,
                    "modified": member.modified
                },
                "contributions": [],
                "loans": [],
                "loan_repayments": [],
                "meetings_attended": [],
                "notifications": []
            }
            
            # Get contributions
            contributions = frappe.get_all(
                "SHG Contribution",
                filters={"member": member_id},
                fields=["*"]
            )
            member_data["contributions"] = contributions
            
            # Get loans
            loans = frappe.get_all(
                "SHG Loan", 
                filters={"member": member_id},
                fields=["*"]
            )
            member_data["loans"] = loans
            
            # Get loan repayments
            repayments = frappe.get_all(
                "SHG Loan Repayment",
                filters={"loan": ["in", [loan.name for loan in loans]]},
                fields=["*"]
            )
            member_data["loan_repayments"] = repayments
            
            # Get meeting attendance
            attendances = frappe.get_all(
                "SHG Member Attendance",
                filters={"member": member_id},
                fields=["*"]
            )
            member_data["meetings_attended"] = attendances
            
            # Get notifications
            notifications = frappe.get_all(
                "SHG Notification Log",
                filters={"member": member_id},
                fields=["*"]
            )
            member_data["notifications"] = notifications
            
            return {
                "status": "success",
                "member_id": member_id,
                "data": member_data,
                "export_timestamp": frappe.utils.now()
            }
            
        except Exception as e:
            frappe.log_error(f"Data export failed for member {member_id}: {str(e)}", 
                           "SHG Data Privacy Error")
            return {
                "status": "error",
                "error": str(e)
            }

# Global functions for easy access
def encrypt_data(data: str) -> str:
    """
    Convenience function to encrypt data
    """
    security = SHGSecurity()
    return security.encrypt_data(data)

def decrypt_data(encrypted_data: str) -> str:
    """
    Convenience function to decrypt data
    """
    security = SHGSecurity()
    return security.decrypt_data(encrypted_data)

def hash_data(data: str, algorithm: str = 'sha256') -> str:
    """
    Convenience function to hash data
    """
    security = SHGSecurity()
    return security.hash_data(data, algorithm)

def anonymize_member_data(member_id: str) -> Dict[str, Any]:
    """
    Convenience function to anonymize member data
    """
    manager = DataPrivacyManager()
    return manager.anonymize_member_data(member_id)

def delete_member_data(member_id: str, retention_period_days: int = 30) -> Dict[str, Any]:
    """
    Convenience function to delete member data
    """
    manager = DataPrivacyManager()
    return manager.delete_member_data(member_id, retention_period_days)

def export_member_data(member_id: str) -> Dict[str, Any]:
    """
    Convenience function to export member data
    """
    manager = DataPrivacyManager()
    return manager.export_member_data(member_id)

def generate_secure_token(length: int = 32) -> str:
    """
    Convenience function to generate secure token
    """
    security = SHGSecurity()
    return security.generate_secure_token(length)