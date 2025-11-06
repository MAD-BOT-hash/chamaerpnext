# Loan Portfolio Reports Enhancement

## Overview
This enhancement fixes and improves the SHG Loan Portfolio reports to ensure accurate computation of principal and interest totals, outstanding balances including interest, delinquent amounts, repayment progress, and loan aging data.

## Reports Enhanced

### 1. Loan Portfolio Report
**File**: `shg/shg/report/loan_portfolio/loan_portfolio.py`

**Fixes**:
- Updated to include interest in outstanding balance calculation
- Added `total_payable` field showing principal + interest
- Improved overdue amount calculation using `overdue_amount` field
- Added filters for member, date range, and loan status

### 2. Member Loan Summary Report
**File**: `shg/shg/report/member_loan_summary/member_loan_summary.py`

**New Features**:
- Created new report for member-centric loan details
- Shows loan amount, total payable (principal + interest), total paid, and outstanding balance
- Includes interest rate, loan period, status, and next due date
- Added days overdue calculation
- Supports filtering by member, loan, and status

### 3. Loan Aging Report
**File**: `shg/shg/report/shg_loan_aging/shg_loan_aging.py`

**Enhancements**:
- Added days overdue calculation
- Improved aging bucket logic with proper date calculations
- Added current bucket for future due dates
- Enhanced data aggregation with accurate grouping

### 4. Loan Disbursement vs. Repayment Report
**File**: `shg/shg/report/loan_disbursement_vs_repayment/loan_disbursement_vs_repayment.py`

**New Features**:
- Created new report showing disbursed vs repaid trend per period
- Monthly aggregation of disbursement and repayment amounts
- Net change calculation (disbursed - repaid)
- Cumulative balance tracking
- Supports filtering by date range and member

### 5. SHG Portfolio Summary Report
**File**: `shg/shg/report/shg_portfolio_summary/shg_portfolio_summary.py`

**Enhancements**:
- Added overdue amount tracking
- Improved data aggregation with accurate grouping
- Enhanced filtering capabilities

## Key Improvements

### Core Calculations
- **Total Due**: Computed as `principal_amount + interest_amount` in Loan Repayment Schedule
- **Payable Balance**: Computed as `total_due - amount_paid`
- **Outstanding Balance**: Computed as `SUM(total_due) - SUM(amount_paid)` for accurate interest inclusion

### Field Mappings
```sql
SELECT 
    loan.name AS loan_id,
    loan.member,
    SUM(sch.principal_amount + sch.interest_amount) AS total_due,
    SUM(sch.amount_paid) AS total_paid,
    SUM((sch.principal_amount + sch.interest_amount) - sch.amount_paid) AS balance_due,
    CASE
        WHEN sch.due_date < CURDATE() AND sch.docstatus = 1 AND sch.status != 'Paid' THEN 'Overdue'
        ELSE 'Current'
    END AS installment_status
FROM `tabSHG Loan` AS loan
JOIN `tabSHG Loan Repayment Schedule` AS sch
    ON sch.parent = loan.name
WHERE loan.docstatus = 1
GROUP BY loan.name;
```

### Data Aggregation
- Filter only active schedules with `.docstatus == 1`
- Proper aggregation of total payable and amount paid per loan
- Accurate delinquency status updates

## Testing
Comprehensive test cases have been created to verify:
- Loan Portfolio report generation with accurate interest calculation
- Member Loan Summary report with proper interest inclusion
- Loan Aging report with correct aging buckets
- Loan Disbursement vs Repayment report with trend analysis
- Portfolio Summary report with enhanced calculations

## Migration
No special migration steps required. The reports will automatically use the enhanced logic when accessed.