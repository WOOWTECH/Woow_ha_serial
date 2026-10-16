"""Sidebar panel registration (the pattern HAIR uses: a bundled web component served as a static file)."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, PANEL_ELEMENT, PANEL_FILE, PANEL_ICON, PANEL_STATIC, PANEL_URL

_LOGGER = logging.getLogger(__name__)
BUNDLE = Path(__file__).parent / "frontend" / PANEL_FILE


async def async_register_panel(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("panel"):
        return
    try:
        raw = await hass.async_add_executor_job(BUNDLE.read_bytes)
    except OSError:
        _LOGGER.warning("Panel bundle %s is missing; the sidebar panel is not available", BUNDLE)
        return
    url = f"{PANEL_STATIC}/{PANEL_FILE}"
    if not data.get("panel_static"):  # a static route cannot be removed, so register it once per run
        await hass.http.async_register_static_paths([StaticPathConfig(url, str(BUNDLE), cache_headers=False)])
        data["panel_static"] = True
    title = "WOOW 串口" if (hass.config.language or "").lower().startswith("zh") else "WOOW Serial"
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name=PANEL_ELEMENT,
        sidebar_title=title,
        sidebar_icon=PANEL_ICON,
        # The content hash makes a browser fetch the new bundle after an update.
        module_url=f"{url}?v={hashlib.md5(raw).hexdigest()[:8]}",
        require_admin=True,
        embed_iframe=False,
        trust_external=False,
        config={},
    )
    data["panel"] = True


@callback
def async_remove_panel(hass: HomeAssistant) -> None:
    if hass.data.get(DOMAIN, {}).pop("panel", None):
        frontend.async_remove_panel(hass, PANEL_URL)
