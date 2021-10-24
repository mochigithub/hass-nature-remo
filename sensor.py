"""Support for Nature Remo E energy sensor."""
from datetime import datetime, timedelta, timezone
import logging
from typing import Callable
from homeassistant.config_entries import ConfigEntry

from homeassistant.const import (
    POWER_WATT,
    DEVICE_CLASS_POWER,
)
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .common import DOMAIN, AppliancesUpdateCoordinator, NatureEntity, check_update, create_appliance_device_info, modify_utc_z

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable):
    """Set up the Nature Remo E sensor."""
    _LOGGER.debug("Setting up sensor platform.")
    appliances: AppliancesUpdateCoordinator = hass.data[DOMAIN]["appliances"]

    def on_add_appliances(appliance):
        if appliance["type"] != "EL_SMART_METER":
            return
        device_info = create_appliance_device_info(appliance)
        yield PowerEntity(appliances, appliance, device_info)

    check_update(entry, async_add_entities, appliances, on_add_appliances)

class SmartMeterEntity(NatureEntity, SensorEntity):
    coordinator: AppliancesUpdateCoordinator

    def __init__(self, coordinator: AppliancesUpdateCoordinator, appliance: dict, device_info: DeviceInfo, key: int):
        super().__init__(coordinator, appliance["id"], f"{appliance['id']}-{key}", device_info)
        self._key = key
        self._on_data_update(appliance)

    def _on_data_update(self, appliance: dict):
        super()._on_data_update(appliance)
        echonetlite_properties = appliance["smart_meter"]["echonetlite_properties"]
        updated_at = modify_utc_z(next(v for v in echonetlite_properties)["updated_at"])
        self._attr_extra_state_attributes = {
            "updated_at": updated_at,
        }
        updated_at = datetime.fromisoformat(updated_at)
        if self._attr_available:
            limit = datetime.now(timezone.utc) - timedelta(seconds=125)
            self._attr_available = updated_at >= limit

class PowerEntity(SmartMeterEntity):
    """Implementation of a Nature Remo E sensor."""

    _attr_device_class = DEVICE_CLASS_POWER
    _attr_native_unit_of_measurement = POWER_WATT
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, coordinator: AppliancesUpdateCoordinator, appliance: dict, device_info: DeviceInfo):
        super().__init__(coordinator, appliance, device_info, 231)
        self._attr_name = f"{appliance['nickname']} instantaneous"

    def _on_data_update(self, appliance: dict):
        super()._on_data_update(appliance)
        echonetlite_properties = appliance["smart_meter"]["echonetlite_properties"]
        self._attr_native_value = next(
            value["val"] for value in echonetlite_properties if value["epc"] == 231
        )
