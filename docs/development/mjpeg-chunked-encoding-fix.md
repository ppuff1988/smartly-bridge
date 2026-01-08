# MJPEG 串流 Chunked Encoding 修正

> **技術文檔** | 更新日期：2026-01-08

## 背景

在實作 MJPEG 串流功能時，發現 Go HTTP 客戶端無法正確解析從 HA Bridge 返回的串流數據，出現 `"invalid byte in chunk length"` 錯誤。經診斷後發現問題根源是 HTTP `Transfer-Encoding: chunked` 與 MJPEG 的 `multipart/x-mixed-replace` 格式不相容。

## 問題分析

### 診斷日誌

**初始診斷（Transfer-Encoding 問題）：**
```
2026/01/08 17:39:29 [HA Camera] Response status: 200, Content-Type: multipart/x-mixed-replace;boundary=frame
2026/01/08 17:39:29 [HA Camera] Response headers: Transfer-Encoding=, Content-Length=, Connection=
2026/01/08 17:39:29 [HA Camera] Response ContentLength field: -1, TransferEncoding: [chunked]
```

**深入診斷（雙層 HTTP 響應問題）：**
```
2026/01/08 18:30:21.565 INFO ... CONTROL: ..., service=camera_stream, result=started
2026/01/08 18:30:21.641 INFO ... Stream cancelled by client for camera: camera.test
```

Go 客戶端在收到響應後 76ms 內立即斷開，且檢測到 body 中包含第二層 HTTP 響應頭（`HTTP/1.1 200 OK`）。

### 根本原因

問題有兩個層面：

#### 1. Transfer-Encoding: chunked（已解決）

HTTP/1.1 的 aiohttp `StreamResponse` 預設使用 chunked encoding，這與 MJPEG 格式不相容。

#### 2. 雙層 HTTP 響應（關鍵問題）

Home Assistant 的 `async_get_mjpeg_stream()` 返回的是一個 **aiohttp Response 對象**，其中包含：
- HTTP 響應頭（200 OK, Content-Type, etc.）
- MJPEG 數據流

如果直接迭代這個對象，會將整個 HTTP 響應（包括頭）寫入我們的響應 body 中，造成：

```
外層: HTTP/1.1 200 OK + headers
Body: HTTP/1.1 200 OK + headers + MJPEG data  ← 來自 HA
```

Go HTTP 客戶端解析時會混淆，以為 body 中的 `HTTP/1.1 200 OK` 是 chunked size，導致解析失敗。

### 技術原因

#### MJPEG 格式

MJPEG (Motion JPEG) 使用 HTTP `multipart/x-mixed-replace` 格式傳輸：

```http
HTTP/1.1 200 OK
Content-Type: multipart/x-mixed-replace;boundary=frame

--frame
Content-Type: image/jpeg
Content-Length: 12345

[JPEG binary data]
--frame
Content-Type: image/jpeg
Content-Length: 12456

[JPEG binary data]
--frame
...
```

每個 JPEG 幀前都有 `--frame` boundary 標記。

#### Chunked Encoding 格式

HTTP/1.1 的 `Transfer-Encoding: chunked` 格式：

```http
HTTP/1.1 200 OK
Transfer-Encoding: chunked

5\r\n
hello\r\n
6\r\n
world!\r\n
0\r\n
\r\n
```

每個 chunk 前都有十六進制的 size 標記。

#### 衝突原因

1. **格式不相容**：MJPEG 的 `--frame` boundary 會被誤認為 chunked size
2. **解析器混淆**：HTTP 客戶端（特別是 Go 的標準庫）會嘗試解析 chunked size，但遇到非十六進制字元（如 `-`）時失敗
3. **數據損壞**：chunked wrapper 破壞了原始的 multipart 結構

### 影響範圍

**雙層 HTTP 響應問題**：
- Go HTTP 客戶端完全無法讀取串流（解析錯誤：`invalid byte in chunk length`）
- 客戶端在收到響應後立即斷開（< 100ms）
- 串流數據傳輸失敗（bytes_written: 0）
- 所有 HTTP 客戶端都會受影響（不只 Go）

**Chunked Encoding 問題**：
- 破壞 MJPEG multipart 邊界
- 部分客戶端可能勉強工作但效能不佳
- 增加不必要的協議開銷

## 解決方案

### 方案 1：禁用 Chunked Encoding

**修改位置**：`custom_components/smartly_bridge/views/camera.py` - `SmartlyCameraStreamView.get()`

```python
# Create stream response
# IMPORTANT: For MJPEG streams, we must avoid chunked encoding
response = web.StreamResponse(
    status=200,
    headers={
        "Content-Type": "multipart/x-mixed-replace;boundary=frame",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Connection": "close",  # Critical: prevents chunked encoding
    },
)

# Explicitly disable compression to avoid any encoding
response.enable_compression(False)

await response.prepare(self.request)
```

### 方案 2：正確處理 HA MJPEG 串流（關鍵修正）

**修改位置**：`custom_components/smartly_bridge/camera.py` - `_stream_from_ha()`

**問題**：原始代碼直接迭代 `async_get_mjpeg_stream()` 返回的對象，導致 HTTP 響應頭也被寫入 body：

```python
# ❌ 錯誤：會將 HTTP 響應頭也寫入 body
stream = await async_get_mjpeg_stream(self.hass, request, entity_id)
async for chunk in stream.iter_chunked(CAMERA_STREAM_CHUNK_SIZE):
    await response.write(chunk)  # 包含 "HTTP/1.1 200 OK\r\n..."
```

**修正**：使用 `.content` 屬性獲取純數據流：

