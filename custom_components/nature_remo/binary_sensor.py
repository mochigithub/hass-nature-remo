from datetime import datetime, timedelta, timezone
import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .common import DOMAIN, NatureUpdateCoordinator, RemoSensorEntity, check_update, create_device_device_info, str_to_datetime

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Setting up binary_sensor platform.")
    devices: NatureUpdateCoordinator = hass.data[DOMAIN]["devices"]

    def on_add(device: dict):
        device_info = create_device_device_info(device)
        if 'mo' in device['newest_events']:
            yield RemoMotionEntity(devices, device, device_info)

    check_update(entry, async_add_entities, devices, on_add)


class RemoMotionEntity(RemoSensorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.MOTION.value

    def __init__(self, coordinator: NatureUpdateCoordinator, device: dict, device_info: DeviceInfo):
        super().__init__(coordinator, device, device_info, "mo")

    def _on_data_update(self, device: dict):
        super()._on_data_update(device)
        mo: dict[str, str] = device['newest_events']['mo']
        created_at = str_to_datetime(mo['created_at'])
        limit = datetime.now(timezone.utc) - timedelta(minutes=1)
        self._attr_is_on = created_at >= limit
