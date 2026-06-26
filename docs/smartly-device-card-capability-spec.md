# Smartly Device Card and Capability Specification

> Version: 2026-06-26
>
> Scope: Smartly Platform customer-facing PWA device cards, device class planning, capability mapping, Bridge labeling, and future device expansion rules.

## 1. Purpose

Smartly will continue to receive new smart home devices from Home Assistant through Smartly Bridge. These devices may come from different vendors, use different model names, and expose different combinations of states, attributes, and controls.

The UI must not be designed around each model name. Instead, Smartly should use a capability-driven system:

```text
Home Assistant entity
-> Bridge synced entity
-> domain
-> capabilities
-> Smartly device class
-> card template
-> dashboard card / detail control surface
```

This lets Smartly support new devices by adding or adjusting a device class mapping, not by redesigning the dashboard for every new model.

## 2. Design Goals

- Make common home controls usable from the dashboard.
- Keep device cards readable within 3-5 seconds.
- Support new device types without rewriting the whole UI.
- Collapse diagnostic child entities into one logical device card where possible.
- Hide Home Assistant and Bridge internals from normal customers.
- Keep one clear primary purpose per card.
- Show important health metadata, such as battery, signal, offline state, and last update.
- Keep full advanced control on the device detail page.
- Preserve Smartly brand rules: off-white page background, white cards, neutral borders, 8-12px card radius, and yellow only for active/action states.

## 3. Non-Goals

- Do not create one custom card per vendor model.
- Do not expose raw Home Assistant `entity_id` in normal UI.
- Do not show every attribute on dashboard cards.
- Do not use Bridge labels as the only source of UI classification.
- Do not place high-risk domains such as locks, alarms, access control, or cameras in MVP dashboard controls.

## 4. Core Concepts

### 4.1 Domain

`domain` is the technical category from Home Assistant or Bridge.

Examples:

| Domain          | Meaning                                     |
| --------------- | ------------------------------------------- |
| `light`         | Light entity                                |
| `switch`        | On/off switch entity                        |
| `sensor`        | Numeric or text sensor                      |
| `binary_sensor` | Boolean sensor                              |
| `fan`           | Fan entity                                  |
| `cover`         | Curtain, blind, garage door, or other cover |
| `climate`       | Air conditioner, thermostat, HVAC           |
| `scene`         | Scene trigger                               |
| `script`        | Script trigger                              |
| `button`        | Stateless button trigger                    |

`domain` is useful but not enough. For example, a `light` may be only on/off, dimmable, color temperature capable, or full RGB capable.

### 4.2 Capability

`capabilities` describe what the entity can show or do.

Examples:

| Capability           | Meaning                        |
| -------------------- | ------------------------------ |
| `on_off`             | Can turn on/off                |
| `brightness`         | Supports brightness control    |
| `color_temp`         | Supports color temperature     |
| `rgb_color`          | Supports color control         |
| `open_close`         | Supports open/close            |
| `stop`               | Supports stop action           |
| `position`           | Supports position percentage   |
| `target_temperature` | Supports target temperature    |
| `fan_speed`          | Supports fan speed or preset   |
| `temperature`        | Reports temperature            |
| `humidity`           | Reports humidity               |
| `battery`            | Reports battery level          |
| `signal_strength`    | Reports signal strength        |
| `occupancy`          | Reports presence or motion     |
| `contact`            | Reports open/closed contact    |
| `event`              | Reports button or action event |
| `run`                | Can run scene/script           |

Capabilities are the foundation of UI behavior. A card should render controls only when the capability exists.

### 4.3 Smartly Device Class

`device_class` is Smartly's UI-level category. It groups devices by user meaning, not by vendor or raw domain.

Examples:

| Device Class          | Purpose                                                   |
| --------------------- | --------------------------------------------------------- |
| `smart_light`         | Light with dimming, color temperature, or RGB control     |
| `simple_light_switch` | A light controlled by a simple on/off switch              |
| `simple_switch`       | Generic on/off switch, plug, relay, or appliance switch   |
| `fan_control`         | Fan with on/off and optional speed control                |
| `environment_sensor`  | Temperature, humidity, AQI, or similar environment values |
| `presence_sensor`     | Motion, occupancy, or presence detection                  |
| `contact_sensor`      | Door/window open-close sensor                             |
| `button_device`       | Stateless button or remote event device                   |
| `multi_button_device` | Multi-key switch panel or multi-channel button device     |
| `cover_control`       | Curtain, blind, shade, or cover control                   |
| `climate_control`     | AC, thermostat, or HVAC control                           |
| `scene_trigger`       | Scene or script run action                                |
| `unknown_device`      | Fallback read-only device                                 |

### 4.4 Card Template

`card_template` decides the visual and interaction structure.

Examples:

| Card Template        | Used By                                                |
| -------------------- | ------------------------------------------------------ |
| `control_card`       | One primary action, usually on/off                     |
| `light_card`         | Light on/off plus optional brightness summary          |
| `metric_card`        | Sensor card with one large value and secondary metrics |
| `binary_state_card`  | Open/closed, detected/clear, active/inactive           |
| `event_card`         | Latest event from button or remote                     |
| `multi_control_card` | Two or more channels in one physical device            |
| `cover_card`         | Open/close/stop and optional position                  |
| `climate_card`       | Current temperature, mode, target temperature          |
| `scene_card`         | Run scene/script action                                |
| `unknown_card`       | Safe read-only fallback                                |

## 5. Data Model Shape

The API should expose enough normalized data for the UI to render without knowing vendor-specific details.

Recommended shape:

```json
{
  "id": "platform-public-device-id",
  "name": "Living Room Temperature",
  "domain": "sensor",
  "device_class": "environment_sensor",
  "icon": "mdi:thermometer",
  "state": "24.6",
  "status": "online",
  "area": {
    "id": "area-id",
    "name": "Living Room"
  },
  "capabilities": ["temperature", "humidity", "battery", "signal_strength"],
  "attributes": {
    "unit_of_measurement": "°C",
    "humidity": 61,
    "battery": 84,
    "signal_strength": -58
  },
  "presentation": {
    "card_template": "metric_card",
    "primary_metric": "temperature",
    "secondary_metrics": ["humidity", "battery"],
    "dashboard_priority": 40,
    "favorite": false
  },
  "last_updated_at": "2026-06-26T10:30:00+08:00"
}
```

Rules:

- `id` must be a Platform opaque public ID.
- `domain` should preserve the source technical domain.
- `device_class` should be Smartly normalized.
- `capabilities` should be explicit and stable.
- `attributes` may preserve raw useful metadata, but the dashboard should not render raw attributes directly.
- `presentation` may guide UI layout, but should not be required for safe fallback rendering.

### 5.1 Bridge Current Implementation Contract

This section documents what Smartly Bridge currently implements in `/api/smartly/sync/states`.

Implemented endpoint envelope:

```json
{
  "states": [],
  "count": 0
}
```

- `states` is the list of allowed entity state objects.
- `count` is the number of objects in `states`.

Implemented response shape per state:

