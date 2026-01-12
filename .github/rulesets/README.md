# GitHub Branch Protection Rulesets

本目錄包含專案的分支保護規則配置檔案。

## 📋 規則集說明

### Main Branch Protection (`main-branch-protection.json`)

**適用分支**: `main`  
**嚴格程度**: ⭐⭐⭐⭐⭐ (最高)

保護生產環境分支，確保所有變更都經過嚴格審查和測試。

**規則內容**:
- ✅ 防止刪除分支
- ✅ 禁止強制推送
- ✅ 要求線性歷史（linear history）
- ✅ 必須通過 Pull Request 合併
  - 需要 1 人審查批准
  - 新提交後需重新審查
  - 必須解決所有討論
- ✅ 必須通過所有 CI 檢查
  - Lint Code (代碼格式)
  - Run Tests (測試)
  - Validate PR (PR 驗證)
  - Check Coverage (覆蓋率)
  - 必須基於最新 main 分支
- ✅ 要求 commit 簽名
- ⚠️ Repository admin 可繞過（緊急修復用）

### Develop Branch Protection (`develop-branch-protection.json`)

**適用分支**: `develop`  
**嚴格程度**: ⭐⭐⭐ (中等)

保護開發分支，平衡安全性與開發效率。

**規則內容**:
- ✅ 防止刪除分支
- ✅ 禁止強制推送
- ✅ 必須通過 Pull Request 合併
  - 需要 1 人審查批准
  - 新提交不強制重新審查
  - 不強制解決所有討論
- ✅ 必須通過基礎 CI 檢查
  - Lint Code (代碼格式)
  - Run Tests (測試)
  - 不要求基於最新分支
- ❌ 不要求線性歷史（允許 merge commits）
- ❌ 不要求 commit 簽名
- ❌ 無繞過權限

## 🚀 套用規則集

### 🎯 快速設定（一鍵完成）

```bash
# 自動套用分支保護 + Squash Merge 設定
cd .github/rulesets
./quick-setup.sh ppuff1988/smartly-bridge
```

這個腳本會自動完成：
- ✅ 建立 Main 與 Develop 分支保護規則
- ✅ 設定僅允許 Squash Merge
- ✅ 啟用自動刪除已合併分支

### 方法 1: 使用個別腳本

```bash
# 1. 套用分支保護規則
./apply-rulesets.sh ppuff1988/smartly-bridge

# 2. 設定 Merge Methods（僅 Squash）
./configure-merge-methods.sh ppuff1988/smartly-bridge squash

# 3. 查看設定結果
./list-rulesets.sh ppuff1988/smartly-bridge
```

### 方法 2: 使用 GitHub CLI（手動）

```bash
# 檢查現有規則集
gh api /repos/OWNER/REPO/rulesets

# 建立 main 分支保護規則
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  /repos/OWNER/REPO/rulesets \
  --input .github/rulesets/main-branch-protection.json

# 建立 develop 分支保護規則  
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  /repos/OWNER/REPO/rulesets \
  --input .github/rulesets/develop-branch-protection.json

# 設定僅允許 Squash Merge
gh api \
  --method PATCH \
  -H "Accept: application/vnd.github+json" \
  /repos/OWNER/REPO \
  -f allow_merge_commit=false \
  -f allow_squash_merge=true \
  -f allow_rebase_merge=false \
  -f delete_branch_on_merge=true
### 方法 3: 使用 GitHub Web UI

1. 前往 **Settings** → **Rules** → **Rulesets**
2. 點擊 **New ruleset** → **New branch ruleset**
3. 參考 JSON 檔案內容手動設定
4. 點擊 **Create** 儲存
5. 前往 **Settings** → **General** → **Pull Requests**
6. 取消勾選 "Allow merge commits" 和 "Allow rebase merging"
7. 保留勾選 "Allow squash merging"
8. 勾選 "Automatically delete head branches"

### 方法 4: 更新現有規則集

```bash
# 更新規則集（替換 RULESET_ID）
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/OWNER/REPO/rulesets/RULESET_ID \
  --input .github/rulesets/main-branch-protection.json
