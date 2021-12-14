import asyncio
import logging
from typing import Callable, Iterable
from homeassistant.config_entries import ConfigEntry

from homeassistant.components.remote import SUPPORT_ACTIVITY, SUPPORT_DELETE_COMMAND, RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from .common import DOMAIN, AppliancesUpdateCoordinator, NatureEntity, check_update, create_appliance_device_info

_LOGGER = logging.getLogger(__name__)

_ACTIVITY_FILTER = [
    "night",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Setting up remote platform.")
    appliances: AppliancesUpdateCoordinator = hass.data[DOMAIN]["appliances"]
    post: Callable = hass.data[DOMAIN]["post"]

    def on_add(appliance: dict):
        if appliance["type"] != "IR" and appliance["type"] != "LIGHT" and appliance["type"] != "TV":
            return
        device_info = create_appliance_device_info(appliance)
        yield NatureRemoIR(appliances, post, appliance, device_info)

    check_update(entry, async_add_entities, appliances, on_add)


class NatureRemoIR(NatureEntity, RemoteEntity):
    _attr_assumed_state = True
    _attr_is_on = None
    _attr_supported_features = SUPPORT_DELETE_COMMAND
    _aptype = None

    def __init__(self, appliances: AppliancesUpdateCoordinator, post: Callable, appliance: dict, device_info: DeviceInfo):
        super().__init__(appliances,
                         appliance["id"], appliance["id"], device_info)
        self._attr_name = appliance["nickname"]
        self._post = post
        if appliance["type"] == "LIGHT":
            self._aptype = "light"
            self._attr_supported_features |= SUPPORT_ACTIVITY
            self._attr_icon = "hass:lightbulb"
        elif appliance["type"] == "TV":
            self._aptype = "tv"
            self._attr_icon = "mdi:television"
        self._on_data_update(appliance)

    async def async_delete_command(self, command: str, **kwargs):
        await self._post(f"signals/{command}/delete")

    async def async_send_command(self, command: Iterable[str], delay_secs: str = "0", num_repeats: str = "1", **kwargs):
        delay_secs = float(delay_secs)
        num_repeats = int(num_repeats)
        signals: dict = self._attr_extra_state_attributes["signals"]
        buttons = self._attr_extra_state_attributes.get("buttons")
        if buttons is not None:
            buttons: list[str] = [b["name"] for b in buttons]
        while True:
            for id in command:
                if buttons is not None and id in buttons:
                    state = await self._post(f"appliances/{self._remo_id}/{self._aptype}", {"button": id})
                    self._on_post_response(state)
                    self.async_write_ha_state()
                else:
                    await self._post(f"signals/{id}/send")
                    image = next((v["image"]
                                 for v in signals if v["id"] == id), None)
                    if image == "ico_on":
                        self._attr_is_on = True
                        self.async_write_ha_state()
                    elif image == "ico_off":
                        self._attr_is_on = False
                        self.async_write_ha_state()
                    elif image == "ico_io":
                        self._attr_is_on = not self._attr_is_on
                        self.async_write_ha_state()
            num_repeats -= 1
            if num_repeats <= 0:
                break
            await asyncio.sleep(delay_secs)

    async def async_turn_off(self, activity: str = None, **kwargs):
        buttons = self._attr_extra_state_attributes.get("buttons")
        if buttons is not None:
            state = await self._async_send_button(buttons, activity, ["off", "onoff", "power"])
            if state is not None:
                self._attr_is_on = activity is not None
                self._on_post_response(state)
                self._async_write_ha_state()
                return
        signals: dict = self._attr_extra_state_attributes["signals"]
        signal = next((v for v in signals if v["image"] == "ico_off"), None)
        if signal is None:
            signal = next((v for v in signals if v["image"] == "ico_io"), None)
        if signal is not None:
            await self._post(f"signals/{signal['id']}/send")
        self._attr_is_on = False
        if self._aptype == "light":
            self._attr_current_activity = None
        self.async_write_ha_state()

    async def async_turn_on(self, activity: str = None, **kwargs):
        buttons = self._attr_extra_state_attributes.get("buttons")
        if buttons is not None:
            state = await self._async_send_button(buttons, activity, ["on", "on-favorite", "on-100", "onoff", "power"])
            if state is not None:
                self._attr_is_on = True
                self._on_post_response(state)
                self._async_write_ha_state()
                return
        signals: dict = self._attr_extra_state_attributes["signals"]
        signal = next((v for v in signals if v["image"] == "ico_on"), None)
        if signal is None:
            signal = next((v for v in signals if v["image"] == "ico_io"), None)
        if signal is not None:
            await self._post(f"signals/{signal['id']}/send")
        self._attr_is_on = True
        if self._aptype == "light":
            self._attr_current_activity = None
        self.async_write_ha_state()

    async def _async_send_button(self, buttons, activity, names):
        buttons: list[str] = [b["name"] for b in buttons]
        if activity:
            return await self._post(f"appliances/{self._remo_id}/{self._aptype}", {"button": activity})
        for b in names:
            if b not in buttons:
                continue
            return await self._post(f"appliances/{self._remo_id}/{self._aptype}", {"button": b})

    def _on_data_update(self, appliance: dict):
        super()._on_data_update(appliance)
        self._attr_extra_state_attributes = {
            "signals": appliance["signals"]
        }
        if self._aptype:
            self._attr_extra_state_attributes["buttons"] = appliance[self._aptype]["buttons"]
            state = appliance[self._aptype]["state"]
            self._on_post_response(state)

    def _on_post_response(self, state: dict):
        if self._aptype == "light":
            if state["power"] == "on":
                self._attr_is_on = True
            elif state["power"] == "off":
                self._attr_is_on = False
            buttons: list[dict] = self._attr_extra_state_attributes["buttons"]
            self._attr_activity_list = [
                b["name"] for b in buttons if b["name"] in _ACTIVITY_FILTER
            ]
            self._attr_current_activity = state["last_button"] if state["last_button"] in _ACTIVITY_FILTER else None