```json
{
  "entity_id": "sensor.living_temperature",
  "state": "24.6",
  "attributes": {
    "device_class": "temperature",
    "unit_of_measurement": "°C",
    "friendly_name": "Living Temperature",
    "humidity": 61,
    "battery": 84,
    "linkquality": 236,
    "signal_strength": 236,
    "signal_unit": "lqi"
  },
  "last_changed": "2026-06-26T04:00:00+00:00",
  "last_updated": "2026-06-26T04:00:00+00:00",
  "icon": "mdi:thermometer",
  "name": "Living Temperature",
  "domain": "sensor",
  "device_class": "environment_sensor",
  "capabilities": ["temperature", "humidity", "battery", "signal_strength"],
  "status": "online",
  "presentation": {
    "card_template": "metric_card",
    "primary_metric": "temperature",
    "secondary_metrics": ["humidity", "battery"],
    "dashboard_priority": 40,
    "favorite": false
  }
}
```

Top-level `device_class` is the Smartly normalized UI class. Home Assistant's raw sensor `device_class` remains in `attributes.device_class`.

Implemented top-level fields:

| Field | Type | Current behavior |
| ----- | ---- | ---------------- |
| `entity_id` | string | Home Assistant entity id. |
| `state` | string \| null | Formatted state value. Numeric sensor states may be rounded by Bridge precision rules. |
| `attributes` | object | JSON-safe Home Assistant attributes after Bridge numeric and signal normalization. |
| `last_changed` | string \| null | Home Assistant `last_changed` ISO timestamp. |
| `last_updated` | string \| null | Home Assistant `last_updated` ISO timestamp. |
| `icon` | string \| null | `attributes.icon`, entity registry icon, original icon, or Bridge domain default. |
| `name` | string | `attributes.friendly_name`; falls back to `entity_id`. |
| `domain` | string | Domain parsed from `entity_id`. |
| `device_class` | string | Smartly normalized class inferred by Bridge. |
| `capabilities` | string[] | Stable capability list inferred by Bridge. |
| `status` | string | `offline` when state is `null`, `unknown`, or `unavailable`; otherwise `online`. |
| `presentation` | object | UI hints built from `device_class` and `capabilities`. |

Implemented capability inference:

| Domain | Current capability rules |
| ------ | ------------------------ |
| `light` | Always `on_off`; adds `brightness` when `attributes.brightness` exists or `supported_color_modes` contains `brightness`; adds `color_temp` when `attributes.color_temp`, `min_mireds`, `max_mireds`, or `supported_color_modes` indicates color temperature; adds `rgb_color` when RGB-like color modes or `rgb_color`, `hs_color`, `xy_color` exist. |
| `switch` | Always `on_off`. |
| `sensor` | Adds `attributes.device_class` when it is one of the implemented environment capabilities; also adds any implemented environment capability that appears as an attribute key. |
| `binary_sensor` | Adds presence/contact capabilities when `attributes.device_class` matches them or when the capability appears as an attribute key. |
| `cover` | Always `open_close` and `stop`; adds `position` when `current_position` or `position` exists. |
| `climate` | Adds `target_temperature` from `temperature`, `target_temp`, or `target_temperature`; adds `hvac_mode` from `hvac_modes` or `hvac_mode`; adds `fan_speed` from `fan_modes` or `fan_mode`. |
| `fan` | Always `on_off`; adds `fan_speed` when `percentage`, `preset_mode`, or `preset_modes` exists. |
| `scene` / `script` | Always `run`. |
| `button` | Always `event`. |
| Unsupported domains | No capabilities. |

Implemented environment capabilities:

```text
temperature, humidity, air_quality, aqi, co2, carbon_dioxide,
carbon_monoxide, pm25, pm10, illuminance, pressure, atmospheric_pressure
```

Implemented health capabilities:

```text
battery, signal_strength
```

`battery` and `signal_strength` are appended to any domain when the normalized attributes contain those keys.

Implemented signal normalization:

| Source attribute | Normalized attributes |
| ---------------- | --------------------- |
| `signal_strength` | Keeps `signal_strength`; adds `signal_unit` with empty string when missing. |
| `rssi` | Adds `signal_strength` from `rssi`; sets `signal_unit` to `dBm`. |
| `linkquality` | Adds `signal_strength` from `linkquality`; sets `signal_unit` to `lqi`. |
| `link_quality` | Adds `signal_strength` from `link_quality`; sets `signal_unit` to `lqi`. |
| `lqi` | Adds `signal_strength` from `lqi`; sets `signal_unit` to `lqi`. |

Implemented Smartly device class classification:

| Condition | Current `device_class` |
| --------- | ---------------------- |
| Domain is `alarm_control_panel`, `camera`, or `lock` | `unknown_device` |
| `light` with `brightness`, `color_temp`, or `rgb_color` | `smart_light` |
| `light` without advanced light capability | `simple_light_switch` |
| `switch` with `on_off` | `simple_switch` |
| `fan` | `fan_control` |
| `sensor` with any environment capability | `environment_sensor` |
| `binary_sensor` with `occupancy`, `motion`, or `presence` | `presence_sensor` |
| `binary_sensor` with `contact`, `opening`, `door`, or `window` | `contact_sensor` |
| `button` | `button_device` |
| `cover` with any cover capability | `cover_control` |
| `climate` with any climate capability | `climate_control` |
| `scene` or `script` with `run` | `scene_trigger` |
| Otherwise | `attributes.smartly_device_class` when present, else `unknown_device` |

Implemented `smartly.class.<device_class>` label override:

- Bridge reads labels from the Home Assistant entity registry.
- The first supported `smartly.class.*` label may override automatic classification only when the domain and capability shape are compatible.
- `smartly.class.unknown_device` is always allowed.
- `smartly.class.fan_control` is allowed for `fan` or `switch` entities with `on_off`.
- `smartly.class.simple_light_switch` and `smartly.class.simple_switch` are currently allowed for `switch` entities with `on_off`.
- `smartly.class.smart_light` is allowed for `light` entities with `brightness`, `color_temp`, or `rgb_color`.
- `smartly.class.environment_sensor` is allowed for `sensor` entities with an implemented environment capability.
- `smartly.class.presence_sensor` is allowed for `binary_sensor` entities with an implemented presence capability.
- `smartly.class.contact_sensor` is allowed for `binary_sensor` entities with an implemented contact capability.
- `smartly.class.cover_control` is allowed for `cover` entities with any inferred capability.
- `smartly.class.climate_control` is allowed for `climate` entities with any inferred capability.
- `smartly.class.scene_trigger` is allowed for `scene` or `script` entities with `run`.
- Unsupported or unsafe overrides are ignored.

Implemented card templates:

| `device_class` | Current `presentation.card_template` |
| -------------- | ------------------------------------ |
| `smart_light` | `light_card` |
| `simple_light_switch` | `control_card` |
| `simple_switch` | `control_card` |
| `fan_control` | `control_card` |
| `environment_sensor` | `metric_card` |
| `presence_sensor` | `binary_state_card` |
| `contact_sensor` | `binary_state_card` |
| `button_device` | `event_card` |
| `multi_button_device` | `multi_control_card` |
| `cover_control` | `cover_card` |
| `climate_control` | `climate_card` |
| `scene_trigger` | `scene_card` |
| `unknown_device` | `unknown_card` |

