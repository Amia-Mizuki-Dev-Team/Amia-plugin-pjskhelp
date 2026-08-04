"""Load Release010 helpers in source and installed plugin layouts."""

from __future__ import annotations

from importlib import import_module


def _load_release010():
    for module_name in ("amia_core.release010", "src.plugins.amia_core.release010"):
        try:
            return import_module(module_name)
        except ModuleNotFoundError as error:
            if error.name not in {
                "amia_core",
                "amia_core.release010",
                "src",
                "src.plugins",
                "src.plugins.amia_core",
                "src.plugins.amia_core.release010",
            }:
                raise

    try:
        from nonebot import require

        core = require("amia_core")
        return import_module(f"{core.__name__}.release010")
    except Exception as error:
        raise ModuleNotFoundError(
            "Amia Core is required; install the amia-core plugin or enable it in plugin_dirs"
        ) from error


_release010 = _load_release010()
HXCodeError = _release010.HXCodeError
send_error_with_diagnostic = _release010.send_error_with_diagnostic
