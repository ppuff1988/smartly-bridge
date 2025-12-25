#!/usr/bin/env python3
"""Update Smartly Bridge webhook URL in Home Assistant config entry."""

import asyncio
import json
import sys
from pathlib import Path


async def update_webhook_url(new_url: str = "http://host.docker.internal:8080/webhook/ha-event"):
    """Update the webhook URL in the config entry."""
    
    # Path to Home Assistant config entries
    config_dir = Path("/config")
    core_config = config_dir / ".storage" / "core.config_entries"
    
    if not core_config.exists():
        print(f"❌ Config entries file not found: {core_config}")
        print("💡 確保您在 Home Assistant 容器內運行此腳本")
        return False
    
    print(f"📂 讀取配置: {core_config}")
    
    # Read current config
    with open(core_config, "r") as f:
        config_data = json.load(f)
    
    # Find Smartly Bridge entry
    found = False
    for entry in config_data.get("data", {}).get("entries", []):
        if entry.get("domain") == "smartly_bridge":
            old_url = entry.get("data", {}).get("webhook_url", "")
            print(f"\n🔍 找到 Smartly Bridge 整合:")
            print(f"   Instance ID: {entry.get('data', {}).get('instance_id')}")
            print(f"   舊 Webhook URL: {old_url}")
            print(f"   新 Webhook URL: {new_url}")
            
            # Update webhook URL
            entry["data"]["webhook_url"] = new_url
            found = True
            print("   ✅ 已更新配置")
    
    if not found:
        print("\n❌ 未找到 Smartly Bridge 整合")
        print("💡 請先在 Home Assistant UI 中設定整合")
        return False
    
    # Backup original
    backup_path = config_dir / ".storage" / "core.config_entries.backup"
    print(f"\n💾 備份原始配置到: {backup_path}")
    with open(backup_path, "w") as f:
        json.dump(config_data, f, indent=2)
    
    # Write updated config
    print(f"💾 寫入更新後的配置")
    with open(core_config, "w") as f:
        json.dump(config_data, f, indent=2)
    
    print("\n✅ 配置已更新！")
    print("\n⚠️  重要：請重新啟動 Home Assistant 以套用更改")
    print("   或在 UI 中：開發者工具 → YAML → 重新載入所有 YAML 配置")
    
    return True


def main():
    """Main function."""
    # Default URL
    default_url = "http://host.docker.internal:8080/webhook/ha-event"
    
    # Allow custom URL from command line
    new_url = sys.argv[1] if len(sys.argv) > 1 else default_url
    
    print("🔧 Smartly Bridge Webhook URL 更新工具")
    print("=" * 60)
    
    success = asyncio.run(update_webhook_url(new_url))
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
