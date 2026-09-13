# BioCore Privacy-First Verified Entry Management
## Complete Change Specification for the Current Product

**Scope:** Event management companies, schools, colleges, workspaces, hotels, factories, hospitals, residential communities, government facilities and other controlled-entry environments.

**Excluded from this document:** Black-market ticket prevention and resale controls. This document focuses only on identity verification, consent, privacy, encryption, face matching, authorization and entry management.

---

# 1. Purpose of this document

The current BioCore platform already contains a strong operational base: a user application, guard console, self-service kiosk, admin portal, attendance, access policies, visitor workflows, emergency muster, audit trails, tenant isolation and a pluggable face engine.

The product now needs to change from a general face-entry platform into a **privacy-first verified identity and entry-management platform**.

The new product must support this principle:

> A person proves their identity through an authorized government-data source, completes liveness and face-to-government-photo verification, creates a purpose-bound encrypted entry credential, and later uses that credential only at approved doors, gates, zones or events.

The platform must avoid unnecessary storage of government data, raw face images and reusable cross-customer identity data.

---

# 2. New product definition

## 2.1 Recommended positioning

**BioCore is a privacy-first identity verification and entry-management platform.**

It enables an organization to:

- Invite or register a person.
- Verify that person using an authorized government-data API.
- Match a live face with the government-record face.
- Obtain purpose-specific consent.
- Create an encrypted entry credential.
- Allow or deny entry at an authorized gate.
- Record minimal attendance or access events.
- Revoke, expire and erase the credential.

## 2.2 Product one-liner

> **Verified once. Authorized only where approved.**

## 2.3 What BioCore must not become

BioCore must not become:

- A central government-ID database.
- A database of raw face photographs.
- A global face-search engine across all customers.
- A tool that lets administrators download facial templates.
- A system that silently reuses one organization’s identity data for another organization.
- A surveillance platform that identifies people outside an approved tenant, event, zone or purpose.

---

# 3. Current product: what stays, changes, and is replaced

## 3.1 Keep

The following current capabilities should remain:

- Four applications: user app, guard console, kiosk and admin portal.
- Multi-tenant architecture.
- Tenant-level roles and permissions.
- Attendance and presence tracking.
- Zones, gates, devices and geofences.
- Visitors, events, memberships and badges.
- Blacklist and access-denial rules.
- Emergency muster.
- Append-only audit records.
- PostgreSQL row-level security.
- Redis sessions and presence.
- RabbitMQ worker and dead-letter processing.
- Docker and Kubernetes deployment.
- Nginx gateway.
- Prometheus and Grafana monitoring.
- Pluggable face-engine adapter.
- Device tokens stored as hashes.
- User withdrawal and erasure workflows.

## 3.2 Modify

The following current capabilities need major modification:

- Global person identity.
- Capture-once and automatic cross-business reuse.
- Consent timing.
- Face-template storage.
- Government-data processing.
- Enrollment flow.
- Gate matching.
- Admin access to biometric status.
- Erasure workflow.
- Data model.
- API surface.
- Logs and observability.
- Device trust.
- Offline entry mode.
- Production face-engine validation.

## 3.3 Replace

Replace these assumptions:

### Current assumption
One global person identity and one reusable master template across businesses.

### New default
One platform account may exist, but every organization receives a separate tenant subject and separate encrypted template.

---

### Current assumption
Consent is mainly part of face capture and reuse.

### New default
Notice and consent must be presented before government-data retrieval and before live face capture. Separate consent must be taken for entry-template creation and cross-organization reuse.

---

### Current assumption
Face data can be treated as safe merely because only a vector is stored.

### New default
A facial vector is still highly sensitive and must be protected with encryption, tenant isolation, key separation, restricted processing, non-exportability, retention controls and complete auditability.

---

### Current assumption
The development face engine can support flow validation.

### New default
The development fake remains only for UI development. No pilot, customer demo claiming real verification, or production deployment may use the fake matcher.

---

# 4. New core architecture

BioCore should be separated into six security and product planes.

## 4.1 Control Plane

Responsible for:

- Tenant configuration.
- Branding.
- Identity-assurance policy.
- Consent templates.
- Retention rules.
- Device registration.
- Zone and gate configuration.
- Roles and permissions.
- Billing and plan management.
- Integration configuration.

The Control Plane must not have direct access to plaintext facial templates or government photographs.

## 4.2 Identity Proofing Plane

Responsible for:

- Calling the government-data API.
- Validating the API response.
- Extracting only approved identity claims.
- Receiving the government-record face.
- Capturing the user’s live face.
- Running quality and liveness checks.
- Performing a 1:1 live-face-to-government-face comparison.
- Producing a signed verification result.
- Deleting temporary government and face material.

## 4.3 Credential Vault Plane

Responsible for:

- Storing encrypted tenant-specific facial templates.
- Storing encrypted data-encryption keys.
- Linking templates to tenant subjects.
- Managing key versions.
- Managing template versions.
- Enforcing expiration and revocation.
- Preventing template export.

## 4.4 Entry Authentication Plane

Responsible for:

- Receiving requests from gates and kiosks.
- Verifying terminal identity.
- Running live face capture, quality and liveness checks.
- Retrieving only the authorized encrypted template or tenant index.
- Performing 1:1 or tenant-scoped 1:N matching.
- Returning a match result.
- Zeroizing temporary plaintext vectors.

## 4.5 Authorization Plane

Responsible for checking:

- Tenant.
- Event.
- Booking or membership.
- Badge.
- Role.
- Zone.
- Gate.
- Allowed time.
- Visit expiry.
- Check-in status.
- Blacklist status.
- Consent status.
- Credential expiry.
- Manual override policy.

