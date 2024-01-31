"""Support for Nature Remo E energy sensor."""
from datetime import datetime, timedelta, timezone
import logging
from typing import Callable
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfEnergy
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .common import DOMAIN, AppliancesUpdateCoordinator, NatureEntity, NatureUpdateCoordinator, RemoSensorEntity, check_update, create_appliance_device_info, create_device_device_info, modify_utc_z

_LOGGER = logging.getLogger(__name__)

_ENERGY_UNITS = {
    0x00: 1,
    0x01: 0.1,
    0x02: 0.01,
    0x03: 0.001,
    0x04: 0.0001,
    0x0A: 10,
    0x0B: 100,
    0x0C: 1000,
    0x0D: 10000,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable):
    """Set up the Nature Remo E sensor."""
    _LOGGER.debug("Setting up sensor platform.")
    devices: NatureUpdateCoordinator = hass.data[DOMAIN]["devices"]
    appliances: AppliancesUpdateCoordinator = hass.data[DOMAIN]["appliances"]

    def on_add_device(device):
        device_info = create_device_device_info(device)
        newest_events = device['newest_events']
        if 'te' in newest_events:
            yield RemoSensorValEntity(devices, device, device_info, 'te', SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)
        if 'hu' in newest_events:
            yield RemoSensorValEntity(devices, device, device_info, 'hu', SensorDeviceClass.HUMIDITY, PERCENTAGE)
        if 'il' in newest_events:
            yield RemoSensorValEntity(devices, device, device_info, 'il', SensorDeviceClass.ILLUMINANCE, LIGHT_LUX)

    def on_add_appliances(appliance):
        if appliance["type"] != "EL_SMART_METER":
            return
        device_info = create_appliance_device_info(appliance)
        yield PowerEntity(appliances, appliance, device_info)
        yield EnergyEntity(appliances, appliance, device_info, 224)
        yield EnergyEntity(appliances, appliance, device_info, 227)

    check_update(entry, async_add_entities, devices, on_add_device)
    check_update(entry, async_add_entities, appliances, on_add_appliances)

    async_add_entities([RateLimitEntity(devices.rate_limit)])


class RateLimitEntity(CoordinatorEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:api"
    _attr_name = "Nature Remo Rate Limit"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unique_id = "rate-limit-remaining"

    def __init__(self, coordinator: DataUpdateCoordinator):
        super().__init__(coordinator)
        self._attr_native_value = self.coordinator.data["remaining"]

    def _handle_coordinator_update(self):
        self._attr_native_value = self.coordinator.data["remaining"]
        return super()._handle_coordinator_update()


class RemoSensorValEntity(RemoSensorEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NatureUpdateCoordinator, device: dict, device_info: DeviceInfo, key: str, device_class: SensorDeviceClass, unit_of_measurement: str):
        super().__init__(coordinator, device, device_info, key)
        self._attr_device_class = device_class
        self._attr_device_info = device_info
        self._attr_native_unit_of_measurement = unit_of_measurement

    def _on_data_update(self, device: dict):
        super()._on_data_update(device)
        self._attr_native_value = device["newest_events"][self._key]["val"]


class SmartMeterEntity(NatureEntity, SensorEntity):
    coordinator: AppliancesUpdateCoordinator

    def __init__(self, coordinator: AppliancesUpdateCoordinator, appliance: dict, device_info: DeviceInfo, key: int):
        super().__init__(coordinator,
                         appliance["id"], f"{appliance['id']}-{key}", device_info)
        self._key = key
        self._on_data_update(appliance)

    def _on_data_update(self, appliance: dict):
        super()._on_data_update(appliance)
        echonetlite_properties = appliance["smart_meter"]["echonetlite_properties"]
        updated_at = modify_utc_z(
            next(v for v in echonetlite_properties)["updated_at"])
        self._attr_extra_state_attributes = {
            "updated_at": updated_at,
        }
        updated_at = datetime.fromisoformat(updated_at)
        if self._attr_available:
            limit = datetime.now(timezone.utc) - timedelta(seconds=125)
            self._attr_available = updated_at >= limit


class PowerEntity(SmartMeterEntity):
    """Implementation of a Nature Remo E sensor."""

    _attr_device_class = SensorDeviceClass.POWER.value
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: AppliancesUpdateCoordinator, appliance: dict, device_info: DeviceInfo):
        super().__init__(coordinator, appliance, device_info, 231)
        self._attr_name = f"{appliance['nickname']} instantaneous"

    def _on_data_update(self, appliance: dict):
        super()._on_data_update(appliance)
        echonetlite_properties = appliance["smart_meter"]["echonetlite_properties"]
        self._attr_native_value = next(
            value["val"] for value in echonetlite_properties if value["epc"] == 231
        )


class EnergyEntity(SmartMeterEntity):
    """Implementation of a Nature Remo E sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    # breaking changes on core side
    # https://github.com/home-assistant/core/commit/1aaf78ef9944ded259298afbdbedcc07c90b80b0
    # also _attr_[native]_unit_of_measurement

    def __init__(self, coordinator: AppliancesUpdateCoordinator, appliance: dict, device_info: DeviceInfo, key: int):
        super().__init__(coordinator, appliance, device_info, key)
        echonetlite_properties = appliance["smart_meter"]["echonetlite_properties"]
        name = next(
            value["name"] for value in echonetlite_properties if value["epc"] == key
        ).split("_")[0]
        self._attr_name = f"{appliance['nickname']} {name} cumulative"

    def _on_data_update(self, appliance: dict):
        super()._on_data_update(appliance)
        echonetlite_properties = appliance["smart_meter"]["echonetlite_properties"]
        cumulative_electric_energy = int(next(
            value["val"] for value in echonetlite_properties if value["epc"] == self._key
        ))
        coefficient = int(next(
            value["val"] for value in echonetlite_properties if value["epc"] == 211
        ))
        cumulative_electric_energy_unit = int(next(
            value["val"] for value in echonetlite_properties if value["epc"] == 225
        ))
        self._attr_native_value = cumulative_electric_energy * \
            coefficient * _ENERGY_UNITS[cumulative_electric_energy_unit]
