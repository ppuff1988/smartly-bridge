"""Constants for Smartly Bridge integration."""

DOMAIN = "smartly_bridge"

# Configuration keys
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_WEBHOOK_URL = "webhook_url"
CONF_INSTANCE_ID = "instance_id"
CONF_ALLOWED_CIDRS = "allowed_cidrs"
CONF_PUSH_BATCH_INTERVAL = "push_batch_interval"
CONF_TRUST_PROXY = "trust_proxy"

# Trust proxy modes
TRUST_PROXY_AUTO = "auto"
TRUST_PROXY_ALWAYS = "always"
TRUST_PROXY_NEVER = "never"

# Private IP ranges (for trust_proxy auto detection)
PRIVATE_IP_RANGES = [
    "127.0.0.0/8",  # localhost
    "::1/128",  # IPv6 localhost
    "10.0.0.0/8",  # Private network
    "172.16.0.0/12",  # Private network
    "192.168.0.0/16",  # Private network
    "fe80::/10",  # IPv6 link-local
]

# Default values
DEFAULT_PUSH_BATCH_INTERVAL = 0.5  # seconds
DEFAULT_TRUST_PROXY = TRUST_PROXY_AUTO  # Auto-detect by default

# Rate limiting
RATE_LIMIT = 60  # requests per window
RATE_WINDOW = 60  # seconds (1 minute)

# HMAC authentication
TIMESTAMP_TOLERANCE = 30  # seconds
NONCE_TTL = 300  # 5 minutes

# Push retry
PUSH_RETRY_MAX = 3
PUSH_RETRY_BACKOFF_BASE = 2  # exponential backoff base

# Camera cleanup
CAMERA_CLEANUP_INTERVAL = 60  # seconds between cache cleanup runs

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
    "camera": ["enable_motion_detection", "disable_motion_detection", "record", "snapshot"],
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
API_PATH_SYNC_STATES = "/api/smartly/sync/states"
API_PATH_STATES = "/api/smartly/states"  # Alternative path for backward compatibility

# Camera API paths
API_PATH_CAMERA_SNAPSHOT = "/api/smartly/camera/{entity_id}/snapshot"
API_PATH_CAMERA_STREAM = "/api/smartly/camera/{entity_id}/stream"
API_PATH_CAMERA_LIST = "/api/smartly/camera/list"
API_PATH_CAMERA_CONFIG = "/api/smartly/camera/config"

# HLS Camera API paths
API_PATH_CAMERA_HLS_INFO = "/api/smartly/camera/{entity_id}/stream/hls"
API_PATH_CAMERA_HLS_MASTER = "/api/smartly/camera/{entity_id}/stream/hls/master.m3u8"
API_PATH_CAMERA_HLS_PLAYLIST = "/api/smartly/camera/{entity_id}/stream/hls/playlist.m3u8"
API_PATH_CAMERA_HLS_INIT = "/api/smartly/camera/{entity_id}/stream/hls/init.mp4"
API_PATH_CAMERA_HLS_SEGMENT = "/api/smartly/camera/{entity_id}/stream/hls/segment/{sequence}.m4s"
API_PATH_CAMERA_HLS_PART = "/api/smartly/camera/{entity_id}/stream/hls/part/{sequence}.{part}.m4s"

# History API paths
API_PATH_HISTORY = "/api/smartly/history/{entity_id}"
API_PATH_HISTORY_BATCH = "/api/smartly/history/batch"
API_PATH_STATISTICS = "/api/smartly/statistics/{entity_id}"

# History API settings
HISTORY_MAX_DURATION_DAYS = 30  # 最大查詢天數
HISTORY_DEFAULT_LIMIT = 1000  # 預設最大筆數
HISTORY_MAX_ENTITIES_BATCH = 50  # 批次查詢最大實體數
HISTORY_DEFAULT_HOURS = 24  # 預設查詢時數

# Camera settings
CAMERA_CACHE_TTL = 10.0  # seconds - snapshot cache time-to-live
CAMERA_SNAPSHOT_TIMEOUT = 10.0  # seconds - timeout for fetching snapshots
CAMERA_STREAM_TIMEOUT = 300.0  # seconds - timeout for streaming (5 minutes)
CAMERA_STREAM_CHUNK_SIZE = 8192  # bytes - chunk size for streaming
CAMERA_MAX_CACHE_SIZE = 50  # maximum number of cached snapshots

