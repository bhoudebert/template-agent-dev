## ADDED Requirements
### Requirement: Request reset link
The system SHALL send a single-use reset link valid for 30 minutes to a registered email, and SHALL respond identically for unknown emails.

#### Scenario: Registered email
- **WHEN** a reset is requested for a registered email
- **THEN** an email with a link expiring in 30 minutes is sent

#### Scenario: Unknown email
- **WHEN** a reset is requested for an unknown email
- **THEN** the response matches the registered case and no email is sent

### Requirement: Rate limiting
The system MUST reject more than 5 reset requests per hour per account or IP.

#### Scenario: Limit exceeded
- **WHEN** a sixth request arrives within an hour
- **THEN** the request is rejected with a retry-after indication

### Requirement: Confirm reset
The system SHALL change the password only with an unexpired, unused token and SHALL revoke all sessions.

#### Scenario: Valid token
- **WHEN** a valid token and a policy-compliant password are submitted
- **THEN** the password changes and all sessions are revoked

#### Scenario: Expired or used token
- **WHEN** an expired or used token is submitted
- **THEN** the change is refused and the user may request a new link