```

## 🔍 驗證規則生效

```bash
# 列出所有規則集
gh api /repos/OWNER/REPO/rulesets | jq '.[] | {id, name, enforcement, target}'

# 查看特定規則集詳情
gh api /repos/OWNER/REPO/rulesets/RULESET_ID | jq

# 測試保護（應該失敗）
git checkout main
git push --force  # 應該被 GitHub 拒絕
```

## 📝 CI 檢查對應

本專案的 CI workflows:

| Workflow | Job Name | 對應檢查 |
|----------|----------|----------|
| `ci.yml` | `lint` | Lint Code |
| `ci.yml` | `test` | Run Tests |
| `ci.yml` | `coverage` | Check Coverage |
| `pr-checks.yml` | `pr-validation` | Validate PR |

## 🛠️ 自訂規則

### 調整審查人數

修改 `required_approving_review_count`:
```json
"parameters": {
  "required_approving_review_count": 2  // 改為需要 2 人審查
}
```

### 新增/移除 CI 檢查

修改 `required_status_checks` 陣列:
```json
"required_status_checks": [
  {
    "context": "Your New Check Name",
    "integration_id": null
  }
]
```

### 調整繞過權限

```json
"bypass_actors": [
  {
    "actor_id": 1,           // 1=Organization admin, 5=Repository admin
    "actor_type": "RepositoryRole",
    "bypass_mode": "always"  // always 或 pull_request
  }
]
```

## ⚠️ 注意事項

1. **首次啟用**: 建議先在 `develop` 分支測試，確認流程順暢
2. **CI 穩定性**: 確保 CI 檢查穩定後再啟用 `required_status_checks`
3. **團隊溝通**: 提前通知團隊新規則，準備遷移指南
4. **緊急修復**: Repository admin 可臨時停用規則處理緊急狀況

## 🔄 分支策略與 Merge 方法

### 分支流程

```
main (生產)
  ↑
  PR (嚴格審查) → Squash Merge
  ↑
develop (開發)
  ↑
  PR (基礎審查) → Squash Merge
  ↑
feature/* (功能分支)
```

### 🔀 Merge 方法：僅 Squash Merge

**已設定**:
- ✅ Allow squash merge: `true`
- ❌ Allow merge commit: `false`
- ❌ Allow rebase merge: `false`
- ✅ Automatically delete head branches: `true`

**優勢**:
- 📝 每個 PR 只產生一個 commit
- 🎯 符合 Conventional Commits 規範
- 📊 保持 main/develop 分支歷史簡潔清晰
- 🧹 已合併分支自動清理

**Squash Merge 流程**:
```bash
# Feature 分支的多個 commits：
feat: add user service
fix: handle edge case
docs: update comments
test: add unit tests

# Squash 後變成單一 commit：
feat(user): 新增使用者服務功能 (#123)
```

## 📚 相關文檔

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets)
- [Conventional Commits](https://www.conventionalcommits.org/)
- 專案內部: `.github/instructions/git-commit.instructions.md`

## 🆘 故障排除

### 問題: 推送被拒絕

**解決方案**: 使用 PR 流程
```bash
git checkout -b feature/my-feature
git push -u origin feature/my-feature
gh pr create --base main
```

### 問題: CI 檢查失敗

**解決方案**: 本地先測試
```bash
# 執行所有檢查
./run-ci-tests.sh

# 單獨執行
black --check .
pytest
```

### 問題: 需要緊急修復

**解決方案**: 臨時停用規則（需要 admin 權限）
```bash
gh api \
  --method PATCH \
  /repos/OWNER/REPO/rulesets/RULESET_ID \
  -f enforcement=disabled

# 修復後重新啟用
gh api \
  --method PATCH \
  /repos/OWNER/REPO/rulesets/RULESET_ID \
  -f enforcement=active
```

---

**維護者**: GitHub Copilot  
**最後更新**: 2026-01-12  
**版本**: 1.0.0
