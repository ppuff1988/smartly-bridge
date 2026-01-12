#!/bin/bash
# 套用 GitHub Branch Protection Rulesets
# 使用方式: ./apply-rulesets.sh [OWNER/REPO]

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 取得 repository 資訊
if [ -z "$1" ]; then
    # 自動偵測 repository
    REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
    if [ -z "$REPO" ]; then
        echo -e "${RED}❌ 無法偵測 repository，請提供 OWNER/REPO 參數${NC}"
        echo "使用方式: $0 OWNER/REPO"
        exit 1
    fi
else
    REPO=$1
fi

echo -e "${BLUE}🔍 目標 Repository: ${REPO}${NC}"
echo ""

# 檢查是否有權限
echo -e "${YELLOW}📋 檢查權限...${NC}"
PERMISSIONS=$(gh api "/repos/${REPO}" --jq '.permissions' 2>/dev/null || echo "")
if [ -z "$PERMISSIONS" ]; then
    echo -e "${RED}❌ 無法存取 repository，請確認：${NC}"
    echo "   1. Repository 名稱正確"
    echo "   2. 已使用 'gh auth login' 登入"
    echo "   3. 擁有 repository 的 admin 權限"
    exit 1
fi

ADMIN=$(echo $PERMISSIONS | grep -o '"admin":true' || echo "")
if [ -z "$ADMIN" ]; then
    echo -e "${RED}❌ 需要 repository admin 權限才能設定分支保護規則${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 權限驗證通過${NC}"
echo ""

# 列出現有規則集
echo -e "${YELLOW}📋 現有的規則集：${NC}"
EXISTING_RULESETS=$(gh api "/repos/${REPO}/rulesets" 2>/dev/null || echo "[]")
echo "$EXISTING_RULESETS" | jq -r '.[] | "  - ID: \(.id) | Name: \(.name) | Status: \(.enforcement)"' 2>/dev/null || echo "  無現有規則集"
echo ""

# 確認是否繼續
echo -e "${YELLOW}⚠️  即將套用以下規則集：${NC}"
echo "  1. Main Branch Protection (嚴格)"
echo "  2. Develop Branch Protection (中等)"
echo ""
read -p "是否繼續？ (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}已取消操作${NC}"
    exit 0
fi
echo ""

# 檢查 JSON 檔案
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MAIN_JSON="${SCRIPT_DIR}/main-branch-protection.json"
DEV_JSON="${SCRIPT_DIR}/develop-branch-protection.json"

if [ ! -f "$MAIN_JSON" ]; then
    echo -e "${RED}❌ 找不到 main-branch-protection.json${NC}"
    exit 1
fi

if [ ! -f "$DEV_JSON" ]; then
    echo -e "${RED}❌ 找不到 develop-branch-protection.json${NC}"
    exit 1
fi

# 函式：套用或更新規則集
apply_or_update_ruleset() {
    local NAME=$1
    local JSON_FILE=$2
    
    echo -e "${BLUE}🚀 套用 ${NAME}...${NC}"
    
    # 檢查是否已存在同名規則集
    EXISTING_ID=$(echo "$EXISTING_RULESETS" | jq -r ".[] | select(.name==\"${NAME}\") | .id" 2>/dev/null)
    
    if [ -n "$EXISTING_ID" ]; then
        echo -e "${YELLOW}ℹ️  發現現有規則集 (ID: ${EXISTING_ID})，執行更新...${NC}"
        RESULT=$(gh api \
          --method PUT \
          -H "Accept: application/vnd.github+json" \
          -H "X-GitHub-Api-Version: 2022-11-28" \
          "/repos/${REPO}/rulesets/${EXISTING_ID}" \
          --input "$JSON_FILE" 2>&1)
        
        if echo "$RESULT" | grep -q "errors\|failed"; then
            echo -e "${RED}❌ 更新失敗${NC}"
            echo "$RESULT"
            return 1
        else
            echo -e "${GREEN}✅ ${NAME} 已更新 (ID: ${EXISTING_ID})${NC}"
            return 0
        fi
    else
        RESULT=$(gh api \
          --method POST \
          -H "Accept: application/vnd.github+json" \
          -H "X-GitHub-Api-Version: 2022-11-28" \
          "/repos/${REPO}/rulesets" \
          --input "$JSON_FILE" 2>&1)
        
        if echo "$RESULT" | grep -q "errors\|failed"; then
            echo -e "${RED}❌ 建立失敗${NC}"
            echo "$RESULT"
            return 1
        else
            NEW_ID=$(echo "$RESULT" | jq -r '.id' 2>/dev/null || echo "unknown")
            echo -e "${GREEN}✅ ${NAME} 已建立 (ID: ${NEW_ID})${NC}"
            return 0
        fi
    fi
}

# 套用 Main Branch Protection
apply_or_update_ruleset "Main Branch Protection" "$MAIN_JSON"
echo ""

# 套用 Develop Branch Protection
apply_or_update_ruleset "Develop Branch Protection" "$DEV_JSON"
echo ""

# 顯示最終結果
echo -e "${GREEN}🎉 分支保護規則套用完成！${NC}"
echo ""
echo -e "${BLUE}📋 驗證設定：${NC}"
echo "  gh api /repos/${REPO}/rulesets | jq '.[] | {id, name, enforcement}'"
echo ""
echo -e "${BLUE}🌐 Web UI：${NC}"
echo "  https://github.com/${REPO}/settings/rules"
echo ""
echo -e "${YELLOW}⚠️  下一步：${NC}"
echo "  1. 前往 Web UI 確認規則設定正確"
echo "  2. 測試 PR 流程確保所有 CI 檢查正常"
echo "  3. 通知團隊成員新的分支保護規則"
echo ""
