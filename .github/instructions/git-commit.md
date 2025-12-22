---
applyTo: '*'
description: 'Git Commit 最佳實作指南，採用 Conventional Commits 規範並使用繁體中文。涵蓋 commit 訊息格式、類型定義、範圍設定、Breaking Changes 處理，以及與 CI/CD 工具整合的完整指引。'
---

# Git Commit 最佳實作（Conventional Commits）

## 你的任務

作為 GitHub Copilot，你是 Git Commit 規範的專家。你的任務是協助開發者建立清晰、一致且具意義的 commit 訊息，遵循 Conventional Commits 規範並使用繁體中文。你必須優先考慮最佳實作、確保團隊協作效率，並提供可執行的詳細指引。

## 核心概念：為什麼要規範 Commit？

良好的 Commit 規範帶來以下優勢：

- **可追溯性：** Commit 歷史是專案的時光機，快速找到「何時」、「為何」引入變更或錯誤
- **協作效率：** 清晰訊息降低程式碼審查負擔，團隊成員快速理解意圖
- **自動化基礎：** 支援版本控制、Changelog 生成、CI/CD 流程自動化
- **文件化：** Commit 歷史是最真實的專案演進文件
- **語意化版本：** 支援自動判斷版本號升級類型（major / minor / patch）

## Conventional Commits 格式規範

### **1. 完整格式結構**

```text
<type>(<scope>): <subject>

<body>

<footer>
```

- **type** 和 **subject** 是必要的
- **scope、body、footer** 視情況選用
- type 後冒號與 subject 間必須有空格
- body 和 footer 前必須空一行

### **2. 最基本常用格式**

```text
type(scope): 簡短描述
```

### **3. 實際範例（繁體中文）**

```text
feat(auth): 新增使用者登入驗證機制
fix(api): 修正裝置列表查詢時的空值錯誤
docs(readme): 更新安裝指南的相依套件版本
```

**Copilot 指引：**
- 建議開發者在每次 commit 前思考：「這個變更的主要目的是什麼？」
- 使用繁體中文撰寫 subject，確保團隊成員能快速理解
- 簡單變更使用基本格式；複雜變更需要增加 body 說明
- Commit 訊息是寫給「未來的自己和團隊成員」看的

## Type 類型定義與最佳實作

### **1. 核心 Type 類型**

| Type | 用途說明 | 版本影響 | 使用時機 |
|------|---------|---------|---------|
| `feat` | 新增功能 | ✅ minor | 新增使用者可見的功能特性 |
| `fix` | 修正錯誤 | ✅ patch | 修復影響使用者的錯誤 |
| `docs` | 文件變更 | ❌ | 僅修改文件、註解、README |
| `style` | 程式碼格式 | ❌ | 不影響程式邏輯的格式調整 |
| `refactor` | 程式碼重構 | ❌ | 重構但不改變功能 |
| `perf` | 效能優化 | ✅ patch | 提升效能但不改變功能 |
| `test` | 測試程式碼 | ❌ | 新增或修改測試 |
| `build` | 建置系統 | ❌ | 修改建置腳本、相依套件 |
| `ci` | CI/CD 設定 | ❌ | 修改 CI/CD 設定檔 |
| `chore` | 雜項維護 | ❌ | 不影響程式碼的維護工作 |
| `revert` | 回復變更 | 視情況 | 回復之前的 commit |

**範例：**
```text
feat(device): 新增溫濕度感測器支援
fix(mqtt): 修正連線逾時未重試問題
docs(api): 補充 REST API 使用範例
perf(query): 優化資料庫查詢效能
build(deps): 升級 pytest 到 8.0
ci(github): 新增自動發布工作流程
```

**Copilot 指引：**
- `feat` vs `fix`：問自己「這是新增功能還是修正既有功能的錯誤？」
- `refactor` vs `perf`：主要目的是提升效能用 `perf`；改善程式碼品質用 `refactor`
- `chore` vs `build`：修改建置腳本或相依套件用 `build`；其他雜項用 `chore`
- 避免濫用 `chore`：如果有更明確的類型（如 `docs`、`test`），應使用更具體的 type

### **2. Breaking Changes 標記**

任何破壞向後相容性的變更都必須明確標記，觸發 major 版本升級。

**什麼算 Breaking Change：**
- API 介面變更
- 設定格式改變
- 移除功能
- 行為變更

