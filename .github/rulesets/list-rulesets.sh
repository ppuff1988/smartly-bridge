#!/bin/bash
# 列出並顯示 GitHub Branch Protection Rulesets
# 使用方式: ./list-rulesets.sh [OWNER/REPO]

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

echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  GitHub Branch Protection Rulesets${NC}"
echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Repository: ${REPO}${NC}"
echo ""

# 取得所有規則集
RULESETS=$(gh api "/repos/${REPO}/rulesets" 2>/dev/null || echo "[]")

if [ "$RULESETS" == "[]" ]; then
    echo -e "${YELLOW}⚠️  沒有設定任何規則集${NC}"
    echo ""
    echo "建議執行: ./apply-rulesets.sh"
    exit 0
fi

# 計算規則集數量
RULESET_COUNT=$(echo "$RULESETS" | jq 'length')
echo -e "${GREEN}找到 ${RULESET_COUNT} 個規則集${NC}"
echo ""

# 遍歷每個規則集
echo "$RULESETS" | jq -c '.[]' | while read ruleset; do
    ID=$(echo "$ruleset" | jq -r '.id')
    NAME=$(echo "$ruleset" | jq -r '.name')
    ENFORCEMENT=$(echo "$ruleset" | jq -r '.enforcement')
    TARGET=$(echo "$ruleset" | jq -r '.target')
    
    # 設定狀態顏色
    if [ "$ENFORCEMENT" == "active" ]; then
        STATUS="${GREEN}✅ Active${NC}"
    elif [ "$ENFORCEMENT" == "disabled" ]; then
        STATUS="${RED}❌ Disabled${NC}"
    else
        STATUS="${YELLOW}⚠️  ${ENFORCEMENT}${NC}"
    fi
    
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}📋 ${NAME}${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ID:         ${ID}"
    echo -e "  Status:     ${STATUS}"
    echo -e "  Target:     ${TARGET}"
    
    # 取得詳細資訊
    DETAIL=$(gh api "/repos/${REPO}/rulesets/${ID}" 2>/dev/null)
    
    # 顯示適用分支
    BRANCHES=$(echo "$DETAIL" | jq -r '.conditions.ref_name.include[]' 2>/dev/null | sed 's/refs\/heads\///')
    if [ ! -z "$BRANCHES" ]; then
        echo -e "  Branches:   ${YELLOW}${BRANCHES}${NC}"
    fi
    
    # 顯示規則
    echo -e "  Rules:"
    echo "$DETAIL" | jq -r '.rules[] | .type' 2>/dev/null | while read rule_type; do
        case $rule_type in
            "deletion")
                echo -e "    ${GREEN}✓${NC} 防止刪除分支"
                ;;
            "non_fast_forward")
                echo -e "    ${GREEN}✓${NC} 禁止強制推送"
                ;;
            "required_linear_history")
                echo -e "    ${GREEN}✓${NC} 要求線性歷史"
                ;;
            "pull_request")
                APPROVALS=$(echo "$DETAIL" | jq -r '.rules[] | select(.type=="pull_request") | .parameters.required_approving_review_count' 2>/dev/null)
                echo -e "    ${GREEN}✓${NC} 必須通過 PR (需要 ${APPROVALS} 人審查)"
                ;;
            "required_status_checks")
                echo -e "    ${GREEN}✓${NC} 必須通過 CI 檢查:"
                echo "$DETAIL" | jq -r '.rules[] | select(.type=="required_status_checks") | .parameters.required_status_checks[].context' 2>/dev/null | while read check; do
                    echo -e "      - ${check}"
                done
                ;;
            "required_signatures")
                echo -e "    ${GREEN}✓${NC} 要求 commit 簽名"
                ;;
            *)
                echo -e "    ${GREEN}✓${NC} ${rule_type}"
                ;;
        esac
    done
    
    # 顯示繞過角色
    BYPASS=$(echo "$DETAIL" | jq -r '.bypass_actors[]?' 2>/dev/null)
    if [ ! -z "$BYPASS" ]; then
        echo -e "  Bypass:"
        echo "$DETAIL" | jq -r '.bypass_actors[] | "    - \(.actor_type): \(.bypass_mode)"' 2>/dev/null
    fi
    
    echo ""
done

echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${CYAN}更多資訊：${NC}"
echo "  Web UI: https://github.com/${REPO}/settings/rules"
echo "  API:    gh api /repos/${REPO}/rulesets"
echo -e "${BLUE}════════════════════════════════════════════════${NC}"