Face match alone must never automatically mean entry. Face match proves identity; the authorization engine decides access.

## 4.6 Audit and Privacy Plane

Responsible for:

- Consent receipts.
- Identity verification result.
- Entry decisions.
- Administrative changes.
- Device changes.
- Key operations.
- Manual overrides.
- Revocation.
- Data-access requests.
- Erasure jobs.
- Erasure certificates.

This plane must store metadata and decisions, not raw face images or plaintext vectors.

---

# 5. Complete enrollment and verification flow

## 5.1 Invitation or registration

The person enters the system through one of these sources:

- Event registration.
- School or college roster.
- Workplace HRMS.
- Hotel PMS or booking system.
- Visitor invitation.
- Self-registration code.
- Admin-created registration.

Create a `tenant_subject` in `pending_verification` state.

Do not create a reusable face template yet.

## 5.2 Pre-capture privacy notice

Before calling the government API or opening the camera, show:

- Organization requesting verification.
- Verification purpose.
- Entry purpose.
- Government-data fields requested.
- Whether a government photograph will be processed.
- Whether a raw image will be stored.
- What facial template will be created.
- Where the template will be stored.
- Retention period.
- Expiry event.
- Withdrawal method.
- Erasure method.
- Alternative entry process.
- Grievance contact.

Record notice version, language, time, tenant, purpose and user action.

## 5.3 Separate consent records

Create separate consent purposes:

1. `identity_verification`
2. `government_data_processing`
3. `live_face_capture`
4. `face_to_government_match`
5. `entry_template_creation`
6. `entry_authentication`
7. `cross_tenant_reuse` — optional and disabled by default
8. `marketing` — optional and completely separate

The user must not be forced to accept marketing to obtain entry.

## 5.4 Government API call

The Identity Proofing Service calls the existing government API.

Required controls:

- API credentials stored in a secrets manager.
- Mutual TLS or signed-request authentication when supported.
- Request IDs for traceability.
- No government response in application logs.
- No response body in APM tools.
- No raw response in error trackers.
- Strict timeout and retry policy.
- Idempotency key to prevent duplicate processing.
- Explicit field allowlist.

## 5.5 Government response minimization

Immediately divide fields into three categories.

### Temporary processing only

- Government photograph.
- Full document payload.
- Full date of birth when only an age threshold is needed.
- Full address when not required.
- Government identifiers not needed after verification.

### Retained as minimal verified claims

Examples:

- `identity_verified = true`
- `verification_method`
- `verification_reference_hash`
- `age_over_18 = true`
- `name_verified = true`
- `document_valid = true`
- `verified_at`
- `verification_expires_at`
- `assurance_level`

### Never store by default

- Raw government API credentials.
- Full API response.
- Government photograph.
- Plain government ID number.
- Temporary comparison vector.

## 5.6 Live face capture

The user app must capture a short live sequence, not a single uncontrolled photo.

Checks:

- Exactly one face.
- Face inside guide area.
- Minimum face size.
- Blur threshold.
- Lighting threshold.
- Eye visibility.
- Head-angle range.
- Camera permission.
- Real-time frame continuity.
- Replay detection.
- Screen-photo detection.
- Printed-photo detection.
- Deepfake or virtual-camera detection where possible.
- Retry limit.

The current MediaPipe face-positioning flow can remain as the front-end gate, but production liveness and matching must come from the real face engine.

## 5.7 Temporary embedding creation

Create two temporary embeddings:

- Government-photo embedding.
- Live-capture embedding.

These embeddings must exist only in protected memory during the verification transaction.

They must not be written to logs, Redis, queues or temporary files.

## 5.8 Face-to-government comparison

Perform a 1:1 comparison.

The decision must consider:

- Liveness result.
- Face-quality result.
- Similarity score.
- Configured threshold.
- Ambiguity check.
- Model version.
- Capture version.
- Retry history.

Possible outcomes:

- `verified`
- `retry_required`
- `manual_review_required`
- `government_photo_unusable`
- `liveness_failed`
- `face_mismatch`
- `multiple_faces`
- `quality_failed`
- `system_error`

Do not expose internal fraud rules or exact thresholds to the end user.

## 5.9 Verification result

After successful verification, create a signed verification assertion containing only necessary claims.

Example:

```json
{
  "tenant_subject_id": "ts_123",
  "identity_verified": true,
  "verification_method": "government_api",
  "face_match_passed": true,
  "liveness_passed": true,
  "assurance_level": "government_photo_verified",
  "verified_at": "2026-07-25T12:00:00Z",
  "verification_expires_at": "2027-07-25T12:00:00Z",
  "verification_version": "v1"
}
```

## 5.10 Temporary-data deletion

After the verification transaction completes, delete:

- Government photograph.
- Raw government response.
- Live frames.
- Liveness video.
- Government-photo embedding.
- Live verification embedding.
- Temporary files.
- Temporary object-store objects.
- Temporary queue payloads.

A deletion result must be added to the audit record.

## 5.11 Entry-template creation

Create the gate-entry template from a fresh, high-quality live capture.

Do not use the government photograph as the permanent gate template.

Reasons:

- Government photo may be old.
- Government photo may have low quality.
- Government photo was used for proofing, not ongoing authentication.
- The user should have a purpose-specific entry credential.

The entry template must be tenant-specific and purpose-specific.

---

# 6. Face encryption design

## 6.1 Important rule

Do not hash the facial vector using SHA-256 as the primary storage method.

Two captures of the same face produce similar but not identical vectors, so exact hashes cannot support normal similarity matching.

Use authenticated encryption.

