# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Which versions are eligible for receiving such patches depends on the CVSS v3.0 Rating:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to security@example.com (replace with actual contact).

You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.

Please include the following information:

- Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

This information will help us triage your report more quickly.

## Preferred Languages

We prefer all communications to be in English.

## Security Update Process

1. The security report is received and assigned to a primary handler
2. The problem is confirmed and a list of affected versions is determined
3. Code is audited to find any potential similar problems
4. Fixes are prepared for all supported releases
5. New releases are issued and security advisory is published

## Security Best Practices for Users

### Authentication
- Keep your `client_secret` secure and never commit it to version control
- Rotate credentials regularly
- Use strong, randomly generated secrets

### Network Security
- Use CIDR filtering to restrict API access to known IP addresses
- Always use HTTPS in production
- Configure firewall rules to limit access to Home Assistant

### Access Control
- Use entity labels (`smartly`) to limit which entities can be controlled
- Regularly review and update ACL settings
- Monitor audit logs for suspicious activity

### Rate Limiting
- Keep rate limiting enabled
- Adjust limits based on your usage patterns
- Monitor for rate limit violations

### Updates
- Keep the integration updated to the latest version
- Subscribe to security advisories
- Review CHANGELOG before updating

## Known Security Considerations

### HMAC Authentication
- Uses HMAC-SHA256 for request signing
- Nonce-based replay attack prevention
- Timestamp validation (requests expire after window)

### Sensitive Data
- Client secrets are stored in Home Assistant's config entry (encrypted at rest)
- Audit logs may contain entity IDs and user information
- Webhook URLs may be logged

### Dependencies
- Regularly audit dependencies for vulnerabilities
- Use `safety` and `pip-audit` for security scanning
- Keep dependencies updated

## Security Scanning

This project uses automated security scanning:
- **Bandit**: Python security linter
- **Safety**: Dependency vulnerability scanner
- **pip-audit**: PyPI package auditing
- **Dependabot**: Automated dependency updates

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine affected versions
2. Audit code to find similar problems
3. Prepare fixes for supported versions
4. Release patches as soon as possible

We aim to disclose vulnerabilities within 90 days of the initial report.

## Bug Bounty Program

We do not currently have a bug bounty program in place.

## Credits

We thank the following researchers for responsibly disclosing security issues:

- (List will be updated as issues are reported and fixed)

## Contact

For security concerns, contact: security@example.com

For general questions: GitHub Issues or Discussions
