"""Config and options flows for Hitokoto Daily."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CATEGORY_NAMES,
    CONF_ALLOW_DUPLICATE_FAVORITES,
    CONF_API_ROUTE,
    CONF_APPLY_NOW,
    CONF_AUTO_UPDATE,
    CONF_CATEGORIES,
    CONF_ENABLE_FAVORITES,
    CONF_HISTORY_LIMIT,
    CONF_MAX_LENGTH,
    CONF_MIN_LENGTH,
    CONF_PREFER_AUTHOR,
    CONF_PREFER_SOURCE,
    CONF_RETRIES,
    CONF_SAVE_HISTORY,
    CONF_TIMEOUT,
    CONF_UPDATE_TIME,
    DEFAULT_CATEGORIES,
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_MAX_LENGTH,
    DEFAULT_MIN_LENGTH,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
    ROUTE_GLOBAL,
    ROUTE_INTERNATIONAL,
)
from .coordinator import RequestGate


def _options_schema(
    defaults: dict[str, Any], *, include_apply_now: bool = False
) -> vol.Schema:
    """Build the shared config/options selector schema."""
    schema: dict[Any, Any] = {
        vol.Required(
            CONF_API_ROUTE, default=defaults.get(CONF_API_ROUTE, ROUTE_GLOBAL)
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[ROUTE_GLOBAL, ROUTE_INTERNATIONAL],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="api_route",
            )
        ),
        vol.Required(
            CONF_TIMEOUT, default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=3, max=60, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(
            CONF_RETRIES, default=defaults.get(CONF_RETRIES, True)
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_CATEGORIES,
            default=defaults.get(CONF_CATEGORIES, list(DEFAULT_CATEGORIES)),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(CATEGORY_NAMES),
                multiple=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="categories",
            )
        ),
        vol.Required(
            CONF_MIN_LENGTH, default=defaults.get(CONF_MIN_LENGTH, DEFAULT_MIN_LENGTH)
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=255, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(
            CONF_MAX_LENGTH, default=defaults.get(CONF_MAX_LENGTH, DEFAULT_MAX_LENGTH)
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=255, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(
            CONF_PREFER_AUTHOR, default=defaults.get(CONF_PREFER_AUTHOR, False)
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_PREFER_SOURCE, default=defaults.get(CONF_PREFER_SOURCE, False)
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_AUTO_UPDATE, default=defaults.get(CONF_AUTO_UPDATE, True)
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_UPDATE_TIME,
            default=defaults.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME.isoformat()),
        ): selector.TimeSelector(),
        vol.Required(
            CONF_SAVE_HISTORY, default=defaults.get(CONF_SAVE_HISTORY, True)
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_HISTORY_LIMIT,
            default=str(defaults.get(CONF_HISTORY_LIMIT, DEFAULT_HISTORY_LIMIT)),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["30", "100", "365", "1000", "0"],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="history_limit",
            )
        ),
        vol.Required(
            CONF_ENABLE_FAVORITES, default=defaults.get(CONF_ENABLE_FAVORITES, True)
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_ALLOW_DUPLICATE_FAVORITES,
            default=defaults.get(CONF_ALLOW_DUPLICATE_FAVORITES, False),
        ): selector.BooleanSelector(),
    }
    if include_apply_now:
        schema[vol.Required(CONF_APPLY_NOW, default=False)] = selector.BooleanSelector()
    return vol.Schema(schema)


def _validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate API parameter relationships before saving the flow."""
    errors: dict[str, str] = {}
    if int(user_input[CONF_MIN_LENGTH]) > int(user_input[CONF_MAX_LENGTH]):
        errors["base"] = "invalid_length_range"
    if not user_input[CONF_CATEGORIES]:
        errors["base"] = "select_category"
    return errors


class HitokotoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial visual setup flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        """Show settings and create a config entry without requiring the API online."""
        if user_input is not None:
            errors = _validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title="Hitokoto Daily",
                    data=dict(user_input),
                )
        else:
            errors = {}
        return self.async_show_form(
            step_id="user",
            data_schema=_options_schema({}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HitokotoOptionsFlow:
        """Return the options flow for an existing entry."""
        return HitokotoOptionsFlow(config_entry)


class HitokotoOptionsFlow(OptionsFlow):
    """Allow the user to update every setting after initial setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Keep the entry whose options are being edited."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        """Save changed options, optionally requesting a new quote immediately."""
        if user_input is not None:
            errors = _validate_input(user_input)
            if not errors:
                apply_now = bool(user_input.pop(CONF_APPLY_NOW, False))
                if apply_now:
                    runtime = self.hass.data.setdefault(
                        DOMAIN,
                        {"entries": {}, "gate": RequestGate(), "services": False},
                    )
                    runtime.setdefault("apply_now", set()).add(
                        self.config_entry.entry_id
                    )
                return self.async_create_entry(title="", data=user_input)
        else:
            errors = {}

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(defaults, include_apply_now=True),
            errors=errors,
        )
