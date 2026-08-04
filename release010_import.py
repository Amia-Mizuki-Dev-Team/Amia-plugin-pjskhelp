"""Optional Release010 helpers; this plugin remains independently loadable."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib import import_module
import os
from pathlib import Path
import re
import traceback
from typing import Any
from uuid import uuid4


def _load_shared_helpers():
    for name in ("amia_core.release010", "src.plugins.amia_core.release010"):
        try:
            return import_module(name)
        except ModuleNotFoundError as error:
            if error.name not in {
                "amia_core", "amia_core.release010", "src", "src.plugins",
                "src.plugins.amia_core", "src.plugins.amia_core.release010",
            }:
                raise
    return None


_shared = _load_shared_helpers()
_SECRET_RE = re.compile(
    r"(?im)(authorization|token|cookie|secret|password|api[_-]?key)"
    r"(\s*[:=]\s*)([^\s,;]+)",
)


class _FallbackHXCodeError(Exception):
    def __init__(self, code: str, reason: str, suggestion: str, cause: str):
        super().__init__(reason)
        self.hx_code = code
        self.hx_reason = reason
        self.hx_suggestion = suggestion
        self.hx_cause = cause


HXCodeError = getattr(_shared, "HXCodeError", _FallbackHXCodeError)


def _code(exc: BaseException, source: str) -> str:
    value = str(getattr(exc, "hx_code", "") or "").strip().upper()
    if value:
        return value if value.startswith("HX-") else f"HX-{source.upper()}-{value}"
    if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
        return f"HX-{source.upper()}-003"
    if isinstance(exc, FileNotFoundError):
        return f"HX-{source.upper()}-006"
    if isinstance(exc, (ValueError, TypeError)):
        return f"HX-{source.upper()}-007"
    return f"HX-{source.upper()}-009"


def _fallback_message(exc: BaseException, source: str) -> str:
    code = _code(exc, source)
    reason = getattr(exc, "hx_reason", "插件处理失败")
    suggestion = getattr(exc, "hx_suggestion", "请稍后重试；持续失败时请提交诊断文件")
    cause = getattr(exc, "hx_cause", type(exc).__name__)
    return (
        "处理失败\n\n"
        f"错误码：{code}\n原因：{reason}\n建议：{suggestion}\n"
        f"错误码分析：{code} 表示 {cause}\n\n"
        "诊断日志已附上，请移交给开发者处理。\n"
        "如需进一步协助，请加入开发群：1053964431"
    )


def _write_diagnostic(
    exc: BaseException,
    source: str,
    *,
    context: str = "",
    log_text: str = "",
    directory: str | Path | None = None,
) -> Path:
    root = Path(directory or os.getenv("AMIA_DIAGNOSTIC_DIR", "data/diagnostics"))
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = root / f"{_code(exc, source).lower()}-{stamp}-{uuid4().hex[:8]}.log"
    raw = "\n".join((
        "Amia Release010 diagnostic", f"time_utc={stamp}",
        f"error_code={_code(exc, source)}", f"source={source}",
        f"context={context}", f"exception={type(exc).__name__}: {exc}",
        "traceback:", "".join(traceback.format_exception(exc)),
        "correlated_log:", log_text,
    ))
    raw = _SECRET_RE.sub(r"\1\2<redacted>", raw)
    path.write_text(raw.encode("utf-8", "replace")[:65536].decode("utf-8", "ignore"), encoding="utf-8")
    return path


async def send_error_with_diagnostic(
    matcher: Any,
    exc: BaseException,
    source: str,
    *,
    context: str = "",
    log_text: str = "",
    directory: str | Path | None = None,
) -> Path:
    if _shared is not None:
        return await _shared.send_error_with_diagnostic(
            matcher, exc, source, context=context, log_text=log_text, directory=directory
        )
    path = _write_diagnostic(exc, source, context=context, log_text=log_text, directory=directory)
    await matcher.send(_fallback_message(exc, source))
    try:
        from nonebot.adapters.onebot.v11 import MessageSegment
        await matcher.send(MessageSegment("file", {"file": path.resolve().as_uri(), "file_name": path.name}))
    except Exception:  # noqa: BLE001 - upload failure must not hide the error code
        await matcher.send("诊断文件上传失败，请把错误码和日志时间一并交给开发者。")
    await matcher.finish()
    return path
