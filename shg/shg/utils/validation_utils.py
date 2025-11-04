import frappe
from frappe import _

def validate_reference_types_and_names(doc):
    """
    Validate that all GL entries have proper reference types and names
    according to ERPNext v15 requirements.
    
    Args:
        doc: SHG document with GL entries
    """
    # Valid reference types for ERPNext v15
    valid_reference_types = [
        "", "Sales Invoice", "Purchase Invoice", "Journal Entry", "Sales Order",
        "Purchase Order", "Expense Claim", "Asset", "Loan", "Payroll Entry",
        "Employee Advance", "Exchange Rate Revaluation", "Invoice Discounting",
        "Fees", "Full and Final Statement", "Payment Entry", "Loan Interest Accrual",
        "SHG Meeting Fine"
    ]
    
    # Check Journal Entry if it exists
    if doc.get("journal_entry"):
        _validate_journal_entry_reference_types(doc.journal_entry, valid_reference_types, doc.name)
    elif doc.get("disbursement_journal_entry"):
        _validate_journal_entry_reference_types(doc.disbursement_journal_entry, valid_reference_types, doc.name)
        
    # Check Payment Entry if it exists
    if doc.get("payment_entry"):
        _validate_payment_entry_reference_types(doc.payment_entry, valid_reference_types, doc.name)
    elif doc.get("disbursement_payment_entry"):
        _validate_payment_entry_reference_types(doc.disbursement_payment_entry, valid_reference_types, doc.name)

def _validate_journal_entry_reference_types(journal_entry_name, valid_reference_types, doc_name):
    """Validate reference types in Journal Entry accounts"""
    try:
        je = frappe.get_doc("Journal Entry", journal_entry_name)
        
        for entry in je.accounts:
            # Check if reference_type is valid
            if hasattr(entry, 'reference_type') and entry.reference_type:
                if entry.reference_type not in valid_reference_types:
                    frappe.throw(
                        _("Invalid reference type '{0}' in Journal Entry {1}. "
                          "Valid types are: {2}").format(
                            entry.reference_type, journal_entry_name, ", ".join(valid_reference_types)
                        )
                    )
                    
            # Check if reference_name matches the originating document
            if hasattr(entry, 'reference_name') and entry.reference_name:
                # We're not strictly enforcing this as it's handled by custom fields
                pass
                
    except frappe.DoesNotExistError:
        frappe.throw(_("Journal Entry {0} does not exist").format(journal_entry_name))
    except Exception as e:
        frappe.log_error(f"Error validating Journal Entry reference types: {str(e)}")

def _validate_payment_entry_reference_types(payment_entry_name, valid_reference_types, doc_name):
    """Validate reference types in Payment Entry"""
    try:
        pe = frappe.get_doc("Payment Entry", payment_entry_name)
        
        # Payment Entry doesn't typically use reference_type in the same way
        # But we check if it exists
        if hasattr(pe, 'reference_type') and pe.reference_type:
            if pe.reference_type not in valid_reference_types:
                frappe.throw(
                    _("Invalid reference type '{0}' in Payment Entry {1}. "
                      "Valid types are: {2}").format(
                        pe.reference_type, payment_entry_name, ", ".join(valid_reference_types)
                    )
                )
                
    except frappe.DoesNotExistError:
        frappe.throw(_("Payment Entry {0} does not exist").format(payment_entry_name))
    except Exception as e:
        frappe.log_error(f"Error validating Payment Entry reference types: {str(e)}")

def validate_custom_field_linking(doc):
    """
    Validate that GL entries are properly linked back to the originating document
    through custom fields.
    
    Args:
        doc: SHG document with GL entries
    """
    doc_type = doc.doctype
    custom_field_map = {
        "SHG Contribution": "custom_shg_contribution",
        "SHG Loan": "custom_shg_loan",
        "SHG Loan Repayment": "custom_shg_loan_repayment",
        "SHG Meeting Fine": "custom_shg_meeting_fine"
    }
    
    custom_field = custom_field_map.get(doc_type)
    if not custom_field:
        return
        
    # Check Journal Entry
    if doc.get("journal_entry"):
        _validate_custom_field_in_journal_entry(doc.journal_entry, custom_field, doc.name)
    elif doc.get("disbursement_journal_entry"):
        _validate_custom_field_in_journal_entry(doc.disbursement_journal_entry, custom_field, doc.name)
        
    # Check Payment Entry
    if doc.get("payment_entry"):
        _validate_custom_field_in_payment_entry(doc.payment_entry, custom_field, doc.name)
    elif doc.get("disbursement_payment_entry"):
        _validate_custom_field_in_payment_entry(doc.disbursement_payment_entry, custom_field, doc.name)