## 6.2 Envelope encryption

Use two key layers.

### Data Encryption Key

- Random 256-bit key.
- Encrypts one facial template or a small tenant batch.
- Generated by KMS or a cryptographically secure random generator.
- Never stored in plaintext.

### Key Encryption Key

- Stored and controlled by KMS or HSM.
- Separate per tenant and environment.
- Encrypts the Data Encryption Key.
- Access allowed only to the matching service.

## 6.3 Recommended encryption algorithm

Use an authenticated-encryption mode such as AES-256-GCM.

Store:

- Ciphertext.
- Encrypted DEK.
- Nonce.
- Authentication tag.
- Key version.
- Model version.
- Template version.
- Creation time.
- Expiry time.

## 6.4 Associated data

Bind the encrypted template to:

- Tenant ID.
- Tenant subject ID.
- Purpose ID.
- Model version.
- Template version.

This prevents ciphertext from being copied into a different tenant or purpose without detection.

## 6.5 Key hierarchy

Recommended hierarchy:

```text
Platform root key
  └── Environment key
       └── Tenant key
            └── Template DEK
```

For high-security customers:

```text
Customer-owned KMS key
  └── Tenant/environment key
       └── Template DEK
```

## 6.6 Key access policy

Only these services may request decryption:

- Identity Proofing Service during the authorized transaction.
- Entry Matching Service during an authorized gate request.
- Erasure Service for verified deletion workflows where required.
- Key Rotation Service for controlled re-encryption.

Administrators, support staff, analytics services and database operators must not have normal decrypt permission.

## 6.7 Key rotation

Support:

- Scheduled key rotation.
- Emergency key rotation.
- Tenant offboarding.
- Key revocation.
- Template re-encryption.
- Audit of every decrypt and re-encrypt request.

## 6.8 Data in transit

Use encrypted transport for:

- User app to API.
- Gate to API.
- API to government service.
- Matching service to KMS.
- Service-to-service traffic.

For internal production services, use mutual TLS where practical.

## 6.9 Data during processing

A standard face engine needs access to a usable image or vector while processing.

Protection options:

### Minimum production design

- Isolated matching service.
- Restricted container or VM.
- No shell access.
- No swap.
- No core dumps.
- Memory limits.
- Short-lived plaintext.
- Explicit memory zeroization where supported.
- Network allowlist.
- KMS authorization.

### Higher-security design

- Confidential VM or TEE.
- Template decrypted only inside protected execution memory.
- Only match result leaves the protected environment.
- Remote attestation before key release.

TEE should be an optional high-security deployment mode, not a dependency for the first SaaS MVP.

---

# 7. Gate-entry matching design

## 7.1 Default mode: claimed identity plus face

Recommended for the first production version.

The person first presents one identifier:

- QR pass.
- Ticket token.
- Employee card.
- Student card.
- Mobile pass.
- NFC credential.
- Booking reference.

Then perform a 1:1 face comparison against that subject’s encrypted template.

## 7.2 Gate request flow

1. Terminal authenticates.
2. Terminal sends tenant, gate and device context.
3. User presents pass or token.
4. Server resolves tenant subject.
5. Server confirms credential is active.
6. Camera captures live frames.
7. Quality and liveness checks run.
8. Live face becomes a temporary embedding.
9. Entry Matching Service retrieves one encrypted template.
10. KMS authorizes temporary decryption.
11. Stored and live embeddings are compared.
12. Plain embeddings are destroyed.
13. Authorization Plane checks policy.
14. Allow, deny or manual review result is returned.
15. Minimal entry event is recorded.

## 7.3 Entry decision

Entry requires all required conditions:

```text
face_match_passed
AND liveness_passed
AND consent_active
AND credential_active
AND tenant_active
AND gate_allowed
AND zone_allowed
AND time_allowed
AND booking_or_membership_active
AND not_blacklisted
```

## 7.4 Face-only mode

Face-only entry uses tenant-scoped 1:N matching.

Restrictions:

- Search only the current tenant or event roster.
- Never search all BioCore identities.
- Use a minimum score.
- Use an ambiguity margin between the first and second candidate.
- Route uncertain results to manual review.
- Limit roster size per index or partition.
- Apply rate limiting.
- Record model and threshold version.

Face-only mode should be enabled only after real-world accuracy testing.

## 7.5 Temporary gate data

Delete after every attempt:

- Raw frame.
- Short video.
- Temporary live embedding.
- Decrypted stored embedding.
- Decrypted DEK.
- Temporary cropped face.

Keep only:

- Tenant subject ID.
- Gate ID.
- Device ID.
- Event type.
- Decision.
- Reason code.
- Timestamp.
- Match confidence band, not necessarily the exact raw score.
- Model and policy version.

## 7.6 Manual fallback

Every tenant must configure at least one fallback:

- QR-only with staff approval.
- Physical ID check.
- One-time PIN.
- Security-desk verification.
- Temporary manual pass.
- Supervisor override.

Manual override must record:

- Operator.
- Supervisor when required.
- Reason.
- Time.
- Gate.
- Subject.
- Supporting note.

---

# 8. Identity model changes

## 8.1 Replace mandatory global identity

The current global `persons` model should not directly expose one biometric identity across tenants.

Recommended structure:

```text
platform_accounts
  └── optional user login and self-service account

tenant_subjects
  ├── unique per tenant
  ├── separate tenant identifier
  ├── separate status
  └── separate consent

tenant_face_credentials
  ├── tenant-specific encrypted template
  ├── tenant-specific key context
  ├── purpose
  └── expiry
```

## 8.2 Optional reusable identity

A future BioCore Pass may allow user-approved reuse.