Implemented presentation defaults:

- Every presentation includes `card_template`, `dashboard_priority`, and `favorite`.
- Default `dashboard_priority` is `50`.
- Default `favorite` is `false`.
- `environment_sensor` sets `dashboard_priority` to `40`.
- `environment_sensor.presentation.primary_metric` is the first implemented environment capability present, in the environment capability order listed above.
- `environment_sensor.presentation.secondary_metrics` chooses up to two values from `humidity`, `battery`, `signal_strength`, `co2`, `pm25`, `illuminance`, excluding the primary metric.
- `smart_light.presentation.primary_metric` is `brightness` when the capability exists.
- `smart_light.presentation.secondary_metrics` chooses up to two values from `battery`, `signal_strength`, excluding the primary metric.
- Other classes use `battery` and `signal_strength` as secondary metrics when present.

## 6. Dashboard Card Information Rules

A dashboard device card should show:

1. Device icon and name.
2. Room or area.
3. One primary state, value, or action.
4. Up to two secondary metrics.
5. Availability or permission state when needed.
6. Last update only when stale, offline, warning, or relevant.

Dashboard cards should not show:

- Full raw attributes.
- More than one primary control purpose.
- Advanced settings such as RGB picker, automation binding, calibration, or sensitivity.
- Vendor model names unless needed for troubleshooting.

Full capability controls belong on the device detail page.

## 7. Device Class Registry

### 7.1 `smart_light`

Use for lights with at least one advanced light capability.

Detection:

- `domain = light`
- Has one or more of: `brightness`, `color_temp`, `rgb_color`

Dashboard:

- Primary: on/off state.
- Secondary: brightness percentage if available.
- Primary control: toggle.
- Optional priority card control: brightness slider.
- Do not show full color picker on normal dashboard cards.

Detail:

- Toggle.
- Brightness slider.
- Color temperature control if available.
- RGB/color picker if available.
- Current color preview if available.
- Supported mode list when Bridge reports multiple light modes.
- Recent activity.

### 7.2 `simple_light_switch`

Use for light circuits represented as switch entities.

Detection:

- `domain = switch`
- Has `on_off`
- User or mapping identifies it as controlling a light.

Dashboard:

- Primary: on/off.
- Primary control: toggle.
- Optional secondary: last updated, battery, signal if the physical switch reports it.

Detail:

- Toggle.
- Health metadata.
- Recent activity.

### 7.3 `simple_switch`

Use for plugs, relays, fan switches without speed, appliance switches, and generic on/off controls.

Detection:

- `domain = switch`
- Has `on_off`
- Not classified as light, fan, or specialized appliance.

Dashboard:

- Primary: on/off.
- Primary control: toggle.

Detail:

- Toggle.
- Health metadata.
- Recent activity.

### 7.4 `fan_control`

Use for fans or fan-related controls.

Detection:

- `domain = fan`, or
- `domain = switch` with user or Bridge class override as fan.

Dashboard:

- Primary: on/off.
- Secondary: speed if available.
- Primary control: toggle.

Detail:

- Toggle.
- Speed or preset mode when available.
- Recent activity.

### 7.5 `environment_sensor`

Use for environmental numeric sensors.

Detection:

- `domain = sensor`
- Has one or more of: `temperature`, `humidity`, `air_quality`, `co2`, `pm25`, `illuminance`

Dashboard:

- Primary: one large metric, usually temperature if present.
- Secondary: humidity, battery, or signal.
- No control button.

Detail:

- All known metrics.
- Battery and signal.
- Last update.
- Optional trend/history in later phases.

### 7.6 `presence_sensor`

Use for motion, occupancy, or presence detection.

Detection:

- `domain = binary_sensor`
- Has `occupancy`, `motion`, or `presence`

Dashboard:

- Primary: detected / clear, or occupied / vacant.
- Secondary: last detected time, battery, signal.
- No control button.

Detail:

- Current state.
- Last changed time.
- Battery and signal.
- Recent events.

### 7.7 `contact_sensor`

Use for door/window open-close sensors.

Detection:

- `domain = binary_sensor`
- Has `contact`, `opening`, `door`, or `window`

Dashboard:

- Primary: open / closed.
- Secondary: last changed, battery.
- No control button.

Detail:

- Current state.
- Last changed time.
- Battery and signal.
- Recent events.

### 7.8 `button_device`

Use for stateless single-button devices or event-only entities.

Detection:

- `domain = button`, or
- `domain = sensor` / `event` source with `event` capability

Dashboard:

- Primary: latest event, such as single press, double press, hold.
- Secondary: last event time, battery.
- Optional action: run linked scene when configured.

Detail:

- Event history.
- Linked scene/action mapping.
- Battery and signal.

### 7.9 `multi_button_device`

Use for physical devices with multiple channels or buttons, such as two-key panels.

Detection:

- Multiple related entities share one Bridge device ID, or
- Bridge mapping groups them into one logical device, or
- Manual class override is set.

Dashboard:

- Option A: one `multi_control_card` with two compact channels.
- Option B: split into separate dashboard cards if each channel controls a high-frequency device.

Default recommendation:

- Use one card in device lists.
- Allow users to pin individual channels to dashboard later.

Detail:

- Physical layout matching the real device when possible.
- Each channel shows state, action, or linked target.
- Recent events and operations.

### 7.10 `cover_control`

Use for curtains, blinds, shades, and covers.

Detection:

- `domain = cover`
- Has `open_close`, `stop`, or `position`

Dashboard:

- Primary: open / closed / position percentage.
- Controls: open, close, stop when available.
- Avoid tiny position sliders on compact cards unless card is large.

Detail:

- Open, close, stop.
- Position control when available.
- Recent activity.

### 7.11 `climate_control`

Use for air conditioners, thermostats, and HVAC devices.

Detection:

- `domain = climate`
- Has `target_temperature`, `hvac_mode`, or related climate capabilities.

Dashboard:

- Primary: current temperature or target temperature.
- Secondary: mode and fan speed.
- Controls: compact target temperature stepper only on priority card.

Detail:

- Power/mode.
- Target temperature.
- Fan speed.
- HVAC mode.
- Recent activity.

### 7.12 `scene_trigger`

Use for scenes and scripts.

Detection:

- `domain = scene` or `domain = script`
- Has `run`

Dashboard:

- Primary: scene/script name.
- Control: run button.
- State: ready, running, failed if available.

Detail:

- Run action.
- Last run result.
- Recent activity.

### 7.13 `unknown_device`

Use when Smartly cannot classify the entity safely.

Detection:

- No supported device class mapping found.

Dashboard:

- Read-only card.
- Show name, room, current state, and last updated.
- No control action.

Detail:

- Read-only state.
- Useful attributes.
- Diagnostic info for owner/support only.

## 8. Card Template Registry