**標記方式：**

```text
# 方式一：Type 後加驚嘆號
feat(api)!: 重構裝置同步 API 回傳格式

# 方式二：Footer 加 BREAKING CHANGE
feat(api): 重構裝置同步 API

BREAKING CHANGE: 裝置同步 API 回傳格式從陣列改為物件，需更新前端解析邏輯
```

**Copilot 指引：**
- Breaking Change 不一定是壞事，但必須謹慎處理
- 建議在 body 中提供遷移指南或相容性說明
- 對於公開 API 或函式庫，Breaking Change 應經過團隊討論和審查
- 考慮使用棄用（deprecation）策略，先標記為即將移除，下個版本再實際移除

## Scope（範圍）定義與管理

### **1. Scope 的目的**

Scope 指出變更影響的模組、元件或子系統，幫助讀者快速定位變更範圍。

### **2. 常見 Scope 範例**

**Home Assistant 整合專案：**
```text
auth, device, ha-integration, mqtt, api, config, ui, audit, acl, push
```

**一般 Web 應用程式：**
```text
frontend, backend, database, router, middleware, validation
```

**基礎設施與工具：**
```text
docker, ci, deps, scripts
```

### **3. Scope 使用範例**

✅ **良好範例**
```text
feat(auth): 新增 OAuth2 認證支援
fix(mqtt): 修正斷線後自動重連失敗問題
refactor(device): 重構裝置狀態管理邏輯
test(acl): 新增角色權限測試案例
docs(api): 補充 REST API 錯誤碼說明
```

❌ **不良範例**
```text
feat: 新增功能                    # 缺少 scope，無法快速定位
fix(all): 修正很多錯誤            # scope 過於籠統
feat(auth.py): 新增登入功能      # scope 過細，不應使用檔案名稱
fix(stuff): 修正一些東西         # scope 不明確
```

### **4. 跨模組變更處理**

```text
# 選項一：使用最主要的 scope
feat(api): 新增裝置查詢端點並更新文件

# 選項二：使用逗號分隔（不建議超過 2 個）
feat(api,device): 新增裝置查詢功能

# 選項三：拆分成多個 commit（推薦）
feat(device): 新增裝置查詢服務
feat(api): 新增裝置查詢端點
docs(api): 更新 API 文件
```

**Copilot 指引：**
- 建議團隊建立並維護 scope 清單，可放在專案 CONTRIBUTING.md 中
- 如果難以決定 scope，可能表示這個 commit 做了太多事，應該拆分
- 在程式碼審查時，檢查 scope 是否準確反映變更範圍
- 使用 commitlint 等工具強制執行 scope 規範

## Subject（標題）撰寫最佳實作

### **1. Subject 撰寫原則**

- **長度限制：** 英文不超過 50 字元，繁體中文約 25 字
- **動詞優先：** 使用命令式動詞開頭（新增、修正、更新、移除、重構、優化）
- **現在式：** 描述「這個 commit 做什麼」而非「做了什麼」
- **不加句號：** Subject 是標題而非完整句子
- **具體明確：** 避免模糊詞彙如「修正問題」、「更新程式碼」

### **2. Subject 撰寫範例**

✅ **推薦寫法**
```text
feat(user): 新增使用者註冊流程
fix(mqtt): 修正斷線後無法自動重連問題
refactor(api): 重構裝置查詢邏輯提升可讀性
perf(query): 優化大量資料查詢效能
docs(readme): 補充 Docker 部署說明
test(auth): 新增登入失敗重試測試
```

❌ **不良寫法**
```text
feat: 新增了一個功能              # 過於模糊，未說明具體功能
fix: bug fix                     # 完全沒有資訊量
update something                 # 沒有 type，不明確
feat(auth): 修正登入。           # 有句號，且 type 錯誤（應為 fix）
修正錯誤                          # 缺少 type 和 scope
很多改進                          # 完全不符合規範
```

### **3. 繁體中文動詞選擇**

- **新增**（不用「加入」或「添加」）
- **修正**（不用「修復」或「fix」）
- **更新**（用於文件或設定）
- **移除**（不用「刪除」或「刪掉」）
- **重構**（不用「改寫」）
- **優化**（用於效能改善）

