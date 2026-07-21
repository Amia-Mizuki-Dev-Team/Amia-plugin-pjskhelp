"""PJSK backend relay.

The relay deliberately lives inside ``pjskhelp``.  Gensokyo owns the public
OneBot WebSocket on port 8080; this module only maintains the two outbound
OneBot reverse-WebSocket connections and maps their API calls back to the
original NoneBot event.
"""

from __future__ import annotations

import asyncio
import json
import os
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
    get_real_qq = _qbind.get_real_qq
except Exception:  # pragma: no cover
    get_real_qq = None


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


PJSK_RELAY_ENABLED = _env_bool("PJSK_RELAY_ENABLED", True)
HARUKI_WS_URL = os.getenv("HARUKI_WS_URL", "ws://127.0.0.1:8111")
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
        + _u(r"\u8868\u60c5")
        + r"|"
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
    _u(r"mysekai\u7167\u7247"), _u(r"\u902e\u6355"),
}

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
}

SAKURA_CMDS = {
    "pjskprofile", "b39", "b30", "pjskdetail", "pjskcard", "pjskevent",
    "ss", "wlss", "pinfo", "charinfo", "findcard", "cardinfo", "findevent",
    _u(r"\u7ed9\u770b"), _u(r"\u4e0d\u7ed9\u770b"), _u(r"\u89c6\u5978"),
    _u(r"b30\u5220\u6b4c"), _u(r"b30\u6062\u590d\u6b4c"),
    _u(r"b30\u5220\u6b4c\u5217\u8868"), _u(r"\u8fdb\u5ea6ex"),
    _u(r"\u8fdb\u5ea6apd"), _u(r"\u5bb6\u5177\u8be6\u60c5"),
    _u(r"\u6ce8\u518c"), _u(r"\u5206\u6570\u7ebf"),
    _u(r"5v5\u80dc\u7387"), _u(r"5v5\u5206\u6570"),
    _u(r"tf\u542f\u52a8"), _u(r"\u542c\u6b4c\u8bc6\u66f2"),
    _u(r"\u7ed3\u675f\u731c\u66f2"), _u(r"\u731c\u5361\u9762"),
    _u(r"\u7ed3\u675f\u731c\u5361\u9762"), _u(r"pjsk\u62bd\u5361"),
    _u(r"\u62bd\u5361"), _u(r"\u53cd\u62bd\u5361"), _u(r"\u770b"),
    _u(r"\u968f\u4e2a"), _u(r"\u8471\u4ec0\u4e48"),
}

PREFIX_RE = re.compile(r"^\s*(?:cn|tw|kr|en|jp)?\s*(?:pjsk|sk)?\s*", re.I)
PJSK_PREFIX_RE = re.compile(r"^\s*(?:cn|tw|kr|en|jp)?\s*(?:pjsk|sk)\b", re.I)
COMPACT_B39_RE = re.compile(r"^\s*(?:cn|tw|kr|en|jp)?\s*pjskb39(?:\s|$)", re.I)
SPACED_B39_RE = re.compile(r"^\s*(?:cn|tw|kr|en|jp)?\s*pjsk\s+b39(?:\s|$)", re.I)


@dataclass(slots=True)
class ReplyTarget:
    bot: Any
    event: Any
    user_id: str
    group_id: str | None


_backend_ws: dict[str, Any] = {"haruki": None, "sakura": None}
_reply_routes: dict[str, ReplyTarget] = {}
_tasks: list[asyncio.Task] = []
_heartbeat_tasks: set[asyncio.Task] = set()
_message_cache: dict[str, float] = {}


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
    shared = _match_command(check, SHARED_CMDS)
    haruki = _match_command(check, HARUKI_CMDS)
    sakura = _match_command(check, SAKURA_CMDS)
    if shared:
        haruki = sakura = True
    if PJSK_PREFIX_RE.match(check) and not (haruki or sakura):
        return False, False, True
    return haruki, sakura, False


def _prepend_slash(raw_payload: str, pure_msg: str, cq_prefix: str) -> str:
    if pure_msg.startswith("/"):
        return raw_payload
    data = _loads(raw_payload)
    data["raw_message"] = cq_prefix + "/" + pure_msg.lstrip()
    for seg in data.get("message", []):
        if isinstance(seg, dict) and seg.get("type") == "text":
            text = seg.get("data", {}).get("text", "")
            if text.strip():
                seg["data"]["text"] = re.sub(r"^(\s*)", r"\1/", text, count=1)
                break
    return _dumps(data)


