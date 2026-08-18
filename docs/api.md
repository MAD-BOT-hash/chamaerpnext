# SHG API Documentation

The SHG app exposes REST endpoints for mobile and third-party integration.
All endpoints are prefixed with the Frappe base URL, typically:

```
https://<your-site>/api/method/<dotted.method.path>
```

## Authentication

Most endpoints require an authenticated Frappe session or a valid API key.
Set the `Authorization` header with a ****** or rely on Frappe session
cookies.

## Response Format

Every endpoint returns a standard envelope:

```json
{
  "success": true,
  "data": { ... },
  "message": "Optional human-readable message",
  "error": null
}
```

On failure:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Missing required parameter: member",
    "details": { "field": "member" }
  }
}
```

## Endpoints

### Health Check

**GET** `/api/method/shg.shg.api.health.health`

Returns the current health status of the SHG app, database, scheduler, and
payment configuration.

#### Response

```json
{
  "success": true,
  "data": {
    "app": "shg",
    "version": "1.0.0",
    "database": true,
    "scheduler_enabled": true,
    "settings_configured": true,
    "mpesa_configured": true,
    "sms_configured": false,
    "timestamp": "2026-08-18 08:00:00"
  },
  "message": "SHG app is healthy",
  "error": null
}
```

### Member Authentication

**POST** `/api/method/shg.api.login`

Authenticate a member using their registered phone number or member ID.

| Parameter | Type   | Required | Description            |
|-----------|--------|----------|------------------------|
| phone     | string | yes*     | Member phone number    |
| member_id | string | yes*     | SHG member ID          |
| password  | string | yes      | Member PIN or password |

\* Provide either `phone` or `member_id`.

### Get Member Statement

**POST** `/api/method/shg.api.get_member_statement`

Retrieve a member's contribution, loan, and payment summary.

| Parameter | Type   | Required | Description      |
|-----------|--------|----------|------------------|
| member    | string | yes      | Member ID        |
| from_date | date   | no       | Statement start  |
| to_date   | date   | no       | Statement end    |

### Submit Contribution

**POST** `/api/method/shg.api.submit_contribution`

Record a new contribution payment.

| Parameter       | Type   | Required | Description                      |
|-----------------|--------|----------|----------------------------------|
| member          | string | yes      | Member ID                        |
| amount          | number | yes      | Contribution amount              |
| contribution_type | string | yes    | Contribution type                |
| payment_method  | string | no       | e.g. Mpesa, Cash, Bank Transfer  |

### Apply for Loan

**POST** `/api/method/shg.api.apply_loan`

Submit a loan application.

| Parameter    | Type   | Required | Description              |
|--------------|--------|----------|--------------------------|
| member       | string | yes      | Member ID                |
| amount       | number | yes      | Requested loan amount    |
| loan_type    | string | yes      | Loan type                |
| purpose      | string | no       | Purpose of the loan      |

### Get Upcoming Meetings

**GET** `/api/method/shg.api.get_upcoming_meetings`

Return meetings scheduled for the authenticated member.

### Get Notifications

**GET** `/api/method/shg.api.get_notifications`

Return pending notifications for the authenticated member.

### Get Member Profile

**GET** `/api/method/shg.api.get_member_profile`

Return the authenticated member's profile information.

## Error Codes

| Code                  | HTTP Status | Description                                |
|-----------------------|-------------|--------------------------------------------|
| GENERAL_ERROR         | 400         | Unspecified error                          |
| VALIDATION_ERROR      | 422         | Missing or invalid request parameter       |
| HEALTH_CHECK_FAILED   | 503         | Health-check could not complete            |

## Rate Limiting

Public endpoints are rate-limited per site. Implement retries with exponential
backoff on `429 Too Many Requests` responses.