Rules:

- Disabled by default.
- Separate consent.
- New tenant subject created.
- New tenant template created or safely derived.
- Receiving tenant cannot see previous tenants.
- User can revoke one tenant without affecting others.
- No cross-tenant face search.

## 8.3 Tenant unlinkability

Where practical:

- Use different subject IDs per tenant.
- Use separate encrypted templates.
- Use separate keys.
- Avoid exposing a stable global identifier to customer systems.
- Do not allow customers to query whether a person exists in another customer.

---

# 9. Data model changes

## 9.1 New or revised tables

### `platform_accounts`

Stores optional account-level information for user login and self-service.

Fields:

- `id`
- `email_hash`
- `phone_hash`
- `status`
- `created_at`
- `last_login_at`

### `tenant_subjects`

Represents a person only inside one tenant.

Fields:

- `id`
- `tenant_id`
- `external_reference`
- `display_name`
- `subject_type`
- `status`
- `verification_status`
- `authorization_status`
- `valid_from`
- `valid_until`
- `created_at`

### `identity_verification_sessions`

Fields:

- `id`
- `tenant_subject_id`
- `government_provider`
- `provider_reference_hash`
- `status`
- `assurance_level`
- `liveness_result`
- `face_match_result`
- `failure_category`
- `model_version`
- `started_at`
- `completed_at`
- `expires_at`

Do not store raw government response or raw images.

### `verified_claims`

Fields:

- `tenant_subject_id`
- `claim_type`
- `claim_value`
- `verified_at`
- `expires_at`
- `source`

Examples:

- `age_over_18 = true`
- `name_verified = true`
- `identity_verified = true`

### `face_credentials`

Fields:

- `id`
- `tenant_id`
- `tenant_subject_id`
- `purpose_id`
- `encrypted_template`
- `encrypted_dek`
- `nonce`
- `authentication_tag`
- `key_version`
- `model_version`
- `template_version`
- `status`
- `created_at`
- `expires_at`
- `revoked_at`
- `erased_at`

### `consent_notices`

Fields:

- `id`
- `tenant_id`
- `purpose_id`
- `version`
- `language`
- `notice_text_hash`
- `active_from`
- `active_until`

### `consent_receipts`

Fields:

- `id`
- `tenant_subject_id`
- `notice_id`
- `purpose_id`
- `decision`
- `method`
- `captured_at`
- `withdrawn_at`
- `device_context`

### `entry_attempts`

Fields:

- `id`
- `tenant_id`
- `tenant_subject_id`
- `device_id`
- `gate_id`
- `zone_id`
- `match_result`
- `liveness_result`
- `authorization_result`
- `reason_code`
- `confidence_band`
- `model_version`
- `policy_version`
- `created_at`

### `template_key_events`

Fields:

- `face_credential_id`
- `operation`
- `key_version`
- `service_identity`
- `authorized_context`
- `created_at`

### `data_retention_policies`

Fields:

- `tenant_id`
- `data_category`
- `retention_period`
- `expiry_trigger`
- `legal_hold_allowed`
- `deletion_method`

### `erasure_jobs`

Fields:

- `tenant_subject_id`
- `scope`
- `status`
- `started_at`
- `completed_at`
- `certificate_id`
- `failure_reason`

### `device_certificates`

Fields:

- `device_id`
- `certificate_thumbprint`
- `issued_at`
- `expires_at`
- `revoked_at`

## 9.2 Existing tables to modify

### `persons`

Either remove the mandatory global-person role or limit it to an optional internal account-link layer that is inaccessible to customers.

### `person_faces`

Replace one reusable master template with tenant-specific encrypted credentials.

### `face_records`

Add:

- Encryption metadata.
- Purpose.
- Key version.
- Model version.
- Expiry.
- Revocation.
- Erasure state.

### `users`

Rename or separate organization membership from platform login.

### `attendance_log`

Ensure it contains only operational access events and no biometric payload.

### `audit`

Add KMS, verification, retention and erasure events.

---

# 10. API changes

## 10.1 Identity proofing APIs

```text
POST /api/v1/identity/sessions
GET  /api/v1/identity/sessions/{id}
POST /api/v1/identity/sessions/{id}/consent
POST /api/v1/identity/sessions/{id}/government-fetch
POST /api/v1/identity/sessions/{id}/live-capture
POST /api/v1/identity/sessions/{id}/verify
POST /api/v1/identity/sessions/{id}/complete
POST /api/v1/identity/sessions/{id}/cancel
```

## 10.2 Face credential APIs

```text
POST   /api/v1/face-credentials
GET    /api/v1/face-credentials/{id}/status
POST   /api/v1/face-credentials/{id}/re-enroll
POST   /api/v1/face-credentials/{id}/revoke
DELETE /api/v1/face-credentials/{id}
```

No endpoint should return a raw or encrypted template to a customer administrator.

## 10.3 Entry APIs

```text
POST /api/v1/entry/resolve-claim
POST /api/v1/entry/capture-session
POST /api/v1/entry/match
POST /api/v1/entry/authorize
POST /api/v1/entry/commit
POST /api/v1/entry/manual-review
POST /api/v1/entry/manual-override
```

For low latency, these may be combined into one transactional endpoint internally, while preserving separate service boundaries.

## 10.4 Consent and privacy APIs

```text
GET  /api/v1/privacy/notices
POST /api/v1/privacy/consents
POST /api/v1/privacy/consents/{id}/withdraw
GET  /api/v1/privacy/my-data
POST /api/v1/privacy/correction-request
POST /api/v1/privacy/erasure-request
GET  /api/v1/privacy/erasure/{id}/status
GET  /api/v1/privacy/erasure/{id}/certificate
```