**Copilot 指引：**
- 好的 subject 能讓團隊在 `git log --oneline` 中快速掌握專案歷史
- 建議先寫 body，再濃縮成 subject，確保 subject 抓到重點
- 避免在 subject 中包含 ticket 編號（應放在 footer）
- 如果 subject 很難寫得簡短，可能表示 commit 做太多事，應該拆分

## Body（本文）撰寫指南

### **1. 何時需要撰寫 Body**

當以下任一成立時，應撰寫 Body：

- **複雜邏輯：** 涉及演算法改動、架構調整、重要決策
- **行為變更：** 改變既有功能的行為，即使不是 breaking change
- **錯誤修正：** 說明錯誤的原因、影響範圍、修正方式
- **背景脈絡：** 提供相關的 issue、討論、設計文件連結
- **取捨說明：** 解釋為何選擇某種方案而非其他方案

### **2. Body 撰寫最佳實作**

- **說明「為什麼」而非「怎麼做」：** 程式碼已經說明「怎麼做」
- **使用條列式：** 清晰列出要點，易於閱讀
- **保持客觀：** 陳述事實和理由，避免主觀情緒
- **每行不超過 72 字元：** 確保在終端機中易於閱讀

### **3. Body 範例**

#### 範例 1：錯誤修正
```text
fix(device): 修正裝置狀態不同步問題

問題描述：
- WebSocket 重連時未重新訂閱 topic
- 導致 Home Assistant 狀態更新無法送達平台
- 影響範圍：所有使用 MQTT 的裝置

解決方案：
- 在 reconnect 流程中重新註冊所有 subscription
- 新增連線狀態檢查機制
- 添加重連後的狀態同步邏輯

相關 Issue: #123
```

#### 範例 2：功能新增
```text
feat(auth): 新增 JWT Token 自動更新機制

背景：
- 使用者反映經常需要重新登入
- 現有 Token 過期時間為 1 小時，體驗不佳

實作內容：
- 實作 Refresh Token 機制
- Token 過期前 5 分鐘自動更新
- 失敗時自動導向登入頁面

技術選擇：
- 使用 JWT Refresh Token 而非 Session
- 考量到未來的多裝置登入需求
```

#### 範例 3：效能優化
```text
perf(query): 優化裝置列表查詢效能

效能問題：
- 裝置數量超過 1000 時，查詢時間超過 3 秒
- 資料庫 CPU 使用率達 80%

優化措施：
- 新增 device_id 索引
- 實作查詢結果快取（5 分鐘）
- 改用分頁查詢取代一次載入全部

效能改善：
- 查詢時間從 3.2 秒降至 0.3 秒
- 資料庫 CPU 使用率降至 20%
```

**Copilot 指引：**
- 撰寫 body 時想像自己在向三個月後的自己解釋
- 對於修正錯誤的 commit，說明「為什麼會發生錯誤」而非只說「修正了錯誤」
- 提供連結到相關 issue、PR、文件或討論串
- 如果有多種解決方案，說明為何選擇當前方案

## Footer 使用指南

### **1. 常見 Footer 類型**

```text
# Issue 參照
Closes #123
Fixes #456
Resolves #789
Refs #101, #102

# Breaking Change
BREAKING CHANGE: 詳細說明不相容的變更

# 共同作者
Co-authored-by: 張三 <zhang@example.com>

# 審查者
Reviewed-by: 李四 <li@example.com>

# 簽署
Signed-off-by: 王五 <wang@example.com>
```

### **2. 完整 Footer 範例**

```text
feat(api): 新增裝置批次操作 API

實作多裝置同時控制功能，提升操作效率。

- 支援最多 50 個裝置同時操作
- 包含狀態回饋機制
- 失敗時自動重試

Closes #234
Refs #189
Co-authored-by: 開發者 <dev@example.com>
```

## 更新 CHANGELOG.md

### **1. CHANGELOG 格式規範**