# HLS streaming settings
HLS_SEGMENT_DURATION = 6.0  # seconds - target duration for HLS segments
HLS_PART_DURATION = 1.0  # seconds - part duration for LL-HLS
HLS_IDLE_TIMEOUT = 300.0  # seconds - timeout before stopping idle HLS stream
HLS_MAX_SEGMENTS = 5  # maximum number of segments in playlist
HLS_STREAM_START_TIMEOUT = 10.0  # seconds - timeout waiting for stream to start

# Stream types
STREAM_TYPE_MJPEG = "mjpeg"
STREAM_TYPE_HLS = "hls"

# Numeric formatting configuration
# 基礎配置：attribute/device_class -> decimal places
NUMERIC_PRECISION_CONFIG = {
    "voltage": 2,  # 電壓：220.12V
    "current": 3,  # 電流：0.456A (預設安培)
    "power": 2,  # 功率：100.99W
    "energy": 2,  # 能量：1.23kWh
    "active_power": 2,  # 有效功率：100.99W
    "reactive_power": 2,  # 無效功率：50.12VAR
    "apparent_power": 2,  # 視在功率：111.80VA
    "power_factor": 3,  # 功率因數：0.905
    "frequency": 2,  # 頻率：50.00Hz
    "temperature": 1,  # 溫度：25.5°C
    "humidity": 1,  # 濕度：65.5%
    "battery": 0,  # 電池：85%
    "illuminance": 0,  # 照度：500lx
    "pressure": 1,  # 氣壓：1013.2hPa
    "co2": 0,  # CO2：450ppm
    "pm25": 1,  # PM2.5：12.5
    "pm10": 1,  # PM10：25.5
}

# 根據單位調整小數點位數：(attribute/device_class, unit) -> decimal places
UNIT_SPECIFIC_PRECISION_CONFIG = {
    ("current", "mA"): 1,  # 毫安培：456.5mA
    ("current", "A"): 3,  # 安培：0.456A
    ("voltage", "mV"): 0,  # 毫伏特：1234mV
    ("voltage", "V"): 2,  # 伏特：220.12V
    ("power", "mW"): 0,  # 毫瓦：1234mW
    ("power", "W"): 2,  # 瓦特：100.99W
    ("power", "kW"): 3,  # 千瓦：1.234kW
    ("energy", "Wh"): 1,  # 瓦時：123.4Wh
    ("energy", "kWh"): 3,  # 千瓦時：1.234kWh
}

# Heartbeat
HEARTBEAT_INTERVAL = 60  # seconds

# Default icons by domain
# 當實體沒有自定義圖標時使用的默認圖標
DEFAULT_DOMAIN_ICONS: dict[str, str] = {
    "switch": "mdi:toggle-switch-outline",  # 開關：使用輪廓版本更清爽
    "light": "mdi:lightbulb-outline",  # 燈光：輪廓版本更通用
    "camera": "mdi:camera",  # 相機：保持原樣
    "sensor": "mdi:gauge",  # 感測器：儀表更能代表數據讀取
    "binary_sensor": "mdi:radiobox-marked",  # 二元感測器：單選框表示開/關狀態
    "cover": "mdi:window-shutter",  # 窗簾：保持原樣
    "climate": "mdi:thermostat",  # 空調：保持原樣
    "fan": "mdi:fan",  # 風扇：保持原樣
    "lock": "mdi:lock",  # 鎖：保持原樣
    "scene": "mdi:palette",  # 場景：保持原樣
    "script": "mdi:script-text",  # 腳本：保持原樣
    "automation": "mdi:robot",  # 自動化：保持原樣
    "input_boolean": "mdi:checkbox-marked-outline",  # 輸入布林值：核取框輪廓版本
    "input_button": "mdi:gesture-tap-button",  # 輸入按鈕：保持原樣
    "input_number": "mdi:numeric",  # 輸入數字：數字符號更直觀
    "input_select": "mdi:format-list-bulleted",  # 輸入選擇：保持原樣
    "input_text": "mdi:form-textbox",  # 輸入文字：保持原樣
    "button": "mdi:button-pointer",  # 按鈕：使用更明確的按鈕圖標
}