## 10.5 Device APIs

```text
POST /api/v1/devices/pair
POST /api/v1/devices/attest
POST /api/v1/devices/rotate-certificate
POST /api/v1/devices/revoke
GET  /api/v1/devices/{id}/policy
POST /api/v1/devices/{id}/heartbeat
```

## 10.6 Administration APIs

Admin APIs may expose:

- Verified/not verified.
- Credential active/revoked/expired.
- Verification method.
- Assurance level.
- Consent status.
- Last successful entry.
- Last failure category.

They must not expose:

- Government photograph.
- Raw government response.
- Face template.
- Decryption key.
- Exact biometric debug payload.

---

# 11. Changes to the four applications

# 11.1 User app

Add:

- Verification introduction page.
- Government-data permission page.
- Purpose-specific consent page.
- Verification-method selection.
- Government API processing screen.
- Live liveness capture.
- Face-to-government match status.
- Entry-template enrollment.
- Verification receipt.
- Active organization credentials.
- Credential expiry.
- Withdraw organization access.
- Re-enroll face.
- Data-access request.
- Erasure request.
- Alternative entry option.

Modify:

- Move all consent before collection.
- Separate identity verification from entry activation.
- Show organization-specific permissions.
- Do not automatically reuse a global master template.

# 11.2 Guard console

Add:

- Claimed-identity scan.
- Liveness result.
- Identity verified status.
- Authorization reason.
- Manual-review queue.
- Supervisor override.
- Device trust status.
- Offline-mode indicator.
- Privacy-safe failure messages.

Do not show:

- Government photo by default.
- Stored face template.
- Full government data.
- Exact internal threshold.

# 11.3 Kiosk

Add:

- Secure device enrollment.
- Full-screen locked mode.
- Device certificate.
- Liveness guidance.
- Quality guidance.
- One-person-at-a-time detection.
- Timeout and automatic reset.
- Memory cleanup after each attempt.
- No browser cache of images.
- Offline policy where enabled.

# 11.4 Admin portal

Add screens:

- Identity policy.
- Government API configuration.
- Verification assurance levels.
- Consent purposes.
- Retention rules.
- Face credential status.
- Key-rotation status.
- Device certificates.
- Matching-policy versions.
- Manual overrides.
- Verification failure analytics.
- Erasure queue.
- Privacy requests.
- Integration health.
- Offline synchronization status.

Admin users should see status and operational data, not biometric payload.

---

# 12. Device and gate security changes

## 12.1 Keep hashed device tokens

The current hashed device-token design remains useful.

## 12.2 Add device certificates

Every production terminal should have:

- Device ID.
- Certificate.
- Tenant assignment.
- Gate assignment.
- Zone assignment.
- Allowed operations.
- Expiry.
- Revocation support.

## 12.3 Terminal hardening

- Kiosk mode.
- Automatic OS updates.
- Restricted local user.
- Disk encryption.
- Disabled unnecessary ports.
- No persistent camera files.
- No browser downloads.
- No local template export.
- Screen lock.
- Health monitoring.
- Remote revocation.

## 12.4 Trusted request context

Every gate request should include signed or authenticated context:

- Device.
- Tenant.
- Gate.
- Zone.
- Timestamp.
- Request nonce.
- Software version.
- Policy version.

---

# 13. Consent, retention and erasure changes

## 13.1 Consent timing

Consent must be recorded before:

- Government-data retrieval.
- Government-photo processing.
- Live face capture.
- Face matching.
- Entry-template creation.

## 13.2 Purpose separation

Identity verification and gate authentication are separate purposes.

A user may pass identity verification but decline face entry. The tenant must define an alternative process where operationally possible.

## 13.3 Retention triggers

Configure by vertical.

### Event

- Expire at event end plus configured grace period.

### School or college

- Expire at withdrawal, graduation, transfer or policy expiry.

### Workspace

- Expire at employment or contract end.

### Hotel

- Revoke at checkout.
- Delete according to configured operational and legal retention rules.

### Visitor

- Expire at visit end.

## 13.4 Erasure cascade

Erasure must cover:

- Encrypted face credential.
- Encrypted DEK.
- Vector database record.
- Search index.
- Cache.
- Redis.
- Temporary objects.
- Backups according to backup-erasure policy.
- Derived cross-tenant credential if included in scope.

Keep only an erasure certificate and minimal audit proof where permitted.

## 13.5 Legal hold

A legal hold must:

- Require an authorized role.
- Record reason and authority.
- Have an expiry or review date.
- Apply only to necessary records.
- Not silently retain biometric data without policy.

---

# 14. Logging and observability changes

## 14.1 Never log

- Raw government API response.
- Government photograph.
- Raw face image.
- Face vector.
- Encryption key.
- Decrypted template.
- Consent document text when a hash and version are sufficient.
- Full personal identifiers in request logs.

## 14.2 Safe logs

Log:

- Request ID.
- Tenant ID.
- Service identity.
- Operation.
- Status.
- Error category.
- Model version.
- Policy version.
- Latency.
- Device ID.
- Key version.

## 14.3 Sensitive debugging

Production debugging must use:

- Short-lived diagnostic mode.
- Explicit approval.
- Redacted payloads.
- Time-limited access.
- Complete audit trail.

No engineer should casually download customer face data for debugging.

---

# 15. Face-engine changes

## 15.1 Replace fake-engine assumptions

The fake engine may remain only for local UI and API development.

Production requires:

- Real embedding model.
- Real liveness model.
- Real spoof model.
- Real quality model.
- Real duplicate check where needed.
- Model-version tracking.
- Reproducible deployment.
- Signed model artifacts.

