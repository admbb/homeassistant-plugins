# Hitokoto Daily · 一言每日语句

[![Tests](https://github.com/admbb/homeassistant-plugins/actions/workflows/tests.yaml/badge.svg)](https://github.com/admbb/homeassistant-plugins/actions/workflows/tests.yaml)
[![Hassfest](https://github.com/admbb/homeassistant-plugins/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/admbb/homeassistant-plugins/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/admbb/homeassistant-plugins/actions/workflows/hacs.yaml/badge.svg)](https://github.com/admbb/homeassistant-plugins/actions/workflows/hacs.yaml)

Hitokoto Daily is a Home Assistant integration for fetching one sentence from the
[official Hitokoto API](https://developer.hitokoto.cn/sentence/). It includes daily
updates, local persistence, history, favorites, visual configuration, and native
Home Assistant sensors and actions.

本集成中文名称为「一言 · 每日诗句」。它每天获取一条一言，提供可视化配置、历史记录、收藏、传感器及 HA 操作服务。语句和收藏只保存在本地 HA Store，不会上传。

## Features

- Daily local-time refresh, defaulting to 00:05; no API request when a dashboard opens.
- Restore today's sentence after HA restarts.
- Choose one or more of the 12 official categories and set sentence length limits.
- Manually fetch a new sentence, with a five-second refresh cooldown.
- Persist history and favorites separately.
- Work with the built-in Markdown card and other native dashboard cards.
- English and Simplified Chinese configuration and entity names.

## Installation with HACS

1. In HACS, open **Integrations** and select **Custom repositories**.
2. Add `https://github.com/admbb/homeassistant-plugins` and choose **Integration**.
3. Download **Hitokoto Daily**, then restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and select **Hitokoto Daily**.

The repository must be public for HACS to install it. Until a public release is made, install locally by copying `custom_components/hitokoto` into your HA `custom_components` directory and restart.

## Sensors

The integration creates these sensors on one Hitokoto Daily device:

| Entity | Value |
| --- | --- |
| `sensor.hitokoto_daily` | Current sentence and metadata attributes |
| `sensor.hitokoto_author` | Author, when supplied by the API |
| `sensor.hitokoto_source` | Source title, when supplied by the API |
| `sensor.hitokoto_category` | Localized category |
| `sensor.hitokoto_last_updated` | Time the current sentence was fetched |
| `sensor.hitokoto_favorites_count` | Number of favorites |
| `sensor.hitokoto_history_count` | Number of saved history sentences |
| `sensor.hitokoto_status` | `normal`, `stale`, `error`, or `unavailable` |

The daily sentence sensor attributes include `uuid`, `type`, `category_name`, `from`,
`from_who`, `creator`, `created_at`, `length`, `source_url`, `fetched_at`, `quote_date`,
and `is_favorite`. The `source_url` attribute is omitted when the API does not return a
UUID.

## Dashboard examples

### Minimal daily sentence

```yaml
type: markdown
content: |
  ## 今日一言

  {{ states('sensor.hitokoto_daily') }}
```

### Author and source, with empty-value handling

```yaml
type: markdown
content: |
  ## 今日一言

  {{ states('sensor.hitokoto_daily') }}

  {% set author = states('sensor.hitokoto_author') %}
  {% set source = states('sensor.hitokoto_source') %}
  {% if author not in ['unknown', 'unavailable', ''] or source not in ['unknown', 'unavailable', ''] %}
  —— {{ author if author not in ['unknown', 'unavailable', ''] else '佚名' }}{% if source not in ['unknown', 'unavailable', ''] %} · {{ source }}{% endif %}
  {% endif %}

  {% set url = state_attr('sensor.hitokoto_daily', 'source_url') %}
  {% if url %}[查看原句]({{ url }}){% endif %}
```

### Sentence with a change button

```yaml
type: markdown
content: |
  ## 今日一言

  {{ states('sensor.hitokoto_daily') }}
  {% set author = states('sensor.hitokoto_author') %}
  {% set source = states('sensor.hitokoto_source') %}
  {% if author not in ['unknown', 'unavailable', ''] or source not in ['unknown', 'unavailable', ''] %}
  —— {{ author if author not in ['unknown', 'unavailable', ''] else '佚名' }}{% if source not in ['unknown', 'unavailable', ''] %} · {{ source }}{% endif %}
  {% endif %}
---
type: button
name: 换一句
icon: mdi:refresh
tap_action:
  action: perform-action
  perform_action: hitokoto.refresh
```

### Favorite button and count

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: |
      ## 今日一言

      {{ states('sensor.hitokoto_daily') }}
  - type: button
    name: 收藏当前语句
    icon: mdi:heart-plus
    tap_action:
      action: perform-action
      perform_action: hitokoto.add_favorite
  - type: entity
    entity: sensor.hitokoto_favorites_count
```

### Dark home view

```yaml
type: markdown
card_mod:
  style: |
    ha-card {
      background: linear-gradient(145deg, #171b24, #282d3a);
      color: #f1f3f8;
      border-radius: 20px;
      padding: 18px;
    }
content: |
  # ✨ 今日一言

  > {{ states('sensor.hitokoto_daily') }}

  {% set author = states('sensor.hitokoto_author') %}
  {% if author not in ['unknown', 'unavailable', ''] %}
  —— {{ author }}
  {% endif %}

  {% set url = state_attr('sensor.hitokoto_daily', 'source_url') %}
  {% if url %}[查看原句]({{ url }}){% endif %}
```

### Compact mobile view

```yaml
type: markdown
content: >-
  **今日一言**  
  {{ states('sensor.hitokoto_daily') }}  
  {% set author = states('sensor.hitokoto_author') %}{% if author not in ['unknown', 'unavailable', ''] %}—— {{ author }}{% endif %}
```

### List history or favorites in a script

The read actions return a response. In an automation or script, store it using the
Home Assistant response variable feature:

```yaml
sequence:
  - action: hitokoto.get_favorites
    response_variable: saved_quotes
```

Use `hitokoto.get_history` with an optional `limit` to return only recent history.

## Actions

| Action | Description |
| --- | --- |
| `hitokoto.refresh` | Fetch a new sentence; the five-second manual cooldown still applies. |
| `hitokoto.add_favorite` | Favorite the current sentence or a locally saved sentence by UUID. |
| `hitokoto.remove_favorite` | Remove the current or specified UUID from favorites. |
| `hitokoto.get_favorites` | Return the saved favorites list. |
| `hitokoto.get_history` | Return history newest first; accepts an optional `limit`. |
| `hitokoto.clear_history` | Requires `confirm: true`; does not clear favorites or today's sentence. |

When more than one config entry is active, include its `entry_id` with each action. When there is only one, the entry is selected automatically.

## Configuration

The initial config flow and Options Flow expose API route, timeout, retry policy, categories, length bounds, metadata preferences, daily update time, history settings, and favorite behavior. The update time uses the Home Assistant system timezone. Category `l` is labeled **抖机灵** following the official API documentation.

## Data and API use

- All user data stays in Home Assistant's local Store.
- No account, API key, or Docker service is needed.
- The selected official HTTPS endpoint is the only service contacted by the integration.
- The integration does not request data when a dashboard is viewed.
- Global and international routes, category codes, response fields, and limits follow the [official API documentation](https://developer.hitokoto.cn/sentence/).

## Development

```bash
uv sync --extra test
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov --cov-report=term-missing
```

CI also runs Home Assistant Hassfest and HACS validation. Issues and feature requests:
[GitHub Issues](https://github.com/admbb/homeassistant-plugins/issues).