### 8.1 Shared Card Anatomy

Every card should follow the same anatomy:

```text
+--------------------------------+
| [Icon] Device Name       State |
| Room name                      |
|                                |
| Primary readout / control      |
| Secondary metric · metric      |
| Disabled reason if needed      |
+--------------------------------+
```

Required slots:

- `icon`
- `name`
- `area_name`
- `primary_readout`
- `status`

Optional slots:

- `primary_control`
- `secondary_metrics`
- `last_updated`
- `disabled_reason`
- `warning_reason`

### 8.2 `control_card`

For simple on/off devices.

```text
+------------------------------+
| [Icon] Coffee Plug        Off |
| Kitchen                      |
|                              |
| Off                    [Toggle]
| Updated 2m ago               |
+------------------------------+
```

### 8.3 `metric_card`

For sensor-first devices.

```text
+------------------------------+
| [Icon] Temperature            |
| Living Room                  |
|                              |
| 24.6°C                       |
| Humidity 61% · Battery 84%   |
+------------------------------+
```

### 8.4 `binary_state_card`

For binary sensors.

```text
+------------------------------+
| [Icon] Door Sensor            |
| Entry                         |
|                              |
| Closed                        |
| Battery 88% · Updated 1m ago |
+------------------------------+
```

### 8.5 `light_card`

For lights.

```text
+------------------------------+
| [Icon] Living Light        On |
| Living Room                  |
|                              |
| On · 72%               [Toggle]
| Color controls in detail     |
+------------------------------+
```

### 8.6 `multi_control_card`

For multi-channel physical controls.

```text
+------------------------------+
| [Icon] Wall Switch            |
| Living Room                  |
|                              |
| Left: Main Light        [On] |
| Right: Accent Light    [Off] |
+------------------------------+
```

### 8.7 `unknown_card`

For safe fallback.

```text
+------------------------------+
| [Icon] New Device             |
| Living Room                  |
|                              |
| State: active                 |
| View details                  |
+------------------------------+
```

## 9. Bridge Label Rules

Bridge and Home Assistant labels should be used for exposure, grouping, and optional overrides. They should not replace automatic capability mapping.

Recommended labels:

| Label                          | Meaning                                        |
| ------------------------------ | ---------------------------------------------- |
| `smartly`                      | Expose this entity/device to Smartly           |
| `smartly.favorite`             | Suggest dashboard priority                     |
| `smartly.hidden`               | Sync but hide from normal device lists         |
| `smartly.class.<device_class>` | Manual device class override                   |
| `smartly.group.<group_name>`   | Group related entities into one logical device |
| `smartly.dashboard`            | Suggest dashboard visibility                   |

Rules:

- `smartly` controls exposure.
- `smartly.class.*` is an override, not the default path.
- If override conflicts with capabilities, Platform should prefer safety and fall back to read-only or limited controls.
- Customer-facing UI should not show raw label names by default.
- Owner/support diagnostic UI may show labels for troubleshooting.

## 10. Classification Strategy

Classification should follow this priority:

1. Safety exclusions and unsupported high-risk domains.
2. Explicit platform or Bridge override.
3. Domain and capability inference.
4. Attribute-based refinement.
5. Fallback to `unknown_device`.

Example:

```text
domain = light
capabilities include brightness, color_temp
=> device_class = smart_light
=> card_template = light_card
```

Example:

```text
domain = switch
capabilities include on_off
label = smartly.class.simple_light_switch
=> device_class = simple_light_switch
=> card_template = control_card
```

Example:

```text
domain = sensor
capabilities include temperature, humidity, battery
=> device_class = environment_sensor
=> card_template = metric_card
```

## 11. Device Detail Page Rules

The device detail page is where Smartly can show complete capability-specific controls.

Detail pages should show:

- Device name.
- Room/area.
- Device class.
- Availability.
- Last updated and last changed.
- Full control surface for supported capabilities.
- Battery, signal, and diagnostic metadata when available.
- Recent operations or events.
- Permission/availability explanation when controls are disabled.

Detail pages may show more raw metadata than dashboard cards, but should still avoid exposing Bridge internals to normal users.

## 12. Status and Disabled States

Device controls must be disabled or read-only when:

- Bridge is offline.
- Device state is `offline`, `unavailable`, or unknown in a blocking way.
- User role is Viewer or otherwise lacks control permission.
- Capability does not support the requested action.
- Device class is `unknown_device`.
- Action is outside MVP allowed domains.

Disabled UI must explain why:

| Reason                 | User Message Direction                       |
| ---------------------- | -------------------------------------------- |
| Bridge offline         | Controls paused until Bridge reconnects      |
| Device unavailable     | Device is unavailable                        |
| No permission          | Your role can view but not control           |
| Unsupported capability | This control is not supported                |
| Unknown device         | View-only until Smartly supports this device |

## 13. Example Device Mappings

### 13.1 TabP L530E

The exact mapping depends on what Bridge reports. If it is a controllable light or switch:

| Input           | Value                                                    |
| --------------- | -------------------------------------------------------- |
| Expected domain | `light` or `switch`                                      |
| Device class    | `smart_light`, `simple_light_switch`, or `simple_switch` |
| Card template   | `light_card` or `control_card`                           |
| Dashboard       | On/off plus brightness if available                      |
| Detail          | Full capabilities reported by Bridge                     |

### 13.2 Sonoff SNZB-06P

Likely presence or occupancy sensor.

| Input           | Value                                                         |
| --------------- | ------------------------------------------------------------- |
| Expected domain | `binary_sensor`                                               |
| Device class    | `presence_sensor`                                             |
| Card template   | `binary_state_card`                                           |
| Dashboard       | Occupied/clear, last detected, battery                        |
| Detail          | Occupancy state, last changed, battery, signal, event history |

### 13.3 Sonoff SNZB-04P

Likely door/window contact sensor.

| Input           | Value                                               |
| --------------- | --------------------------------------------------- |
| Expected domain | `binary_sensor`                                     |
| Device class    | `contact_sensor`                                    |
| Card template   | `binary_state_card`                                 |
| Dashboard       | Open/closed, battery                                |
| Detail          | State, last changed, battery, signal, event history |

### 13.4 Aqara D1 Two-Key Switch

Multi-channel physical switch.

| Input           | Value                                                            |
| --------------- | ---------------------------------------------------------------- |
| Expected domain | `switch`, `light`, or event entities                             |
| Device class    | `multi_button_device` or multiple `simple_light_switch` entities |
| Card template   | `multi_control_card`                                             |
| Dashboard       | Left/right channel states or pinned channel cards                |
| Detail          | Physical two-key layout, channel mapping, recent operations      |

Recommendation:

- In device list: one grouped multi-control card.
- On dashboard: allow each channel to be pinned separately later.

### 13.5 Aqara Temperature and Humidity Sensor

Environment sensor.

| Input           | Value                                                     |
| --------------- | --------------------------------------------------------- |
| Expected domain | `sensor`                                                  |
| Device class    | `environment_sensor`                                      |
| Card template   | `metric_card`                                             |
| Dashboard       | Temperature as primary, humidity and battery as secondary |
| Detail          | Temperature, humidity, battery, signal, last updated      |