## 15.2 Separate models if required

You may use:

- One model for identity proofing.
- One model for gate authentication.

But model compatibility and template migration must be managed.

## 15.3 Threshold management

Thresholds must be:

- Versioned.
- Tested.
- Different by security profile, not casually changed per customer.
- Audited.
- Associated with model version.
- Validated in real gate conditions.

## 15.4 Failure handling

Use stable reason categories:

- `NO_FACE`
- `MULTIPLE_FACES`
- `QUALITY_FAILED`
- `LIVENESS_FAILED`
- `FACE_MISMATCH`
- `AMBIGUOUS_MATCH`
- `CREDENTIAL_EXPIRED`
- `CONSENT_WITHDRAWN`
- `ACCESS_NOT_ALLOWED`
- `DEVICE_NOT_TRUSTED`
- `MATCH_ENGINE_UNAVAILABLE`

---

# 16. Offline and poor-network mode

Offline mode is currently a gap and should become a priority for events, schools, factories and remote sites.

## 16.1 Offline options

### Option A: No biometric data on terminal

- Gate falls back to QR or manual process.
- Strongest privacy.
- Weakest continuity.

### Option B: Encrypted local event roster

- Download only the active gate roster.
- Encrypt with device-bound key.
- Strict expiry.
- No export.
- Automatic wipe after event.
- Sync decisions when network returns.

### Option C: On-site edge matcher

- Local server holds tenant-scoped encrypted templates.
- Gates connect over local network.
- Internet is required only for synchronization.
- Best for schools, factories and large events.

Recommended:

- Events: on-site edge matcher or encrypted event roster.
- Schools/workspaces/hotels: on-prem or site-edge matcher for strict customers.

---

# 17. Deployment modes

## 17.1 Secure SaaS

Best for:

- Events.
- Small workspaces.
- Gyms.
- Co-working.

Characteristics:

- India-region deployment where required by customer policy.
- Tenant-specific encryption keys.
- Central managed matching.
- Fast onboarding.

## 17.2 Customer-controlled cloud

Best for:

- Enterprises.
- Universities.
- Hotel chains.
- Hospitals.

Characteristics:

- Customer cloud account.
- Customer-owned KMS option.
- BioCore managed application.
- Customer-controlled biometric vault.

## 17.3 On-premises

Best for:

- Government.
- Banks.
- Sensitive schools.
- Factories.
- Critical infrastructure.

Characteristics:

- Local vault and matcher.
- Local KMS/HSM option.
- Controlled synchronization.
- Customer data does not leave site except approved metadata.

## 17.4 Confidential-computing mode

Best for high-trust requirements.

Characteristics:

- TEE or confidential VM.
- Key release tied to approved workload measurement.
- Matching inside protected memory.
- Only decision and audit metadata leave the environment.

---

# 18. Vertical-specific changes

# 18.1 Event management

Required modules:

- Event roster integration.
- Attendee verification.
- Event-specific consent.
- Event-specific credential.
- Portable gate devices.
- Fast 1:1 or event-scoped 1:N matching.
- VIP and zone access.
- Temporary staff access.
- Emergency headcount.
- Automatic post-event expiration and erasure.
- Offline gate mode.

Recommended assurance levels:

- Basic event: invitation or ticket plus face.
- Higher-security event: government API plus face-to-government match.
- VIP/restricted area: government verification plus claimed identity plus face.

# 18.2 Schools

Required modules:

- Student roster.
- Staff roster.
- Guardian relationship.
- Guardian consent workflow.
- Student gate entry.
- Bus boarding.
- Classroom attendance.
- Guardian pickup verification.
- Emergency muster.
- Alternative non-biometric process.
- SIS integration.

Do not require government verification for every student when the school’s verified admission roster is sufficient for the selected purpose.

# 18.3 Colleges and universities

Required modules:

- Student and staff roster.
- Hostel access.
- Library access.
- Lab access.
- Examination access.
- Event access.
- Visitor flow.
- SIS/ERP integration.
- Role and zone policy.

Use stronger assurance for exams, hostels and restricted labs than for general attendance.

# 18.4 Workspaces

Required modules:

- HRMS integration.
- Employee onboarding.
- Contractor verification.
- Visitor invitation.
- Shift and time policy.
- Floor and zone access.
- Attendance and breaks.
- Payroll export.
- Emergency headcount.
- Employment-end revocation.

# 18.5 Hotels

Required modules:

- PMS integration.
- Guest verification.
- Booking and stay linkage.
- Guest and staff separation.
- Floor and facility access.
- Visitor access.
- Checkout revocation.
- Retention policy by record category.
- Customer-controlled or on-prem deployment option.

The legal guest record and biometric entry credential must remain separate data domains.

---

# 19. Integration changes

## 19.1 Government API adapter

Create a dedicated adapter interface:

```text
GovernmentIdentityProvider
  - create_session()
  - fetch_verified_data()
  - validate_response()
  - extract_allowed_claims()
  - extract_temporary_photo()
  - revoke_or_close_session()
```

The adapter must isolate provider-specific formats from the main product.

## 19.2 Business integrations

Prioritize:

- Event ticketing and registration.
- School SIS.
- College ERP.
- HRMS and payroll.
- Hotel PMS.
- Visitor management.
- Door and turnstile controllers.
- SMS, email and WhatsApp notifications.

## 19.3 Hardware bridge

Add a local hardware bridge for:

- Door relay.
- Turnstile.
- Boom barrier.
- Elevator access.
- Alarm.
- LED or buzzer.

The bridge receives only an allow/deny command and signed context, not the face template.