```python
# ✅ 正確：只傳輸純 MJPEG 數據
stream_response = await async_get_mjpeg_stream(self.hass, request, entity_id)
async for chunk in stream_response.content.iter_chunked(CAMERA_STREAM_CHUNK_SIZE):
    await response.write(chunk)  # 純 MJPEG 數據：--frame\r\n...
```

### 關鍵技術點

1. **禁用 Chunked Encoding**：
   - 設置 `Connection: close` 頭
   - 調用 `response.enable_compression(False)` 明確禁用壓縮
   - 不設置 `Content-Length`（因為串流長度未知）

2. **正確提取 MJPEG 數據**（關鍵）：
   - `async_get_mjpeg_stream()` 返回 aiohttp `Response` 對象
   - 使用 `.content.iter_chunked()` 獲取純數據流
   - **不要**直接迭代 Response 對象，那會包含 HTTP 頭

2. **適當的 Cache Headers**：
   - `Cache-Control: no-cache, no-store, must-revalidate`：防止快取
   - `Pragma: no-cache`：相容舊版瀏覽器
   - `Expires: 0`：確保即時性

3. **Connection 管理**：
   - `Connection: close`：每個串流使用獨立連線
   - 避免 keep-alive 導致的串流干擾

## 驗證方法

### 使用 curl 檢查響應

```bash
# 檢查響應頭
curl -I http://localhost:8123/api/smartly/camera/camera.test/stream \
  -H "X-Client-Id: xxx" \
  -H "X-Timestamp: xxx" \
  -H "X-Nonce: xxx" \
  -H "X-Signature: xxx"

# 檢查前 200 bytes
curl -s http://localhost:8123/api/smartly/camera/camera.test/stream \
  -H "X-Client-Id: xxx" \
  ... | head -c 200 | hexdump -C
```

### 預期結果

**響應頭：**
```http
HTTP/1.1 200 OK
Content-Type: multipart/x-mixed-replace;boundary=frame
Cache-Control: no-cache, no-store, must-revalidate
Connection: close
```

✅ **不應包含**：`Transfer-Encoding: chunked`  
✅ **不應包含**：`Content-Length: 0`

**響應 Body（前 100 bytes）：**
```
00000000  2d 2d 66 72 61 6d 65 0d  0a 43 6f 6e 74 65 6e 74  |--frame..Content|
00000010  2d 54 79 70 65 3a 20 69  6d 61 67 65 2f 6a 70 65  |-Type: image/jpe|
00000020  67 0d 0a 43 6f 6e 74 65  6e 74 2d 4c 65 6e 67 74  |g..Content-Lengt|
```

✅ **應該看到**：`--frame` boundary 標記  
❌ **不應看到**：`HTTP/1.1 200 OK`（這表示雙層響應問題）  
❌ **不應看到**：chunked size 的十六進制數字（如 `5\r\n`）

### Home Assistant 日誌

```
INFO ... Attempting to get MJPEG stream for camera: camera.test
INFO ... MJPEG stream obtained, starting to proxy data for camera: camera.test
DEBUG ... Streamed 10 chunks (xxxxx bytes) for camera: camera.test
INFO ... Stream completed for camera camera.test (sent N chunks, XXXXX bytes)
```

✅ **chunk_count > 0** 且 **bytes_written > 0** 表示有數據傳輸  
❌ **bytes_written: 0** 表示串流立即結束（有問題）

## 相關資源

### 標準文件
- [RFC 2046 - Multipart Media Type](https://datatracker.ietf.org/doc/html/rfc2046)
- [RFC 7230 - HTTP/1.1 Transfer Encoding](https://datatracker.ietf.org/doc/html/rfc7230#section-4.1)
- [MJPEG Streaming Protocol](https://en.wikipedia.org/wiki/Motion_JPEG#M-JPEG_over_HTTP)

### 相關 Issues
- Go HTTP chunked encoding: https://github.com/golang/go/issues/15527
- MJPEG streaming best practices: https://stackoverflow.com/questions/21702477

### 相關文檔
- [需求規格文檔](../../HA_BRIDGE_MJPEG_REQUIREMENTS.md)
- [Camera API 文檔](../camera-api.md)

## 未來改進

### 可選優化

1. **HTTP/1.0 協議降級**：
   - 當檢測到客戶端無法處理 chunked encoding 時，自動降級為 HTTP/1.0
   - 需要修改 aiohttp 響應協議版本

2. **客戶端檢測**：
   - 根據 User-Agent 自動選擇最佳傳輸方式
   - 為已知的客戶端（如 Go）提供優化配置

3. **WebSocket 串流**：
   - 考慮實作 WebSocket-based 串流作為替代方案
   - 避免 HTTP 傳輸層的限制

### 效能監控

建議監控以下指標：

- 串流建立時間（首幀延遲）
- 傳輸速率（bytes/sec）
- 客戶端連線錯誤率
- 串流持續時間

## 版本記錄

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| 1.0.0 | 2026-01-08 | 初始版本，修正 chunked encoding 問題 |
| 1.1.0 | 2026-01-08 | 發現並修正雙層 HTTP 響應問題（關鍵修正）|

## 經驗教訓

1. **不要假設 API 返回的是純數據**：Home Assistant 的 `async_get_mjpeg_stream()` 返回的是 Response 對象，不是純數據流

2. **使用 `.content` 屬性**：對於 aiohttp Response 對象，使用 `.content.iter_chunked()` 獲取純數據

3. **檢查實際傳輸的數據**：使用 hexdump 檢查前幾個 bytes，確認格式正確

4. **測試多個客戶端**：Go、Python、瀏覽器可能有不同的行為

---

**作者**：Smartly Bridge Team  
**審查者**：技術團隊  
**最後更新**：2026-01-08
