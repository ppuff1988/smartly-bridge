HA_CONTAINER ?= smartly-bridge-ha
HA_SERVICE ?= homeassistant
HA_COMPONENT_SRC ?= custom_components/smartly_bridge
HA_COMPONENT_DEST ?= /config/custom_components/smartly_bridge

.PHONY: help dev up sync copy restart logs down ps shell

help:
	@printf '%s\n' 'Home Assistant development targets:'
	@printf '  %-10s %s\n' 'dev' 'Start HA, copy Smartly Bridge, and restart HA'
	@printf '  %-10s %s\n' 'sync' 'Copy Smartly Bridge into HA and restart HA'
	@printf '  %-10s %s\n' 'copy' 'Copy Smartly Bridge into the running HA container'
	@printf '  %-10s %s\n' 'restart' 'Restart the HA service'
	@printf '  %-10s %s\n' 'logs' 'Follow HA logs'
	@printf '  %-10s %s\n' 'down' 'Stop the Docker Compose environment'
	@printf '  %-10s %s\n' 'ps' 'Show Docker Compose service status'
	@printf '  %-10s %s\n' 'shell' 'Open a shell inside the HA container'

dev: up sync

up:
	docker compose up -d

sync: copy restart

copy:
	docker exec $(HA_CONTAINER) mkdir -p $(HA_COMPONENT_DEST)
	docker cp $(HA_COMPONENT_SRC)/. $(HA_CONTAINER):$(HA_COMPONENT_DEST)/

restart:
	docker compose restart $(HA_SERVICE)

logs:
	docker compose logs -f $(HA_SERVICE)

down:
	docker compose down

ps:
	docker compose ps

shell:
	docker exec -it $(HA_CONTAINER) sh
