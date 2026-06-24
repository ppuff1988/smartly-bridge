# Smartly Bridge Docker Development

This folder is the local Home Assistant runtime workspace for developing the
Smartly Bridge custom integration.

## Directory layout

```text
integration/
|-- README.md
`-- config/
    |-- configuration.yaml
    `-- custom_components/
```

The integration source code stays in the repository standard path:

```text
custom_components/smartly_bridge/
```

Docker Compose mounts it into Home Assistant at:

```text
/config/custom_components/smartly_bridge
```

That means you edit code in `custom_components/smartly_bridge/`, then restart
Home Assistant to load the latest integration code.

## Start Home Assistant

Run this from the repository root:

```bash
docker compose up -d
```

Open Home Assistant:

```text
http://localhost:8123
```

View logs:

```bash
docker compose logs -f homeassistant
```

Restart after code changes:

```bash
docker compose restart homeassistant
```

Stop the environment:

```bash
docker compose down
```

## Git hygiene

Most files created under `integration/config/` are Home Assistant runtime state
and are intentionally ignored by git. The tracked files here are only the
minimal development scaffold.
