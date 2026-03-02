# SHG Enterprise Architecture Documentation

## Overview
This document describes the enterprise-grade architecture refactor for the SHG Multi Member Payment system, designed for production use with 10,000+ members.

## Architecture Components

### 1. Service Layer Architecture
The system follows a clean service layer architecture with proper separation of concerns:

```
shg/
└── shg/
   └── services/
        ├── contribution/
        │  └── contribution_service.py
        ├── payment/
        │   └── payment_service.py
        ├── accounting/
        │   └── gl_service.py
        ├── notification/
        │   └── notification_service.py
        ├── member/
        │   └── member_service.py
        ├── audit/
        │   └── audit_service.py
       └── scheduler_service.py
```

### 2. Core Services

#### ContributionService
- **Location**: `shg.shg.services.contribution.contribution_service`
- **Responsibilities**:
  - Create and manage SHG contributions
  - Prevent duplicate contributions using unique constraints
  - Handle contribution status updates
  - Generate contributions from sales invoices
  - Process contribution reversals

#### PaymentService
- **Location**: `shg.shg.services.payment.payment_service`
- **Key Features**:
  - **Overpayment Protection**: Prevents payments exceeding expected amounts
  - **Concurrency Safety**: Uses `SELECT FOR UPDATE` locking
  - **Idempotency**: All operations are idempotent
  - **Partial Payment Support**: Handles partial payments correctly
  - **Payment Reversal**: Safe payment reversal logic
  - **Atomic Operations**: All payment allocations are atomic

#### GLService
- **Location**: `shg.shg.services.accounting.gl_service`
- **Functions**:
  - Journal entry creation
  - Payment entry creation
  - Account balance calculations
  - Financial reporting

#### NotificationService
- **Location**: `shg.shg.services.notification.notification_service`
- **Channels**:
  - SMS notifications
  - Email notifications
  - WhatsApp notifications
  - Template-based messaging

#### MemberService
- **Location**: `shg.shg.services.member.member_service`
- **Features**:
  - Concurrency-safe member account creation
  - Financial summary calculations
  - Member eligibility validation
  - Account onboarding

#### AuditService
- **Location**: `shg.shg.services.audit.audit_service`
- **Capabilities**:
  - Comprehensive audit logging
  - Compliance reporting
  - Security event tracking
  - System health monitoring

#### SchedulerService
- **Location**: `shg.shg.services.scheduler_service`
- **Jobs**:
  - Daily overdue contribution processing
  - Weekly member statement generation
  - Monthly financial reporting
  - Payment reminder system

## Key Enterprise Features

### 1. Transaction Safety
All database operations use proper transaction management:
```python
def allocate_payment_transaction(self, payment_entry, contributions_data, total_payment):
    try:
        # All operations within single transaction
        frappe.db.commit()  # Only at successful completion
    except Exception:
        frappe.db.rollback()  # Automatic rollback on any error
        raise
```

### 2. Concurrency Protection
Critical sections use database-level locking:
```python
def _lock_contribution(self, contribution_name: str):
    # SELECT FOR UPDATE prevents race conditions
    locked_contribution = frappe.db.sql("""
        SELECT * FROM `tabSHG Contribution` 
        WHERE name = %s FOR UPDATE
    """, contribution_name, as_dict=True)
```

### 3. Overpayment Protection
Built-in validation prevents overpayments:
```python
def _validate_payment_amount(self, contribution, payment_amount: float):
    if contribution.paid_amount + payment_amount > contribution.expected_amount:
        frappe.throw(
            f"Payment amount {payment_amount} exceeds expected amount {contribution.expected_amount}"
        )
```

### 4. Duplicate Prevention
Strict unique constraints prevent duplicate entries:
```python
def _check_duplicate_contribution(self, member: str, contribution_type: str, 
                                 posting_date: str) -> bool:
    existing = frappe.db.exists("SHG Contribution", {
        "member": member,
        "contribution_type": contribution_type,
        "posting_date": posting_date
    })
    return existing is not None
```

### 5. Idempotency Guarantee
All operations are designed to be idempotent:
```python
def create_contribution(self, contribution_data: Dict) -> Dict:
    # Check if already exists before creating
    if self._check_duplicate_contribution(...):
        frappe.throw("Contribution already exists")
    # Only proceed if not duplicate
```

### 6. Structured Logging
Comprehensive logging for audit and debugging:
```python
def log_action(self, reference_doctype: str, reference_name: str, 
               action: str, details: Dict = None):
    # Create audit trail entry
    audit_log = frappe.get_doc({
        "doctype": "SHG Audit Trail",
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "action": action,
        "details": json.dumps(details) if details else None
    })
    audit_log.insert()
```