### 13.6 Fan Switch

Simple fan switch unless speed is available.

| Input           | Value                                                |
| --------------- | ---------------------------------------------------- |
| Expected domain | `switch` or `fan`                                    |
| Device class    | `fan_control`                                        |
| Card template   | `control_card`                                       |
| Dashboard       | On/off, speed if available                           |
| Detail          | Toggle, speed/preset when available, recent activity |

### 13.7 General Light Switch

Simple light switch.

| Input           | Value                                    |
| --------------- | ---------------------------------------- |
| Expected domain | `switch`                                 |
| Device class    | `simple_light_switch`                    |
| Card template   | `control_card`                           |
| Dashboard       | On/off                                   |
| Detail          | Toggle, health metadata, recent activity |

### 13.8 Smart Bulb

Advanced light.

| Input           | Value                                            |
| --------------- | ------------------------------------------------ |
| Expected domain | `light`                                          |
| Device class    | `smart_light`                                    |
| Card template   | `light_card`                                     |
| Dashboard       | On/off and brightness                            |
| Detail          | Toggle, brightness, color temperature, RGB color |

## 14. Adding a New Device Class

When a new class of devices appears, add support in this order:

1. Identify source `domain`.
2. List actual capabilities from Bridge.
3. Decide whether an existing `device_class` can represent it.
4. If not, add a new `device_class`.
5. Choose or add a `card_template`.
6. Define dashboard primary readout.
7. Define at most two secondary metrics.
8. Define allowed controls.
9. Define disabled-state behavior.
10. Define detail page controls.
11. Add test examples for classification and UI presentation.

Do not add a new class only because the vendor model is new. Add a new class only when the device has a new user meaning or control pattern.

## 15. Registry Change Checklist

Before adding a new class or card template, verify:

- Does an existing class already cover this device?
- Is there a clear user-facing name?
- Is the primary state obvious?
- Is the dashboard action safe?
- What happens when Bridge is offline?
- What happens when the user is Viewer?
- What happens if battery or signal is missing?
- What is the fallback if capabilities are incomplete?
- Does the card remain readable on mobile?
- Does the class avoid raw vendor-specific assumptions?

## 16. API and Storage Implications

Existing platform data already includes:

- `entities.domain`
- `entities.icon`
- `entities.capabilities_json`
- `entity_states.state`
- `entity_states.attributes_json`

Recommended additions or derivations:

- `device_class`: stored or derived from domain, capabilities, labels, and overrides.
- `presentation_json`: optional UI hints such as favorite, primary metric, secondary metrics, grouping, and dashboard priority.
- `logical_device_group`: optional grouping key for multi-entity physical devices.

The server should be the source of truth for classification when possible. The frontend may have a fallback presentation mapper, but should not contain the only copy of classification logic long term.

## 17. Frontend Implementation Rules

The frontend should render from a normalized presentation model:

```text
DeviceSummary
-> DevicePresentation
-> CardTemplate component
```

Recommended `DevicePresentation` fields:

```json
{
  "device_class": "environment_sensor",
  "card_template": "metric_card",
  "title": "Living Room Temperature",
  "subtitle": "Living Room",
  "primary_readout": "24.6°C",
  "secondary_metrics": ["Humidity 61%", "Battery 84%"],
  "primary_control": null,
  "status": "online",
  "disabled_reason": null
}
```

Rules:

- Components should not parse raw attributes directly when a normalized value exists.
- Unknown or unsupported devices must still render safely.
- Dashboard cards should keep stable dimensions across state changes.
- Detail views can render richer controls based on capabilities.

## 18. Visual Direction

Device cards should follow Smartly dashboard visual rules:

- Page background: `#F6F8FC`.
- Card background: white or high-opacity white surface.
- Border: neutral line color.
- Radius: 8-12px for dashboard cards.
- Primary text: Smartly Ink.
- Purple/blue: icon emphasis, focus, selected states, data highlights.
- Yellow: active/action detail only, such as switch-on thumb or small active marker.
- Warning should use semantic warning color, not brand yellow.
- Icons must be paired with text or values; do not rely on icon-only meaning.

## 19. Recommended MVP Scope

MVP should support these classes:

- `smart_light`
- `simple_light_switch`
- `simple_switch`
- `fan_control`
- `environment_sensor`
- `presence_sensor`
- `contact_sensor`
- `multi_button_device`
- `cover_control`
- `climate_control`
- `scene_trigger`
- `unknown_device`

MVP should exclude direct controls for:

- Locks.
- Alarm/security panels.
- Access control.
- Camera streaming.
- Automation editing.
- Full Home Assistant tunnel behavior.

Unsupported or high-risk entities may appear as read-only where useful.

## 20. Screenshot-Based Card Class Specification

本段落依照參考截圖逐類制定卡片規格。截圖中的畫面是 entity 粒度，會把同一個實體裝置拆成許多卡片，例如「溫濕度感應器」底下有氣溫、濕度、氣壓、電量、電壓、Last seen、Linkquality。

Smartly 的正式 UI 必須把這些 entity 轉成「一般使用者看得懂的裝置卡片」。每一類 entity 仍要有明確規格，但它們不一定都會成為 dashboard 主卡。

### 20.1 Screenshot Entity Type Matrix

| 截圖卡片類型          | Example              | Smartly Entity Kind               | Dashboard Treatment                | Detail Treatment        |
| --------------------- | -------------------- | --------------------------------- | ---------------------------------- | ----------------------- |
| 溫度                  | 氣溫 25.1°C          | `temperature_metric`              | environment card primary           | 主要數值                |
| 濕度                  | 濕度 44.04%          | `humidity_metric`                 | environment card secondary         | 主要數值                |
| 氣壓                  | 氣壓 991.00 hPa      | `pressure_metric`                 | secondary only if useful           | 主要/進階數值           |
| 電量百分比            | 電量 100%            | `battery_percent_health`          | secondary health metric            | 裝置健康                |
| 電量狀態              | 電量 正常            | `battery_status_health`           | warning only when abnormal         | 裝置健康                |
| 電壓                  | 電壓 3,015 mV        | `voltage_diagnostic`              | hidden by default                  | 診斷                    |
| Linkquality           | 236 lqi / 255 lqi    | `signal_quality_diagnostic`       | hidden unless weak                 | 診斷                    |
| Last seen             | 10 分鐘前 / 5 分鐘前 | `last_seen_health`                | only if stale/offline              | 裝置健康                |
| 人體存在              | 已觸發               | `presence_state`                  | presence card primary              | 狀態                    |
| Occupancy value       | Occupancy 15         | `occupancy_value_diagnostic`      | hidden by default                  | 診斷/進階               |
| Illuminance           | bright               | `illuminance_metric`              | presence card secondary            | 主要/進階數值           |
| Occupancy sensitivity | low                  | `presence_setting`                | hidden                             | 設定/診斷               |
| Update status         | 已最新               | `update_status_health`            | warning only when update available | 裝置健康                |
| 門窗狀態              | 門 關閉              | `contact_state`                   | contact card primary               | 狀態                    |
| 風扇燈                | 4 秒前               | `light_control` or `button_event` | depends on capability              | 控制/事件               |
| 風扇按鈕              | 8 秒前               | `button_event`                    | event card if user-facing          | 事件                    |
| 無線雙鍵電量          | 電量 100%            | `battery_percent_health`          | secondary health metric            | 裝置健康                |
| 無線雙鍵電壓          | 電壓 3,175 mV        | `voltage_diagnostic`              | hidden by default                  | 診斷                    |
| 新區塊                | 關閉 / 14 秒前       | `unknown_or_binary_state`         | unknown/read-only until classified | raw state + diagnostics |

