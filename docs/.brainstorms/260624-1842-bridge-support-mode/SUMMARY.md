# Brainstorm: Bridge Support Mode for Platform Maintenance

> Created: 2026-06-24 18:42:00

## Context

- Smartly Platform needs to be rebuilt after the previous local copy was lost.
- The future Platform will let customers log in through a website/PWA, view device information returned through Smartly Bridge APIs, and control devices through the Platform.
- Smartly Bridge currently uses server-to-server HMAC authentication and is designed so Platform never holds a Home Assistant long-lived token.
- Platform should own user login, RBAC, tenant/community access, support workflows, and audit logs.
- Bridge should remain the final local safety boundary for Home Assistant access.
- A future requirement is for support/admin users to help customers troubleshoot without giving admins permanent or unrestricted customer HA access.

## Goals

- Design a future "Support Mode" or maintenance authorization flow where the customer can approve temporary support access from the Bridge/HA side.
- Keep PWA and browser clients away from Bridge secrets and direct Bridge API access.
- Require Platform admins to operate through Platform UI/API, with Platform calling Bridge using HMAC.
- Let Bridge enforce a short-lived support grant for support/admin actions, not only trust Platform UI state.
- Make support access time-limited, scoped, revocable, and auditable.
- Support a first implementation that is simpler than a full HA remote tunnel.

## Non-Goals

- Do not let users or admins OAuth directly to Bridge.
- Do not expose Bridge `client_secret` or HMAC signing capability to PWA/browser code.
- Do not give Platform or support admins HA long-lived tokens.
- Do not implement a full Home Assistant UI tunnel in the first version.
- Do not allow support admins to bypass Platform RBAC or Bridge entity/service restrictions.

## Chosen Approach

- Implement a Bridge/HA-side "Support Mode" authorization button or notification, similar in spirit to a temporary developer mode.
- A Platform admin starts a support request from Platform with reason, requested scopes, duration, and target community/HA instance.
- The customer approves or rejects the request locally through Bridge/HA UI, such as a persistent notification or integration option.
- Once approved, Bridge stores a short-lived support grant with scopes, expiry, allowed entities/areas/actions, support session ID, and revocation state.
- Platform support/admin API calls must include actor metadata and `support_session_id`.
- Bridge verifies HMAC, existing smartly entity label, service whitelist, and the active support grant before allowing support/admin actions.
- Customer can revoke Support Mode before expiry.

## Alternatives Considered

- Platform-only support authorization - simpler to build, but Bridge would not independently enforce customer approval. A Platform bug or compromised admin path could grant too much access.
- Direct admin access to Home Assistant - powerful for troubleshooting, but too risky because full HA access can bypass Platform RBAC and Bridge limits.
- Full tunnel similar to cloudflared - useful for emergency diagnostics, but should be treated as a later break-glass feature due to higher security and implementation complexity.
- OAuth from admin/user to Bridge - not aligned with current Bridge architecture, which is server-to-server HMAC and not a user-facing OAuth resource server.

## Risks & Mitigations

- Risk: Support Mode becomes an unrestricted remote control path -> mitigation: scope grants by capability, area/entity/action, and duration.
- Risk: Admin performs sensitive actions such as unlocking doors -> mitigation: separate high-risk scopes, require customer approval, MFA, and short duration; exclude from MVP by default.
- Risk: Customer cannot tell when support access is active -> mitigation: visible HA notification/status plus Platform customer UI banner and revoke button.
- Risk: Platform and Bridge audit logs diverge -> mitigation: include `support_session_id`, actor, reason, and request ID in every support action.
- Risk: Bridge restart loses grant state unexpectedly -> mitigation: decide whether grants are in-memory only for safety or persisted with expiry; in-memory is safer for MVP.
- Risk: Entity IDs expose sensitive labels -> mitigation: Platform should expose opaque IDs to PWA and keep Bridge entity IDs internal.

## Open Questions

- Should Support Mode approval happen only inside HA, or also from a customer Platform/PWA screen?
- Who is allowed to approve support access: homeowner, community manager, property manager, or tenant admin?
- What are the MVP scopes: diagnostics-only, safe control, camera view, history read, bridge resync?
- Should support grants survive HA/Bridge restart, or should restart revoke all active grants?
- Should high-risk domains such as locks, alarms, and access control be completely excluded from first release?
- How should Platform present active support access to customers and admins?

## Next Step Recommendation

- When implementation planning starts, write a concrete plan for:
  - Bridge Support Mode data model and grant validation.
  - HA UI/notification approval and revoke flow.
  - Platform support request and support session workflow.
  - Actor/audit payload contract between Platform and Bridge.
  - MVP scope list and explicit high-risk exclusions.