## Hooks Integration

### Document Event Hooks
```python
# In hooks.py
doc_events = {
    "Payment Entry": {
        "on_submit": [
            "shg.shg.services.payment.payment_service.handle_payment_entry_submit"
        ]
    },
    "Sales Invoice": {
        "on_submit": [
            "shg.shg.services.contribution.contribution_service.create_contribution_from_invoice"
        ]
    },
    "SHG Contribution": {
        "on_update": [
            "shg.shg.services.member.member_service.update_member_financial_summary"
        ]
    }
}
```

### Scheduler Jobs
```python
scheduler_events = {
    "daily": [
        "shg.shg.jobs.scheduler_jobs.process_daily_overdue_contributions",
        "shg.shg.jobs.scheduler_jobs.send_daily_payment_reminders"
    ],
    "weekly": [
        "shg.shg.jobs.scheduler_jobs.generate_weekly_member_statements"
    ],
    "monthly": [
        "shg.shg.jobs.scheduler_jobs.generate_monthly_financial_reports"
    ]
}
```

## Testing Strategy

### Unit Tests
- Service layer unit tests
- Concurrency testing
- Error handling validation
- Audit trail completeness

### Integration Tests
- Multi-member payment scenarios
- End-to-end payment flows
- Hook integration testing
- Scheduler job verification

### Performance Tests
- High-concurrency scenarios
- Large dataset processing
- Memory usage monitoring
- Response time benchmarks

## Security Features

### Access Control
- Role-based permissions
- Field-level security
- Audit trail for all operations
- Secure data handling

### Data Integrity
- Database constraints
- Validation rules
- Consistency checks
- Backup and recovery

## Monitoring and Maintenance

### Health Checks
- System health monitoring
- Performance metrics
- Error rate tracking
- Resource utilization

### Audit and Compliance
- Comprehensive audit trails
- Compliance reporting
- Data lineage tracking
- Regulatory requirements

## Deployment Considerations

### Production Ready Features
- Automatic retry mechanisms
- Graceful error handling
- Zero-downtime deployments
- Scalability planning

### Backup and Recovery
- Automated backups
- Point-in-time recovery
- Disaster recovery procedures
- Data consistency verification

## Performance Optimizations

### Database Optimizations
- Proper indexing
- Query optimization
- Connection pooling
- Caching strategies

### Application Optimizations
- Asynchronous processing
- Background job queues
- Memory-efficient operations
- Load balancing

## Error Handling Strategy

### Graceful Degradation
- Fallback mechanisms
- Circuit breaker patterns
- Error recovery procedures
- User-friendly error messages

### Monitoring and Alerting
- Real-time error detection
- Automated alerts
- Performance degradation warnings
- System health dashboards

## Best Practices Implemented

### ERPNext Compliance
- Follows ERPNext development patterns
- Uses standard Frappe framework features
- Integrates with existing ERPNext modules
- Maintains backward compatibility

### Code Quality
- Clean code principles
- Proper documentation
- Code review processes
- Testing standards

### DevOps Practices
- Automated deployment
- Continuous integration
- Infrastructure as code
- Monitoring and observability

## Usage Examples

### Creating a Contribution
```python
from shg.shg.services.contribution.contribution_service import ContributionService

service = ContributionService()
contribution_data = {
    "member": "SHG-MEMBER-001",
    "contribution_type": "Monthly",
    "expected_amount": 500,
    "posting_date": "2024-01-01",
    "due_date": "2024-01-31"
}
result = service.create_contribution(contribution_data)
```

### Processing Payment
```python
from shg.shg.services.payment.payment_service import PaymentService

service = PaymentService()
contributions_data = [{
    "contribution_name": "SHG-CONTRIBUTION-001",
    "amount": 500
}]
result = service.allocate_payment("PE-001", contributions_data)
```

### Sending Notifications
```python
from shg.shg.services.notification.notification_service import NotificationService

service = NotificationService()
notification_data = {
    "member": "SHG-MEMBER-001",
    "notification_type": "Payment Receipt",
    "amount": 500
}
service.send_sms_notification(notification_data)
service.send_email_notification(notification_data)
```

## Troubleshooting

### Common Issues
- Database connection problems
- Permission errors
- Concurrency conflicts
- Performance bottlenecks

### Diagnostic Tools
- Audit trail analysis
- System health reports
- Performance monitoring
- Error log analysis

## Future Enhancements

### Planned Features
- Advanced reporting capabilities
- Mobile app integration
- API improvements
- Machine learning integrations

### Scalability Improvements
- Horizontal scaling support
- Database sharding
- Caching enhancements
- Load distribution