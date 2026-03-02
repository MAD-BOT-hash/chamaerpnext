"""
SHG Services Main Entry Point
Enterprise-grade service layer orchestration
"""
from .payment.payment_service import payment_service, PaymentService
from .contribution.contribution_service import contribution_service, ContributionService
from .accounting.gl_service import gl_service, GLService
from .notification.notification_service import notification_service, NotificationService
from .member.member_service import member_service, MemberService
from .scheduler_service import scheduler_service, SchedulerService

# Service layer exports
__all__ = [
    'payment_service',
    'contribution_service', 
    'gl_service',
    'notification_service',
    'member_service',
    'scheduler_service',
    'PaymentService',
    'ContributionService',
    'GLService', 
    'NotificationService',
    'MemberService',
    'SchedulerService'
]

# Service registry for dependency injection
SERVICE_REGISTRY = {
    'payment': payment_service,
    'contribution': contribution_service,
    'accounting': gl_service,
    'notification': notification_service,
    'member': member_service,
    'scheduler': scheduler_service
}

def get_service(service_name: str):
    """Get service instance by name"""
    return SERVICE_REGISTRY.get(service_name)

def get_all_services():
    """Get all service instances"""
    return SERVICE_REGISTRY.copy()