### 20.2 Source Entity Card vs Smartly Card

| Card Type              | Purpose                                      | Who Sees It                | Example                      |
| ---------------------- | -------------------------------------------- | -------------------------- | ---------------------------- |
| Source entity card     | 忠實顯示 Bridge/HA/Zigbee2MQTT 的單一 entity | Owner/support 診斷         | Linkquality 255 lqi          |
| Smartly logical card   | 聚合成一般使用者理解的裝置                   | 所有一般使用者             | 門窗感應器：關閉 · 電量 100% |
| Smartly detail section | 顯示完整數值、健康、事件、診斷               | 一般使用者 + owner/support | 電壓、Last seen、更新狀態    |

Rule:

- Dashboard 預設顯示 Smartly logical card。
- Source entity card 只能出現在診斷視圖、裝置詳情頁、或尚未分類的 fallback。
- 同一個 physical device 的健康資訊不可在 dashboard 分裂成多張主卡。

### 20.3 Card Size and Layout

截圖中的卡片是橫向 compact entity card。Smartly 可以保留這種視覺密度，但內容要改成 logical card。

| Size                  | Use                            | Desktop        | Mobile                  |
| --------------------- | ------------------------------ | -------------- | ----------------------- |
| Compact entity row    | 診斷或詳情頁 entity 列表       | 2 columns      | 1 column                |
| Standard logical card | dashboard 裝置主卡             | 1-2 grid units | full width              |
| Rich logical card     | 優先裝置、多控制裝置、燈光控制 | 2-4 grid units | full width / expandable |

Standard logical card anatomy:

```text
+--------------------------------------+
| [Icon] Device Name            Status |
| Room / Group                          |
|                                      |
| Primary value or state                |
| Secondary metric · Health metric      |
+--------------------------------------+
```

Rules:

- Icon slot 固定寬度。
- Title 最多兩行，dashboard 優先一行。
- Primary value 比 title 更醒目。
- Secondary metrics 最多兩個。
- 控制卡的 touch target 不小於 44px。

### 20.4 Environment Sensor Group

Applies to screenshot group: `溫濕度感應器`.

Source entities:

| Source Entity | Entity Kind                 | Dashboard Role       | Detail Role     |
| ------------- | --------------------------- | -------------------- | --------------- |
| 氣溫          | `temperature_metric`        | Primary metric       | Main metric     |
| 濕度          | `humidity_metric`           | Secondary metric     | Main metric     |
| 氣壓          | `pressure_metric`           | Optional secondary   | Extended metric |
| 電量          | `battery_percent_health`    | Secondary health     | Health          |
| 電壓          | `voltage_diagnostic`        | Hidden               | Diagnostic      |
| Last seen     | `last_seen_health`          | Stale/offline only   | Health          |
| Linkquality   | `signal_quality_diagnostic` | Warning only if weak | Diagnostic      |

Dashboard card:

```text
+--------------------------------------+
| [Thermometer] 溫濕度感應器             |
| 客廳                                  |
|                                      |
| 25.1°C                               |
| 濕度 44% · 電量 100%                 |
+--------------------------------------+
```

Detail layout:

```text
主要數值
- 氣溫 25.1°C
- 濕度 44.04%
- 氣壓 991.00 hPa

裝置健康
- 電量 100%
- Last seen 10 分鐘前

診斷
- 電壓 3,015 mV
- Linkquality 236 lqi
```

Rules:

- `temperature` is the default primary metric.
- `humidity` is the default secondary metric.
- `battery` is preferred over `pressure` on dashboard if battery is available.
- `pressure` can replace battery only for weather-oriented cards.
- `voltage` and `linkquality` are diagnostics, not dashboard primary content.

### 20.5 Presence Sensor Group

Applies to screenshot group: `人體存在感應器`.

Source entities:

| Source Entity         | Entity Kind                  | Dashboard Role                   | Detail Role         |
| --------------------- | ---------------------------- | -------------------------------- | ------------------- |
| 人體存在              | `presence_state`             | Primary state                    | Main state          |
| Occupancy value       | `occupancy_value_diagnostic` | Hidden                           | Diagnostic/advanced |
| Illuminance           | `illuminance_metric`         | Secondary metric                 | Metric              |
| Last seen             | `last_seen_health`           | Stale/offline only               | Health              |
| Linkquality           | `signal_quality_diagnostic`  | Warning only if weak             | Diagnostic          |
| Occupancy sensitivity | `presence_setting`           | Hidden                           | Setting/diagnostic  |
| Update status         | `update_status_health`       | Warning only if update available | Health              |

Dashboard card:

```text
+--------------------------------------+
| [Presence] 人體存在感應器       已偵測 |
| 書房                                  |
|                                      |
| 已偵測                               |
| 光線 bright · 6 分鐘前                |
+--------------------------------------+
```

Detail layout:

```text
狀態
- 人體存在：已偵測
- 光線：bright

進階值
- Occupancy value：15
- Occupancy sensitivity：low

裝置健康
- Last seen：6 分鐘前
- Update status：已最新

診斷
- Linkquality：255 lqi
```

Rules:

- Customer-facing text should be `有人`, `無人`, `已偵測`, or `未偵測`.
- Raw occupancy value must not be the dashboard primary state.
- `occupancy_sensitivity` is a setting, not a dashboard metric.
- `illuminance` may appear as secondary when it helps explain automation behavior.

### 20.6 Contact Sensor Group

Applies to screenshot group: `門窗感應器`.

Source entities:

| Source Entity | Entity Kind                 | Dashboard Role             | Detail Role |
| ------------- | --------------------------- | -------------------------- | ----------- |
| 門            | `contact_state`             | Primary state              | Main state  |
| 電量狀態      | `battery_status_health`     | Warning only when abnormal | Health      |
| 電量百分比    | `battery_percent_health`    | Secondary health           | Health      |
| 電壓          | `voltage_diagnostic`        | Hidden                     | Diagnostic  |
| Last seen     | `last_seen_health`          | Stale/offline only         | Health      |
| Linkquality   | `signal_quality_diagnostic` | Warning only if weak       | Diagnostic  |

Dashboard card:

```text
+--------------------------------------+
| [Door] 門窗感應器              關閉   |
| 玄關                                  |
|                                      |
| 關閉                                 |
| 電量 100% · 5 分鐘前                 |
+--------------------------------------+
```

