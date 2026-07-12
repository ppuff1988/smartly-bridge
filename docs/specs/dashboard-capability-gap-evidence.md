# Dashboard Capability Gap Evidence

> Date: 2026-07-13
>
> Branch: `feature/dashboard-capability-gaps`
>
> Worktree: `/home/jordan/Projects/smartly/.worktrees/smartly-bridge-dashboard-capability-gaps`

## Scope

本文件記錄 Smartly Platform 自訂 Dashboard 所需 Bridge capability、state、event、command 與 history contract 的實際證據。規格宣告不等同完成；狀態需由程式碼、測試及代表 fixture 證明。

## Confirmed Gap

### Capability state quality

修正前，API vNext state update 已包含來源 `updated_at`，但沒有通用 `quality`。這使 Platform 無法可靠區分 online、stale、unknown 與 error。

已新增 canonical mapping：

| Source snapshot status | Capability state quality |
|---|---|
| `online` | `good` |
| `offline` | `stale` |
| `error` | `error` |
| missing or other | `unknown` |

證據：

- `tests/test_application_hexagonal.py::test_sync_states_use_case_marks_online_capability_updates_good`
- `tests/test_application_hexagonal.py::test_sync_states_use_case_marks_offline_capability_updates_stale`
- `tests/test_application_hexagonal.py::test_sync_states_use_case_preserves_error_capability_quality`
- current-sync 與 API vNext fixtures 已更新 `quality=good`。

## Verified Existing Capability

### Aqara environment sensor group

去識別化 fixture 證明同一 `source_device_id` 的 Aqara environment siblings 會聚合成一個 logical device，並輸出：

- `temperature`
- `humidity`
- `pressure`
- `battery`
- `signal_quality`
- 每個 capability 自己的 `updated_at`
- online source 的 `quality=good`

證據：

- `tests/test_application_hexagonal.py::test_sync_states_use_case_groups_aqara_environment_capability_updates`

### Aqara D1 and button events

現有 event application tests 已證明品牌／來源 action 會正規化為 canonical `button_event`：

- `single_left` → `event=single_press`, `payload.button=left`
- `left_single` → `event=single_press`, `payload.button=left`
- `1_single` → `event=single_press`, `payload.button=1`
- canonical event 包含 `occurred_at`，並由 event ID 執行 idempotent ingest。

證據：

- `tests/test_application_device_events.py::test_button_action_is_published_with_canonical_event_payload`
- `tests/test_application_device_events.py::test_button_action_alias_formats_are_normalized_to_canonical_events`
- `tests/test_application_device_events.py` deduplication cases。

### Dashboard control commands

現有 application tests 已覆蓋 Dashboard 需要的 canonical commands：

- power、brightness、color temperature、RGB、effect。
- cover position、tilt、open／close。
- fan speed、preset、direction、oscillation。
- climate target、range、mode、fan、preset、swing。
- scene／script `run`、button `press`。
- numeric／option setting constraints。

證據：

- `tests/test_application_hexagonal.py` Smartly command dispatch and rejection cases。

## Non-blocking Contract Gap

### Logical-device history identity

現有 History API 以 Home Assistant entity identity 查詢，尚未提供以 logical device public ID + canonical capability 查詢的 customer contract。Platform Dashboard 不得把 raw source entity ID 傳到瀏覽器繞過此缺口。

本次 Dashboard 的允許行為：

- 已有正規化 `bridge_chart` 時可顯示 Detailed 趨勢。
- 沒有可靠資料時只顯示即時值與健康資訊。
- 不建立假資料或 raw source fallback。

此項不阻擋自訂 Dashboard 第一版，但在通用 Detailed history 前仍需另立 API contract、ACL、pagination 與 retention 工作。

## Verification

實際結果：

- `python -m pytest tests/test_application_hexagonal.py -v`：通過。
- event tests：51 passed。
- history tests：87 passed。
- full Bridge suite：1023 passed。
- Black：72 files unchanged。
- isort：通過。
- mypy 2.1.0 在 Python 3.14 的 incremental cache 發生 internal error；改用 `--no-incremental` 後顯示 5 個既有 errors。相同命令在乾淨 `dev` 基線顯示完全相同的 5 個 errors，`sync.py` 沒有新增 finding。

## Commit Evidence

- `a3da572 fix(sync): include capability state quality`
