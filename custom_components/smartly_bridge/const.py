"""Constants for Smartly Bridge integration."""

DOMAIN = "smartly_bridge"

# Configuration keys
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_WEBHOOK_URL = "webhook_url"
CONF_INSTANCE_ID = "instance_id"
CONF_ALLOWED_CIDRS = "allowed_cidrs"
CONF_PUSH_BATCH_INTERVAL = "push_batch_interval"

# Default values
DEFAULT_PUSH_BATCH_INTERVAL = 0.5  # seconds

# Rate limiting
RATE_LIMIT = 60  # requests per window
RATE_WINDOW = 60  # seconds (1 minute)

# HMAC authentication
TIMESTAMP_TOLERANCE = 30  # seconds
NONCE_TTL = 300  # 5 minutes

# Push retry
PUSH_RETRY_MAX = 3
PUSH_RETRY_BACKOFF_BASE = 2  # exponential backoff base

# Entity label for access control
PLATFORM_CONTROL_LABEL = "smartly"

# Allowed services whitelist
ALLOWED_SERVICES: dict[str, list[str]] = {
    "switch": ["turn_on", "turn_off", "toggle"],
    "light": ["turn_on", "turn_off", "toggle"],
    "cover": ["open_cover", "close_cover", "stop_cover", "set_cover_position"],
    "climate": ["set_temperature", "set_hvac_mode", "set_fan_mode"],
    "fan": ["turn_on", "turn_off", "set_percentage", "set_preset_mode"],
    "lock": ["lock", "unlock"],
    "scene": ["turn_on"],
    "script": ["turn_on", "turn_off"],
    "automation": ["trigger", "turn_on", "turn_off"],
}

# HTTP Headers
HEADER_CLIENT_ID = "X-Client-Id"
HEADER_TIMESTAMP = "X-Timestamp"
HEADER_NONCE = "X-Nonce"
HEADER_SIGNATURE = "X-Signature"
HEADER_HA_INSTANCE_ID = "X-HA-Instance-Id"

# API paths
API_PATH_CONTROL = "/api/smartly/control"
API_PATH_SYNC = "/api/smartly/sync/structure"
