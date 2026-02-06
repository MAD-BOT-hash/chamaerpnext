# SHG ERPNext Testing Guide

## Overview

Your SHG ERPNext application has an extensive test suite with 23 test files covering various aspects of the application functionality.

## Test Suite Structure

```
tests/
├── shg/                              # SHG-specific tests
├── test_bank_entry_references.py     # Bank entry reference handling
├── test_bank_reference_auto_fill.py  # Auto-fill bank references
├── test_custom_field_fixtures.py     # Custom field fixtures
├── test_emi_loan_calculations.py     # EMI loan calculations
├── test_fetch_unpaid_installments.py # Fetch unpaid installments
├── test_get_active_members.py        # Get active members functionality
├── test_improved_loan_functionality.py # Improved loan features
├── test_inline_repayment.py          # Inline repayment functionality
├── test_inline_repayment_workflow.py # Inline repayment workflow
├── test_installment_repayment.py     # Installment repayment
├── test_loan_balance_calculation.py  # Loan balance calculations
├── test_loan_balance_calculations.py # More loan balance tests
├── test_loan_portfolio_reports.py    # Loan portfolio reports
├── test_loan_refactor.py             # Loan refactoring tests
├── test_loan_repayment_balance_fix.py # Repayment balance fixes
├── test_new_posting_logic.py         # New posting logic
├── test_partial_payment_repayment.py # Partial payment handling
├── test_repayment_balance_calculation.py # Repayment balance calculation
├── test_repayment_schedule.py        # Repayment schedule generation
├── test_shg_contribution_erpnext15_compliance.py # Contribution compliance
├── test_shg_erpnext15_compliance.py  # ERPNext v15 compliance
├── test_shg_transactions.py          # SHG transaction processing
└── test_voucher_type_fixes.py        # Voucher type fixes
```

## Prerequisites

To run the tests, you need:
1. Python 3.8+
2. ERPNext/Frappe development environment
3. pytest (pip install pytest)

## Test Categories

### Unit Tests
- Test individual functions and methods
- Focus on business logic validation
- Files with `test_*` prefix

### Integration Tests
- Test interactions between modules
- Require database connectivity
- Test end-to-end workflows

### Compliance Tests
- Test ERPNext v15 compatibility
- Test accounting standards compliance
- Test Kenya-specific requirements

## Running Tests

### Using pytest directly:
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_shg_erpnext15_compliance.py -v

# Run tests with specific marker
python -m pytest tests/ -m unit -v
python -m pytest tests/ -m integration -v
```

### Using the test runner script:
```bash
# Run all tests
python run_tests.py

# List available tests
python run_tests.py list

# Run unit tests only
python run_tests.py unit

# Run integration tests only
python run_tests.py integration

# Run specific test file
python run_tests.py test_shg_erpnext15_compliance.py
```

### Environment Requirements

The tests require access to:
- Frappe framework
- ERPNext modules
- Database connection
- Proper company/chart of accounts setup

## Common Test Patterns

### Setting up test data:
```python
def setUp(self):
    # Create required master data
    if not frappe.db.exists("Company", "Test Company"):
        # Create test company
        pass
    
    # Create required doctypes
    if not frappe.db.exists("SHG Member", "TEST-MEMBER-001"):
        # Create test member
        pass
```

### Testing document workflows:
```python
def test_member_registration_workflow(self):
    # Test complete member registration flow
    member = frappe.get_doc({
        "doctype": "SHG Member",
        "member_name": "Test Member",
        "phone_number": "1234567890"
    })
    member.insert()
    member.submit()
    
    # Verify GL entries created
    gle = frappe.get_all("GL Entry", 
        filters={"voucher_no": member.name})
    self.assertGreater(len(gle), 0)
```

## Test Coverage Areas

1. **Member Management**
   - Registration and validation
   - Customer linking
   - Account creation

2. **Contribution Processing**
   - Payment entry creation
   - GL entry posting
   - Status updates

3. **Loan Management**
   - Application processing
   - Disbursement workflows
   - Repayment calculations
   - Schedule generation

4. **Accounting Compliance**
   - ERPNext v15 compatibility
   - Proper reference types
   - Chart of accounts mapping

5. **Kenya-Specific Features**
   - Mobile money integration
   - M-Pesa payment processing
   - Local currency handling

## Troubleshooting

### Common Issues:
1. **Import errors** - Ensure Frappe is properly installed
2. **Database connection errors** - Verify ERPNext site is running
3. **Permission errors** - Check user permissions in test environment
4. **Missing master data** - Run setup methods in setUp()

### Debugging Tips:
1. Use `--tb=long` for detailed traceback
2. Add `print()` statements for debugging
3. Use `frappe.log_error()` for persistent logging
4. Check ERPNext logs for detailed error information

## Best Practices

1. **Isolate test data** - Use unique test identifiers
2. **Clean up after tests** - Remove test data in tearDown()
3. **Use proper assertions** - Test specific conditions
4. **Mock external services** - For integration tests
5. **Test edge cases** - Invalid inputs, boundary conditions
6. **Maintain test documentation** - Keep tests self-documenting

## Continuous Integration

For CI/CD pipeline integration:
```yaml
# Example GitHub Actions workflow
name: SHG Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: |
        pip install pytest frappe-bench
    - name: Run tests
      run: |
        python -m pytest tests/ -v --tb=short
```

## Test Results Interpretation

- **PASS**: Test executed successfully
- **FAIL**: Test assertion failed
- **ERROR**: Test execution error (exception)
- **SKIP**: Test was skipped (dependency not met)
- **xfail**: Expected failure (known issue)

The test suite provides comprehensive coverage of your SHG application functionality and should be run regularly to ensure code quality and prevent regressions.