Detail layout:

```text
狀態
- 門窗：關閉

裝置健康
- 電量狀態：正常
- 電量：100%
- Last seen：5 分鐘前

診斷
- 電壓：3,100 mV
- Linkquality：255 lqi
```

Rules:

- `open` must be visually stronger than `closed`.
- `closed` should be calm and neutral.
- Battery status appears on dashboard only when abnormal or missing.
- Battery percentage can be dashboard secondary metric.

### 20.7 Battery Health Class

Applies to screenshot entities:

- `溫濕度感應器 電量`
- `無線雙鍵 電量`
- `門窗感應器 電量`
- `門窗感應器 電量 正常`

Entity kinds:

- `battery_percent_health`
- `battery_status_health`

Dashboard rules:

- Show as secondary metric: `電量 100%`.
- If battery is low, promote to warning chip: `電量低`.
- If battery status says normal, do not use a separate dashboard card.
- If both status and percentage exist, dashboard uses percentage; detail shows both.

Detail rules:

```text
裝置健康
- 電量：100%
- 電量狀態：正常
```

Visual rules:

- Green battery icon can indicate healthy battery in detail.
- Do not use brand yellow for low battery warning.
- Low battery must include text, not only color.

### 20.8 Voltage Diagnostic Class

Applies to screenshot entities:

- `溫濕度感應器 電壓 3,015 mV`
- `無線雙鍵 電壓 3,175 mV`
- `門窗感應器 電壓 3,100 mV`

Entity kind:

- `voltage_diagnostic`

Dashboard rules:

- Hidden by default.
- May appear only when owner opens diagnostic mode.
- Never use voltage as primary dashboard content.

Detail rules:

```text
診斷
- 電壓：3,015 mV
```

Reason:

- Voltage is useful for debugging battery devices, but most customers understand battery percentage better.

### 20.9 Signal Quality Diagnostic Class

Applies to screenshot entities:

- `Linkquality 236 lqi`
- `Linkquality 255 lqi`

Entity kind:

- `signal_quality_diagnostic`

Dashboard rules:

- Hidden when signal is healthy.
- Promote to warning only when signal is weak or stale.
- Suggested wording: `訊號弱`, not raw `236 lqi`.

Detail rules:

```text
診斷
- Linkquality：236 lqi
- Signal quality：Good / Weak / Unknown
```

Rules:

- Keep raw LQI/RSSI values in detail.
- Map raw values to customer-facing labels when shown outside diagnostic context.

### 20.10 Last Seen Health Class

Applies to screenshot entities:

- `Last seen 10 分鐘前`
- `Last seen 6 分鐘前`
- `Last seen 5 分鐘前`

Entity kind:

- `last_seen_health`

Dashboard rules:

- Hidden when recent and healthy.
- Show only if it explains freshness, stale state, or offline state.
- Use relative time: `5 分鐘前`.

Detail rules:

```text
裝置健康
- Last seen：5 分鐘前
- Last updated：exact timestamp if available
```

Threshold recommendation:

| Device Type         | Dashboard Shows Last Seen When           |
| ------------------- | ---------------------------------------- |
| Battery sensor      | Stale beyond expected reporting interval |
| Contact sensor      | Stale or offline                         |
| Presence sensor     | Useful as secondary event freshness      |
| Button/event device | Always useful as last event time         |

### 20.11 Illuminance Metric Class

Applies to screenshot entity:

- `人體存在感應器 Illuminance bright`

Entity kind:

- `illuminance_metric`

Dashboard rules:

- Secondary metric on presence sensor cards.
- If it is a dedicated lux sensor, it may become primary metric.
- Prefer customer wording: `光線 bright` or localized `明亮`.

Detail rules:

```text
主要/進階數值
- Illuminance：bright
```

### 20.12 Presence Setting Class

Applies to screenshot entity:

- `人體存在感應器 Occupancy sensitivity low`

Entity kind:

- `presence_setting`

Dashboard rules:

- Never show by default.
- Not a state card.

Detail rules:

- Show in settings or diagnostics section.
- If editable later, render as a select/segmented control.

```text
設定
- Occupancy sensitivity：low
```

### 20.13 Update Status Health Class

Applies to screenshot entity:

- `人體存在感應器 已最新`

Entity kind:

- `update_status_health`

Dashboard rules:

- Hidden when latest/current.
- Show warning only when update is available, failed, or required.

Detail rules:

```text
裝置健康
- Update status：已最新
```

### 20.14 Fan, Fan Light, and Button Event Group

Applies to screenshot group: `usb-fan`.

Source entities:

| Source Entity | Possible Entity Kind              | Dashboard Role                                              |
| ------------- | --------------------------------- | ----------------------------------------------------------- |
| 風扇燈        | `light_control` or `button_event` | Control if light capability exists; event if only timestamp |
| 風扇按鈕      | `button_event`                    | Event card or action binding                                |

Classification rule:

- If entity has `on_off`, classify as control.
- If entity only reports time/event, classify as `button_event`.
- If both belong to the same physical device, group under one device detail page.

Dashboard card when controllable:

```text
+--------------------------------------+
| [Fan] USB Fan                         |
| 桌面                                  |
|                                      |
| 風扇 Off                       [Toggle]
| 風扇燈 On                     [Toggle]
+--------------------------------------+
```

Dashboard card when event-only:

```text
+--------------------------------------+
| [Button] 風扇按鈕                      |
| 桌面                                  |
|                                      |
| 最近觸發 8 秒前                       |
| Linked scene: None                    |
+--------------------------------------+
```

Rules:

- Button event cards are not toggles.
- Event-only entities can show last event time.
- If a button is bound to a scene, show the scene name and a run/edit entry depending on permissions.

### 20.15 Wireless Dual-Key Group

Applies to screenshot group: `無線雙鍵`.

Visible source entities in screenshot:

| Source Entity | Entity Kind              | Dashboard Role                         | Detail Role |
| ------------- | ------------------------ | -------------------------------------- | ----------- |
| 電量          | `battery_percent_health` | Secondary health if device card exists | Health      |
| 電壓          | `voltage_diagnostic`     | Hidden                                 | Diagnostic  |

Expected related entities, if Bridge reports them:

| Expected Entity    | Entity Kind    | Dashboard Role         |
| ------------------ | -------------- | ---------------------- |
| Left key event     | `button_event` | Event or linked action |
| Right key event    | `button_event` | Event or linked action |
| Left relay/switch  | `on_off`       | Channel control        |
| Right relay/switch | `on_off`       | Channel control        |

Dashboard card:

```text
+--------------------------------------+
| [Switch] 無線雙鍵                      |
| 客廳                                  |
|                                      |
| 左鍵 最近觸發 2 分鐘前                 |
| 右鍵 最近觸發 8 分鐘前                 |
| 電量 100%                             |
+--------------------------------------+
```

If it controls two channels:

```text
+--------------------------------------+
| [Switch] 無線雙鍵                      |
| 客廳                                  |
|                                      |
| 左鍵 On                        [Toggle]
| 右鍵 Off                       [Toggle]
+--------------------------------------+
```