---

# 20. Roles and permissions changes

## 20.1 New service roles

- `identity_proofing_service`
- `entry_matching_service`
- `authorization_service`
- `erasure_service`
- `key_rotation_service`
- `device_attestation_service`

## 20.2 Human roles

- Tenant owner.
- Privacy administrator.
- Security administrator.
- Enrollment operator.
- Guard.
- Supervisor.
- HR/SIS/PMS integration administrator.
- Auditor.
- Support operator with restricted access.

## 20.3 Separation of duties

- Enrollment operator cannot export verification data.
- Guard cannot change policy.
- Security admin cannot access KMS keys.
- Support cannot decrypt templates.
- Privacy admin can manage consent and erasure but not gate overrides.
- Auditor has read-only metadata access.

---

# 21. Security changes

Keep current:

- Argon2 passwords.
- ~~Admin TOTP.~~ **REMOVED 2026-09-13 by product decision.** Admin sign-in is
  email + password. This is a deliberate deviation from this spec, not an
  oversight: the second factor, its storage column and every reference were
  removed (migration 0013). Reinstating it means re-implementing, not re-enabling.
- Redis sessions.
- HttpOnly cookies.
- CSRF protection.
- PostgreSQL RLS.
- Non-superuser application database role.

Add:

- Service identities.
- Mutual TLS.
- KMS/HSM.
- Device certificates.
- Template envelope encryption.
- Network segmentation.
- Egress restrictions.
- No core dumps.
- No swap for matching workloads where practical.
- Dependency and container scanning.
- Signed images.
- Software bill of materials.
- Secrets rotation.
- Rate limiting.
- Replay protection.
- Request nonces.
- Key-operation audit.
- Incident-response playbook.
- Biometric breach-response process.

---

# 22. Testing changes

The current functional acceptance suite is not sufficient for production biometric verification.

Add the following test programs.

## 22.1 Functional testing

- Enrollment success.
- Government API failure.
- Government-photo missing.
- Live capture retry.
- Consent withdrawal.
- Credential expiry.
- Gate allow and deny.
- Manual override.
- Erasure.
- Key rotation.

## 22.2 Biometric testing

- Same-person comparison.
- Different-person comparison.
- Lighting variation.
- Camera variation.
- Age variation.
- Glasses.
- Headwear.
- Facial hair.
- Skin-tone coverage.
- Similar-looking users.
- Twins where possible.
- Threshold evaluation.
- False match rate.
- False non-match rate.

## 22.3 Spoof testing

- Printed photo.
- Phone screen.
- Tablet replay.
- Recorded video.
- Mask.
- Deepfake feed.
- Virtual camera.
- Camera injection.

## 22.4 Performance testing

- Verification latency.
- Gate latency.
- Peak entries per minute.
- Concurrent gates.
- KMS latency.
- Government API latency.
- 1:N roster size.
- Offline synchronization.

## 22.5 Security testing

- API penetration test.
- Device compromise test.
- Tenant-isolation test.
- KMS-policy test.
- Template-copy test.
- Replay attack.
- Session hijack.
- Log leakage.
- Backup leakage.
- Erasure verification.

## 22.6 Operational acceptance

A deployment is not ready until:

- Real face engine is enabled.
- Fake engine is disabled.
- Production keys are active.
- Government API logs are redacted.
- Retention rules are configured.
- Fallback entry works.
- Devices are paired and trusted.
- Monitoring is active.
- Erasure drill passes.
- Backup restore drill passes.
- Incident contacts are assigned.

---

# 23. Monitoring changes

Add metrics:

- Government API success rate.
- Verification completion rate.
- Liveness failure rate.
- Face mismatch rate.
- Quality retry rate.
- Gate match latency.
- KMS latency.
- Decrypt failure rate.
- Device trust failures.
- Template expiration count.
- Consent withdrawal count.
- Erasure completion time.
- Manual override rate.
- Offline synchronization backlog.

Alerts:

- Sudden spike in mismatches.
- Sudden spike in liveness failure.
- Repeated requests from one device.
- Device certificate expired.
- KMS access denied.
- Government API response leakage detected.
- Erasure job delayed.
- Matching service unavailable.
- Tenant-isolation violation.

---

# 24. Product configuration model

Each tenant should choose:

- Verification requirement.
- Government API requirement.
- Accepted identity methods.
- Liveness strength.
- Gate mode: 1:1 or 1:N.
- Match policy.
- Manual fallback.
- Retention period.
- Offline behavior.
- Device security level.
- Deployment mode.
- Allowed zones.
- Consent notice.
- Data-processing region.

Create named policy profiles:

- `basic_attendance`
- `standard_entry`
- `government_verified_entry`
- `high_security_entry`
- `minor_guardian_entry`
- `temporary_event_entry`
- `hotel_guest_entry`

---

# 25. Updated status matrix

## Already built and reusable

- Four applications.
- Multi-tenancy.
- RLS.
- Roles.
- Attendance.
- Zones.
- Events.
- Visitors.
- Blacklist.
- Alerts.
- Muster.
- Audit.
- Docker/Kubernetes.
- Monitoring foundation.
- Worker and retries.
- MediaPipe positioning.
- Face-engine adapter.

## Built but needs modification

- Person model.
- Face record model.
- Consent flow.
- Erasure flow.
- Admin screens.
- Guard flow.
- Kiosk flow.
- Device pairing.
- Settings.
- Reports.
- Verification status.

## Must be newly built

