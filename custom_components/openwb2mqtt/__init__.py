"""The openwbmqtt component for controlling the openWB wallbox via home assistant / MQTT."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

# Import global values.
from .const import PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Trigger the creation of sensors."""
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload all sensor entities and services if integration is removed via UI.

    No restart of home assistant is required.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok
