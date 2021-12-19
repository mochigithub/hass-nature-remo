import logging
from typing import Callable

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .common import (DOMAIN, NatureEntity, NatureUpdateCoordinator,
                     check_update, create_device_device_info)

_LOGGER = logging.getLogger(__name__)

_KEY_TO_ICON = {
    "humidity_offset": "mdi:water-percent",
    "temperature_offset": "mdi:thermometer",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Setting up number platform.")
    devices: NatureUpdateCoordinator = hass.data[DOMAIN]["devices"]
    post: Callable = hass.data[DOMAIN]["post"]

    def on_add(device: dict):
        device_info = create_device_device_info(device)
        if ("temperature_offset" in device):
            yield OffsetConfigEntity(devices, post, device, "temperature_offset", 5, 0.5, device_info)
        if ("humidity_offset" in device):
            yield OffsetConfigEntity(devices, post, device, "humidity_offset", 20, 5, device_info)

    check_update(entry, async_add_entities, devices, on_add)


class OffsetConfigEntity(NatureEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: NatureUpdateCoordinator, post: Callable, device: dict, key: str, range: float, step: float, device_info: DeviceInfo):
        super().__init__(coordinator,
                         device['id'], f"{device['id']}_{key}", device_info)
        self._attr_icon = _KEY_TO_ICON[key]
        self._attr_max_value = range
        self._attr_min_value = -range
        self._attr_name = key
        self._attr_step = step
        self._key = key
        self._post = post
        self._on_data_update(device)

    def _on_data_update(self, device: dict):
        super()._on_data_update(device)
        self._attr_value = device[self._key]

    async def async_set_value(self, value: float) -> None:
        await self._post(f"devices/{self._remo_id}/{self._key}", {"offset": value})
        self._attr_value = value
        self.async_write_ha_state()