def _rewrite_for_sakura(raw_payload: str, virtual_user_id: Any) -> str:
    data = _loads(raw_payload)
    data["self_id"] = int(SAKURA_BOT_ID)
    real_qq = str(get_real_qq(str(virtual_user_id))) if get_real_qq else str(virtual_user_id)
    if real_qq.isdigit():
        data["user_id"] = int(real_qq)
        if isinstance(data.get("sender"), dict):
            data["sender"]["user_id"] = int(real_qq)
    return _dumps(data)


def _event_payload(event: Any) -> str:
    if hasattr(event, "model_dump"):
        data = event.model_dump()
    elif hasattr(event, "dict"):
        data = event.dict()
    else:  # pragma: no cover - only used by small external adapters/tests
        data = dict(vars(event))
    return _dumps(data)


def _event_user_id(event: Any) -> str:
    return str(getattr(event, "user_id", ""))


def _event_group_id(event: Any) -> str | None:
    group_id = getattr(event, "group_id", None)
    return str(group_id) if group_id else None


def _route_keys(user_id: str, group_id: str | None) -> list[str]:
    keys = [f"user_{user_id}"]
    if get_real_qq:
        real = get_real_qq(user_id)
        if real and str(real) != user_id:
            keys.append(f"user_{real}")
    if group_id:
        keys.insert(0, f"group_{group_id}")
    return keys


def _register_route(target: ReplyTarget) -> None:
    for key in _route_keys(target.user_id, target.group_id):
        _reply_routes[key] = target


def _message_from_api(value: Any) -> Message:
    if isinstance(value, str):
        return Message(value)
    if isinstance(value, list):
        segments = []
        for item in value:
            if isinstance(item, dict) and item.get("type"):
                segments.append(MessageSegment(type=item["type"], data=dict(item.get("data") or {})))
            elif item is not None:
                segments.append(MessageSegment.text(str(item)))
        return Message(segments)
    if isinstance(value, dict) and value.get("type"):
        return Message([MessageSegment(type=value["type"], data=dict(value.get("data") or {}))])
    return Message(str(value or ""))


async def _deliver_backend_message(target: ReplyTarget, action: str, params: dict[str, Any]) -> dict[str, Any]:
    message = _message_from_api(params.get("message", ""))
    group_id = params.get("group_id") or target.group_id
    user_id = params.get("user_id") or target.user_id

    if action in {"send_group_msg"} or (action == "send_msg" and group_id):
        if hasattr(target.bot, "send_group_msg"):
            result = await target.bot.send_group_msg(group_id=int(group_id), message=message)
        else:
            result = await target.bot.send(target.event, message)
    elif action in {"send_private_msg", "send_private_msg_wakeup"} or (action == "send_msg" and user_id):
        if hasattr(target.bot, "send_private_msg"):
            result = await target.bot.send_private_msg(user_id=int(user_id), message=message)
        else:
            result = await target.bot.send(target.event, message)
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
            gid = params.get("group_id")
            uid = params.get("user_id")
            target = _reply_routes.get(f"group_{gid}") if gid else None
            target = target or (_reply_routes.get(f"user_{uid}") if uid else None)
            if target:
                result = await _deliver_backend_message(target, action, params)
                await _ws_send(source_ws, _dumps({"status": "ok", "retcode": 0, "data": result, "echo": echo}))
            elif echo:
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

    user_id = _event_user_id(event)
    group_id = _event_group_id(event)
    cache_key = f"{group_id or 0}:{user_id}:{raw_msg}"
    now = time.time()
    for key, seen in list(_message_cache.items()):
        if now - seen > 1.5:
            _message_cache.pop(key, None)
    if cache_key in _message_cache:
        return {"matched": True, "blocked": False, "sent": []}
    _message_cache[cache_key] = now

    target = ReplyTarget(bot=bot, event=event, user_id=user_id, group_id=group_id)
    _register_route(target)
    raw_payload = _event_payload(event)
    sent: list[str] = []
    if sakura and _backend_ws["sakura"]:
        await _ws_send(_backend_ws["sakura"], _rewrite_for_sakura(raw_payload, user_id))
        sent.append("sakura")
    if haruki and _backend_ws["haruki"]:
        match = re.match(r"^(\s*(?:\[CQ:[^\]]+\]\s*)*)(.*)$", raw_msg)
        cq_prefix, pure_msg = (match.group(1), match.group(2)) if match else ("", raw_msg)
        await _ws_send(_backend_ws["haruki"], _prepend_slash(raw_payload, pure_msg, cq_prefix))
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
    _message_cache.clear()
