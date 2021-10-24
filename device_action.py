"""Provides device automations for Alarm control panel."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from .common import DOMAIN

ACTION_TYPES = {
    "arm_away",
    "arm_home",
    "arm_night",
    "arm_vacation",
    "disarm",
    "trigger",
}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_TYPE): "send_command",
        vol.Required(ATTR_COMMAND): cv.string,
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict]:
    actions = await toggle_entity.async_get_actions(hass, device_id, DOMAIN)

    registry = await entity_registry.async_get_registry(hass)

    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != "remote":
            continue

        state = hass.states.get(entry.entity_id)
        if not state.attributes.get("signals") and not state.attributes.get("buttons"): continue

        actions.append({
            CONF_TYPE: "send_command",
            CONF_DEVICE_ID: device_id,
            CONF_ENTITY_ID: entry.entity_id,
            CONF_DOMAIN: DOMAIN,
        })

    return actions


async def async_get_action_capabilities(hass, config):
    """List action capabilities."""
    state = hass.states.get(config[ATTR_ENTITY_ID])
    signals = state.attributes.get("signals", [])
    buttons = state.attributes.get("buttons", [])

    cmd = {}
    cmd.update({v["id"]: v["name"] for v in signals})
    cmd.update({v["name"]: v["label"] for v in buttons})

    extra_fields = {
        vol.Optional(ATTR_COMMAND): vol.In(cmd),
    }
    return {"extra_fields": vol.Schema(extra_fields)}


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    await hass.services.async_call(
        "remote", "send_command",
        service_data={ATTR_COMMAND: config[ATTR_COMMAND]},
        context=context,
        target={ATTR_DEVICE_ID: config[ATTR_DEVICE_ID]},
    )
