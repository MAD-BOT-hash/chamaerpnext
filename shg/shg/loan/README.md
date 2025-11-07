# SHG Loan Module

This directory contains the refactored loan management system for SHG ERPNext.

## Module Structure

```
loan/
├── __init__.py          # Module exports
├── schedule.py          # Loan schedule generation and management
├── accounting.py        # Payment entry and accounting operations
├── repayment.py         # Core repayment service and operations
├── schedule_manager.py  # Schedule row management and status updates
├── payment_allocator.py # Payment allocation algorithms
├── reporting.py         # Loan portfolio and member reporting
└── services.py          # Legacy services (to be deprecated)
```

## Key Components

### 1. Schedule Management (`schedule.py`)
- `get_schedule()` - Retrieve repayment schedule for a loan
- `compute_totals()` - Calculate financial totals from schedule rows
- `build_schedule()` - Generate new amortization schedule

### 2. Accounting (`accounting.py`)
- `create_payment_entry()` - Create Payment Entry documents for repayments

### 3. Repayment Service (`repayment.py`)
- `SHGLoanRepaymentService` - Central service for loan repayment operations
- Unified interface for repayment validation, allocation, and accounting

### 4. Schedule Manager (`schedule_manager.py`)
- `ScheduleManager` - Manage individual schedule row status and updates
- Handle overdue calculations and next due date determination

### 5. Payment Allocator (`payment_allocator.py`)
- `PaymentAllocator` - Advanced payment allocation algorithms
- Support for both automatic and specific installment allocation

### 6. Reporting (`reporting.py`)
- `LoanReporting` - Comprehensive reporting system
- Portfolio summaries, member statements, aging reports, and performance metrics

## API Endpoints

### Repayment Operations
- `allocate_loan_payment()` - Allocate payment to loan schedule
- `validate_repayment_amount()` - Validate repayment amount
- `post_repayment_to_ledger()` - Post repayment to accounting ledger

### Schedule Management
- `update_schedule_row()` - Update individual schedule row
- `mark_installment_paid()` - Mark specific installment as paid
- `refresh_schedule_summary()` - Refresh loan summary from schedule
- `recompute_schedule()` - Recompute entire schedule from scratch

### Reporting
- `get_portfolio_summary()` - Get loan portfolio summary
- `get_member_summary()` - Get member loan summary
- `get_aging_report()` - Get loan aging report
- `get_monthly_performance()` - Get monthly performance metrics
- `get_loan_statement()` - Get detailed loan statement

## Usage Examples

### Allocate Payment
```python
from shg.shg.loan.repayment import allocate_loan_payment

# Allocate payment to earliest unpaid installments
result = allocate_loan_payment("LOAN-001", 5000)

# Allocate payment to specific installments
allocations = [
    {"row_name": "SCH-001", "amount_to_pay": 2000},
    {"row_name": "SCH-002", "amount_to_pay": 3000}
]
result = allocate_loan_payment("LOAN-001", 5000, allocations)
```

### Generate Loan Statement
```python
from shg.shg.loan.reporting import get_detailed_loan_statement

statement = get_detailed_loan_statement("LOAN-001")
print(statement["loan_details"])
print(statement["financial_summary"])
```

## Migration Notes

The new loan module provides improved:
- Data consistency through centralized operations
- Better error handling and validation
- Enhanced reporting capabilities
- More flexible payment allocation options
- Improved client-side user experience

Legacy functions in `loan_utils.py` and `services.py` are maintained for backward compatibility but new development should use the refactored modules.