#!/bin/bash
# 設定 Repository Merge Methods
# 使用方式: ./configure-merge-methods.sh [OWNER/REPO] [merge_method]
# merge_method: squash (僅 squash) | all (全部允許) | rebase (僅 rebase) | merge (僅 merge)

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

# 取得設定類型（預設為 squash only）
MERGE_TYPE=${2:-squash}

echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  配置 Repository Merge Methods${NC}"
echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Repository: ${REPO}${NC}"
echo ""

# 檢查權限
echo -e "${YELLOW}📋 檢查權限...${NC}"
PERMISSIONS=$(gh api "/repos/${REPO}" --jq '.permissions' 2>/dev/null || echo "")
if [ -z "$PERMISSIONS" ]; then
    echo -e "${RED}❌ 無法存取 repository${NC}"
    exit 1
fi

ADMIN=$(echo $PERMISSIONS | grep -o '"admin":true' || echo "")
if [ -z "$ADMIN" ]; then
    echo -e "${RED}❌ 需要 repository admin 權限${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 權限驗證通過${NC}"
echo ""

# 顯示當前設定
echo -e "${YELLOW}📋 當前 Merge Methods 設定：${NC}"
CURRENT=$(gh api "/repos/${REPO}" 2>/dev/null)
echo "$CURRENT" | jq -r '"  Allow merge commit:    \(.allow_merge_commit)"'
echo "$CURRENT" | jq -r '"  Allow squash merge:    \(.allow_squash_merge)"'
echo "$CURRENT" | jq -r '"  Allow rebase merge:    \(.allow_rebase_merge)"'
echo "$CURRENT" | jq -r '"  Allow auto merge:      \(.allow_auto_merge)"'
echo "$CURRENT" | jq -r '"  Delete branch on merge: \(.delete_branch_on_merge)"'
echo ""

# 根據類型設定參數
case $MERGE_TYPE in
    squash)
        ALLOW_MERGE=false
        ALLOW_SQUASH=true
        ALLOW_REBASE=false
        DESC="僅允許 Squash Merge"
        ;;
    rebase)
        ALLOW_MERGE=false
        ALLOW_SQUASH=false
        ALLOW_REBASE=true
        DESC="僅允許 Rebase Merge"
        ;;
    merge)
        ALLOW_MERGE=true
        ALLOW_SQUASH=false
        ALLOW_REBASE=false
        DESC="僅允許 Merge Commit"
        ;;
    all)
        ALLOW_MERGE=true
        ALLOW_SQUASH=true
        ALLOW_REBASE=true
        DESC="允許所有 Merge 方法"
        ;;
    *)
        echo -e "${RED}❌ 不支援的設定類型: ${MERGE_TYPE}${NC}"
        echo "支援的類型: squash, rebase, merge, all"
        exit 1
        ;;
esac

echo -e "${YELLOW}⚠️  即將套用設定：${NC}"
echo -e "  ${CYAN}${DESC}${NC}"
echo ""
echo "  Allow merge commit:     ${ALLOW_MERGE}"
echo "  Allow squash merge:     ${ALLOW_SQUASH}"
echo "  Allow rebase merge:     ${ALLOW_REBASE}"
echo "  Delete branch on merge: true (自動刪除已合併分支)"
echo ""
read -p "是否繼續？ (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}已取消操作${NC}"
    exit 0
fi
echo ""

# 套用設定
echo -e "${BLUE}🚀 套用 Merge Methods 設定...${NC}"
RESULT=$(gh api \
  --method PATCH \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "/repos/${REPO}" \
  -f allow_merge_commit=${ALLOW_MERGE} \
  -f allow_squash_merge=${ALLOW_SQUASH} \
  -f allow_rebase_merge=${ALLOW_REBASE} \
  -f delete_branch_on_merge=true \
  2>&1)

if echo "$RESULT" | grep -q "errors\|failed"; then
    echo -e "${RED}❌ 設定失敗${NC}"
    echo "$RESULT"
    exit 1
fi

echo -e "${GREEN}✅ Merge Methods 設定完成！${NC}"
echo ""

# 顯示更新後的設定
echo -e "${YELLOW}📋 更新後的設定：${NC}"
UPDATED=$(gh api "/repos/${REPO}" 2>/dev/null)
echo "$UPDATED" | jq -r '"  Allow merge commit:    \(.allow_merge_commit)"'
echo "$UPDATED" | jq -r '"  Allow squash merge:    \(.allow_squash_merge)"'
echo "$UPDATED" | jq -r '"  Allow rebase merge:    \(.allow_rebase_merge)"'
echo "$UPDATED" | jq -r '"  Delete branch on merge: \(.delete_branch_on_merge)"'
echo ""

# 顯示效果說明
echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${CYAN}📝 設定說明${NC}"
echo -e "${BLUE}════════════════════════════════════════════════${NC}"

case $MERGE_TYPE in
    squash)
        echo -e "${GREEN}✓${NC} PR 合併時所有 commits 會被壓縮成單一 commit"
        echo -e "${GREEN}✓${NC} 保持 main/develop 分支歷史簡潔"
        echo -e "${GREEN}✓${NC} 符合 Conventional Commits 規範"
        echo -e "${YELLOW}!${NC} 功能分支的 commit 歷史會遺失"
        ;;
    rebase)
        echo -e "${GREEN}✓${NC} 保留所有原始 commits"
        echo -e "${GREEN}✓${NC} 線性歷史，無 merge commits"
        echo -e "${YELLOW}!${NC} 需要解決 rebase 衝突"
        ;;
    merge)
        echo -e "${GREEN}✓${NC} 保留完整分支歷史"
        echo -e "${GREEN}✓${NC} 產生 merge commit"
        echo -e "${YELLOW}!${NC} 歷史較複雜，有分支結構"
        ;;
    all)
        echo -e "${GREEN}✓${NC} 開發者可自由選擇 merge 方法"
        echo -e "${YELLOW}!${NC} 歷史可能不一致"
        ;;
esac

echo ""
echo -e "${BLUE}🌐 Web UI：${NC}"
echo "  https://github.com/${REPO}/settings"
echo -e "${BLUE}════════════════════════════════════════════════${NC}"
