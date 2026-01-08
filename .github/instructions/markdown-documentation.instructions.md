---
applyTo: '**/*.md'
description: 'Markdown 文檔的命名規範、內容要求、組織結構與最佳實作指南。確保文檔系統保持清晰、一致且易於維護。'
---

# Markdown 文檔規範指南

## 你的任務

作為 GitHub Copilot，你負責協助創建、編輯和組織專案中的 Markdown 文檔。你必須遵循本指南的規範，確保文檔系統保持清晰、一致且專業。

## 核心原則

### 📏 三大規範支柱

1. **命名規範** - 清晰、一致、簡潔的檔案命名
2. **位置規則** - 根據文檔類型放置在正確的目錄
3. **內容要求** - 結構完整、連結正確、易於維護

---

## 1. 命名規範

### 📜 命名規則清單

| 位置 | 規則 | 範例 |
|------|------|------|
| **根目錄核心文檔** | 大寫 + 底線 | `README.md`, `CHANGELOG.md` |
| **docs/ 所有文檔** | kebab-case | `api-basics.md`, `security-audit.md` |
| **docs/ 索引頁面** | `README.md` | `docs/README.md`, `docs/control/README.md` |
| **.github/instructions/** | kebab-case.instructions.md | `git-commit.instructions.md` |
| **scripts/ 說明文檔** | `README.md` | `scripts/manual_tests/README.md` |

⚠️ **重要：docs/ 目錄下唯一例外是 `README.md` 索引頁面，其他所有文檔必須使用 kebab-case！**

### 1.1 根目錄核心文檔

**規則**：使用**全大寫 + 底線**命名

```
✅ 正確範例：
README.md
CHANGELOG.md
CONTRIBUTING.md
SECURITY.md
LICENSE.md

❌ 錯誤範例：
Readme.md
change-log.md
Contributing.MD
security_policy.md
```

**適用文檔**：
- `README.md` - 專案主頁
- `CHANGELOG.md` - 版本變更記錄
- `CONTRIBUTING.md` - 貢獻指南
- `SECURITY.md` - 安全政策
- `LICENSE.md` - 授權條款
- `CODE_OF_CONDUCT.md` - 行為準則

### 1.2 其他所有文檔

**規則**：使用 **kebab-case**（小寫 + 連字號）

```
✅ 正確範例：
trust-proxy.md
security-audit.md
api-basics.md
code-examples.md
device-types.md

❌ 錯誤範例：
TrustProxy.md
Security_Audit.md
API_Basics.md
codeExamples.md
DeviceTypes.MD
```

### 1.3 避免的命名模式

❌ **冗餘後綴**（已經從目錄結構可知）
```
❌ SECURITY_AUDIT_REPORT.md  → ✅ security-audit.md
❌ TRUST_PROXY_IMPLEMENTATION.md  → ✅ trust-proxy.md
❌ API_DOCUMENTATION.md  → ✅ api.md
```

❌ **過長的檔案名稱**
```
❌ home-assistant-integration-development-guide.md
✅ ha-integration-guide.md
```

❌ **底線分隔**（僅根目錄核心文檔使用）
```
❌ api_reference.md  → ✅ api-reference.md
❌ test_guide.md  → ✅ test-guide.md
```

### 1.4 特殊情況

**索引頁面**：使用大寫（視為目錄的核心文檔）
```
✅ docs/control/README.md
✅ docs/development/README.md
✅ scripts/manual_tests/README.md
```

⚠️ **重要：重定向頁面也必須使用 kebab-case**
```
✅ docs/control-examples.md  # 重定向頁面
❌ docs/CONTROL_EXAMPLES.md  # 錯誤！不可使用大寫
```

**指導文件**（.github/instructions/）
```
✅ git-commit.instructions.md
✅ python-testing.instructions.md
✅ markdown-documentation.instructions.md
```

---

## 2. 位置規則

### 2.1 目錄結構與用途

```
專案根目錄/
├── *.md                          # 核心專案文檔（4-6 個）
│
├── docs/                         # 文檔中心
│   ├── *.md                      # API 文檔、指南
│   ├── control/                  # 專題文檔（如 API 控制）
│   └── development/              # 技術深度文檔
│
├── scripts/
│   └── manual_tests/
│       └── README.md             # 腳本使用說明
│
└── .github/
    └── instructions/             # 開發規範文檔
        └── *.instructions.md
```

### 2.2 放置位置決策樹

#### 問題 1：是否為核心專案文檔？

```
核心文檔定義：
- 專案概覽（README）
- 變更記錄（CHANGELOG）
- 貢獻指南（CONTRIBUTING）
- 安全政策（SECURITY）
- 授權條款（LICENSE）
```

**YES** → 放在**根目錄**，使用大寫命名  
**NO** → 繼續問題 2

#### 問題 2：是否為用戶文檔？

```
用戶文檔定義：
- API 使用說明
- 功能指南
- 配置說明
- 故障排除
```

**YES** → 放在 **docs/** 目錄  
**NO** → 繼續問題 3

#### 問題 3：是否為技術深度文檔？

```
技術文檔定義：
- 實作細節
- 架構說明
- 技術決策記錄
- 開發者指南
```

**YES** → 放在 **docs/development/**  
**NO** → 繼續問題 4

#### 問題 4：是否為開發規範？

```
規範文檔定義：
- 編碼風格
- 測試規範
- Git 規範
- 流程指南
```

**YES** → 放在 **.github/instructions/**  
**NO** → 考慮是否真的需要這個文檔

### 2.3 位置範例對照

| 文檔類型 | 範例 | 正確位置 | 錯誤位置 |
|---------|------|---------|---------|
| 專案主頁 | README.md | `/` | `/docs/` |
| API 指南 | api-basics.md | `/docs/control/` | `/` |
| 技術文檔 | trust-proxy.md | `/docs/development/` | `/` |
| 安全審計 | security-audit.md | `/docs/` | `/` |
| 測試規範 | python-testing.instructions.md | `/.github/instructions/` | `/docs/` |
| 腳本說明 | README.md | `/scripts/manual_tests/` | `/` |

---

## 3. 內容要求

### 3.1 必要元素

每個文檔都應包含：

```markdown
# 文檔標題

> **文檔類型** | 更新日期：YYYY-MM-DD

[簡短描述 1-2 句話說明文檔內容和用途]

## 目錄（可選，長文檔需要）

- [章節 1](#章節-1)
- [章節 2](#章節-2)

## 章節 1

內容...

## 相關文檔（推薦）

- [相關文檔 1](相對路徑)
- [相關文檔 2](相對路徑)
```

### 3.2 技術文檔額外要求

```markdown
# 標題

> **技術文檔** | 更新日期：2026-01-08

## 背景

為什麼需要這個功能/文檔？

## 技術細節

具體實作方式、架構說明

## 使用指南

如何配置、使用、測試

## 安全考量

相關的安全注意事項

## 範例

實際使用範例或程式碼

## 相關文檔

- [相關技術文檔](路徑)
```

### 3.3 索引文檔規範

每個子目錄都應該有 `README.md` 作為索引：

```markdown
# 目錄名稱

> **索引頁面** | 說明本目錄的內容和組織

## 📚 文檔列表

### [文檔名稱](檔案名.md)
**簡短說明**

詳細說明該文檔的內容和適用場景。

## 🔗 相關資源

- [外部連結或其他目錄]

## 📝 貢獻

如何向本目錄新增文檔的說明。
```

---

## 4. 連結規範

### 4.1 使用相對路徑

✅ **正確**：
```markdown
[API 文檔](../docs/api.md)
[安全政策](../../SECURITY.md)
[控制範例](./control/code-examples.md)
```

❌ **錯誤**：
```markdown
[API 文檔](/workspace/docs/api.md)  # 絕對路徑
[安全政策](https://github.com/user/repo/blob/main/SECURITY.md)  # 完整 URL
```

### 4.2 連結格式

```markdown
# 內部文檔連結
[文字說明](相對路徑/檔案.md)

# 特定章節連結
[章節連結](檔案.md#章節標題)

# 同檔案章節連結
[跳轉到章節](#章節標題)

# 外部連結
[外部資源](https://example.com)
```

### 4.3 連結驗證規則

新增或修改文檔時，必須：

1. ✅ 確認所有內部連結指向存在的文件
2. ✅ 使用正確的相對路徑
3. ✅ 更新索引文檔（README.md）
4. ✅ 驗證章節錨點正確

---

## 5. 文檔組織最佳實作

### 5.1 保持根目錄簡潔

**規則**：根目錄只放 4-6 個核心文檔

```
✅ 良好的根目錄：
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
└── SECURITY.md

❌ 混亂的根目錄：
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── API_GUIDE.md              # 應該在 docs/
├── TRUST_PROXY_IMPL.md       # 應該在 docs/development/
├── test_script.py            # 應該在 scripts/
└── SECURITY_AUDIT.md         # 應該在 docs/
```

### 5.2 建立清晰的文檔層級

```
Level 0（根目錄）
├── README.md                  ← 包含完整文檔導覽

Level 1（主要分類）
├── docs/
│   └── README.md              ← API 文檔總覽

Level 2（專題分類）
├── docs/control/
│   └── README.md              ← 控制 API 索引

Level 3（具體文檔）
└── docs/control/api-basics.md
```

### 5.3 索引頁面責任

每個 `README.md` 必須：

- ✅ 列出該目錄所有重要文檔
- ✅ 提供每個文檔的簡短說明
- ✅ 說明適用場景或使用時機
- ✅ 提供快速連結到相關資源

---

## 6. 特殊文檔類型

### 6.1 重定向頁面

當內容已遷移到其他位置時，保留簡短的重定向頁面：

```markdown
# 文檔標題

> ⚠️ **本文檔已遷移**
> 
> 完整內容已移至 **[新位置](新路徑/)** 目錄。

## 快速導覽

| 文檔 | 說明 |
|------|------|
| [文檔 1](路徑) | 說明 |
| [文檔 2](路徑) | 說明 |

請直接前往 **[新位置](路徑)** 查看完整文檔。
```

**範例**：[docs/control-examples.md](../../docs/control-examples.md)

**命名規範**：重定向頁面也必須使用 **kebab-case**，不可使用大寫。

### 6.2 開發規範文檔（.instructions.md）

```markdown
---
applyTo: '適用的文件模式'
description: '簡短描述'
---

# 規範標題

## 你的任務

作為 GitHub Copilot，你的任務是...

## 核心概念

說明為什麼需要這個規範...

## 規範內容

具體的規則和要求...

## 範例

✅ 正確範例
❌ 錯誤範例

## 工具整合

相關工具的配置...
```

### 6.3 技術決策記錄（ADR）

如需記錄重要技術決策，可在 `docs/development/` 下創建：

```markdown
# ADR-001: 決策標題

**狀態**：已採用 / 已棄用 / 草案  
**日期**：2026-01-08  
**決策者**：團隊名稱

## 背景

說明需要做決策的情境...

## 決策

我們決定...

## 理由

選擇這個方案的原因：
1. 原因 1
2. 原因 2

## 替代方案

考慮過但未採用的方案：
- 方案 A：缺點...
- 方案 B：缺點...

## 影響

這個決策的影響範圍...

## 相關文檔

- [實作指南](路徑)
```

---

## 7. 工作流程

### 7.1 創建新文檔

```
1. 確定文檔類型 → 決定放置位置
2. 選擇適當的命名格式
3. 使用文檔模板建立基本結構
4. 撰寫內容
5. 更新相關索引頁面（README.md）
6. 更新主索引（根目錄 README.md 的文檔導覽）
7. 驗證所有連結
```

### 7.2 修改現有文檔

```
1. 確認修改不影響其他文檔的連結
2. 更新「更新日期」
3. 如結構變更，更新目錄
4. 驗證相關連結仍然有效
```

### 7.3 移動或重新命名文檔

```
1. 檢查所有引用此文檔的連結
2. 移動/重新命名文件
3. 更新所有引用連結
4. 更新所有相關索引頁面
5. 考慮是否需要保留重定向頁面
```

---

## 8. 檢查清單

### 新增文檔前

- [ ] 確認是否已有類似文檔
- [ ] 確定正確的放置位置
- [ ] 選擇適當的檔案名稱
- [ ] 準備必要的內容元素

### 文檔完成後

- [ ] 標題清晰明確
- [ ] 包含更新日期
- [ ] 內容結構完整
- [ ] 所有連結使用相對路徑
- [ ] 所有內部連結已驗證
- [ ] 更新相關索引頁面
- [ ] 更新主文檔導覽（README.md）

### 移動文檔後

- [ ] 文件已移至新位置
- [ ] 所有引用已更新
- [ ] 索引頁面已更新
- [ ] 考慮是否需要重定向頁面

---

## 9. 常見問題

### Q: 何時應該拆分文檔？

**A**: 當單一文檔超過 500 行或包含多個獨立主題時，考慮拆分。

範例：
```
❌ 單一大文檔：
docs/api-complete-guide.md (2000 行)

✅ 拆分後：
docs/control/
├── README.md
├── api-basics.md
├── device-types.md
├── code-examples.md
└── troubleshooting.md
```

### Q: 是否應該保留舊文檔？

**A**: 視情況而定：

- ✅ 內容已遷移 → 保留簡短重定向頁面
- ✅ 文檔已過時但有歷史價值 → 移至 `docs/archive/`
- ❌ 內容完全不再需要 → 刪除並更新所有引用

### Q: 如何處理多語言文檔？

**A**: 使用語言代碼後綴：

```
✅ 推薦方式：
docs/
├── api-guide.md           # 預設語言（英文）
├── api-guide.zh-TW.md     # 繁體中文
└── api-guide.ja.md        # 日文

❌ 不推薦：
docs/
├── en/
│   └── api-guide.md
└── zh-TW/
    └── api-guide.md
```

### Q: 技術文檔和用戶文檔如何區分？

**A**: 判斷標準：

```
用戶文檔（docs/）：
- 如何使用 API
- 配置指南
- 故障排除
→ 目標：幫助用戶使用產品

技術文檔（docs/development/）：
- 實作細節
- 架構決策
- 開發指南
→ 目標：幫助開發者理解和改進系統
```

---

## 10. Copilot 協助項目

作為 GitHub Copilot，我可以協助你：

### 文檔創建
- 根據類型選擇適當的模板
- 生成符合規範的檔案名稱
- 建立完整的文檔結構

### 文檔整理
- 評估文檔是否放在正確位置
- 建議重新命名不符合規範的文件
- 建立目錄索引頁面

### 連結管理
- 驗證所有內部連結
- 修正損壞的連結
- 更新文檔移動後的引用

### 內容優化
- 改善文檔結構
- 補充缺少的章節
- 添加適當的範例

---

## 附錄：快速參考

### 命名速查表

| 位置 | 格式 | 範例 |
|------|------|------|
| 根目錄核心文檔 | `UPPERCASE_WITH_UNDERSCORE.md` | `README.md`, `SECURITY.md` |
| 所有其他文檔 | `kebab-case.md` | `api-basics.md`, `trust-proxy.md` |
| 指導文件 | `kebab-case.instructions.md` | `git-commit.instructions.md` |

### 位置速查表

| 文檔類型 | 位置 |
|---------|------|
| 專案核心 | `/` |
| API 文檔 | `/docs/` |
| API 專題 | `/docs/control/`, `/docs/sync/` 等 |
| 技術文檔 | `/docs/development/` |
| 開發規範 | `/.github/instructions/` |
| 腳本說明 | `/scripts/*/README.md` |

### 文件模板連結

- [標準文檔模板](#31-必要元素)
- [技術文檔模板](#32-技術文檔額外要求)
- [索引頁面模板](#33-索引文檔規範)
- [重定向頁面模板](#61-重定向頁面)

---

## 版本記錄

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| 1.0.0 | 2026-01-08 | 初始版本，基於專案文檔整理經驗建立 |

---

**製作**：Smartly Bridge Team  
**維護**：文檔管理規範  
**最後更新**：2026-01-08
