# Smartly Bridge Migration Progress

> 日期：2026-06-30  
> 分支：`dev`  
> 目標：將 `main` 上的既有 entity-based 架構逐步遷移到六邊形架構與 logical-device / capability-based contract。  
> 原則：所有 runtime 行為變更以 TDD slice 推進，並保留 legacy endpoint 相容性。

## Current Status

- `dev` 已建立 application/domain/adapter/view 分層，並以 ports 讓主要 sync、control、event use case 可以脫離 Home Assistant runtime 測試。
- `/api/smartly/sync/structure` application response 已保留 legacy structure 欄位，並同步輸出 API vNext `schema_version`、`data`、`data.device_count`、`warnings`、`errors` envelope 欄位。
- `/api/smartly/sync/states` 已雙軌輸出既有 entity state 與 shadow `logical_devices`。
- `/api/smartly/sync/states` application response 已保留 legacy `states` / `logical_devices` 欄位，並同步輸出 API vNext `schema_version`、`data`、`data.device_count`、`warnings`、`errors` envelope 欄位。
- `/api/smartly/sync/states` API vNext `data` 現在同步輸出 capability state `updates`，讓 Platform read path 可直接讀 `device_id` / `capability` / `state.updated_at`。
- `use_logical_devices` feature flag 可讓 sync states response 在 top-level 與 vNext `data` 內同步標記 logical-device read path，同時保留 legacy `states` 供 rollback。
- Canonical `SmartlyCommand` path 已可解析 logical device capability target，並映射回 Home Assistant service call。
- SmartlyCommand resolved denial audit 現在同時記錄 logical device ID 與 source entity ID，讓 command path 切換期間可追蹤 canonical command 與 legacy target。
- SmartlyCommand success audit 現在也在 actor metadata 內保留 `source_entity_id`，讓成功與拒絕路徑的 trace 欄位一致。
- Presence sensor sibling `number` setting 已開始從 presentation-only control 升格為 canonical `numeric_setting` capability，可透過 SmartlyCommand `set_value` 控制。
- Presence sensor sibling `select` setting 已開始從 presentation-only control 升格為 canonical `option_setting` capability，可透過 SmartlyCommand `select_option` 控制。
- 重複同類型 editable setting capability 現在會保留所有 sibling source refs，避免權限追蹤與後續切換時遺失來源。
- SmartlyCommand success response 已保留 legacy top-level 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- SmartlyCommand error response 已保留 legacy `error`，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors[]` envelope 欄位。
- Device event ingestion 已輸出 canonical `button_event` envelope，支援去重與多種來源 action alias。
- Device event accepted response 已保留 legacy event fields，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Device event duplicate response 已保留 legacy duplicate fields，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Device event invalid action response 已保留 legacy `error` / `message`，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors[]` envelope 欄位。
- Device event HTTP invalid action response 已改用 application error envelope builder，讓 view-level validation 也輸出 API vNext `schema_version`、`data`、`warnings`、`errors[]` 欄位。
- Device event HTTP invalid timestamp response 已改用 application error envelope builder，讓 view-level timestamp validation 也輸出 API vNext `schema_version`、`data`、`warnings`、`errors[]` 欄位。
- Device event HTTP invalid meta response 已改用 application error envelope builder，讓 view-level metadata validation 也輸出 API vNext `schema_version`、`data`、`warnings`、`errors[]` 欄位。
- Device event HTTP missing required fields response 已改用 application error envelope builder，讓 view-level required-field validation 也輸出 API vNext `schema_version`、`data`、`warnings`、`errors[]` 欄位。
- Device event HTTP invalid JSON response 已改用 application error envelope builder，讓 view-level JSON parsing validation 也輸出 API vNext `schema_version`、`data`、`warnings`、`errors[]` 欄位。
- Camera list application response 已保留 legacy `cameras` / `count` / stats 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera register application response 已保留 legacy `success` / `action` / `entity_id` 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera unregister application response 已保留 legacy `success` / `action` / `entity_id` 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera clear-cache application response 已保留 legacy `success` / `action` / `cleared_count` 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera config-list application response 已保留 legacy `cameras` / `count` 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera HLS start application response 已保留 legacy HLS payload 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera HLS info application response 已保留 legacy stream info 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera HLS stats application response 已保留 legacy stats 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera HLS stop success application response 已保留 legacy `success` / `action` 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera HLS stop 404 application response 已保留 legacy `success=false` / `action` 欄位與 404 status，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera HLS unsupported application response 已保留 legacy `error` 欄位與 400 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- Camera HLS camera-not-found application response 已保留 legacy `error` 欄位與 404 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- Camera HLS unknown-action application response 已保留 legacy `error` 欄位與 400 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- Camera config register missing-entity application response 已保留 legacy `error` 欄位與 400 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- Camera config unregister missing-entity application response 已保留 legacy `error` 欄位與 400 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- Camera config unknown-action application response 已保留 legacy `error` 欄位與 400 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- Camera snapshot success application response 已保留 legacy `snapshot` 欄位與 cache headers，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Camera snapshot 304 與 MJPEG stream application response 已明確標記為非 JSON envelope 例外，分別輸出 `X-Smartly-Response-Mode: empty` / `stream` 並保留空 body / streaming headers。
- Camera snapshot unavailable application response 已保留 legacy `error` 欄位與 404 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- WebRTC ICE session-not-found application response 已保留 legacy `error` 欄位與 404 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- WebRTC ICE entity-mismatch application response 已保留 legacy `error` 欄位與 403 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- WebRTC hangup session-not-found application response 已保留 legacy `error` 欄位與 404 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- WebRTC hangup entity-mismatch application response 已保留 legacy `error` 欄位與 403 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- WebRTC token application response 已保留 legacy token / endpoint / ICE 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- WebRTC ICE accepted application response 已保留 legacy `status` / `candidates` 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- WebRTC hangup closed application response 已保留 legacy `status` 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- WebRTC offer answer application response 已保留 legacy `type` / `sdp` / `session_id` 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- WebRTC token camera-missing application response 已保留 legacy `error` / `message` 欄位與 404 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- WebRTC offer invalid-token application response 已保留 legacy `error` / `message` 欄位與 401 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- WebRTC offer signaling-failure application response 已保留 legacy `error` / `message` / `session_id` 欄位與 500 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- Legacy control success application response 已保留 legacy `success` / `entity_id` / `action` / new state 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Legacy control entity-not-allowed application response 已保留 legacy `error` 欄位與 403 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- Legacy control service-not-allowed application response 已保留 legacy `error` 欄位與 403 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- Legacy control service-call-failed application response 已保留 legacy `error` 欄位與 500 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- History invalid-time-range application response 已保留 legacy `error` 欄位與 400 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- History time-range-too-large application response 已保留 legacy `error` / `max_days` 欄位與 400 status，並同步輸出 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位。
- History single-query application response 已保留 legacy `entity_id` / `history` / `count` / metadata 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- History batch application response 已保留 legacy `history` / `count` / `truncated` / `denied_entities` / metadata 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- History statistics application response 已保留 legacy `entity_id` / `period` / `statistics` / `count` 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- Legacy control body 與既有 endpoint 仍保留，尚未進入 legacy cleanup。

