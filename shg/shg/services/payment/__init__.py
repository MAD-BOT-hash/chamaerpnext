# Payment Service Package
# Centralized allocation engine for all SHG payments

from .allocation_engine import (
    AllocationEngine,
    get_shg_document_total,
    get_outstanding_amount,
    get_paid_amount,
    allocate_payment_to_document,
    get_document_outstanding,
    get_invoice_total,  # Backward compatibility alias
    AllocationError,
    OverpaymentError,
    DocumentNotFoundError,
    DocumentLockedError,
    AlreadyPaidError,
    # Status constants
    STATUS_UNPAID,
    STATUS_PENDING,
    STATUS_PARTIALLY_PAID,
    STATUS_PAID,
    STATUS_WAIVED,
    STATUS_CANCELLED,
    STATUS_OVERDUE,
    PAYABLE_STATUSES,
    SETTLED_STATUSES,
)

from .bulk_payment_service import (
    BulkPaymentService,
    BulkPaymentServiceError,
    # Query functions
    get_unpaid_invoices_for_company,
    get_unpaid_invoices_for_member,
    get_unpaid_contributions_for_company,
    get_unpaid_contributions_for_member,
    get_unpaid_meeting_fines_for_company,
    get_unpaid_meeting_fines_for_member,
    get_unpaid_loan_installments_for_company,
    get_unpaid_loan_installments_for_member,
    get_all_unpaid_items_for_company,
    get_all_unpaid_items_for_member,
)

__all__ = [
    # Allocation Engine (SINGLE SOURCE OF TRUTH)
    'AllocationEngine',
    'get_shg_document_total',
    'get_outstanding_amount',
    'get_paid_amount',
    'allocate_payment_to_document',
    'get_document_outstanding',
    'get_invoice_total',
    'AllocationError',
    'OverpaymentError',
    'DocumentNotFoundError',
    'DocumentLockedError',
    'AlreadyPaidError',
    
    # Status constants
    'STATUS_UNPAID',
    'STATUS_PENDING',
    'STATUS_PARTIALLY_PAID',
    'STATUS_PAID',
    'STATUS_WAIVED',
    'STATUS_CANCELLED',
    'STATUS_OVERDUE',
    'PAYABLE_STATUSES',
    'SETTLED_STATUSES',
    
    # Bulk Payment Service
    'BulkPaymentService',
    'BulkPaymentServiceError',
    
    # Query Functions
    'get_unpaid_invoices_for_company',
    'get_unpaid_invoices_for_member',
    'get_unpaid_contributions_for_company',
    'get_unpaid_contributions_for_member',
    'get_unpaid_meeting_fines_for_company',
    'get_unpaid_meeting_fines_for_member',
    'get_unpaid_loan_installments_for_company',
    'get_unpaid_loan_installments_for_member',
    'get_all_unpaid_items_for_company',
    'get_all_unpaid_items_for_member',
]