本專案遵循 [Keep a Changelog](https://keepachangelog.com/) 格式，基於語意化版本控制。

### **2. 何時更新 CHANGELOG**

在以下情況應更新 CHANGELOG.md：

- **feat：** 新增功能 → 記錄在 `### Added` 區塊
- **fix：** 修正錯誤 → 記錄在 `### Fixed` 區塊
- **BREAKING CHANGE：** 不相容變更 → 記錄在 `### Changed` 並標註 **BREAKING**
- **perf：** 效能優化 → 記錄在 `### Changed`
- **refactor：** 重要的重構 → 記錄在 `### Changed`
- **security：** 安全性修正 → 記錄在 `### Security`
- **deprecated：** 標記即將移除的功能 → 記錄在 `### Deprecated`
- **removed：** 移除功能 → 記錄在 `### Removed`

### **3. CHANGELOG 更新流程**

#### 步驟 1：在 `[Unreleased]` 區塊下新增變更

```markdown
## [Unreleased]

### Added
- 新增使用者批次匯入功能 (#234)
- 支援裝置群組管理

### Fixed
- 修正 MQTT 連線逾時問題 (#456)
```

#### 步驟 2：發布版本時移動到新版本區塊

```markdown
## [Unreleased]

## [1.2.0] - 2025-12-22

### Added
- 新增使用者批次匯入功能 (#234)
- 支援裝置群組管理

### Fixed
- 修正 MQTT 連線逾時問題 (#456)
```

### **4. CHANGELOG 撰寫最佳實作**

✅ **良好範例**
```markdown
### Added
- 新增裝置批次控制 API 端點 (#234)
- 支援 JWT Token 自動更新機制
- 實作查詢結果快取提升效能

### Fixed
- 修正裝置狀態不同步問題 (#123)
- 修正 WebSocket 重連時 subscription 遺失
- 解決大量裝置查詢逾時問題

### Changed
- **BREAKING:** API 回傳格式改為物件結構（遷移指南見 docs/migration-v2.md）
- 優化資料庫查詢效能，查詢時間降低 90%
- 重構認證流程提升可維護性

### Security
- 修正 HMAC 簽章驗證繞過漏洞 (CVE-2025-XXXX)
- 強化 CIDR IP 過濾邏輯
```

❌ **不良範例**
```markdown
### Changed
- 更新一些東西                    # 不具體
- 修正 bug                        # 沒有說明什麼 bug
- 改進效能                        # 沒有量化
- 更新文件 (#123)                 # 文件更新通常不需要記錄在 CHANGELOG
```

### **5. CHANGELOG 與 Commit 的對應**

| Commit Type | CHANGELOG 區塊 | 是否必須記錄 |
|-------------|---------------|-------------|
| `feat` | Added | ✅ 是 |
| `fix` | Fixed | ✅ 是（除非是微小的修正）|
| `perf` | Changed | ✅ 是 |
| `refactor` | Changed | ⚠️ 視影響範圍 |
| `docs` | - | ❌ 否 |
| `style` | - | ❌ 否 |
| `test` | - | ❌ 否 |
| `build` | - | ❌ 否（除非影響使用者）|
| `ci` | - | ❌ 否 |
| `chore` | - | ❌ 否 |
| `security` | Security | ✅ 是 |
| Breaking Change | Changed | ✅ 是（必須標註 BREAKING）|

### **6. CHANGELOG 自動化工具**

#### 使用 Semantic Release 自動生成
```javascript
// .releaserc.js
module.exports = {
  plugins: [
    '@semantic-release/commit-analyzer',
    '@semantic-release/release-notes-generator',
    '@semantic-release/changelog',
    '@semantic-release/github',
    '@semantic-release/git'
  ]
};
```

#### 手動更新 CHANGELOG 的 Git Hook
```bash
# .husky/pre-commit
#!/bin/sh
if git diff --cached --name-only | grep -q "^(feat|fix|perf|security)"; then
  if ! git diff --cached --name-only | grep -q "CHANGELOG.md"; then
    echo "⚠️  警告：您的變更可能需要更新 CHANGELOG.md"
    echo "請確認是否需要在 CHANGELOG.md 的 [Unreleased] 區塊中新增條目"
  fi
fi
```

### **7. CHANGELOG 更新範例完整流程**

#### 場景：新增功能並修正錯誤

**Commit 1:**
```text
feat(device): 新增裝置批次控制功能

Closes #234
```

**Commit 2:**
```text
fix(mqtt): 修正連線逾時未重試問題

Fixes #456
```

**對應 CHANGELOG 更新:**
```markdown
## [Unreleased]

### Added
- 新增裝置批次控制功能，支援最多 50 個裝置同時操作 (#234)

### Fixed
- 修正 MQTT 連線逾時未自動重試問題 (#456)
```

**發布新版本時:**
```markdown
## [Unreleased]

## [1.2.0] - 2025-12-22

### Added
- 新增裝置批次控制功能，支援最多 50 個裝置同時操作 (#234)

### Fixed
- 修正 MQTT 連線逾時未自動重試問題 (#456)

## [1.1.0] - 2025-12-15
...
```

### **8. CHANGELOG 審查清單**

在 Pull Request 審查時，檢查：

- [ ] 所有 `feat` commit 是否已記錄在 CHANGELOG
- [ ] 所有 `fix` commit 是否已記錄在 CHANGELOG
- [ ] Breaking Changes 是否明確標註 **BREAKING**
- [ ] 條目描述是否清晰具體，避免模糊詞彙
- [ ] Issue 或 PR 編號是否正確引用
- [ ] 變更是否放在正確的區塊（Added/Fixed/Changed/etc.）
- [ ] 描述是否面向使用者而非開發者（除非是開發者工具）

**Copilot 指引：**
- CHANGELOG 是面向使用者的文件，使用他們能理解的語言
- 避免過於技術性的描述，除非目標受眾是開發者
- 每個條目應該回答「這個變更對我（使用者）有什麼影響？」
- 建議團隊在 PR 模板中加入「CHANGELOG 已更新」的檢查項
- 使用自動化工具輔助，但仍需人工審查確保品質

## 實務建議與最佳實作

### **1. 原子性 Commit（Atomic Commits）**

每個 commit 應該只做一件事，且該件事應該是完整且可獨立理解的。

❌ **不良範例**
```text
feat: 新增登入功能 + 修正 bug + 更新文件 + 調整 UI
```

✅ **良好範例**（拆分成多個 commit）
```text
feat(auth): 新增使用者登入功能
fix(auth): 修正登入失敗未顯示錯誤訊息
docs(auth): 補充認證流程說明
style(auth): 調整登入頁面排版
```

### **2. Commit 頻率建議**

- **經常 Commit：** 完成一個邏輯單元就 commit
- **本地整理：** 使用 `git rebase -i` 在推送前整理 commit 歷史
- **有意義的單元：** 確保每個 commit 都有意義

### **3. 測試與 Commit**

每個 commit 都應該通過測試（除非是實驗性的分支）。

```bash
# 設定 pre-commit hook
npm install husky commitlint --save-dev

# 或使用 Python
pip install pre-commit commitlint
```

### **4. Commit Message 模板**

建立專案級別的 commit 模板：

```bash
# .gitmessage
type(scope): subject

# 為什麼需要這個變更？

# 這個變更做了什麼？

# 有什麼副作用或注意事項？

# Issue 參照
# Closes #
```

設定使用模板：
```bash
git config commit.template .gitmessage
```

**Copilot 指引：**
- 建議團隊建立 commit 模板，降低撰寫門檻
- commit 是為了幫助未來的自己和團隊，不是應付檢查
- 鼓勵在 PR 中檢視 commit 歷史，確保每個 commit 都有意義
- 對於新成員，提供 commit 範例和 pair programming

## 與 CI/CD 工具整合

### **1. Commitlint 設定**

#### Node.js 專案
```bash
npm install --save-dev @commitlint/cli @commitlint/config-conventional husky

# 初始化 husky
npx husky install

# 新增 commit-msg hook
npx husky add .husky/commit-msg 'npx --no -- commitlint --edit "$1"'
```

#### commitlint.config.js
```javascript
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [2, 'always', [
      'feat', 'fix', 'docs', 'style', 'refactor',
      'perf', 'test', 'build', 'ci', 'chore', 'revert'
    ]],
    'type-case': [2, 'always', 'lower-case'],
    'subject-empty': [2, 'never'],
    'subject-full-stop': [2, 'never', '.'],
    'subject-max-length': [2, 'always', 72],
    'scope-case': [2, 'always', 'lower-case'],
    'body-leading-blank': [2, 'always'],
    'footer-leading-blank': [2, 'always']
  }
};
```

#### Python 專案
```bash
pip install pre-commit

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.13.0
    hooks:
      - id: commitizen
        stages: [commit-msg]
```

### **2. Semantic Release**

```javascript
// .releaserc.js
module.exports = {
  branches: ['main'],
  plugins: [
    '@semantic-release/commit-analyzer',
    '@semantic-release/release-notes-generator',
    '@semantic-release/changelog',
    '@semantic-release/npm',
    '@semantic-release/github',
    '@semantic-release/git'
  ]
};
```

### **3. GitHub Actions 整合**

```yaml
name: Release

on:
  push:
    branches:
      - main

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npx semantic-release
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## 完整範例總覽

```text
feat(user): 新增使用者註冊功能
fix(api): 修正取得裝置清單時的排序錯誤
docs(readme): 補充本地開發環境設定說明
refactor(mqtt): 重構連線管理邏輯提升維護性
perf(query): 優化裝置狀態查詢效能
test(auth): 新增登入流程整合測試
chore(ci): 更新 GitHub Actions 至 Node.js 20
build(deps): 升級 pytest 到 8.0.0
```

### **包含 Body 的範例**

```text
feat(device): 新增裝置批次控制功能

實作同時控制多個裝置的功能，提升使用者操作效率。

- 支援最多 50 個裝置同時操作
- 包含即時狀態回饋
- 失敗時自動重試機制

Closes #234
```

### **Breaking Change 範例**

```text
feat(api)!: 重構裝置同步 API 回傳格式

BREAKING CHANGE: API 回傳格式從陣列改為物件結構

變更前:
```json
[
  {"id": 1, "name": "device1"},
  {"id": 2, "name": "device2"}
]
```

變更後:
```json
{
  "devices": [...],
  "total": 2,
  "page": 1
}
```

遷移指南：請參考 docs/migration-v2.md
```

## 故障排除與常見問題

### **1. Commitlint 檢查失敗**

**問題：** `type must be one of [feat, fix, ...]`
- 確認 type 拼寫正確且為小寫
- 檢查是否使用團隊定義的 type 列表

**問題：** `subject may not be empty`
- 確保冒號後有空格且有 subject
- 格式：`type(scope): subject` 而非 `type(scope):`

### **2. 中文字元長度計算**

```javascript
// commitlint.config.js 調整中文字元限制
'subject-max-length': [2, 'always', 72], // 中文約 24-36 字
```

### **3. Pre-commit Hook 被跳過**

- 在 CI 階段再次檢查 commit 訊息
- 團隊共識不使用 `--no-verify`
- 使用 GitHub Branch Protection 強制要求

### **4. Scope 選擇困難**

- 建立並維護 scope 清單文件
- 從專案目錄結構或架構圖決定
- 如果變更橫跨多個模組，考慮拆分 commit

## 團隊共識與最佳實作總結

### **核心原則**

> **Commit 訊息是寫給「未來的自己和團隊成員」看的，不是應付工具或流程。**

### **實施建議**

1. **循序漸進：** 先從基本格式開始，逐步增加 body 和 footer 的要求
2. **工具輔助：** 使用 commitlint、pre-commit 降低人為錯誤
3. **文件清晰：** 在 CONTRIBUTING.md 明確定義團隊的 commit 規範
4. **定期審查：** 在 PR 審查時檢查 commit 品質，給予建設性回饋
5. **以身作則：** 資深成員應樹立良好範例

### **成功指標**

- ✅ 團隊成員能快速從 commit 歷史理解專案演進
- ✅ Changelog 自動產生且內容完整
- ✅ 版本號自動升級準確無誤
- ✅ 使用 `git bisect` 時能精準定位問題
- ✅ 新成員能快速理解 commit 規範並遵循

### **避免過度規範**

- ❌ 不要為了規範而規範，保持彈性
- ❌ 不要過度細分 type 或 scope，保持簡潔
- ❌ 不要讓工具成為開發阻礙，適時調整設定
- ❌ 不要懲罰性對待不符規範的 commit，提供教育和協助

---

## Copilot 協助項目

作為 GitHub Copilot，我可以協助你：

1. **客製化團隊規範：** 根據專案特性建立適合的 commit 規範
2. **工具設定：** 產生 commitlint、husky、pre-commit 設定檔
3. **CI/CD 整合：** 建立 semantic-release 或 release-please 工作流程
4. **模板建立：** 產生 commit message 模板和 PR 模板
5. **歷史整理：** 協助整理既有 commit 歷史以符合規範
6. **教育訓練：** 提供團隊培訓材料和範例

只需告訴我你的專案類型和特殊需求即可。

---

<!-- End of Git Commit Best Practices Instructions -->

