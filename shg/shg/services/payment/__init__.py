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
)

from .bulk_payment_service import (
    BulkPaymentService,
    BulkPaymentServiceError,
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
    
    # Bulk Payment Service
    'BulkPaymentService',
    'BulkPaymentServiceError',
]