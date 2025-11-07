# SHG Loan Services

Pure Python domain services for loan processing in the SHG module.

## Overview

This package contains pure Python services for handling various loan operations including:

- Schedule generation (Flat, EMI, Declining Balance)
- Payment allocation
- GL posting
- Accrual calculations
- Loan rescheduling
- Write-off processing

## Modules

### schedule.py
Handles loan schedule generation for different interest calculation methods:
- Flat Rate
- Reducing Balance (EMI)
- Reducing Balance (Declining)

### allocation.py
Manages payment allocation across principal, interest, and penalty components.

### gl.py
Handles General Ledger posting for loan transactions including:
- Disbursements
- Repayments
- Accruals
- Write-offs

### accrual.py
Calculates daily interest and penalty accruals for active loans.

### reschedule.py
Manages loan rescheduling and amendment workflows.

### writeoff.py
Handles loan write-off processes and reversals.

## Usage

All services are designed to be pure functions with no side effects. They can be imported and used independently:

```python
from shg.shg.loan_services.schedule import build_flat_rate_schedule

schedule = build_flat_rate_schedule(
    principal=10000,
    interest_rate=12,
    term_months=12
)
```

## Testing

Unit tests are available in `shg/shg/tests/test_loan_services.py` and can be run with:

```bash
bench run-tests --app shg --test test_loan_services
```

## Integration

These services are designed to work with the SHG Loan DocType and related documents. They provide the business logic layer that can be called from whitelisted methods in the DocType classes.