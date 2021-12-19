from __future__ import annotations

from aiohttp.client_exceptions import ClientError
from typing import Any

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

import voluptuous as vol
from voluptuous.schema_builder import UNDEFINED

from .common import DOMAIN, RESOURCE


class NatureRemoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            return self._access_token_form({}, {})

        session = async_get_clientsession(self.hass)
        headers = {"Authorization": f"Bearer {user_input[CONF_ACCESS_TOKEN]}"}
        response = await session.get(f"{RESOURCE}/users/me", headers=headers)
        if response.status == 401:
            return self._access_token_form({"base": "code_401"}, user_input)
        if response.status == 429:
            return self._access_token_form({"base": "code_429"}, user_input)
        if response.status != 200:
            raise ClientError(f"response status: {response.status}")

        json = await response.json()
        id = json["id"]
        nickname = json["nickname"]

        existing_entry = await self.async_set_unique_id(DOMAIN)
        if existing_entry:
            self.hass.config_entries.async_update_entry(
                existing_entry, data=user_input)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(title="Nature Remo", description=nickname, data=user_input)

    def _access_token_form(self, errors: dict[str, str], user_input: dict[str, Any]):
        return self.async_show_form(
            errors=errors,
            data_schema=vol.Schema({
                vol.Required(CONF_ACCESS_TOKEN, default=user_input.get(CONF_ACCESS_TOKEN, UNDEFINED)): str,
            }),
            last_step=True,
            step_id="user",
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_user(user_input)
