"""PJSK backend relay.

The relay deliberately lives inside ``pjskhelp``.  Gensokyo owns the public
OneBot WebSocket on port 8080; this module only maintains the two outbound
OneBot reverse-WebSocket connections and maps their API calls back to the
original NoneBot event.
"""

from __future__ import annotations

import asyncio
from base64 import b64encode
import json
import os
from pathlib import Path
import re
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from nonebot import logger, require
from nonebot.adapters.onebot.v11 import Message, MessageSegment

try:
    import orjson
except Exception:  # pragma: no cover
    orjson = None

try:
    _qbind = require("qbind")
    get_real_qq = getattr(_qbind, "get_real_qq", None)
    _qbind_group = getattr(_qbind, "group", None)
    get_real_group = getattr(_qbind_group, "get_real_group", None)
    if get_real_group is None:
        get_real_group = getattr(_qbind, "get_real_group", None)
except Exception:  # pragma: no cover
    get_real_qq = None
    get_real_group = None


def _u(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


def _loads(raw: str | bytes) -> dict[str, Any]:
    if orjson:
        return orjson.loads(raw)
    return json.loads(raw)


def _dumps(data: dict[str, Any]) -> str:
    if orjson:
        return orjson.dumps(data).decode("utf-8")
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _normalize_haruki_ws_url(value: str) -> str:
    """Use Haruki Client's reverse-WebSocket endpoint when no path is given."""

    raw = value.strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw
    if parsed.scheme.lower() in {"ws", "wss"} and parsed.path in {"", "/"}:
        return parsed._replace(path="/ws").geturl()
    return raw


PJSK_RELAY_ENABLED = _env_bool("PJSK_RELAY_ENABLED", True)
# Haruki Client v3 exposes its reverse OneBot WebSocket at /ws.
HARUKI_WS_URL = _normalize_haruki_ws_url(
    os.getenv("HARUKI_WS_URL", "ws://127.0.0.1:8111/ws")
)
SAKURA_WS_URL = os.getenv("SAKURA_WS_URL", "ws://101.34.19.31:13888/onebot/v11/ws")
HARUKI_TOKEN = os.getenv("HARUKI_TOKEN", "")
SAKURA_TOKEN = os.getenv("SAKURA_TOKEN", "")

# A reverse-WS client must identify itself consistently.  The old gateway
# selected a random ID on every reconnect, which is rejected by strict
# OneBot/NapCat-compatible servers and also breaks identity mapping.
HARUKI_BOT_ID = os.getenv("HARUKI_BOT_ID", "3889047402")
SAKURA_BOT_ID = os.getenv("SAKURA_BOT_ID", "3889004352")
IDENTITY_QQ = HARUKI_BOT_ID
WS_HEADER_PROFILE = os.getenv("PJSK_BACKEND_HEADER_PROFILE", "napcat").strip().lower()
WS_USER_AGENT = os.getenv(
    "PJSK_WS_USER_AGENT",
    "NapCat/OneBot11" if WS_HEADER_PROFILE == "napcat" else "CQHttp/4.15.0",
)
WS_IMPL = os.getenv("PJSK_WS_IMPL", "napcat" if WS_HEADER_PROFILE == "napcat" else "gensokyo")


LOCAL_ONLY_RE = [
    re.compile(r"^\s*(?:cn|tw|kr|en|jp)?\s*pjsk(?:help|" + _u(r"\u5e2e\u52a9") + r")", re.I),
    re.compile(r"^\s*pjsk\s*(?:" + _u(r"\u6f2b\u753b|\u8d44\u6e90\u72b6\u6001") + r")(?:\s|$|\d)", re.I),
    re.compile(
        r"^\s*(?:cn|tw|kr|en|jp)?\s*pjsk\s*(?:-h|"
        + _u(r"\u8868\u60c5\u5236\u4f5c")
        + r")",
        re.I,
    ),
]

SHARED_CMDS = {
    "sk", "rk", "id", "msa", "msm", "msf", "msg", "msgate", "msr", "mss", "mssong", "msp",
    _u(r"\u7ed1\u5b9a"), _u(r"\u89e3\u7ed1"), _u(r"\u67e5\u65f6\u95f4"),
    _u(r"\u67e5\u5361"), _u(r"\u67e5\u66f2"), _u(r"\u67e5\u6b4c"),
    _u(r"\u6b4c\u66f2"), _u(r"\u4e50\u66f2"), _u(r"\u96be\u5ea6\u6392\u884c"),
    _u(r"\u8c31\u9762\u9884\u89c8"), _u(r"\u6280\u80fd\u9884\u89c8"),
    _u(r"\u67e5\u7269\u91cf"), _u(r"\u67e5bpm"), _u(r"\u6d3b\u52a8"),
    _u(r"\u67e5\u6d3b\u52a8"), _u(r"sk\u7ebf"), _u(r"\u65f6\u901f"),
    _u(r"\u65e5\u901f"), _u(r"\u67e5\u623f"), _u(r"\u7ec4\u5361"),
    _u(r"\u6d3b\u52a8\u7ec4\u5361"), _u(r"\u6311\u6218\u7ec4\u5361"),
    _u(r"\u6700\u5f3a\u7ec4\u5361"), _u(r"\u5bb6\u5177\u5217\u8868"),
    _u(r"mysekai\u7167\u7247"),
}

# Binding is a write-capable command exposed by both PJSK backends.  It must
# be dispatched to both instead of being treated as a single-backend fallback.
BINDING_DUAL_CMDS = {_u(r"\u7ed1\u5b9a")}

HARUKI_CMDS = {
    "bind", "profile", "set main", "unbind", "hide suite", "show suite", "hide mysekai",
    "show mysekai", "hide id", "show id", "check data", "sud", "msd", "verify",
    "reg time", "card-detail", "cards", "card-list", "box", "card-box", "card img",
    "card", "song", "music", "music-list", "chart", "music rewards", "music-progress",
    "progress", "note num", "note count", "music cover", "events", "event-list", "event",
    "event record", "sk-line", "sk-query", "sk board", "sk speed", "sk daily speed",
    "sk-check-room", "ptr", "sk-player-trace", "sk-rank-trace", "sk predict",
    "winrate predict", "event card", "event deck", "deck", "challenge card",
    "challenge deck", "best deck", "bonus deck", "bonus card", "mysekai deck",
    "challenge info", "power bonus info", "area item", "bonds", "leader count",
    "mysekai res", "mysekai map", "mysekai furniture", "mysekai fixture", "mysekai gate",
    "mysekai musicrecord", "mysekai blueprint", "mysekai photo", "music alias", "alias",
    "chara alias", "chara birthday", "stamp", "vlive", "gacha", "pjsktz", "tz",
    _u(r"\u4e2a\u4eba\u4fe1\u606f"), _u(r"\u4e2a\u4eba\u4e2d\u5fc3"),
    _u(r"\u7ed1\u5b9a\u5217\u8868"), _u(r"\u4ea4\u6362\u7ed1\u5b9a"),
    _u(r"\u4e3b\u8d26\u53f7"), _u(r"\u9a8c\u8bc1"), _u(r"\u67e5\u5361\u6c60"),
    # Haruki 的中文账号/抓包入口。区域指令会先去掉 cn，再使用这里的别名匹配。
    _u(r"\u6293\u5305\u6570\u636e"), _u(r"\u70e4\u68ee\u6293\u5305"),
    _u(r"\u9690\u85cf\u6293\u5305"), _u(r"\u5c55\u793a\u6293\u5305"),
    _u(r"\u663e\u793a\u6293\u5305"), _u(r"\u9690\u85cfID"), _u(r"\u663e\u793aID"),
    _u(r"\u8fdb\u5ea6"), _u(r"\u67e5\u65f6\u95f4"), _u(r"\u6ce8\u518c\u65f6\u95f4"),
    _u(r"\u902e\u6355"),
}

SAKURA_CMDS = {
    # Sakura 13888 Chunithm relay. Arguments are intentionally passed through
    # unchanged so Sakura can apply its DivingFish CN data semantics.
    "chusearch", "chuinfo", "chuchart", "chu b30",
    "pjskprofile", "b39", "b30", "pjskdetail", "pjskcard", "pjskevent",
    "rk", "id", "ss", "wlss", "pinfo", "pset", "pdel",
    "charinfo", "charset", "chardel",
    "findcard", "cardinfo", "findevent",
    _u(r"\u7ed9\u770b"), _u(r"\u4e0d\u7ed9\u770b"), _u(r"\u89c6\u5978"),
    _u(r"b30\u5220\u6b4c"), _u(r"b30\u6062\u590d\u6b4c"),
    _u(r"b30\u8fd8\u539f\u6b4c"), _u(r"b30\u5220\u6b4c\u5217\u8868"),
    _u(r"\u5207\u7ed1\u5b9a"), _u(r"\u8fdb\u5ea6ex"),
    _u(r"\u8fdb\u5ea6apd"), _u(r"\u5bb6\u5177\u8be6\u60c5"),
    _u(r"\u6ce8\u518c"), _u(r"\u5206\u6570\u7ebf"),
    _u(r"5v5\u80dc\u7387"), _u(r"5v5\u5206\u6570"),
    _u(r"tf\u542f\u52a8"), _u(r"\u542c\u6b4c\u8bc6\u66f2"),
    _u(r"\u7ed3\u675f\u731c\u66f2"), _u(r"\u731c\u5361\u9762"),
    _u(r"\u7ed3\u675f\u731c\u5361\u9762"), _u(r"pjsk\u62bd\u5361"),
    _u(r"\u62bd\u5361"), _u(r"\u53cd\u62bd\u5361"), _u(r"\u770b"),
    _u(r"\u968f\u4e2a"), _u(r"\u8471\u4ec0\u4e48"),
    _u(r"\u5f00\u542flive\u8ba2\u9605"), _u(r"\u5f00\u542flive\u63a8\u9001"),
    _u(r"\u5f00\u542flive\u901a\u77e5"), _u(r"\u5173\u95edlive\u8ba2\u9605"),
    _u(r"\u5173\u95edlive\u63a8\u9001"), _u(r"\u5173\u95edlive\u901a\u77e5"),
}


def _load_documented_haruki_commands() -> set[str]:
    """Load the generated Haruki NEO command catalog without network access."""

    catalog_path = Path(__file__).with_name("haruki_commands.json")
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        commands = catalog.get("commands", [])
        return {
            str(command).strip().lstrip("/").strip().lower()
            for command in commands
            if str(command).strip().startswith("/")
        }
    except FileNotFoundError:
        logger.warning("Haruki command catalog is missing; using built-in aliases only")
    except Exception as exc:
        logger.warning(f"Haruki command catalog could not be loaded: {type(exc).__name__}")
    return set()


HARUKI_DOCUMENTED_CMDS = _load_documented_haruki_commands()
HARUKI_CMDS.update(HARUKI_DOCUMENTED_CMDS)

PREFIX_RE = re.compile(r"^\s*(?:cn|tw|kr|en|jp)?\s*(?:pjsk|sk)?\s*", re.I)
PJSK_PREFIX_RE = re.compile(r"^\s*(?:cn|tw|kr|en|jp)?\s*(?:pjsk|sk)(?![a-z0-9_])", re.I)
REGIONAL_PREFIX_RE = re.compile(r"^\s*(?:cn|tw|kr|en|jp)(?!pjsk)", re.I)
COMPACT_B39_RE = re.compile(r"^\s*(?:cn|tw|kr|en|jp)?\s*pjskb39(?:\s|$)", re.I)
SPACED_B39_RE = re.compile(r"^\s*(?:cn|tw|kr|en|jp)?\s*pjsk\s+b39(?:\s|$)", re.I)
SAKURA_DYNAMIC_RE = [
    re.compile(r"^\s*(?:cn|tw)?\s*pjsk\d+\u8fde(?:\s|$)", re.I),
]


@dataclass(slots=True)
class ReplyTarget:
    bot: Any
    event: Any
    user_id: str
    group_id: str | None
    self_id: str = ""
    real_user_id: str | None = None
    real_group_id: str | None = None


_backend_ws: dict[str, Any] = {"haruki": None, "sakura": None}
_reply_routes: dict[str, ReplyTarget] = {}
# Legacy entries are kept only for callers/tests that predate scoped routes.  The
# target identity guards against stale metadata after a direct map assignment.
_legacy_route_kinds: dict[str, tuple[ReplyTarget, str]] = {}
_tasks: list[asyncio.Task] = []
_heartbeat_tasks: set[asyncio.Task] = set()
_message_cache: dict[str, float] = {}

# QQ 公域群对外链图片的接受条件比测试群更严格。将后端返回的远程图片
# 转成 OneBot 的 base64 图片后再交给 Gensokyo 上传，可以避免 QQ 直接抓取
# Haruki 图片缓存地址失败。限制大小，防止异常后端响应占满内存。
_REMOTE_IMAGE_MAX_BYTES = 16 * 1024 * 1024
_REMOTE_IMAGE_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
_REMOTE_IMAGE_PROXY = os.getenv("PJSK_IMAGE_PROXY", "").strip()
_MARKDOWN_BOT_IDS = {
    value.strip()
    for value in os.getenv("PJSK_MARKDOWN_BOT_IDS", "3889004352,3889047402").split(",")
    if value.strip()
}
_PLAIN_URL_RE = re.compile(r"https?://[^\s<>\]\)]+", re.I)


def _backoff(fail_count: int) -> int:
    if fail_count <= 1:
        return 3
    if fail_count == 2:
        return 30
    return 300


def _headers(self_id: str, token: str = "") -> dict[str, str]:
    headers = {
        "User-Agent": WS_USER_AGENT,
        "X-Self-ID": str(self_id),
        "X-Client-Role": "Universal",
        "X-Impl": WS_IMPL,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _url_label(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or "?"
    port = parsed.port
    path = parsed.path or "/"
    return f"{parsed.scheme}://{host}{f':{port}' if port else ''}{path}"


def _classify_connection_error(exc: BaseException) -> str:
    if isinstance(exc, aiohttp.WSServerHandshakeError):
        return f"HTTP Upgrade rejected ({exc.status})"
    if isinstance(exc, aiohttp.ClientConnectorError):
        return "TCP/DNS connection failed"
    if isinstance(exc, aiohttp.InvalidURL):
        return "invalid WebSocket URL"
    if isinstance(exc, asyncio.TimeoutError):
        return "connect or lifecycle timeout"
    return type(exc).__name__


async def _ws_send(ws: Any, data: str) -> None:
    if hasattr(ws, "send_str"):
        await ws.send_str(data)
    else:
        await ws.send(data)


async def _mock_heartbeat(ws: Any, self_id: str) -> None:
    while True:
        try:
            payload = {
                "post_type": "meta_event",
                "meta_event_type": "heartbeat",
                "time": int(time.time()),
                "self_id": int(self_id),
                "status": {"app_initialized": True, "app_enabled": True, "good": True, "online": True},
                "interval": 5000,
            }
            await _ws_send(ws, _dumps(payload))
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise
        except Exception:
            return


async def _mock_lifecycle(ws: Any, self_id: str) -> None:
    await _ws_send(ws, _dumps({
        "post_type": "meta_event",
        "meta_event_type": "lifecycle",
        "sub_type": "connect",
        "time": int(time.time()),
        "self_id": int(self_id),
    }))


def _command_body(text: str) -> str:
    return PREFIX_RE.sub("", text.lstrip("/"), count=1).strip().lower()


def _match_command(text: str, commands: set[str]) -> bool:
    raw = text.strip().lower()
    body = _command_body(text)
    return any(
        raw == cmd.lower()
        or raw.startswith(cmd.lower() + " ")
        or body == cmd.lower()
        or body.startswith(cmd.lower() + " ")
        for cmd in commands
    )


def _route_for(text: str) -> tuple[bool, bool, bool]:
    check = text.lstrip("/")
    if any(pattern.match(check) for pattern in LOCAL_ONLY_RE):
        return False, False, True
    if COMPACT_B39_RE.match(check):
        return False, True, False
    if SPACED_B39_RE.match(check):
        return False, False, True
    if check.strip().lower() == "pjskprofile":
        return False, True, False
    if any(pattern.match(check) for pattern in SAKURA_DYNAMIC_RE):
        return False, True, False

    documented_haruki = _match_command(check, HARUKI_DOCUMENTED_CMDS)
    binding_dual = _match_command(check, BINDING_DUAL_CMDS)
    shared = _match_command(check, SHARED_CMDS)
    haruki = _match_command(check, HARUKI_CMDS)
    sakura = _match_command(check, SAKURA_CMDS)

    # Prefer the current Haruki NEO documentation when an alias exists on both
    # services. Sakura receives only its legacy/specialized command surface.
    if binding_dual:
        return True, True, False
    if documented_haruki:
        return True, False, False
    if sakura:
        return False, True, False
    if haruki or shared:
        return True, False, False
    if PJSK_PREFIX_RE.match(check) and not (haruki or sakura):
        # Unknown pjsk text used to wake Haruki and generated noisy false
        # positives. Only documented/static aliases are forwarded.
        return False, False, True
    if REGIONAL_PREFIX_RE.match(check) and not (haruki or sakura):
        return False, False, True
    return False, False, False


def _numeric_id(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value)
    return int(text) if text.isdigit() else None


def _resolve_real_qq(user_id: str, self_id: str) -> str | None:
    if not get_real_qq:
        return None
    resolved = get_real_qq(str(user_id), str(self_id))
    return None if resolved is None else str(resolved)


def _resolve_real_group(group_id: str | None, self_id: str) -> str | None:
    if group_id is None or not get_real_group:
        return None
    resolved = get_real_group(str(group_id), str(self_id))
    return None if resolved is None else str(resolved)


def _rewrite_numeric_field(data: dict[str, Any], field: str, resolved: str | None) -> None:
    numeric = _numeric_id(resolved)
    if numeric is not None and field in data:
        data[field] = numeric


def _rewrite_payload_ids(
    data: dict[str, Any],
    real_user_id: str | None,
    real_group_id: str | None,
) -> None:
    _rewrite_numeric_field(data, "user_id", real_user_id)
    sender = data.get("sender")
    if isinstance(sender, dict):
        _rewrite_numeric_field(sender, "user_id", real_user_id)
    _rewrite_numeric_field(data, "group_id", real_group_id)


def _prepend_slash(
    raw_payload: str,
    pure_msg: str,
    cq_prefix: str,
    real_user_id: str | None = None,
    real_group_id: str | None = None,
) -> str:
    data = _loads(raw_payload)
    _rewrite_payload_ids(data, real_user_id, real_group_id)
    command = pure_msg.strip()
    if not command.startswith("/"):
        command = "/" + command
    data["raw_message"] = cq_prefix + command
    for seg in data.get("message", []):
        if isinstance(seg, dict) and seg.get("type") == "text":
            text = seg.get("data", {}).get("text", "")
            if text.strip():
                leading = text[: len(text) - len(text.lstrip())]
                content = text[len(leading):]
                if not content.startswith("/"):
                    content = "/" + content
                seg["data"]["text"] = leading + content
                break
    return _dumps(data)


def _rewrite_for_sakura(
    raw_payload: str,
    virtual_user_id: Any,
    self_id: str = "",
    virtual_group_id: Any = None,
    real_user_id: str | None = None,
    real_group_id: str | None = None,
) -> str:
    data = _loads(raw_payload)
    if real_user_id is None:
        real_user_id = _resolve_real_qq(str(virtual_user_id), str(self_id))
    if real_group_id is None and virtual_group_id is not None:
        real_group_id = _resolve_real_group(str(virtual_group_id), str(self_id))
    _rewrite_payload_ids(data, real_user_id, real_group_id)
    data["self_id"] = int(SAKURA_BOT_ID)
    return _dumps(data)


def _event_payload(event: Any) -> str:
    if hasattr(event, "model_dump"):
        data = event.model_dump()
    elif hasattr(event, "dict"):
        data = event.dict()
    else:  # pragma: no cover - only used by small external adapters/tests
        data = dict(vars(event))
    return _dumps(data)


def _event_self_id(event: Any) -> str:
    self_id = getattr(event, "self_id", None)
    return _normalize_scope(self_id)


def _event_user_id(event: Any) -> str:
    user_id = getattr(event, "user_id", None)
    return "" if user_id is None else str(user_id)


def _event_group_id(event: Any) -> str | None:
    group_id = getattr(event, "group_id", None)
    return None if group_id is None else str(group_id)


def _normalize_scope(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_source(source: Any) -> str:
    return _normalize_scope(source).lower()


def _scoped_route_key(source: str, scope: str, route_key: str) -> str:
    return f"{_normalize_source(source)}|{_normalize_scope(scope)}|{route_key}"


def _target_scope(target: ReplyTarget) -> str:
    scope = _normalize_scope(target.self_id)
    if scope:
        return scope
    return _normalize_scope(getattr(target.bot, "self_id", ""))


def _route_kind(route_key: str) -> str:
    if route_key.startswith("group_"):
        return "group"
    if route_key.startswith("user_"):
        return "private"
    raise ValueError(f"unknown PJSK route key: {route_key}")


def _target_matches_destination(
    target: ReplyTarget,
    destination: str,
    route_key: str,
    *,
    legacy_route: bool = False,
) -> bool:
    if _route_kind(route_key) != destination:
        return False
    if destination == "group":
        return target.group_id is not None
    if not target.user_id:
        return False
    if target.group_id is None:
        return True
    if not legacy_route:
        return False
    legacy_kind = _legacy_route_kinds.get(route_key)
    return legacy_kind is not None and legacy_kind[0] is target and legacy_kind[1] == "private"


def _route_keys(
    user_id: str,
    group_id: str | None,
    *,
    real_user_id: str | None = None,
    real_group_id: str | None = None,
) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for prefix, values in (
        ("group", (group_id, real_group_id)),
        ("user", (user_id, real_user_id)),
    ):
        for value in values:
            if value is None:
                continue
            key = f"{prefix}_{_normalize_scope(value)}"
            if key not in seen:
                keys.append(key)
                seen.add(key)
    return keys


def _register_route(target: ReplyTarget, source: str | None = None) -> None:
    target.self_id = _normalize_scope(target.self_id)
    if target.real_user_id is None:
        target.real_user_id = _resolve_real_qq(target.user_id, target.self_id)
    if target.group_id is not None and target.real_group_id is None:
        target.real_group_id = _resolve_real_group(target.group_id, target.self_id)

    route_keys = _route_keys(
        target.user_id,
        target.group_id,
        real_user_id=target.real_user_id,
        real_group_id=target.real_group_id,
    )
    if source is None:
        # Compatibility for callers that still populate the historical
        # unscoped table. Production dispatch always supplies a backend source.
        for key in route_keys:
            _reply_routes[key] = target
            _legacy_route_kinds[key] = (target, _route_kind(key))
        return

    target_kind = "group" if target.group_id is not None else "private"
    scope = _target_scope(target)
    for key in route_keys:
        if _route_kind(key) != target_kind:
            continue
        scoped_key = _scoped_route_key(source, scope, key)
        _reply_routes[scoped_key] = target


def _backend_destination(action: Any, params: dict[str, Any]) -> str | None:
    action_name = str(action or "")
    action_destination: str | None = None
    if action_name == "send_group_msg":
        action_destination = "group"
    elif action_name in {"send_private_msg", "send_private_msg_wakeup"}:
        action_destination = "private"
    elif action_name not in {"send", "send_msg"}:
        return None

    message_type = _normalize_scope(params.get("message_type")).lower()
    if message_type and message_type not in {"group", "private"}:
        return None
    if action_destination is not None:
        if message_type and message_type != action_destination:
            return None
        return action_destination
    if message_type:
        return message_type

    has_group_id = params.get("group_id") is not None
    has_user_id = params.get("user_id") is not None
    if has_group_id and has_user_id:
        return None
    if has_group_id:
        return "group"
    if has_user_id:
        return "private"
    return None


def _route_key_for_destination(
    destination: str,
    group_id: Any,
    user_id: Any,
) -> str | None:
    if destination == "group":
        return None if group_id is None else f"group_{_normalize_scope(group_id)}"
    return None if user_id is None else f"user_{_normalize_scope(user_id)}"


def _requested_route_scope(params: dict[str, Any]) -> str | None:
    for field in ("self_id", "scope", "qbind_self_id", "bot_id"):
        value = params.get(field)
        if value is not None:
            return _normalize_scope(value)
    return None


def _find_backend_route(
    source: str,
    action: Any,
    params: dict[str, Any],
) -> tuple[ReplyTarget, bool] | None:
    destination = _backend_destination(action, params)
    if destination is None:
        return None
    route_key = _route_key_for_destination(
        destination,
        params.get("group_id"),
        params.get("user_id"),
    )
    if route_key is None:
        return None

    normalized_source = _normalize_source(source)
    source_prefix = f"{normalized_source}|"
    route_suffix = f"|{route_key}"
    requested_scope = _requested_route_scope(params)
    candidates: list[tuple[str, ReplyTarget]] = []
    has_scoped_routes = False
    for key, target in _reply_routes.items():
        if not key.startswith(source_prefix):
            continue
        has_scoped_routes = True
        if not key.endswith(route_suffix):
            continue
        scope = key[len(source_prefix):-len(route_suffix)]
        if requested_scope is not None and scope != requested_scope:
            continue
        if _target_matches_destination(target, destination, route_key):
            candidates.append((scope, target))

    if candidates:
        scopes = {scope for scope, _target in candidates}
        targets = {id(target) for _scope, target in candidates}
        if len(scopes) > 1 or len(targets) > 1:
            logger.warning(
                "PJSK backend route is ambiguous: "
                f"source={normalized_source} route={route_key} scopes={sorted(scopes)!r}"
            )
            return None
        return candidates[0][1], False

    # Once a source has scoped routes, an unscoped fallback could silently
    # select the wrong qbind scope. Legacy fallback is only for old callers
    # that populated the unscoped table and have no scoped entries at all.
    if has_scoped_routes:
        return None
    target = _reply_routes.get(route_key)
    if target is not None:
        if requested_scope is not None and _target_scope(target) != requested_scope:
            logger.warning(
                "PJSK legacy backend route scope mismatch: "
                f"source={normalized_source} route={route_key} "
                f"requested_scope={requested_scope!r} target_scope={_target_scope(target)!r}"
            )
            return None
        if _target_matches_destination(
            target,
            destination,
            route_key,
            legacy_route=True,
        ):
            return target, True
    return None


async def _download_remote_image(session: aiohttp.ClientSession, url: str) -> str | None:
    """Download an HTTP(S) image and return a OneBot ``base64://`` file value."""

    # 默认直连；如部署环境确实需要代理，可显式设置 PJSK_IMAGE_PROXY。
    proxies = [_REMOTE_IMAGE_PROXY, _REMOTE_IMAGE_PROXY] if _REMOTE_IMAGE_PROXY else []
    proxies.append(None)
    for proxy in proxies:
        try:
            request_kwargs = {"allow_redirects": True}
            if proxy:
                request_kwargs["proxy"] = proxy
            async with session.get(url, **request_kwargs) as response:
                if response.status != 200:
                    logger.warning(
                        f"PJSK relay image download failed: status={response.status} "
                        f"proxy={'set' if proxy else 'direct'} url={_url_label(url)}"
                    )
                    continue
                content = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    content.extend(chunk)
                    if len(content) > _REMOTE_IMAGE_MAX_BYTES:
                        logger.warning(
                            f"PJSK relay image download skipped: image too large url={_url_label(url)}"
                        )
                        return None
                expected_size = getattr(response, "content_length", None)
                if expected_size and len(content) != expected_size:
                    logger.warning(
                        f"PJSK relay image download incomplete: expected={expected_size} "
                        f"actual={len(content)} proxy={'set' if proxy else 'direct'} "
                        f"url={_url_label(url)}"
                    )
                    continue
                logger.info(
                    f"PJSK relay image materialized: bytes={len(content)} "
                    f"proxy={'set' if proxy else 'direct'}"
                )
                return f"base64://{b64encode(bytes(content)).decode('ascii')}"
        except Exception as exc:
            logger.warning(
                f"PJSK relay image download failed: {type(exc).__name__} "
                f"proxy={'set' if proxy else 'direct'} url={_url_label(url)}"
            )
    return None


async def _message_from_api(value: Any) -> Message:
    if isinstance(value, str):
        # Haruki may serialize the OneBot message as a CQ-code string instead
        # of an array. Parse it first so image segments go through the same
        # proxy download/base64 path as array-form messages.
        parsed = Message(value)
        return await _message_from_api([
            {"type": segment.type, "data": dict(segment.data)}
            for segment in parsed
        ])
    if isinstance(value, Message):
        return await _message_from_api([
            {"type": segment.type, "data": dict(segment.data)}
            for segment in value
        ])
    if isinstance(value, list):
        segments = []
        session: aiohttp.ClientSession | None = None
        try:
            for item in value:
                if isinstance(item, dict) and item.get("type"):
                    data = dict(item.get("data") or {})
                    file_value = data.get("file")
                    if (
                        item["type"] == "image"
                        and isinstance(file_value, str)
                        and urlsplit(file_value).scheme in {"http", "https"}
                    ):
                        # Gensokyo/QQ may reuse an external URL's cached upload
                        # across groups. That cache entry can be valid in the
                        # first group but rejected in the next one, so force a
                        # fresh upload for backend-generated images.
                        data["cache"] = "false"
                        if session is None:
                            session = aiohttp.ClientSession(
                                timeout=_REMOTE_IMAGE_TIMEOUT,
                                headers={"User-Agent": WS_USER_AGENT},
                            )
                        encoded = await _download_remote_image(session, file_value)
                        if encoded:
                            data["file"] = encoded
                    segments.append(MessageSegment(type=item["type"], data=data))
                elif item is not None:
                    segments.append(MessageSegment.text(str(item)))
        finally:
            if session is not None:
                await session.close()
        return Message(segments)
    if isinstance(value, dict) and value.get("type"):
        return await _message_from_api([value])
    return Message(str(value or ""))


def _escape_markdown_text(value: str) -> str:
    return re.sub(r"([\\`*_\[\]{}()#+\-.!|>])", r"\\\1", value)


def _linkify_markdown(value: str) -> str:
    parts: list[str] = []
    offset = 0
    for match in _PLAIN_URL_RE.finditer(value):
        parts.append(_escape_markdown_text(value[offset:match.start()]))
        parts.append(f"[打开链接]({match.group(0)})")
        offset = match.end()
    parts.append(_escape_markdown_text(value[offset:]))
    return "".join(parts)


def _markdownize_plain_urls(message: Message, bot: Any) -> Message:
    """Convert plain-text web links to QQ official-bot Markdown segments."""

    if str(getattr(bot, "self_id", "")) not in _MARKDOWN_BOT_IDS:
        return message
    converted: list[MessageSegment] = []
    changed = False
    for segment in message:
        if segment.type == "text":
            text = str(segment.data.get("text", ""))
            if _PLAIN_URL_RE.search(text):
                md_data = {
                    "markdown": {"content": _linkify_markdown(text)},
                    "keyboard": {"content": {"rows": []}},
                }
                converted.append(MessageSegment(type="markdown", data={"data": md_data}))
                changed = True
                continue
        converted.append(segment)
    return Message(converted) if changed else message


def _target_api_id(
    target_id: str | None,
    requested_id: Any,
    real_id: str | None,
) -> Any:
    if target_id is None:
        return requested_id
    if requested_id is not None and str(requested_id) == target_id:
        return requested_id
    if real_id is not None and requested_id is not None and str(requested_id) == real_id:
        return target_id
    return target_id


async def _deliver_backend_message(
    target: ReplyTarget,
    action: str,
    params: dict[str, Any],
    *,
    legacy_route: bool = False,
) -> dict[str, Any]:
    destination = _backend_destination(action, params)
    route_key = _route_key_for_destination(
        destination,
        params.get("group_id"),
        params.get("user_id"),
    ) if destination is not None else None
    if route_key is None or not _target_matches_destination(
        target,
        destination,
        route_key,
        legacy_route=legacy_route,
    ):
        raise ValueError(
            f"PJSK backend target type mismatch: destination={destination} route={route_key}"
        )

    message = await _message_from_api(params.get("message", ""))
    message = _markdownize_plain_urls(message, target.bot)
    requested_group_id = params.get("group_id")
    requested_user_id = params.get("user_id")

    if destination == "group":
        group_id = _target_api_id(target.group_id, requested_group_id, target.real_group_id)
        if hasattr(target.bot, "send_group_msg"):
            # Release010 may use non-numeric OpenID-like identifiers.  Keep the
            # adapter value opaque instead of forcing an int conversion.
            result = await target.bot.send_group_msg(group_id=group_id, message=message)
        else:
            result = await target.bot.send(target.event, message)
    else:
        user_id = _target_api_id(target.user_id, requested_user_id, target.real_user_id)
        if hasattr(target.bot, "send_private_msg"):
            result = await target.bot.send_private_msg(user_id=user_id, message=message)
        else:
            result = await target.bot.send(target.event, message)

    if isinstance(result, dict):
        return result
    return {"message_id": int(time.time() * 1000)}


async def _process_backend_api(message: str, source: str, source_ws: Any) -> None:
    try:
        data = _loads(message)
        action = data.get("action")
        echo = data.get("echo")
        backend_id = HARUKI_BOT_ID if source == "haruki" else SAKURA_BOT_ID

        if action in {"get_login_info", "get_version_info", "get_status", "get_group_list", "get_friend_list"}:
            responses = {
                "get_login_info": {"user_id": int(backend_id), "nickname": f"PJSK-{source}"},
                "get_version_info": {"app_name": "napcat", "app_version": "compatible", "protocol_version": "v11"},
                "get_status": {"app_initialized": True, "app_enabled": True, "good": True, "online": True},
                "get_group_list": [],
                "get_friend_list": [],
            }
            await _ws_send(source_ws, _dumps({"status": "ok", "retcode": 0, "data": responses[action], "echo": echo}))
            return

        if action in {"send", "send_msg", "send_group_msg", "send_private_msg", "send_private_msg_wakeup"}:
            params = data.get("params") or {}
            match = _find_backend_route(source, action, params)
            if match is not None:
                target, legacy_route = match
                try:
                    result = await _deliver_backend_message(
                        target,
                        action,
                        params,
                        legacy_route=legacy_route,
                    )
                except ValueError as exc:
                    logger.warning(f"PJSK backend route rejected: source={source} reason={exc}")
                else:
                    await _ws_send(source_ws, _dumps({"status": "ok", "retcode": 0, "data": result, "echo": echo}))
                    return
            if echo:
                await _ws_send(source_ws, _dumps({"status": "failed", "retcode": 1, "data": None, "echo": echo}))
            return

        if echo:
            await _ws_send(source_ws, _dumps({"status": "ok", "retcode": 0, "data": None, "echo": echo}))
    except Exception as exc:
        logger.exception(f"PJSK backend message error from {source}: {exc}")


async def _maintain_backend(name: str, url: str, token: str, self_id: str) -> None:
    fail_count = 0
    while True:
        cancelled = False
        heartbeat_task: asyncio.Task | None = None
        try:
            logger.info(
                "PJSK backend connecting: "
                f"backend={name} endpoint={_url_label(url)} self_id={self_id} "
                f"profile={WS_HEADER_PROFILE} token={'set' if token else 'unset'}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url, headers=_headers(self_id, token), timeout=15) as ws:
                    _backend_ws[name] = ws
                    fail_count = 0
                    logger.info(f"PJSK backend connected: backend={name} endpoint={_url_label(url)} self_id={self_id}")
                    await _mock_lifecycle(ws, self_id)
                    heartbeat_task = asyncio.create_task(_mock_heartbeat(ws, self_id))
                    _heartbeat_tasks.add(heartbeat_task)
                    heartbeat_task.add_done_callback(_heartbeat_tasks.discard)
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await _process_backend_api(msg.data, name, ws)
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception as exc:
            fail_count += 1
            logger.warning(
                f"PJSK backend disconnected: backend={name} endpoint={_url_label(url)} "
                f"reason={_classify_connection_error(exc)}"
            )
        finally:
            _backend_ws[name] = None
            if heartbeat_task:
                heartbeat_task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await heartbeat_task
            if not cancelled:
                await asyncio.sleep(_backoff(fail_count))


async def dispatch_message(bot: Any, event: Any) -> dict[str, Any]:
    """Route one NoneBot message to the configured PJSK backends."""

    if not PJSK_RELAY_ENABLED:
        return {"matched": False, "blocked": True, "sent": []}

    raw_msg = str(event.get_plaintext()).strip()
    if not raw_msg or len(raw_msg) > 300:
        return {"matched": False, "blocked": True, "sent": []}

    haruki, sakura, blocked = _route_for(raw_msg)
    if blocked or not (haruki or sakura):
        return {"matched": False, "blocked": blocked, "sent": []}

    logger.info(
        f"PJSK relay routing command={raw_msg!r} haruki={haruki} sakura={sakura}"
    )

    self_id = _event_self_id(event)
    user_id = _event_user_id(event)
    group_id = _event_group_id(event)
    cache_key = "\x1f".join((
        _normalize_scope(self_id),
        _normalize_scope(getattr(bot, "self_id", "")),
        _normalize_scope(group_id) or "0",
        _normalize_scope(user_id),
        raw_msg,
    ))
    now = time.time()
    for key, seen in list(_message_cache.items()):
        if now - seen > 1.5:
            _message_cache.pop(key, None)
    if cache_key in _message_cache:
        return {"matched": True, "blocked": False, "sent": []}
    _message_cache[cache_key] = now

    target = ReplyTarget(
        bot=bot,
        event=event,
        user_id=user_id,
        group_id=group_id,
        self_id=self_id,
    )
    if sakura:
        _register_route(target, source="sakura")
    if haruki:
        _register_route(target, source="haruki")
    raw_payload = _event_payload(event)
    sent: list[str] = []
    if sakura and _backend_ws["sakura"]:
        await _ws_send(
            _backend_ws["sakura"],
            _rewrite_for_sakura(
                raw_payload,
                user_id,
                self_id=self_id,
                virtual_group_id=group_id,
                real_user_id=target.real_user_id,
                real_group_id=target.real_group_id,
            ),
        )
        sent.append("sakura")
    if haruki and _backend_ws["haruki"]:
        match = re.match(r"^(\s*(?:\[CQ:[^\]]+\]\s*)*)(.*)$", raw_msg)
        cq_prefix, pure_msg = (match.group(1), match.group(2)) if match else ("", raw_msg)
        await _ws_send(
            _backend_ws["haruki"],
            _prepend_slash(
                raw_payload,
                pure_msg,
                cq_prefix,
                target.real_user_id,
                target.real_group_id,
            ),
        )
        sent.append("haruki")
    logger.info(f"PJSK relay dispatched command={raw_msg!r} backends={sent}")
    return {"matched": True, "blocked": False, "sent": sent}


async def start_gateway() -> None:
    if _tasks:
        return
    if not PJSK_RELAY_ENABLED:
        logger.info("PJSK internal relay disabled by PJSK_RELAY_ENABLED")
        return
    _tasks.extend([
        asyncio.create_task(_maintain_backend("haruki", HARUKI_WS_URL, HARUKI_TOKEN, HARUKI_BOT_ID)),
        asyncio.create_task(_maintain_backend("sakura", SAKURA_WS_URL, SAKURA_TOKEN, SAKURA_BOT_ID)),
    ])
    logger.info("PJSK internal relay enabled; no local 8113 ingress is used")


async def stop_gateway() -> None:
    for task in list(_tasks):
        task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks.clear()
    for task in list(_heartbeat_tasks):
        task.cancel()
    if _heartbeat_tasks:
        await asyncio.gather(*_heartbeat_tasks, return_exceptions=True)
    _heartbeat_tasks.clear()
    _reply_routes.clear()
    _legacy_route_kinds.clear()
    _message_cache.clear()
