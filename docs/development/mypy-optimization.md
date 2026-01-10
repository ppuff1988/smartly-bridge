# MyPy 效能優化指南

## 問題描述

MyPy 類型檢查執行緩慢，每次檢查需要 10-30 秒，影響開發效率。

## 根本原因

1. **`follow_imports = "normal"`**：追蹤所有導入模組，包括 Home Assistant 龐大的程式碼庫
2. **未啟用增量快取**：每次都重新分析所有檔案
3. **分析第三方套件**：對 `homeassistant`, `aiohttp` 等大型套件進行完整分析

## 優化方案

### 1. 修改 `pyproject.toml` 配置

```toml
[tool.mypy]
python_version = "3.13"
show_error_codes = true
follow_imports = "skip"          # ⚡ 不追蹤第三方套件
ignore_missing_imports = true
cache_dir = ".mypy_cache"        # ⚡ 啟用快取
incremental = true               # ⚡ 增量分析
sqlite_cache = true              # ⚡ 使用 SQLite 快取

[[tool.mypy.overrides]]
module = "homeassistant.*"
follow_imports = "skip"          # 跳過 HA 程式碼

[[tool.mypy.overrides]]
module = "aiohttp.*"
follow_imports = "skip"
```

### 2. 使用 `--cache-fine-grained` 選項

```bash
mypy custom_components/ --cache-fine-grained
```

## 效能提升

- **優化前**：10-30 秒
- **優化後**：~3 秒
- **提升**：約 3-10 倍

## 快取管理

### 清除快取（當遇到奇怪錯誤時）

```bash
rm -rf .mypy_cache/
```

### 快取位置

- `.mypy_cache/3.13/` - Python 3.13 的快取檔案

## follow_imports 選項說明

| 選項 | 行為 | 適用場景 |
|------|------|---------|
| `normal` | 完整分析所有導入 | 小型專案、庫開發 |
| `silent` | 導入但不報告錯誤 | 中型專案 |
| `skip` | 跳過不分析 | 大型專案、第三方依賴多 |
| `error` | 遇到缺失型別就報錯 | 嚴格型別檢查 |

## 權衡

### ✅ 優點
- 大幅提升執行速度
- 減少 CI/CD 時間
- 改善開發體驗

### ⚠️ 注意事項
- 不會檢查第三方套件的型別錯誤
- 依賴第三方套件的型別存根(stub)正確性
- 本專案場景下影響極小（我們主要檢查自己的程式碼）

## 進一步優化

### 1. 使用 MyPy Daemon (dmypy)

```bash
# 啟動 daemon
dmypy start

# 檢查程式碼（秒級回應）
dmypy check custom_components/

# 停止 daemon
dmypy stop
```

### 2. 只檢查變更的檔案

```bash
# 使用 git 找出變更的檔案
git diff --name-only --diff-filter=ACM "*.py" | xargs mypy
```

### 3. 平行處理（大型專案）

```bash
mypy custom_components/ --cache-fine-grained --parallel
```

## 最佳實作

1. **開發時**：使用 `dmypy` 或 IDE 整合（如 VS Code 的 Pylance）
2. **CI/CD**：使用優化後的設定檔 + `--cache-fine-grained`
3. **定期**：偶爾用 `follow_imports = "normal"` 做完整檢查
4. **快取**：將 `.mypy_cache/` 加入 CI 快取以加速

## 監控效能

```bash
# 測試執行時間
time mypy custom_components/

# 查看快取使用情況
du -sh .mypy_cache/

# 詳細效能分析
mypy custom_components/ --verbose --cache-fine-grained
```

## 相關文件

- [MyPy 官方效能指南](https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports)
- [快取原理說明](https://mypy.readthedocs.io/en/stable/running_mypy.html#incremental)
- [follow_imports 文件](https://mypy.readthedocs.io/en/stable/running_mypy.html#following-imports)

## 故障排除

### 問題：快取損壞

**症狀**：出現奇怪的型別錯誤
**解決**：`rm -rf .mypy_cache/`

### 問題：仍然很慢

**檢查**：
```bash
# 確認設定已生效
mypy --config-file pyproject.toml --show-config

# 確認使用快取
ls -lah .mypy_cache/3.13/
```

### 問題：型別檢查變鬆了

**說明**：這是正常的，我們跳過了第三方套件的分析。如需嚴格檢查，可以：
```bash
# 定期執行完整檢查
mypy custom_components/ --follow-imports=normal
```
