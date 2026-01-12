#!/bin/bash
# 快速設定完整的分支保護與 Merge Methods
# 使用方式: ./quick-setup.sh [OWNER/REPO]

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 取得 repository 資訊
if [ -z "$1" ]; then
    REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
    if [ -z "$REPO" ]; then
        echo -e "${RED}❌ 無法偵測 repository${NC}"
        exit 1
    fi
else
    REPO=$1
fi

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  ${CYAN}GitHub Repository Protection 快速設定${NC}      ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Repository: ${REPO}${NC}"
echo ""

# 步驟 1: 套用分支保護規則
echo -e "${CYAN}步驟 1/2: 套用分支保護規則${NC}"
echo -e "${BLUE}─────────────────────────────────────────────${NC}"
./apply-rulesets.sh "$REPO"
echo ""

# 步驟 2: 設定 Merge Methods（僅 Squash）
echo -e "${CYAN}步驟 2/2: 設定 Merge Methods${NC}"
echo -e "${BLUE}─────────────────────────────────────────────${NC}"
./configure-merge-methods.sh "$REPO" squash
echo ""

# 顯示最終結果
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}  ${CYAN}✨ 設定完成！${NC}                                  ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}📋 已套用的設定：${NC}"
echo ""
echo -e "${GREEN}✓${NC} Main 分支保護（最嚴格）"
echo -e "  - 防止刪除與強制推送"
echo -e "  - 要求線性歷史"
echo -e "  - 必須 1 人審查 PR"
echo -e "  - 必須通過所有 CI 檢查"
echo ""
echo -e "${GREEN}✓${NC} Develop 分支保護（中等）"
echo -e "  - 防止刪除與強制推送"
echo -e "  - 必須 1 人審查 PR"
echo -e "  - 必須通過基礎 CI 檢查"
echo ""
echo -e "${GREEN}✓${NC} 僅允許 Squash Merge"
echo -e "  - 所有 PR 合併時自動壓縮成單一 commit"
echo -e "  - 保持分支歷史簡潔"
echo -e "  - 已合併分支自動刪除"
echo ""

echo -e "${YELLOW}🔍 驗證設定：${NC}"
echo ""
echo -e "  ${BLUE}分支保護：${NC}"
echo "  ./list-rulesets.sh"
echo ""
echo -e "  ${BLUE}Merge Methods：${NC}"
echo "  gh api /repos/${REPO} | jq '{allow_merge_commit, allow_squash_merge, allow_rebase_merge}'"
echo ""

echo -e "${YELLOW}🌐 Web UI：${NC}"
echo "  Branch Protection: https://github.com/${REPO}/settings/rules"
echo "  Merge Methods:     https://github.com/${REPO}/settings"
echo ""

echo -e "${YELLOW}📚 下一步：${NC}"
echo "  1. 前往 Web UI 確認所有設定"
echo "  2. 測試 PR 流程"
echo "  3. 通知團隊成員新規則"
echo ""
