"""The Nature Remo integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from datetime import datetime
from homeassistant.helpers import device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_ACCESS_TOKEN

from .common import DOMAIN, RESOURCE, AppliancesUpdateCoordinator, NatureUpdateCoordinator, create_appliance_device_info, create_device_device_info

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "climate"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Nature Remo component."""
    _LOGGER.debug("Setting up Nature Remo component.")
    session = async_get_clientsession(hass)
    dr = device_registry.async_get(hass)
    hass.data[DOMAIN] = {}

    rate_limit = DataUpdateCoordinator(hass, _LOGGER, name="Nature Remo rate limit")
    devices = NatureUpdateCoordinator(hass, _LOGGER, entry, session, rate_limit, "devices")
    appliances = AppliancesUpdateCoordinator(hass, _LOGGER, entry, session, rate_limit)

    def update_device_info():
        if not devices.last_update_success:
            return
        for device in devices.data.values():
            dr.async_get_or_create(
                config_entry_id=entry.entry_id,
                **create_device_device_info(device),
            )
    def update_appliance_info():
        if not appliances.last_update_success:
            return
        for appliance in appliances.data.values():
            dr.async_get_or_create(
                config_entry_id=entry.entry_id,
                **create_appliance_device_info(appliance),
            )

    await devices.async_config_entry_first_refresh()
    await appliances.async_config_entry_first_refresh()
    update_device_info()
    update_appliance_info()
    entry.async_on_unload(devices.async_add_listener(update_device_info))
    entry.async_on_unload(appliances.async_add_listener(update_appliance_info))

    async def post(path: str, data = None):
        _LOGGER.debug("Trying to request post:%s, data:%s", path, data)
        access_token = entry.data[CONF_ACCESS_TOKEN]
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await session.post(
            f"{RESOURCE}/{path}", data=data, headers=headers
        )
        if response.status == 401:
            raise ConfigEntryAuthFailed()
        if "x-rate-limit-remaining" in response.headers:
            remaining = int(response.headers.get("x-rate-limit-remaining"))
            reset = datetime.fromtimestamp(int(response.headers.get("x-rate-limit-reset")))
            rate_limit.async_set_updated_data({"remaining":remaining, "reset":reset})
        if response.status != 200:
            raise UpdateFailed(f"status code: {response.status}")
        return await response.json()

    hass.data[DOMAIN]["devices"] = devices
    hass.data[DOMAIN]["appliances"] = appliances
    hass.data[DOMAIN]["post"] = post

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
