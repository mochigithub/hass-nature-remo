import logging
from typing import Callable
from homeassistant.components.media_player.const import SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP
from homeassistant.config_entries import ConfigEntry

from homeassistant.components.media_player import MediaPlayerDeviceClass, MediaPlayerEntity
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from .common import DOMAIN, AppliancesUpdateCoordinator, NatureEntity, check_update, create_appliance_device_info

_LOGGER = logging.getLogger(__name__)

_INPUT_TO_SOURCE = {
    "t": "terrestrial",
    "bs": "bs",
    "cs": "cs",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Setting up media_player platform.")
    appliances: AppliancesUpdateCoordinator = hass.data[DOMAIN]["appliances"]
    post: Callable = hass.data[DOMAIN]["post"]

    def on_add(appliance: dict):
        if appliance["type"] != "TV":
            return
        device_info = create_appliance_device_info(appliance)
        yield NatureRemoTV(appliances, post, appliance, device_info)

    check_update(entry, async_add_entities, appliances, on_add)


class NatureRemoTV(NatureEntity, MediaPlayerEntity):
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_state = STATE_OFF

    def __init__(self, appliances: AppliancesUpdateCoordinator, post: Callable, appliance: dict, device_info: DeviceInfo):
        super().__init__(appliances,
                         appliance["id"], f'{appliance["id"]}-tv', device_info)
        self._attr_name = appliance["nickname"]
        self._post = post
        self._attr_icon = "mdi:television"
        self._on_data_update(appliance)

    async def async_turn_off(self):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": "power"})
        self._attr_state = STATE_OFF
        self._on_post_response(state)
        self._async_write_ha_state()

    async def async_turn_on(self):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": "power"})
        if self._attr_state == STATE_OFF:
            self._attr_state = STATE_IDLE
        self._on_post_response(state)
        self._async_write_ha_state()

    async def async_select_source(self, source):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": f"input-{source}"})
        self._on_post_response(state)
        self._async_write_ha_state()

    async def async_mute_volume(self, mute):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": "mute"})
        self._attr_is_volume_muted = mute
        self._on_post_response(state)
        self._async_write_ha_state()

    async def async_volume_down(self):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": "vol-down"})
        self._attr_is_volume_muted = False
        self._on_post_response(state)
        self._async_write_ha_state()

    async def async_volume_up(self):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": "vol-up"})
        self._attr_is_volume_muted = False
        self._on_post_response(state)
        self._async_write_ha_state()

    async def async_media_play(self):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": "play"})
        self._attr_state = STATE_PLAYING
        self._on_post_response(state)
        self._async_write_ha_state()

    async def async_media_pause(self):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": "pause"})
        self._attr_state = STATE_PAUSED
        self._on_post_response(state)
        self._async_write_ha_state()

    async def async_media_stop(self):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": "pause"})
        self._attr_state = STATE_IDLE
        self._on_post_response(state)
        self._async_write_ha_state()

    async def async_media_previous_track(self):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": "prev"})
        self._on_post_response(state)
        self._async_write_ha_state()

    async def async_media_next_track(self):
        state = await self._post(f"appliances/{self._remo_id}/tv", {"button": "next"})
        self._on_post_response(state)
        self._async_write_ha_state()

    def _on_data_update(self, appliance: dict):
        super()._on_data_update(appliance)
        buttons: list[str] = [x["name"] for x in appliance["tv"]["buttons"]]
        features = 0
        self._attr_source_list = []
        if "power" in buttons:
            features |= SUPPORT_TURN_ON | SUPPORT_TURN_OFF
        for x in buttons:
            if not x.startswith("input-"):
                continue
            self._attr_source_list.append(x[6:])
            features |= SUPPORT_SELECT_SOURCE
        if "mute" in buttons:
            features |= SUPPORT_VOLUME_MUTE
        if "vol-up" in buttons and "vol-down" in buttons:
            features |= SUPPORT_VOLUME_STEP
        if "play" in buttons:
            features |= SUPPORT_PLAY
        if "pause" in buttons:
            features |= SUPPORT_PAUSE
        if "stop" in buttons:
            features |= SUPPORT_STOP
        if "prev" in buttons:
            features |= SUPPORT_PREVIOUS_TRACK
        if "next" in buttons:
            features |= SUPPORT_NEXT_TRACK
        self._attr_supported_features = features
        self._on_post_response(appliance["tv"]["state"])

    def _on_post_response(self, state: dict):
        self._attr_source = _INPUT_TO_SOURCE.get(state["input"])
