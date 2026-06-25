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

Docker Compose mounts `integration/config/` into Home Assistant at:

```text
/config
```

That means Home Assistant loads the synced copy from
`/config/custom_components/smartly_bridge`. After starting Home Assistant, copy
the integration source into the running container:

```bash
make dev
```

Run `make sync` after editing code in `custom_components/smartly_bridge/`.

## Start Home Assistant

Run this from the repository root:

```bash
make dev
```

Open Home Assistant:

```text
http://localhost:8123
```

View logs:

```bash
make logs
```

Restart after code changes:

```bash
make sync
```

Stop the environment:

```bash
make down
```

## Git hygiene

Most files created under `integration/config/` are Home Assistant runtime state
and are intentionally ignored by git. The tracked files here are only the
minimal development scaffold.