Rules:

- Do not show battery and voltage as the only dashboard cards if no key/channel entity is visible.
- If only battery/voltage are available, show the physical device as `diagnostic_only_device` in owner/support view.
- For normal customers, hide diagnostic-only devices unless there is a warning.

### 20.16 Unknown or New Block Group

Applies to screenshot group: `新區塊`.

Source entity:

- Shows icon, relative time, and state `關閉`.

Entity kind:

- `unknown_or_binary_state`

Dashboard card:

```text
+--------------------------------------+
| [Unknown] 新區塊                      |
| 未分類                                |
|                                      |
| 關閉                                 |
| 14 秒前                              |
+--------------------------------------+
```

Rules:

- If the entity has only state and no safe capability, render read-only.
- If later mapped to `switch`, `light`, `binary_sensor`, or another domain, replace this with the correct class.
- Owner/support detail should show source domain, raw state, attributes, and suggested mapping.

### 20.17 Diagnostic-Only Device Rule

Some physical devices may sync only health entities in early development, such as battery and voltage, but no user-facing state/control.

Rules:

- Normal dashboard should not show diagnostic-only devices.
- Device list may show them under a collapsed `Diagnostics` or `Needs mapping` section for owner.
- Detail page can show raw entities and suggested mapping.
- If any diagnostic entity is abnormal, a warning can appear in Home Summary or device health summary.

### 20.18 Screenshot-Derived Display Priority

When multiple entities exist for one logical device, Smartly chooses dashboard content by this priority:

1. Primary control state: on/off, open/closed, occupied/clear.
2. Primary metric: temperature, humidity, illuminance, pressure.
3. User-relevant secondary metric: humidity, brightness, battery.
4. Freshness only when relevant: last seen, last event.
5. Warning health: low battery, weak signal, unavailable, update available.
6. Diagnostic values: voltage, linkquality, raw occupancy value.

Only the first 2-3 relevant items should appear on dashboard. The rest goes to detail.

## 21. Smart Light Control Specification

燈光是 MVP 的主要控制類型，必須支援從簡單開關到智慧燈泡的漸進式能力。

### 21.1 Light Capability Levels

| Level             | Capabilities                                      | Device Class          | Dashboard                                 |
| ----------------- | ------------------------------------------------- | --------------------- | ----------------------------------------- |
| L1 Simple light   | `on_off`                                          | `simple_light_switch` | Toggle                                    |
| L2 Dimmable light | `on_off`, `brightness`                            | `smart_light`         | Toggle + brightness summary               |
| L3 Tunable white  | `on_off`, `brightness`, `color_temp`              | `smart_light`         | Toggle + brightness; color temp in detail |
| L4 Color light    | `on_off`, `brightness`, `color_temp`, `rgb_color` | `smart_light`         | Toggle + brightness; color in detail      |

### 21.2 Dashboard Light Card

Normal dashboard card:

```text
+--------------------------------------+
| [Light] 客廳主燈                On    |
| 客廳                                  |
|                                      |
| On · 72%                       [Toggle]
| 色溫 4200K                             |
+--------------------------------------+
```

Rules:

- Always show on/off state.
- Show brightness percentage when available.
- Show color temperature only as text or small indicator on normal card.
- Do not put full color picker on a compact dashboard card.
- Toggle must be reachable with one tap.

### 21.3 Priority Light Card

Priority card 可放更完整但仍克制的控制：

```text
+--------------------------------------+
| [Light] 客廳主燈                On    |
| 客廳                                  |
|                                      |
| 亮度 72%                              |
| [----------●------]                   |
| 暖白 4200K                            |
| [Warm] [Neutral] [Cool]        [Power]|
+--------------------------------------+
```

Rules:

- 只能在 priority device 或 detail preview 使用。
- Brightness slider 可以出現在 priority card。
- 色溫用 segmented preset 優先於精細 slider。
- RGB 顏色最多顯示目前顏色 swatch，不放完整 picker。

### 21.4 Light Detail Page

Detail page 必須支援完整 light controls：

```text
Header
- 裝置名稱
- 房間
- 狀態
- Last updated

Controls
- Power toggle
- Brightness slider
- Color temperature slider or preset
- Color picker / swatches
- Current color preview

Device health
- Battery if applicable
- Signal if applicable
- Last seen if applicable

Activity
- 最近操作紀錄
```

### 21.5 Light Control Mapping

| UI Control        | Required Capability    | Action Payload Direction           |
| ----------------- | ---------------------- | ---------------------------------- |
| Power toggle      | `on_off`               | `turn_on` / `turn_off`             |
| Brightness slider | `brightness`           | `turn_on` with `brightness`        |
| Color temperature | `color_temp`           | `turn_on` with `color_temp_kelvin` |
| Color control     | `hs_color`             | `turn_on` with `hs_color`          |
| Preset scene      | `run` or scene binding | Run scene/script                   |

Rules:

- If a light is off and user changes brightness/color, Smartly may turn it on only if the action is explicit in UI.
- Failed Bridge actions must not be shown as successful.
- Optimistic UI is allowed only with rollback and visible error handling.
- Unsupported controls must be hidden, not disabled, unless hiding would confuse the user.

### 21.6 Light Action Payloads

Smartly light controls should send Home Assistant-compatible action payloads through Platform/Bridge. Brightness, color temperature, and color all use `turn_on` with additional data.

Brightness:

```json
{
  "action": "turn_on",
  "data": {
    "brightness": 191
  }
}
```

Brightness rules:

- Home Assistant brightness range is `0-255`.
- UI brightness is displayed as `0-100%`.
- Convert UI percent to HA brightness with `round(percent / 100 * 255)`.
- Example: `75%` -> `191`.
- Clamp values before sending: below `0` becomes `0`, above `100` becomes `100`.
- If UI uses `0%` as an off gesture, prefer sending `turn_off` instead of `turn_on` with `brightness: 0`.

Color temperature:

```json
{
  "action": "turn_on",
  "data": {
    "color_temp_kelvin": 3500
  }
}
```

Color temperature rules:

- UI should display Kelvin values or user-friendly presets such as warm, neutral, cool.
- Send Kelvin using `color_temp_kelvin`.
- Clamp to the device-supported min/max Kelvin range when Bridge reports it.
- If min/max is unknown, keep presets conservative.

Color:

```json
{
  "action": "turn_on",
  "data": {
    "hs_color": [260, 100]
  }
}
```

Color rules:

- Use `hs_color` for color-capable lights.
- Hue range is `0-360`.
- Saturation range is `0-100`.
- Clamp hue and saturation before sending.
- UI color picker should store/send `[hue, saturation]`, not RGB, unless Bridge explicitly maps RGB to HS.

## 22. Summary

Smartly should treat new devices as combinations of capabilities and user-facing device classes, not as isolated vendor models.

The stable expansion model is:

```text
Capability Registry
+ Device Class Registry
+ Card Template Registry
+ Safe Unknown Fallback
```

With this structure, future device support usually requires adding a mapping and a presentation rule, not redesigning the dashboard.