## Recording Rule

- 每個重構 slice 都要依完成順序追加到 `Chronological Refactor Log`。
- 若 slice 有 runtime 行為變更，紀錄需包含 TDD RED/GREEN/verification 摘要。
- `Completed Slices` 保留為依功能區分的總覽，不取代依序紀錄。

## Chronological Refactor Log

| Order | Commit | Slice | Verification |
|---:|---|---|---|
| 1 | `0841be1` | 建立 flexible bridge architecture specs：總體架構、Device Abstraction、Capability Contracts、Adapter Contract、Presentation Contract、API vNext、Migration Plan | Docs only |
| 2 | `cf27b15` | 修正 devcontainer workspace 權限：改以 `vscode` user 執行，避免 host/container 權限衝突 | Devcontainer rebuild verified |
| 3 | `912b21c` | 建立 canonical capability migration 基礎：application/domain/ports 與初始 logical-device contracts | TDD application tests |
| 4 | `62f618d` | 依 source device ID group sibling entities 成單一 logical device | TDD sync/logical tests |
| 5 | `564c8c4` | 新增 canonical `SmartlyCommand` dispatcher，將 logical command 映射到 source entity | TDD control tests |
| 6 | `2dd37ac` | SmartlyCommand response 回傳 expected state，支援 command/state correlation | TDD control tests |
| 7 | `edb4a68` | 標準化 SmartlyCommand 錯誤 response | TDD control tests |
| 8 | `3b54b65` | Device event ingestion 回傳 canonical event envelope | TDD event tests |
| 9 | `42e0c61` | Canonical device event 去重，避免重複觸發 automation | TDD event tests |
| 10 | `e47050c` | logical device 輸出 Home Assistant entity alias | TDD sync tests |
| 11 | `040f769` | sync response 回報 normalization warnings | TDD sync tests |
| 12 | `adf268c` | color temperature constraints 由 mired metadata 正規化成 kelvin constraints | TDD logical-device tests |
| 13 | `59380db` | RGB color state 正規化成 canonical `{r,g,b}` contract | TDD logical-device tests |
| 14 | `69261c1` | signal quality 正規化成 percent 並保留 raw metric | TDD logical-device tests |
| 15 | `dc3da2c` | SmartlyCommand 拒絕 capability 不支援的 command | TDD control tests |
| 16 | `4e37faf` | SmartlyCommand params schema validation | TDD control tests |
| 17 | `1380499` | cover position canonical command 映射到 Home Assistant cover services | TDD control tests |
| 18 | `d5e802e` | fan speed canonical command 映射到 percentage / preset source services | TDD control tests |
| 19 | `e95d7ee` | fan speed state 正規化 percentage / preset mode | TDD logical-device tests |
| 20 | `824a555` | cover position state 正規化成 percent contract | TDD logical-device tests |
| 21 | `9ea1854` | lock state 與 lock/unlock command expected state | TDD logical/control tests |
| 22 | `53ac6c0` | climate HVAC mode 正規化成 `mode_select` | TDD logical/control tests |
| 23 | `f6daf58` | climate target temperature state/control contract | TDD logical/control tests |
| 24 | `f04b742` | scene/script `run` capability 與 command mapping | TDD logical/control tests |
| 25 | `0451e08` | climate fan modes 正規化成 `fan_speed` | TDD logical/control tests |
| 26 | `58ba900` | air quality measurements 正規化 | TDD logical-device tests |
| 27 | `3d8e865` | binary sensor states 正規化 presence/open-close 等 contracts | TDD logical-device tests |
| 28 | `0ec3497` | electrical measurements 正規化 current/voltage/power/energy | TDD logical-device tests |
| 29 | `844495c` | light effect metadata/state/control contract | TDD logical/control tests |
| 30 | `c02479b` | legacy cover `stop` 合併到 canonical `position` commands | TDD logical-device tests |
| 31 | `5e569e5` | cover tilt position state/control contract | TDD logical/control tests |
| 32 | `87723a4` | climate preset mode state/control contract | TDD logical/control tests |
| 33 | `0aff83a` | climate swing mode state/control contract | TDD logical/control tests |
| 34 | `e3583fc` | climate target temperature range state/control contract | TDD logical/control tests |
| 35 | `a1e6818` | fan direction state/control contract | TDD logical/control tests |
| 36 | `03abb58` | fan oscillation state/control contract | TDD logical/control tests |
| 37 | `3b48f87` | HS color fallback 正規化成 canonical RGB state | RED failed with `{}` state; full suite `515 passed` |
| 38 | `ddac6bb` | XY color fallback 正規化成 canonical RGB state | RED failed with `{}` state; full suite `516 passed` |
| 39 | `74fc92c` | brightness delta commands：`increase_brightness` / `decrease_brightness` 映射 `brightness_step_pct` | RED failed as `command_not_supported`; full suite `518 passed` |
| 40 | `ed729a1` | rotary button events：`rotate_left/right` 正規化成 canonical button events | RED failed as `invalid_action`; full suite `519 passed` |
| 41 | `3347735` | button action alias formats：`left_single`、`1_single` 正規化成 `single_press`，HTTP ingestion 使用同一 parser validation | RED failed as `invalid_action`; full suite `522 passed` |
| 42 | `4527bd5` | `use_logical_devices` read-path feature flag：sync states response 加上 logical `read_path`、`devices`、`device_count`，但保留 legacy `states` | RED failed with missing constructor flag / missing `read_path`; full suite `525 passed` |
| 43 | `df54f35` | SmartlyCommand error response 補上 API vNext `errors[]` structured error，同時保留 legacy `error` 相容欄位 | RED failed with missing `errors`; affected tests `106 passed`; full suite `526 passed` |
| 44 | `a073269` | SmartlyCommand success response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy top-level 欄位 | RED failed with missing `schema_version`; affected tests `107 passed`; full suite `527 passed` |
| 45 | `a094b98` | SmartlyCommand error response 補上 API vNext `schema_version`、`data`、`warnings` envelope 欄位，同時保留 legacy top-level error 欄位 | RED failed with missing `schema_version`; affected tests `108 passed`; full suite `528 passed` |
| 46 | `e01355e` | Device event accepted response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy event response 欄位 | RED failed with missing `schema_version`; affected tests `14 passed`; full suite `529 passed` |
| 47 | `ddadb62` | Device event duplicate response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy duplicate response 欄位 | RED failed with missing `schema_version`; affected tests `15 passed`; full suite `530 passed` |
| 48 | `14f5de7` | Sync states response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `states` / `logical_devices` 欄位 | RED failed with missing `schema_version`; affected tests `99 passed`; full suite `531 passed` |
| 49 | `aad30d2` | Sync structure response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy structure top-level 欄位 | RED failed with missing `schema_version`; affected tests `100 passed`; full suite `532 passed` |
| 50 | `372cf5a` | Device event invalid action response 補上 API vNext `schema_version`、`data`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` / `message` 欄位 | RED failed with missing `schema_version`; affected tests `16 passed`; full suite `533 passed` |
| 51 | `b915337` | Device event HTTP invalid action response 改用 application error envelope builder，補上 API vNext `schema_version`、`data`、`warnings`、`errors[]` 欄位 | RED failed with missing vNext fields; affected tests `17 passed`; full suite `534 passed` |
| 52 | `6176c49` | Device event HTTP invalid timestamp response 改用 application error envelope builder，補上 API vNext `schema_version`、`data`、`warnings`、`errors[]` 欄位 | RED failed with legacy-only `invalid_timestamp`; affected tests `18 passed`; full suite `535 passed` |
| 53 | `71a3aec` | Device event HTTP invalid meta response 改用 application error envelope builder，補上 API vNext `schema_version`、`data`、`warnings`、`errors[]` 欄位 | RED failed with legacy-only `invalid_meta`; affected tests `19 passed`; full suite `536 passed` |
| 54 | `89e0948` | Device event HTTP missing required fields response 改用 application error envelope builder，補上 API vNext `schema_version`、`data`、`warnings`、`errors[]` 欄位，並標記 first missing field target | RED failed with legacy-only `missing_required_fields`; affected tests `20 passed`; full suite `537 passed` |
| 55 | `1e7ea16` | Device event HTTP invalid JSON response 改用 application error envelope builder，補上 API vNext `schema_version`、`data`、`warnings`、`errors[]` 欄位 | RED failed with legacy-only `invalid_json`; affected tests `21 passed`; full suite `538 passed` |
| 56 | `b174ee2` | Camera list application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `cameras` / `count` / stats 欄位 | RED failed with missing `schema_version`; camera tests `106 passed`; full suite `539 passed` |
| 57 | `1531478` | Camera register application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `success` / `action` / `entity_id` 欄位 | RED failed with missing `schema_version`; camera tests `107 passed`; full suite `540 passed` |
| 58 | `b42d26a` | Camera unregister application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `success` / `action` / `entity_id` 欄位 | RED failed with missing `schema_version`; camera tests `108 passed`; full suite `541 passed` |
| 59 | `7660fb8` | Camera clear-cache application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `success` / `action` / `cleared_count` 欄位 | RED failed with missing `schema_version`; camera tests `109 passed`; full suite `542 passed` |
| 60 | `9ef6f75` | Camera config-list application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `cameras` / `count` 欄位 | RED failed with missing `schema_version`; camera tests `110 passed`; full suite `543 passed` |
| 61 | `77665f5` | Camera HLS start application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy HLS payload 欄位 | RED failed with missing `schema_version`; camera tests `111 passed`; full suite `544 passed` |
| 62 | `ede433d` | Camera HLS info application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy stream info 欄位 | RED failed with missing `schema_version`; camera tests `112 passed`; full suite `545 passed` |
| 63 | `ae647d9` | Camera HLS stats application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy stats 欄位 | RED failed with missing `schema_version`; camera tests `113 passed`; full suite `546 passed` |
| 64 | `9383ab8` | Camera HLS stop success application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `success` / `action` 欄位 | RED failed with missing `schema_version`; camera tests `114 passed`; full suite `547 passed` |
| 65 | `8ec2d62` | Camera HLS stop 404 application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `success=false` / `action` 欄位與 404 status | RED failed with missing `schema_version`; camera tests `115 passed`; full suite `548 passed` |
| 66 | `59aeed0` | Camera HLS unsupported application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 400 status | RED failed with missing `schema_version`; camera tests `115 passed`; full suite `548 passed` |
| 67 | `97b8329` | Camera HLS camera-not-found application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 404 status | RED failed with missing `schema_version`; camera tests `116 passed`; full suite `549 passed` |
| 68 | `dead64d` | Camera HLS unknown-action application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 400 status | RED failed with missing `schema_version`; camera tests `117 passed`; full suite `550 passed` |
| 69 | `6e9bec6` | Camera config register missing-entity application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 400 status | RED failed with missing `schema_version`; camera tests `117 passed`; full suite `550 passed` |
| 70 | `bd03650` | Camera config unregister missing-entity application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 400 status | RED failed with missing `schema_version`; camera tests `118 passed`; full suite `551 passed` |
| 71 | `4d14906` | Camera config unknown-action application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 400 status | RED failed with missing `schema_version`; camera tests `119 passed`; full suite `552 passed` |
| 72 | `72901ae` | Camera snapshot unavailable application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 404 status | RED failed with missing `schema_version`; camera tests `119 passed`; full suite `552 passed` |
| 73 | `ff78eb5` | WebRTC ICE session-not-found application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 404 status | RED failed with missing `schema_version`; WebRTC tests `48 passed`; full suite `553 passed` |
| 74 | `8d56e3e` | WebRTC ICE entity-mismatch application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 403 status | RED failed with missing `schema_version`; WebRTC tests `49 passed`; full suite `554 passed` |
| 75 | `93a2ee5` | WebRTC hangup session-not-found application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 404 status | RED failed with missing `schema_version`; WebRTC tests `50 passed`; full suite `555 passed` |
| 76 | `fc083e3` | WebRTC hangup entity-mismatch application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 403 status | RED failed with missing `schema_version`; WebRTC tests `51 passed`; full suite `556 passed` |
| 77 | `eaad20a` | Legacy control entity-not-allowed application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 403 status | RED failed with missing `schema_version`; affected tests `110 passed`; full suite `556 passed` |
| 78 | `b29cd33` | Legacy control service-not-allowed application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 403 status | RED failed with missing `schema_version`; affected tests `111 passed`; full suite `557 passed` |
| 79 | `d6da427` | Legacy control service-call-failed application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 500 status | RED failed with missing `schema_version`; affected tests `112 passed`; full suite `558 passed` |
| 80 | `4979988` | History invalid-time-range application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` 欄位與 400 status | RED failed with missing `schema_version`; history tests `44 passed`; full suite `558 passed` |
| 81 | `4e27a90` | WebRTC token application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy token / endpoint / ICE 欄位 | RED failed with missing `schema_version`; WebRTC tests `51 passed`; full suite `558 passed` |
| 82 | `97a13dd` | WebRTC ICE accepted application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `status` / `candidates` 欄位 | RED failed with missing `schema_version`; WebRTC tests `51 passed`; full suite `558 passed` |
| 83 | `3307f29` | WebRTC hangup closed application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `status` 欄位 | RED failed with missing `schema_version`; WebRTC tests `51 passed`; full suite `558 passed` |
| 84 | `6f88e91` | WebRTC offer answer application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `type` / `sdp` / `session_id` 欄位 | RED failed with missing `schema_version`; WebRTC tests `51 passed`; full suite `558 passed` |
| 85 | `8f95180` | WebRTC token camera-missing application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` / `message` 欄位與 404 status | RED failed with missing `schema_version`; WebRTC tests `51 passed`; full suite `558 passed` |
| 86 | `54cedc0` | WebRTC offer invalid-token application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` / `message` 欄位與 401 status | RED failed with missing `schema_version`; WebRTC tests `51 passed`; full suite `558 passed` |
| 87 | `d70eab6` | WebRTC offer signaling-failure application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` / `message` / `session_id` 欄位與 500 status | RED failed with missing `schema_version`; WebRTC tests `51 passed`; full suite `558 passed` |
| 88 | `be5a1e5` | History time-range-too-large application response 補上 API vNext `schema_version`、`data.status`、`warnings`、`errors[]` envelope 欄位，同時保留 legacy `error` / `max_days` 欄位與 400 status | RED failed with missing `schema_version`; history tests `44 passed`; full suite `558 passed` |
| 89 | `296da10` | History single-query application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `entity_id` / `history` / `count` / metadata 欄位 | RED failed with missing `schema_version`; targeted test `1 passed`; history tests `44 passed`; full suite `558 passed` |
| 90 | `0e6db58` | History batch application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `history` / `count` / `truncated` / `denied_entities` / metadata 欄位 | RED failed with missing `schema_version`; targeted test `1 passed`; history tests `44 passed`; full suite `558 passed` |
| 91 | `ae03e72` | History statistics application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `entity_id` / `period` / `statistics` / `count` 欄位 | RED failed with missing `schema_version`; targeted test `1 passed`; history tests `44 passed`; full suite `558 passed` |
| 92 | `6ddca2e` | Legacy control success application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `success` / `entity_id` / `action` / new state 欄位 | RED failed with missing `schema_version`; targeted test `1 passed`; affected control/http/acl tests `136 passed`; full suite `558 passed` |
| 93 | `360bf42` | Camera snapshot success application response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy `snapshot` 欄位與 ETag / cache headers | RED failed with missing `schema_version`; targeted test `1 passed`; camera tests `122 passed`; full suite `558 passed` |
| 94 | `cb7bac5` | Camera snapshot 304 與 MJPEG stream response 固定為非 JSON envelope 例外，分別輸出 `X-Smartly-Response-Mode: empty` / `stream` 並保留空 body / streaming headers | RED failed with missing response-mode headers; targeted tests `3 passed`; camera tests `122 passed`; full suite `558 passed` |
| 95 | `c0bbf1e` | Sync states logical-device read path 在 API vNext `data` 內同步輸出 `read_path` / `devices` / `device_count`，讓 vNext client 不需讀 top-level legacy 欄位即可切換 read path | RED failed with missing `data.read_path`; targeted tests `2 passed`; affected sync/hexagonal tests `102 passed`; full suite `558 passed` |
| 96 | `35dfdd6` | Current-sync API vNext data fixture 覆蓋 sync states payload，並讓 `data.device_count` 永遠輸出 logical device count，避免 vNext client 只能讀 legacy entity `count` | RED failed with fixture expecting `device_count`; targeted test `1 passed`; affected sync/hexagonal tests `103 passed`; full suite `559 passed` |
| 97 | `1e0ba0b` | Current-sync structure API vNext data fixture 覆蓋 structure payload，並讓 `data.device_count` 永遠輸出 structure device count，讓 vNext sync contract 不需推導 devices array 長度 | RED failed with fixture expecting `device_count`; targeted test `1 passed`; affected sync/hexagonal tests `104 passed`; full suite `560 passed` |
| 98 | `137a8da` | Presence sibling `number` setting 升格為 canonical `numeric_setting` capability，SmartlyCommand `set_value` 可解析同 device group 的 number sibling 並映射到 HA `number.set_value` | RED failed with missing `numeric_setting`, `command_not_supported`, and sibling target 404; targeted tests `3 passed`; affected logical/hexagonal/http/sync tests `182 passed`; full suite `563 passed` |
| 99 | `de481d6` | Presence sibling `select` setting 升格為 canonical `option_setting` capability，SmartlyCommand `select_option` 可解析同 device group 的 select sibling 並映射到 HA `select.select_option` | RED failed with missing `option_setting`, `command_not_supported`, and sibling target 404; targeted tests `3 passed`; affected logical/hexagonal/http/sync tests `185 passed`; full suite `566 passed` |
| 100 | `584c1bc` | 重複同類型 editable setting capability 保留所有 source refs，避免 `numeric_setting` 合併時遺失第二個 sibling number 來源 | RED failed with only first `number` source ref retained; targeted test `1 passed`; affected logical/hexagonal/http/sync tests `186 passed`; full suite `567 passed` |
| 101 | `a6b4057` | Sync states API vNext `data` 補上 capability state `updates` array，讓 Platform read path 可直接消費 `device_id` / `capability` / `state.updated_at` 而不必解析 legacy entity state | RED failed with missing `data.updates`; targeted tests `2 passed`; affected hexagonal/sync tests `107 passed`; full suite `568 passed` |
| 102 | `edf71be` | SmartlyCommand resolved denial audit 改以 source entity 作為 audit target，並在 actor metadata 保留 `logical_device_id` / `source_entity_id`，讓拒絕路徑也能追蹤 canonical command 與 legacy target | RED failed with audit denials missing logical/source trace metadata; targeted tests `3 passed`; affected command/http/acl tests `143 passed`; full suite `568 passed` |
| 103 | `02e8f66` | SmartlyCommand success audit actor metadata 補上 `source_entity_id`，讓成功路徑也與拒絕路徑一樣同時保留 canonical logical device 與 legacy source target | RED failed with success audit actor missing `source_entity_id`; targeted test `1 passed`; affected command/http/acl tests `143 passed`; full suite `568 passed` |
| 104 | `82be030` | Sync structure view test 明確 mock Home Assistant entity/device/area/floor registries，避免 Python 3.14 / HA 2026 registry setup 變更讓 view wiring test 依賴真 registry | RED full suite failed with `Device registry not set up`; targeted sync view test `1 passed`; full suite `568 passed` |

## Completed Slices

| Area | Done | Evidence |
|---|---|---|
| Architecture specs | 新增總體架構、Device Abstraction、Capability Contracts、Adapter Contract、Presentation Contract、API vNext、Migration Plan | `0841be1` |
| Devcontainer permissions | devcontainer workspace 改以 `vscode` user 執行，避免 host/container 權限互相衝突 | `cf27b15` |
| Hexagonal application base | 建立 canonical capability migration 基礎 use cases 與 application ports | `912b21c` |
| Logical device grouping | 以 Home Assistant source device ID 將 sibling entities group 成同一 logical device | `62f618d` |
| Command path | 新增 canonical `SmartlyCommand` dispatcher、target resolver、expected state、standard error shape，並為 command success/error 與 legacy control success/entity deny/service deny/service failure 補上 API vNext envelope/error fields；resolved denial 與 success audit 都會同時保留 logical device 與 source entity trace metadata | `564c8c4`, `2dd37ac`, `edb4a68`, `df54f35`, `a073269`, `a094b98`, `6ddca2e`, `eaad20a`, `b29cd33`, `d6da427`, `edf71be`, `02e8f66` |
| Test harness | Sync structure view test 明確 mock HA registries，讓 Python 3.14 / HA 2026.6 registry setup 下的 full suite 可穩定驗證 view wiring | `82be030` |
| Event path | 新增 canonical event envelope、event deduplication，並為 accepted / duplicate / invalid action event response、HTTP invalid JSON/action/timestamp/meta/missing-required response 補上 API vNext envelope fields | `3b54b65`, `42e0c61`, `e01355e`, `ddadb62`, `372cf5a`, `b915337`, `6176c49`, `71a3aec`, `89e0948`, `1e7ea16` |
| History path | history invalid-time-range、time-range-too-large、single-query、batch 與 statistics application response envelope，保留 legacy `error` / `max_days` / history/statistics payload 欄位 | `4979988`, `be5a1e5`, `296da10`, `0e6db58`, `ae03e72` |
| Camera path | camera list/register/unregister/clear-cache/config-list/HLS start/info/stats/stop/snapshot success application response envelope、snapshot 304 / MJPEG stream 非 JSON response-mode 標記，與 HLS unsupported/camera-not-found/unknown-action/config register/unregister missing-entity/config unknown-action/snapshot unavailable error envelope；保留 legacy camera list body、stats、config success/list、HLS payload、stream info、stop 404、snapshot payload/cache headers、streaming headers 與 error 欄位 | `b174ee2`, `1531478`, `b42d26a`, `7660fb8`, `9ef6f75`, `77665f5`, `ede433d`, `ae647d9`, `9383ab8`, `8ec2d62`, `59aeed0`, `97b8329`, `dead64d`, `6e9bec6`, `bd03650`, `4d14906`, `72901ae`, `360bf42`, `cb7bac5` |
| WebRTC path | WebRTC token response envelope、offer answer envelope、ICE accepted success envelope、hangup closed success envelope 與 token camera-missing、offer invalid-token/signaling-failure、ICE session-not-found/entity-mismatch、hangup session-not-found/entity-mismatch application response envelope，保留 legacy token / endpoint / ICE、`type` / `sdp` / `session_id`、`status` / `candidates`、`message` 與 `error` 欄位 | `ff78eb5`, `8d56e3e`, `93a2ee5`, `fc083e3`, `4e27a90`, `97a13dd`, `3307f29`, `6f88e91`, `8f95180`, `54cedc0`, `d70eab6` |
| Sync aliases, warnings, and read path | structure/states response envelope、logical devices migration aliases、normalization warnings、current-sync vNext data fixture 與 logical/structure device count，並支援 `use_logical_devices` read-path flag；logical-device read path 與 capability state `updates` 已同步到 API vNext `data` payload | `e47050c`, `040f769`, `4527bd5`, `14f5de7`, `aad30d2`, `c0bbf1e`, `35dfdd6`, `1e0ba0b`, `a6b4057` |
| Light capabilities | 色溫 constraints、RGB contract、effects、HS/XY color fallback、brightness delta commands | `adf268c`, `59380db`, `844495c`, `3b48f87`, `ddac6bb`, `74fc92c` |
| Sensors | signal quality、air quality、binary sensor、electrical measurements normalization | `69261c1`, `58ba900`, `3d8e865`, `0ec3497` |
| Cover | position、stop merge、tilt position control | `824a555`, `c02479b`, `5e569e5` |
| Fan | fan speed state/control、direction、oscillation | `e95d7ee`, `d5e802e`, `a1e6818`, `03abb58` |
| Climate | mode select、target temperature、fan modes、preset mode、swing mode、temperature range | `53ac6c0`, `f6daf58`, `0451e08`, `87723a4`, `0aff83a`, `e3583fc` |
| Scene/script | scene/script `run` capability and command mapping | `f04b742` |
| Lock | lock state and command expected-state contract | `9ea1854` |
| Button events | rotary `rotate_left/right` normalization; source alias formats such as `left_single` and `1_single` normalize to canonical `single_press` | `ed729a1`, `3347735` |
| Setting controls | Presence sibling `number` / `select` setting 已從 presentation-only control 升格為 canonical `numeric_setting` / `option_setting` capability 與 SmartlyCommand `set_value` / `select_option` path；重複同類型 setting capability 會保留所有 sibling source refs | `137a8da`, `de481d6`, `584c1bc` |

## Latest Verification

- Targeted SmartlyCommand success audit test: `1 passed`
- Affected command/http/acl tests: `143 passed`
- Targeted sync structure view registry test: `1 passed`
- Full suite: `568 passed` on Python 3.14.2 container

## Remaining Work

- Finish a requirement-by-requirement audit against `migration-plan.md`, `api-vnext-contract.md`, and `capability-contracts.md`.
- Add stronger fixture coverage for current-sync snapshots and API vNext contract snapshots.
- Continue API vNext envelope migration for endpoints beyond SmartlyCommand command responses.
- Continue hardening editable sibling setting controls now that `number` / `select` are covered by canonical `numeric_setting` / `option_setting` command capabilities.
- Continue filling P0 command mapping and event automation gaps before Platform read/write path cutover.
- Do not start Phase 6 legacy cleanup until legacy endpoint usage and rollback requirements are proven.