- Government API adapter.
- Identity Proofing Service.
- Government-photo-to-live-face verification.
- Tenant-specific Credential Vault.
- KMS/HSM envelope encryption.
- Entry Matching Service.
- Key-rotation service.
- Device certificates.
- Policy-version management.
- Privacy receipt.
- Verification claim service.
- Offline edge matching.
- Template migration.
- Biometric accuracy test suite.
- Spoof test suite.
- Customer integration connectors.
- Hardware bridge.
- Production privacy and security runbooks.

## External production dependencies

- Real face model and weights.
- Real liveness and anti-spoof engine.
- Government API production access.
- KMS/HSM.
- TLS certificates.
- Secrets manager.
- Managed or hardened datastores.
- Security review.
- Privacy review.
- Pilot hardware.
- Customer integrations.

---

# 26. Recommended delivery roadmap

## Phase 0: Architecture correction

- Replace global-template default.
- Define tenant-subject model.
- Define consent purposes.
- Define retention rules.
- Define government API adapter.
- Define KMS key hierarchy.
- Define matching-service boundary.

## Phase 1: Verified enrollment

Build:

- Government API integration.
- Consent-before-capture flow.
- Live capture and liveness.
- Government-face-to-live-face match.
- Minimal verified claims.
- Temporary-data deletion.

## Phase 2: Encrypted entry credential

Build:

- Tenant-specific entry template.
- AES-GCM envelope encryption.
- KMS integration.
- Credential status and expiry.
- Revocation and erasure.

## Phase 3: Gate authentication

Build:

- Device certificates.
- Claimed-identity plus face.
- 1:1 matching.
- Authorization engine.
- Guard and kiosk changes.
- Manual fallback.

## Phase 4: Event production pilot

Deploy:

- One event.
- One or two gates.
- Limited attendee count.
- Real face engine.
- Government verification only where required.
- QR plus face by default.
- Offline fallback.
- Full monitoring.

## Phase 5: Workspace and college

Add:

- HRMS/SIS integration.
- Role and zone access.
- Employment/student lifecycle.
- Site-edge deployment.

## Phase 6: School and hotel

Add:

- Guardian workflows.
- Minor consent.
- PMS integration.
- Checkout revocation.
- Customer-controlled data deployment.

## Phase 7: High-security mode

Add:

- TEE or confidential VM.
- Customer-owned KMS.
- Remote attestation.
- On-prem HSM.
- Advanced device attestation.

---

# 27. Recommended MVP definition

The first production MVP should include:

1. Tenant setup.
2. Event or organization roster.
3. Consent before data collection.
4. Government API integration.
5. Live liveness capture.
6. 1:1 live face to government face verification.
7. Minimal verified claims.
8. Deletion of government photograph and raw verification media.
9. Fresh entry-template capture.
10. Tenant-specific encrypted template.
11. KMS envelope encryption.
12. QR/card/pass plus face at gate.
13. 1:1 gate matching.
14. Authorization checks.
15. Minimal entry log.
16. Manual fallback.
17. Credential expiry.
18. Withdrawal and erasure.
19. Real monitoring.
20. Real face-engine testing.

Do not include in the first MVP:

- Global cross-tenant face search.
- Automatic universal face reuse.
- Face-only 1:N entry for very large populations.
- TEE as a mandatory dependency.
- Native mobile app unless required by pilot.
- Complex analytics using biometric data.

---

# 28. Final architecture decision summary

## Identity verification

```text
Consent
→ Government API
→ Temporary government face
→ Live face and liveness
→ 1:1 comparison
→ Minimal verified claims
→ Delete government and raw face material
```

## Entry credential

```text
Fresh live capture
→ Entry embedding
→ Tenant-specific AES-GCM encryption
→ DEK encrypted by tenant KMS key
→ Expiry and consent linked
```

## Gate entry

```text
Trusted device
→ Claimed identity or tenant-scoped search
→ Live liveness
→ Temporary live embedding
→ Decrypt stored template only inside matcher
→ Face match
→ Authorization policy
→ Allow, deny or manual review
→ Delete temporary biometric data
```

## Privacy model

```text
No raw image storage by default
No full government response storage
No template export
No global face search
Tenant-specific identity
Tenant-specific encryption
Purpose-specific consent
Automatic expiry
Verified erasure
```

---

# 29. Final non-negotiable rules

1. Consent and notice before government-data retrieval and camera capture.
2. Government verification and gate authentication remain separate processes.
3. Raw government photo is temporary.
4. Raw live images are temporary by default.
5. Government-photo embeddings are temporary.
6. Gate templates are created from a fresh live capture.
7. Every face credential is tenant-specific.
8. Every face credential is encrypted with authenticated envelope encryption.
9. Keys remain outside the application database.
10. Only approved matching services may decrypt templates.
11. Face match does not itself grant access; policy must also allow entry.
12. No global face search across customers.
13. No administrator template download.
14. No biometric data in logs, queues or analytics.
15. Every credential has purpose, status, consent, expiry and erasure state.
16. Every production terminal is paired, certified and revocable.
17. Every deployment has a manual fallback.
18. Fake face engine is forbidden in production and real pilots.
19. Real biometric, spoof, load and security testing is mandatory.
20. Schools, colleges, workspaces, hotels and events use separate policy profiles.

---

# 30. Product outcome after these changes

After these changes, BioCore will become a complete verified-entry platform rather than only a face-attendance application.

It will be able to say:

> BioCore verifies a person through an authorized identity source, checks that the live person matches the verified government record, deletes unnecessary verification material, creates an organization-specific encrypted face credential, and uses that credential only for approved entry decisions. The system stores no raw face image by default, prevents cross-customer face search, limits access to biometric templates, supports withdrawal and erasure, and can run as SaaS, customer-cloud, edge or on-premises software.
