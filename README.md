# í¿¦ SHG Management System for ERPNext

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ERPNext](https://img.shields.io/badge/ERPNext-v14+-blue.svg)](https://github.com/frappe/erpnext)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)](https://python.org)

A comprehensive Self Help Group (SHG) management application for ERPNext, specifically designed for Kenyan SHGs with mobile money integration, automated notifications, and compliance features.

## í¼Ÿ Features

### í²¼ Core Functionality
- **Member Management**: Complete registration with Kenyan ID/phone validation
- **Savings & Contributions**: Automated weekly/monthly tracking with GL integration
- **Loan Management**: Full lifecycle from application to closure with interest calculation
- **Meeting Management**: Attendance tracking with automated fine calculation
- **Notification System**: SMS/Email/WhatsApp reminders and alerts
- **Financial Reporting**: Comprehensive statements and portfolio analysis

### í·°í·ª Kenyan Localization
- **Currency**: KES as default with proper formatting
- **Phone Validation**: Supports +254, 07xx, 01xx formats
- **ID Validation**: 8-digit Kenyan national ID format
- **Mobile Money**: M-Pesa STK Push integration
- **SMS Gateway**: Africa's Talking integration
- **Regulatory Compliance**: CBK and SASRA guidelines adherence

### í³± Mobile Integration
- **REST API**: Complete endpoints for mobile app development
- **Real-time Data**: Live dashboard updates
- **Offline Support**: Sync capabilities for poor connectivity areas
- **Push Notifications**: Member alerts and reminders

### í´’ Security & Compliance
- **Role-based Access**: Admin, Treasurer, Member, Auditor roles
- **Data Encryption**: Secure data transmission and storage
- **Audit Trails**: Complete transaction history
- **GDPR Compliant**: Privacy and data protection

## íº€ Quick Installation
```bash
# Install the SHG app
bench get-app shg https://github.com/your-username/shg-erpnext.git

# Install on your site
bench --site [site-name] install-app shg

# Run database migrations
bench --site [site-name] migrate

# Restart services
bench restart
