# SHG Email Log

## Overview
This doctype tracks all email communications sent from the SHG system, providing an audit trail for email activities.

## Fields

### Member Information
- **Member**: Link to SHG Member (required)
- **Member Name**: Auto-fetched member name (read-only)

### Email Information
- **Email Address**: Recipient email address (required)
- **Subject**: Email subject line (required)
- **Status**: Sent/Failed/Pending (required)
- **Document Type**: Type of document sent (Member Statement, Loan Statement, etc.) (required)
- **Reference Document**: Dynamic link to related document

### Activity Information
- **Sent By**: User who initiated the email (auto-populated)
- **Sent On**: Timestamp when email was sent (auto-populated)
- **Error Log**: Error details if email failed (read-only)

## Features
- Automatic logging of email activities
- Status tracking (Sent, Failed, Pending)
- Error logging for failed emails
- Integration with member records
- Audit trail for compliance

## Usage
This doctype is automatically populated by the member statement email functionality and other email sending features in the SHG system.