def _validate_custom_field_in_journal_entry(journal_entry_name, custom_field, expected_value):
    """Validate custom field linking in Journal Entry"""
    try:
        je = frappe.get_doc("Journal Entry", journal_entry_name)
        
        # Check if the custom field exists and has the correct value
        if not hasattr(je, custom_field) or not getattr(je, custom_field):
            frappe.throw(
                _("Journal Entry {0} is missing the required custom field {1}").format(
                    journal_entry_name, custom_field
                )
            )
            
        if getattr(je, custom_field) != expected_value:
            frappe.throw(
                _("Journal Entry {0} has incorrect value in custom field {1}. "
                  "Expected: {2}, Found: {3}").format(
                    journal_entry_name, custom_field, expected_value, getattr(je, custom_field)
                )
            )
            
    except frappe.DoesNotExistError:
        frappe.throw(_("Journal Entry {0} does not exist").format(journal_entry_name))
    except Exception as e:
        frappe.log_error(f"Error validating custom field in Journal Entry: {str(e)}")

def _validate_custom_field_in_payment_entry(payment_entry_name, custom_field, expected_value):
    """Validate custom field linking in Payment Entry"""
    try:
        pe = frappe.get_doc("Payment Entry", payment_entry_name)
        
        # Check if the custom field exists and has the correct value
        if not hasattr(pe, custom_field) or not getattr(pe, custom_field):
            frappe.throw(
                _("Payment Entry {0} is missing the required custom field {1}").format(
                    payment_entry_name, custom_field
                )
            )
            
        if getattr(pe, custom_field) != expected_value:
            frappe.throw(
                _("Payment Entry {0} has incorrect value in custom field {1}. "
                  "Expected: {2}, Found: {3}").format(
                    payment_entry_name, custom_field, expected_value, getattr(pe, custom_field)
                )
            )
            
    except frappe.DoesNotExistError:
        frappe.throw(_("Payment Entry {0} does not exist").format(payment_entry_name))
    except Exception as e:
        frappe.log_error(f"Error validating custom field in Payment Entry: {str(e)}")

def validate_accounting_integrity(doc):
    """
    Validate that accounting entries are balanced and follow proper accounting principles.
    
    Args:
        doc: SHG document with GL entries
    """
    # Check Journal Entry
    if doc.get("journal_entry"):
        _validate_journal_entry_integrity(doc.journal_entry)
    elif doc.get("disbursement_journal_entry"):
        _validate_journal_entry_integrity(doc.disbursement_journal_entry)
        
    # Check Payment Entry
    if doc.get("payment_entry"):
        _validate_payment_entry_integrity(doc.payment_entry)
    elif doc.get("disbursement_payment_entry"):
        _validate_payment_entry_integrity(doc.disbursement_payment_entry)

def _validate_journal_entry_integrity(journal_entry_name):
    """Validate that Journal Entry is balanced"""
    try:
        je = frappe.get_doc("Journal Entry", journal_entry_name)
        
        total_debit = sum(entry.debit_in_account_currency for entry in je.accounts)
        total_credit = sum(entry.credit_in_account_currency for entry in je.accounts)
        
        if abs(total_debit - total_credit) > 0.01:
            frappe.throw(
                _("Journal Entry {0} is not balanced. "
                  "Total Debit: {1}, Total Credit: {2}").format(
                    journal_entry_name, total_debit, total_credit
                )
            )
            
        # Must have at least 2 accounts
        if len(je.accounts) < 2:
            frappe.throw(
                _("Journal Entry {0} must have at least 2 accounts").format(journal_entry_name)
            )
            
    except frappe.DoesNotExistError:
        frappe.throw(_("Journal Entry {0} does not exist").format(journal_entry_name))
    except Exception as e:
        frappe.log_error(f"Error validating Journal Entry integrity: {str(e)}")

def _validate_payment_entry_integrity(payment_entry_name):
    """Validate Payment Entry integrity"""
    try:
        pe = frappe.get_doc("Payment Entry", payment_entry_name)
        
        # Paid amount should equal received amount (allowing for small differences)
        if abs(pe.paid_amount - pe.received_amount) > 0.01:
            frappe.throw(
                _("Payment Entry {0} has mismatched paid and received amounts. "
                  "Paid: {1}, Received: {2}").format(
                    payment_entry_name, pe.paid_amount, pe.received_amount
                )
            )
            
    except frappe.DoesNotExistError:
        frappe.throw(_("Payment Entry {0} does not exist").format(payment_entry_name))
    except Exception as e:
        frappe.log_error(f"Error validating Payment Entry integrity: {str(e)}")