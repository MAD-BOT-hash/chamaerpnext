# SHG Management System for ERPNext

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ERPNext](https://img.shields.io/badge/ERPNext-v14+-blue.svg)](https://github.com/frappe/erpnext)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)](https://python.org)

A comprehensive Self Help Group (SHG) management application for ERPNext, specifically designed for Kenyan SHGs with mobile money integration, automated notifications, and compliance features.

## Overview

The SHG Management System is a complete solution for managing Self Help Groups, particularly tailored for the Kenyan context. It provides tools for member management, financial tracking, loan processing, meeting coordination, and mobile integration. The system integrates seamlessly with ERPNext's existing financial and customer management capabilities while adding specialized features for SHG operations.

## Features

### Core Functionality
- **Member Management**: Complete registration with Kenyan ID/phone validation and auto-generated account numbers (MN001, MN002, etc.)
- **Savings & Contributions**: Automated weekly/bi-weekly/monthly/bi-monthly tracking with GL integration and Mpesa payments
- **Loan Management**: Full lifecycle from application to closure with interest calculation and configurable loan types
- **Meeting Management**: Attendance tracking with automated fine calculation
- **Notification System**: SMS/Email/WhatsApp reminders and alerts
- **Financial Reporting**: Comprehensive statements and portfolio analysis including member statements
- **Member Account Management**: Auto-generated unique account numbers for each member
- **Automated Financial Updates**: Real-time member financial summaries and credit scoring

### Configurable Modules
- **Loan Types**: Emergency Loan, Development Loan, etc. with customizable interest rates, terms, and penalties
- **Contribution Types**: Monthly Contribution, Welfare Contribution, Bi-Monthly Contribution with configurable settings
- **Repayment Schedules**: Support for daily, weekly, bi-weekly, monthly, bi-monthly, quarterly, and yearly repayment frequencies
- **Flexible Configuration**: SHG Settings for customizing all aspects of the system

### Kenyan Localization
- **Currency**: KES as default with proper formatting
- **Phone Validation**: Supports +254, 07xx, 01xx formats
- **ID Validation**: 8-digit Kenyan national ID format
- **Mobile Money**: M-Pesa STK Push & C2B integration
- **SMS Gateway**: Africa's Talking integration
- **Regulatory Compliance**: CBK and SASRA guidelines adherence

### Mobile Integration
- **REST API**: Complete endpoints for mobile app development
- **Real-time Data**: Live dashboard updates
- **Offline Support**: Sync capabilities for poor connectivity areas
- **Push Notifications**: Member alerts and reminders
- **Mobile Payments**: Mpesa STK Push for contributions and loan repayments

### Security & Compliance
- **Role-based Access**: Admin, Treasurer, Member, Auditor roles
- **Data Encryption**: Secure data transmission and storage
- **Audit Trails**: Complete transaction history
- **GDPR Compliant**: Privacy and data protection

### Dashboard & Analytics
- **Number Cards**: Active members, outstanding loans, monthly contributions, bi-monthly contributions, loan repayments, Mpesa payments
- **Charts**: Members overview, financial summary, Mpesa payments, loan types overview, contribution types overview
- **Quick Access**: Member statement button, configurable settings
- **Real-time Updates**: Live dashboard with current SHG metrics

## Quick Installation
```bash
# Install the SHG app
bench get-app shg https://github.com/your-username/shg-erpnext.git

# Install on your site
bench --site [site-name] install-app shg

# Run database migrations
bench --site [site-name] migrate

# Restart services
bench restart

# If reinstalling after updates
bench --site [site-name] reinstall-app shg
```

## Configuration
1. Go to SHG Settings to configure:
   - Contribution settings (amounts, frequencies)
   - Loan settings (interest rates, terms)
   - Meeting settings (fines, quorum)
   - Mpesa payment settings (API keys, credentials)
   - Notification settings (SMS, Email)
   - Account numbering preferences

2. Create Loan Types and Contribution Types as needed for your SHG

3. Register members who will automatically receive account numbers

4. Set up user roles (SHG Admin, SHG Treasurer, SHG Member, SHG Auditor) for proper access control

## API Endpoints
The app provides REST API endpoints for mobile app integration:
- `/api/method/shg.api.login` - Member authentication
- `/api/method/shg.api.get_member_statement` - Member statement retrieval
- `/api/method/shg.api.submit_contribution` - Contribution submission
- `/api/method/shg.api.apply_loan` - Loan application
- `/api/method/shg.api.get_notifications` - Notification retrieval
- `/api/method/shg.api.get_upcoming_meetings` - Meeting schedule
- `/api/method/shg.api.get_member_profile` - Member profile information

## Reports
- Member Statement: Complete transaction history for individual members
- Loan Portfolio: Overview of all loans
- Financial Summary: Organization-wide financial metrics
- Member Summary: Member demographics and statistics
- Loan Statement: Detailed loan information

## Testing and Verification

After installation, verify the following components are working:

1. **Doctypes**: All SHG doctypes should be available (Member, Contribution, Loan, etc.)
2. **Workspace**: SHG dashboard should be accessible with all cards and charts
3. **Reports**: All reports should generate correctly
4. **API Endpoints**: Mobile API endpoints should be accessible
5. **Scheduled Tasks**: Daily, weekly, and monthly tasks should run
6. **Member Accounts**: New members should receive auto-generated account numbers
7. **Financial Integration**: Contributions and loans should post to General Ledger

## Troubleshooting

If you encounter issues:

1. Check that all dependencies are installed
2. Verify database migrations completed successfully
3. Ensure proper permissions are set for SHG roles
4. Check the Frappe error logs for specific error messages
5. Reinstall the app if necessary using `bench --site [site-name] reinstall-app shg`