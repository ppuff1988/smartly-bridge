# 自動化 Release 流程說明

## 🤖 自動化配置

本專案已配置 **Semantic Release**，會根據 Conventional Commits 自動：
- 🔢 決定版本號 (major/minor/patch)
- 📝 生成 CHANGELOG.md
- 📦 更新 manifest.json 版本
- 🏷️ 建立 Git tag
- 🚀 發布 GitHub Release

## 📋 版本規則

根據 commit type 自動決定版本號：

| Commit Type | 版本影響 | 範例 |
|-------------|---------|------|
| `feat: ...` | **Minor** (1.0.0 → 1.1.0) | 新增功能 |
| `fix: ...` | **Patch** (1.0.0 → 1.0.1) | 錯誤修正 |
| `perf: ...` | **Patch** (1.0.0 → 1.0.1) | 效能優化 |
| `refactor: ...` | **Patch** (1.0.0 → 1.0.1) | 程式碼重構 |
| `BREAKING CHANGE` | **Major** (1.0.0 → 2.0.0) | 不相容變更 |
| `docs`, `style`, `test`, `ci`, `chore` | 不發布 | 不影響版本 |

## 🚀 Release 觸發流程

### 自動觸發（推薦）

1. **在 `dev` 分支開發並遵循 Conventional Commits**
   ```bash
   git commit -m "feat(device): 新增裝置批次控制功能"
   git commit -m "fix(mqtt): 修正連線逾時問題"
   ```

2. **推送到 `dev` 分支**
   ```bash
   git push origin dev
   ```

3. **建立 Pull Request 合併到 `main`**
   - PR 標題也應遵循 Conventional Commits
   - 審查通過後合併

4. **自動執行 Release**
   - ✅ 合併到 `main` 後自動觸發
   - ✅ 分析所有新的 commits
   - ✅ 決定版本號並更新檔案
   - ✅ 建立 GitHub Release

### 範例流程

```bash
# 在 dev 分支開發
git checkout dev
git pull origin dev

# 完成功能開發
git add .
git commit -m "feat(acl): 實作實體標籤存取控制"
git push origin dev

# 建立 PR 到 main
# 合併後自動 release！
```

## 📊 版本號決定邏輯

假設目前版本是 `1.0.0`：

### 範例 1：只有 feat commits
```
feat(device): 新增裝置控制
feat(api): 新增批次 API
```
→ 發布 **1.1.0** (Minor)

### 範例 2：有 fix 和 feat
```
fix(mqtt): 修正連線問題
feat(auth): 新增 OAuth 支援
```
→ 發布 **1.1.0** (Minor，以最高等級為準)

### 範例 3：只有 fix
```
fix(api): 修正回應格式
fix(db): 修正查詢錯誤
```
→ 發布 **1.0.1** (Patch)

### 範例 4：有 BREAKING CHANGE
```
feat(api)!: 重構 API 格式

BREAKING CHANGE: API 回傳格式改變
```
→ 發布 **2.0.0** (Major)

### 範例 5：只有 docs/chore
```
docs(readme): 更新文檔
chore(ci): 更新 workflow
```
→ **不發布** (沒有程式碼變更)

## 🛠️ 手動測試

測試版本更新腳本：

```bash
# 測試腳本
python scripts/update_manifest_version.py 1.2.0

# 檢查結果
cat custom_components/smartly_bridge/manifest.json | grep version
```

## 📝 CHANGELOG 格式

自動生成的 CHANGELOG 格式：

```markdown
## [1.1.0] - 2025-12-22

### ✨ 新增功能 (Features)
- **acl**: 實作實體標籤存取控制 ([abc123](commit-link))
- **device**: 新增裝置批次控制功能 ([def456](commit-link))

### 🐛 錯誤修正 (Bug Fixes)
- **mqtt**: 修正連線逾時問題 ([ghi789](commit-link))

### ⚡ 效能優化 (Performance)
- **query**: 優化資料庫查詢效能 ([jkl012](commit-link))
```

## 🔍 檢查 Release 狀態

### 查看 GitHub Actions
```
GitHub → Actions → Auto Release workflow
```

### 查看已發布的版本
```
GitHub → Releases
```

### 本地查看版本
```bash
# 查看 manifest.json
cat custom_components/smartly_bridge/manifest.json | grep version

# 查看最新 tag
git tag -l | sort -V | tail -1

# 查看 CHANGELOG
head -50 CHANGELOG.md
```

## ⚠️ 注意事項

1. **只有合併到 `main` 才會觸發 release**
   - `dev` 分支的 push 不會觸發
   - 其他分支的 push 也不會觸發

2. **Commit 訊息必須遵循 Conventional Commits**
   - 否則可能不會觸發版本更新
   - 或版本號計算錯誤

3. **每次合併到 `main` 都會分析所有新 commits**
   - 如果沒有 `feat`/`fix`/`perf` 等，不會發布
   - 有效的 commits 會累積決定版本號

4. **BREAKING CHANGE 必須謹慎使用**
   - 會觸發 major 版本升級
   - 建議在 PR 中明確說明影響

## 🎯 最佳實踐

1. **定期合併 dev 到 main**
   - 累積多個功能一起發布
   - 避免頻繁的小版本

2. **PR 標題也遵循規範**
   - Squash merge 時會使用 PR 標題
   - 確保 PR 標題清晰準確

3. **審查 commit 歷史**
   - 合併前檢查 commit 訊息
   - 必要時使用 rebase 整理

4. **測試後再合併**
   - CI 測試通過
   - 功能驗證完成
   - 文檔已更新

## 🔧 故障排除

### Release 沒有觸發
- 檢查是否合併到 `main` 分支
- 檢查 commit 訊息格式
- 查看 GitHub Actions 日誌

### 版本號不正確
- 檢查 commit type 是否正確
- 檢查是否有 BREAKING CHANGE
- 查看 `.releaserc.json` 配置

### manifest.json 更新失敗
- 檢查腳本權限
- 檢查 Python 環境
- 手動測試腳本

## 📚 相關資源

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Semantic Release](https://semantic-release.gitbook.io/)
- [Keep a Changelog](https://keepachangelog.com/)
