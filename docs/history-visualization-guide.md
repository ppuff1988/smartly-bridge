# History API 視覺化指南

## 快速開始

History API v1.3.0 新增了智能視覺化元數據，讓前端能自動選擇最佳的呈現方式。

## 使用流程

### 1. 獲取歷史數據

```javascript
const response = await fetch('/api/smartly/history/sensor.current');
const envelope = await response.json();
const data = envelope.data;
```

### 2. 檢查元數據

```javascript
const { metadata } = data;

console.log(metadata);
// {
//   "domain": "sensor",
//   "device_class": "current",
//   "unit_of_measurement": "mA",
//   "friendly_name": "小燈電流",
//   "is_numeric": true,
//   "decimal_places": 1,
//   "visualization": {
//     "type": "chart",
//     "chart_type": "line",
//     "color": "#FFA726",
//     "show_points": true,
//     "interpolation": "linear"
//   }
// }
```

### 3. 根據類型渲染

```javascript
const viz = metadata.visualization;

switch(viz.type) {
    case 'chart':
        renderChart(history, viz);
        break;
    case 'timeline':
        renderTimeline(history, viz);
        break;
    case 'gauge':
        renderGauge(history[history.length - 1], viz);
        break;
    case 'bar':
        renderBarChart(history, viz);
        break;
}
```

## 視覺化類型

### 📈 Chart（圖表）

適用於：連續數值數據（電流、電壓、溫度等）

**配置欄位：**
- `chart_type`: `line` | `area` | `spline`
- `color`: 建議顏色（Hex 格式）
- `show_points`: 是否顯示數據點
- `interpolation`: 插值方式

**實作範例（Chart.js）：**
```javascript
const config = {
    type: viz.chart_type === 'spline' ? 'line' : viz.chart_type,
    data: {
        labels: history.map(h => new Date(h.last_changed)),
        datasets: [{
            data: history.map(h => h.state),
            borderColor: viz.color,
            backgroundColor: viz.chart_type === 'area' ? viz.color + '40' : viz.color,
            fill: viz.chart_type === 'area',
            pointRadius: viz.show_points ? 3 : 0,
            tension: viz.interpolation === 'natural' ? 0.4 : 0
        }]
    }
};
```

### ⏱️ Timeline（時間軸）

適用於：開關狀態（switch、light、binary_sensor）

**配置欄位：**
- `on_color`: 開啟狀態顏色
- `off_color`: 關閉狀態顏色

**實作範例（ECharts）：**
```javascript
const timeRanges = history.map((h, i) => ({
    name: h.state === 'on' ? '開啟' : '關閉',
    value: [
        new Date(h.last_changed),
        new Date(history[i + 1]?.last_changed || endTime)
    ],
    itemStyle: {
        color: h.state === 'on' ? viz.on_color : viz.off_color
    }
}));
```

### 🎚️ Gauge（儀表板）

適用於：範圍數值（power_factor）

**配置欄位：**
- `min`: 最小值
- `max`: 最大值
- `color`: 顏色

### 📊 Bar（柱狀圖）

適用於：累積數據（energy）

**配置欄位：**
- `chart_type`: `bar`
- `color`: 顏色

## 顏色對照表

| device_class | 顏色 | Hex | 適用場景 |
|-------------|------|-----|---------|
| current | 橘色 | #FFA726 | 電流數據 |
| voltage | 藍色 | #42A5F5 | 電壓數據 |
| power | 綠色 | #66BB6A | 功率數據 |
| energy | 紫色 | #AB47BC | 能量數據 |
| temperature | 紅色 | #EF5350 | 溫度數據 |
| humidity | 青色 | #26C6DA | 濕度數據 |
| battery | 淺綠 | #9CCC65 | 電池數據 |
| illuminance | 黃色 | #FFEE58 | 照度數據 |

## 插值方式

| interpolation | 說明 | 適用場景 |
|--------------|------|---------|
| `linear` | 線性插值 | 一般連續數據 |
| `monotone` | 單調插值 | 平滑變化的數據 |
| `natural` | 自然曲線 | 溫度、氣壓等自然變化 |
| `step-after` | 階梯狀 | 電池百分比等階段性變化 |

## 數值精度

API 會自動根據 device_class 和 unit 格式化數值：

```javascript
// 原始狀態
"state": "34.000001847744"

// 格式化後（mA 保留 1 位小數）
"state": 34.0
```

使用 `metadata.decimal_places` 來顯示：

```javascript
const formattedValue = parseFloat(state).toFixed(metadata.decimal_places);
// "34.0"
```

## 完整範例

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <canvas id="historyChart"></canvas>
    
    <script>
    async function renderHistory(entityId) {
        // 1. 獲取數據
        const response = await fetch(`/api/smartly/history/${entityId}`);
        const envelope = await response.json();
        const data = envelope.data;
        
        const { history, metadata } = data;
        const viz = metadata.visualization;
        
        // 2. 根據類型渲染
        if (viz.type === 'chart') {
            const ctx = document.getElementById('historyChart');
            new Chart(ctx, {
                type: viz.chart_type === 'spline' ? 'line' : viz.chart_type,
                data: {
                    labels: history.map(h => new Date(h.last_changed)),
                    datasets: [{
                        label: metadata.friendly_name,
                        data: history.map(h => h.state),
                        borderColor: viz.color,
                        backgroundColor: viz.chart_type === 'area' 
                            ? viz.color + '40' 
                            : viz.color,
                        fill: viz.chart_type === 'area',
                        pointRadius: viz.show_points ? 3 : 0,
                        tension: viz.interpolation === 'natural' ? 0.4 : 0
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            title: {
                                display: true,
                                text: metadata.unit_of_measurement
                            }
                        }
                    }
                }
            });
        } else if (viz.type === 'timeline') {
            // 實作時間軸視覺化
            renderTimeline(history, viz);
        }
    }
    
    renderHistory('sensor.micro_wake_word_pzem_004t_v3_current');
    </script>
</body>
</html>
```

## 自適應主題

根據應用主題調整顏色：

```javascript
function adjustColorForTheme(color, isDarkMode) {
    if (isDarkMode) {
        // 深色模式下提高亮度
        return lightenColor(color, 20);
    }
    return color;
}

const chartColor = adjustColorForTheme(viz.color, document.body.classList.contains('dark'));
```

## 參考資料

- [History API 完整文檔](./history-api.md)
- [Chart.js 文檔](https://www.chartjs.org/)
- [ECharts 文檔](https://echarts.apache.org/)
- [Material Design 顏色系統](https://material.io/design/color)
