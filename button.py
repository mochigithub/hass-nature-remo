import logging
from typing import Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .common import (DOMAIN, ICONS_MAP, AppliancesUpdateCoordinator, NatureEntity,
                     check_update, create_appliance_device_info)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Setting up button platform.")
    appliances: AppliancesUpdateCoordinator = hass.data[DOMAIN]["appliances"]
    post: Callable = hass.data[DOMAIN]["post"]

    def on_add(appliance: dict):
        device_info = create_appliance_device_info(appliance)
        for signal in appliance["signals"]:
            yield SignalButtonEntity(appliances, post, signal, device_info)

    check_update(entry, async_add_entities, appliances, on_add)


class SignalButtonEntity(NatureEntity, ButtonEntity):
    def __init__(self, appliances: AppliancesUpdateCoordinator, post: Callable, signal: str, device_info: DeviceInfo):
        super().__init__(appliances, signal["id"], signal["id"], device_info)
        self._attr_icon = ICONS_MAP.get(signal["image"])
        self._attr_name = signal["name"]
        self._post = post

    @property
    def available(self):
        return True

    async def async_press(self):
        await self._post(f"signals/{self._remo_id}/send")
