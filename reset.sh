#!/bin/sh
#
# Home Assistant 重置腳本
# 此腳本會將 Home Assistant 重置為全新安裝狀態
#

set -e

CONFIG_DIR="${CONFIG_DIR:-/config}"

if [ ! -d "$CONFIG_DIR" ] && [ -d "/workspace/integration/config" ]; then
    CONFIG_DIR="/workspace/integration/config"
fi

echo "======================================================"
echo "Home Assistant 完全重置腳本"
echo "======================================================"
echo ""
echo "⚠️  警告：此操作將刪除以下內容："
echo "  - 所有實體、裝置、區域註冊表"
echo "  - 所有標籤、使用者帳號、授權資料"
echo "  - 歷史資料庫"
echo "  - 所有日誌"
echo "  - 雲端設定"
echo ""
echo "✓ 保留的內容："
echo "  - configuration.yaml, automations.yaml 等配置文件"
echo "  - custom_components/ (自訂整合)"
echo "  - blueprints/ (藍圖)"
echo ""

# 檢查是否在互動模式
if [ -t 0 ]; then
    printf "確定要繼續嗎？(yes/no): "
    read -r CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "已取消操作"
        exit 0
    fi
fi

echo ""
echo "開始重置..."
echo ""

# 刪除 .storage 目錄
if [ -d "$CONFIG_DIR/.storage" ]; then
    echo "  [1/6] 刪除 .storage/ (註冊表、狀態)..."
    rm -rf "$CONFIG_DIR/.storage"
else
    echo "  [1/6] .storage/ 不存在，跳過"
fi

# 刪除資料庫
if [ -f "$CONFIG_DIR/home-assistant_v2.db" ]; then
    echo "  [2/6] 刪除 home-assistant_v2.db (歷史資料庫)..."
    rm -f "$CONFIG_DIR/home-assistant_v2.db"
    rm -f "$CONFIG_DIR/home-assistant_v2.db-shm"
    rm -f "$CONFIG_DIR/home-assistant_v2.db-wal"
else
    echo "  [2/6] 資料庫不存在，跳過"
fi

# 刪除版本文件
if [ -f "$CONFIG_DIR/.HA_VERSION" ]; then
    echo "  [3/6] 刪除 .HA_VERSION..."
    rm -f "$CONFIG_DIR/.HA_VERSION"
else
    echo "  [3/6] .HA_VERSION 不存在，跳過"
fi

# 刪除鎖文件
echo "  [4/6] 刪除鎖文件..."
rm -f "$CONFIG_DIR/.ha_run.lock"

# 刪除日誌
echo "  [5/6] 刪除日誌文件..."
rm -f "$CONFIG_DIR/home-assistant.log"*

# 刪除雲端設定
if [ -d "$CONFIG_DIR/.cloud" ]; then
    echo "  [6/6] 刪除 .cloud/ (雲端設定)..."
    rm -rf "$CONFIG_DIR/.cloud"
else
    echo "  [6/6] .cloud/ 不存在，跳過"
fi

# 刪除其他可能的狀態文件
echo "  [7/7] 清理其他狀態文件..."
rm -rf "$CONFIG_DIR/.uuid"
rm -rf "$CONFIG_DIR/deps"
rm -rf "$CONFIG_DIR/tts"
rm -f "$CONFIG_DIR"/*.db-journal
rm -f "$CONFIG_DIR"/*.db-shm
rm -f "$CONFIG_DIR"/*.db-wal

echo ""
echo "======================================================"
echo "✅ Home Assistant 已重置為全新狀態！"
echo "======================================================"
echo ""
echo "⚠️  重要：確保 Home Assistant 完全停止後再啟動"
echo ""
echo "下一步："
echo "  1. 停止 Home Assistant (如果正在運行)"
echo "  2. 重新啟動 Home Assistant"
echo "  3. 訪問 http://your-ha-ip:8123"
echo "  4. 應該會看到初始設定頁面（創建管理員帳號）"
echo "  5. 完成設定後，創建 'smartly' 標籤"
echo "  6. 將標籤套用到需要控制的實體"
echo ""
echo "💡 提示：如果沒有進入初始設定流程，請確保："
echo "  - Home Assistant 已完全停止"
echo "  - 清除瀏覽器快取或使用無痕模式"
echo "  - 檢查是否有 .storage/onboarding 文件被重新創建"
echo ""
echo "保留的配置文件："
ls -1 "$CONFIG_DIR"/*.yaml 2>/dev/null || echo "  (無)"
echo ""
