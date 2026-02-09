# SHG ERPNext - Advanced Features Documentation

## 1. Comprehensive Notification System

### Overview
The SHG ERPNext application now includes a comprehensive notification system supporting multiple channels (SMS, Email, WhatsApp, Push Notifications) with scheduling capabilities.

### Features

#### 1.1 Multi-Channel Support
- **SMS**: Integrated with Africa's Talking and generic SMS gateways
- **Email**: Standard email delivery with rich templates
- **WhatsApp**: Business API integration for WhatsApp notifications
- **Push Notifications**: Mobile app push notifications

#### 1.2 Smart Phone Number Handling
- Automatic normalization of Kenyan phone numbers
- Converts various formats to international standard (+254...)
- Handles edge cases for different input formats

#### 1.3 Notification Scheduling
- Schedule notifications for future delivery
- Daily background job processes scheduled notifications
- Track delivery status and errors

#### 1.4 Batch Notifications
- Send notifications to multiple members at once
- Personalized message templates with member data
- Bulk processing with detailed results tracking

### API Endpoints

#### Send Individual Notification
```
POST /api/method/shg.shg.api.notifications.send_member_notification
Parameters:
- member_id: ID of the member
- notification_type: Type of notification
- message: Content of the message
- channel: Channel to use (SMS, Email, WhatsApp, Push Notification)
- reference_document: Reference document type (optional)
- reference_name: Reference document name (optional)
```

#### Get Member Notifications
```
GET /api/method/shg.shg.api.notifications.get_member_notifications
Parameters:
- member_id: ID of the member
- limit: Number of notifications to return (default 20)
- offset: Offset for pagination (default 0)
```

#### Schedule Notification
```
POST /api/method/shg.shg.api.notifications.schedule_member_notification
Parameters:
- member_id: ID of the member
- notification_type: Type of notification
- message: Content of the message
- scheduled_date: Date when notification should be sent (YYYY-MM-DD)
- channel: Channel to use (SMS, Email, WhatsApp, Push Notification)
- reference_document: Reference document type (optional)
- reference_name: Reference document name (optional)
```

#### Send Batch Notifications
```
POST /api/method/shg.shg.api.notifications.send_batch_notifications_api
Parameters:
- members: JSON string of member IDs list
- notification_type: Type of notification
- message_template: Message template with placeholders
- channel: Channel to use (SMS, Email, WhatsApp, Push Notification)
- reference_document: Reference document type (optional)
- reference_name: Reference document name (optional)
```

## 2. Mobile Integration

### Overview
Full REST API support for mobile applications with offline capabilities and push notifications.

### Features

#### 2.1 Offline Support
- Data synchronization capabilities
- Queue management for offline operations
- Conflict resolution for concurrent updates

#### 2.2 Mobile-Optimized APIs
- Lightweight JSON responses
- Efficient data transfer
- Caching support

#### 2.3 Push Notifications
- Real-time alerts and reminders
- Customizable notification preferences
- Delivery status tracking

## 3. Enhanced Security & Compliance

### Overview
Robust security features including encryption, GDPR compliance, and data privacy controls.

### Features

#### 3.1 Data Encryption
- AES-256 encryption for sensitive data
- Fernet symmetric encryption implementation
- Secure key management in SHG Settings

#### 3.2 GDPR Compliance
- Data anonymization capabilities
- Right to be forgotten implementation
- Data export functionality
- Retention period management

#### 3.3 Privacy Controls
- Data retention policies
- Secure token generation
- Hash-based data verification
- Sensitive data masking

### Configuration in SHG Settings

#### Security Settings Section
- **Enable Data Encryption**: Toggle for encryption features
- **Encryption Key**: Secure key storage (hidden)
- **Enable GDPR Compliance**: GDPR compliance features
- **Data Retention Period**: Days to retain data before anonymization/deletion
- **Privacy Policy URL**: Link to privacy policy
- **Terms of Service URL**: Link to terms of service

## 4. Implementation Details

### 4.1 Notification Service Architecture
```
NotificationService
├── send_notification()
├── send_batch_notifications()
├── schedule_notification()
├── process_scheduled_notifications()
├── _send_sms()
├── _send_email()
├── _send_whatsapp()
└── _send_push_notification()
```

### 4.2 Security Module Architecture
```
SHGSecurity
├── encrypt_data()
├── decrypt_data()
├── hash_data()
├── generate_secure_token()
└── mask_sensitive_data()

DataPrivacyManager
├── anonymize_member_data()
├── delete_member_data()
└── export_member_data()
```

### 4.3 Scheduled Jobs
- `process_scheduled_notifications`: Daily job to process scheduled notifications
- Runs automatically as part of the daily scheduler

## 5. Usage Examples

### 5.1 Send SMS Notification
```python
from shg.shg.utils.notification_service import send_notification

result = send_notification(
    member_id="MEM001",
    notification_type="Payment Confirmation",
    message="Dear John, your payment of KES 500.00 has been received.",
    channel="SMS",
    reference_document="SHG Contribution",
    reference_name="CONTR001"
)
```

### 5.2 Schedule Notification
```python
from shg.shg.utils.notification_service import schedule_notification

scheduled_id = schedule_notification(
    member_id="MEM001",
    notification_type="Meeting Reminder",
    message="Reminder: Meeting tomorrow at 9 AM",
    scheduled_date="2025-01-15",
    channel="SMS"
)
```

### 5.3 Batch Notifications
```python
from shg.shg.utils.notification_service import send_batch_notifications

results = send_batch_notifications(
    members=["MEM001", "MEM002", "MEM003"],
    notification_type="General Announcement",
    message_template="Dear {member_name}, please note the policy change...",
    channel="SMS"
)
```

### 5.4 Data Encryption
```python
from shg.shg.utils.security import encrypt_data, decrypt_data

# Encrypt sensitive data
encrypted = encrypt_data("Sensitive information")

# Decrypt data
decrypted = decrypt_data(encrypted)
```

## 6. Best Practices

### 6.1 Notification Best Practices
- Always use message templates with placeholders for personalization
- Implement proper error handling for failed deliveries
- Monitor delivery status and retry failed notifications
- Respect member preferences for notification channels

### 6.2 Security Best Practices
- Regularly rotate encryption keys
- Implement proper access controls
- Audit sensitive data access
- Maintain data retention policies

### 6.3 Performance Considerations
- Use batch operations for multiple notifications
- Implement proper indexing for notification logs
- Monitor scheduled job performance
- Optimize database queries for large datasets

## 7. Troubleshooting

### 7.1 Common Issues
- **SMS not sending**: Verify Africa's Talking credentials in SHG Settings
- **Scheduled notifications not processing**: Check if daily scheduler is enabled
- **Encryption errors**: Ensure encryption key is properly configured
- **API access issues**: Verify user permissions and authentication

### 7.2 Logging
- All notification activities are logged in SHG Notification Log
- Security events are logged with timestamps
- Failed operations include detailed error messages
- Scheduled jobs log processing results

This comprehensive notification and security system enhances the SHG ERPNext application with enterprise-grade features while maintaining the simplicity and usability that makes the system effective for Self Help Groups in Kenya.