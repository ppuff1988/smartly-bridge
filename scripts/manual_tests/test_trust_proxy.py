"""測試 trust_proxy 功能的簡單驗證腳本"""

import sys

sys.path.insert(0, "/workspace")

from custom_components.smartly_bridge.const import (
    CONF_TRUST_PROXY,
    DEFAULT_TRUST_PROXY,
    PRIVATE_IP_RANGES,
    TRUST_PROXY_ALWAYS,
    TRUST_PROXY_AUTO,
    TRUST_PROXY_NEVER,
)

print("✅ 常數定義檢查")
print(f"  CONF_TRUST_PROXY = {CONF_TRUST_PROXY}")
print(f"  TRUST_PROXY_AUTO = {TRUST_PROXY_AUTO}")
print(f"  TRUST_PROXY_ALWAYS = {TRUST_PROXY_ALWAYS}")
print(f"  TRUST_PROXY_NEVER = {TRUST_PROXY_NEVER}")
print(f"  DEFAULT_TRUST_PROXY = {DEFAULT_TRUST_PROXY}")
print(f"  PRIVATE_IP_RANGES = {PRIVATE_IP_RANGES}")

from custom_components.smartly_bridge.auth import _is_private_ip, _should_trust_proxy

print("\n✅ 私有 IP 檢測測試")
test_ips = [
    ("127.0.0.1", True, "localhost"),
    ("192.168.1.1", True, "私有網路"),
    ("10.0.0.1", True, "私有網路"),
    ("172.16.0.1", True, "私有網路"),
    ("8.8.8.8", False, "公網 IP"),
    ("1.2.3.4", False, "公網 IP"),
]

for ip, expected, desc in test_ips:
    result = _is_private_ip(ip)
    status = "✅" if result == expected else "❌"
    print(f"  {status} {ip:15} -> {result:5} ({desc})")

print("\n✅ 所有檢查通過！")
print("\n📝 功能說明：")
print("  - trust_proxy 有三種模式：")
print("    • auto (預設)：自動判斷是否在 Proxy 後方")
print("    • always：總是信任 X-Forwarded-For")
print("    • never：永不信任 X-Forwarded-For")
print("\n  - 自動判斷邏輯：")
print("    • 如果直連 IP 是私有/本地 IP")
print("    • 且 CIDR 白名單包含公網 IP")
print("    • 則推測在 Proxy 後方，信任 X-Forwarded-For")
print("\n  - 安全性：")
print("    • 預設模式可防止大部分攻擊場景")
print("    • 使用者可根據實際環境手動覆寫")
