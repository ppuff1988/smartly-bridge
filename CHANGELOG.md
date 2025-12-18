# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial CI/CD pipeline setup
- GitHub Actions workflows for testing, linting, and deployment

### Changed
- Fixed config flow integration type in manifest.json
- Fixed HTTP views to properly inherit from HomeAssistantView
- Fixed OptionsFlow initialization

### Fixed
- AttributeError in HTTP view registration
- Config entry property setter issue

## [1.0.0] - 2025-12-17

### Added
- Initial release of Smartly Bridge integration
- OAuth-like authentication with HMAC-SHA256
- RESTful API endpoints for device control and sync
- Push notification system for state changes
- Access control list (ACL) for entities and services
- Audit logging for all control actions
- Rate limiting and CIDR-based IP filtering
- Support for Home Assistant structure (floors, areas, devices)
- Internationalization support (en, zh-Hant)

### Security
- HMAC-SHA256 request signing
- Nonce-based replay attack prevention
- Configurable CIDR IP whitelist
- Rate limiting per client
