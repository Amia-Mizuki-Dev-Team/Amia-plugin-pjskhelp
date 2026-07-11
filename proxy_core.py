import asyncio
import json
import os
import random
import re
import time
from contextlib import suppress
from typing import Any

import aiohttp
import websockets
from nonebot import logger

try:
    import orjson
except Exception:  # pragma: no cover
    orjson = None

try:
    from src.plugins.qbind import get_real_qq
except Exception:  # pragma: no cover
    get_real_qq = None


def _u(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


def _loads(raw: str) -> dict[str, Any]:
    if orjson:
        return orjson.loads(raw)
    return json.loads(raw)


def _dumps(data: dict[str, Any]) -> str:
    if orjson:
        return orjson.dumps(data).decode("utf-8")
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


PJSK_GATEWAY_HOST = os.getenv("PJSK_GATEWAY_HOST", "127.0.0.1")
PJSK_GATEWAY_PORT = int(os.getenv("PJSK_GATEWAY_PORT", "8113"))
HARUKI_WS_URL = os.getenv("HARUKI_WS_URL", "ws://127.0.0.1:8111")
SAKURA_WS_URL = os.getenv("SAKURA_WS_URL", "ws://101.34.19.31:13888/onebot/v11/ws")
HARUKI_TOKEN = os.getenv("HARUKI_TOKEN", "")
SAKURA_TOKEN = os.getenv("SAKURA_TOKEN", "")
SAKURA_BOT_ID = os.getenv("SAKURA_BOT_ID", "3889004352")
IDENTITY_QQS = [
    item.strip()
    for item in os.getenv(
        "PJSK_GATEWAY_IDENTITY_QQS",
        "1005524479,3889004352,3889047402,2854196301,3175824960,1946285730,2583941762,3427185906",
    ).split(",")
    if item.strip()
]
IDENTITY_QQ = IDENTITY_QQS[0] if IDENTITY_QQS else "3889047402"


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

_backend_ws: dict[str, Any] = {"haruki": None, "sakura": None}
_ingress_clients: set[Any] = set()
_reply_routes: dict[str, Any] = {}
_echo_routes: dict[str, Any] = {}
_server: Any = None
_tasks: list[asyncio.Task] = []
_message_cache: dict[str, float] = {}


def _backoff(fail_count: int) -> int:
    if fail_count <= 1:
        return 3
    if fail_count == 2:
        return 30
    return 300


def _headers(self_id: str, token: str = "") -> dict[str, str]:
    headers = {
        "User-Agent": "CQHttp/4.15.0",
        "X-Self-ID": str(self_id),
        "X-Client-Role": "Universal",
        "X-Impl": "gensokyo",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


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
    if not get_real_qq:
        return raw_payload
    real_qq = str(get_real_qq(str(virtual_user_id)))
    if not real_qq or real_qq == str(virtual_user_id):
        return raw_payload
    data = _loads(raw_payload)
    data["user_id"] = int(real_qq)
    data["self_id"] = int(SAKURA_BOT_ID)
    if isinstance(data.get("sender"), dict):
        data["sender"]["user_id"] = int(real_qq)
    return _dumps(data)


async def _process_backend_api(message: str, source: str, source_ws: Any) -> None:
    try:
        data = _loads(message)
        action = data.get("action")
        echo = data.get("echo")
        if action in {"get_login_info", "get_version_info", "get_status", "get_group_list", "get_friend_list"}:
            responses = {
                "get_login_info": {"user_id": int(IDENTITY_QQ), "nickname": "PJSK-Gateway"},
                "get_version_info": {"app_name": "gensokyo", "app_version": "pjsk-gateway", "protocol_version": "v11"},
                "get_status": {"app_initialized": True, "app_enabled": True, "good": True, "online": True},
                "get_group_list": [],
                "get_friend_list": [],
            }
            await _ws_send(source_ws, _dumps({"status": "ok", "retcode": 0, "data": responses[action], "echo": echo}))
            return
        if echo:
            _echo_routes[str(echo)] = source_ws
        params = data.get("params", {})
        gid = params.get("group_id", 0)
        uid = params.get("user_id", 0)
        target = _reply_routes.get(f"group_{gid}") or _reply_routes.get(f"user_{uid}")
        if not target and _ingress_clients:
            target = next(iter(_ingress_clients))
        if target:
            await _ws_send(target, _dumps(data))
        elif echo:
            await _ws_send(source_ws, _dumps({"status": "ok", "retcode": 0, "data": None, "echo": echo}))
    except Exception as exc:
        logger.exception(f"PJSK backend message error from {source}: {exc}")


async def _maintain_backend(name: str, url: str, token: str) -> None:
    fail_count = 0
    while True:
        cancelled = False
        self_id = random.choice(IDENTITY_QQS) if IDENTITY_QQS else IDENTITY_QQ
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url, headers=_headers(self_id, token), timeout=15) as ws:
                    _backend_ws[name] = ws
                    fail_count = 0
                    logger.info(f"PJSK gateway connected to {name}: {url}")
                    await _mock_lifecycle(ws, self_id)
                    asyncio.create_task(_mock_heartbeat(ws, self_id))
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
            logger.warning(f"PJSK gateway {name} disconnected: {exc}")
        finally:
            _backend_ws[name] = None
            # Do not wait through reconnect backoff while the application is stopping.
            if not cancelled:
                await asyncio.sleep(_backoff(fail_count))


async def _handle_ingress(ws: Any) -> None:
    _ingress_clients.add(ws)
    try:
        async for message in ws:
            try:
                data = _loads(message)
                echo = data.get("echo")
                if echo and str(echo) in _echo_routes:
                    await _ws_send(_echo_routes.pop(str(echo)), message)
                    continue
                if data.get("post_type") == "meta_event":
                    continue
                if data.get("post_type") in {"notice", "request"}:
                    for backend in _backend_ws.values():
                        if backend:
                            await _ws_send(backend, message)
                    continue
                if data.get("post_type") != "message":
                    continue

                raw_msg = str(data.get("raw_message", "")).strip()
                if not raw_msg or len(raw_msg) > 300:
                    continue
                user_id = data.get("user_id")
                group_id = int(data.get("group_id", 0) or 0)
                now = time.time()
                for key, seen in list(_message_cache.items()):
                    if now - seen > 1.5:
                        _message_cache.pop(key, None)
                cache_key = f"{group_id}:{user_id}:{raw_msg}"
                if cache_key in _message_cache:
                    continue
                _message_cache[cache_key] = now

                match = re.match(r"^(\s*(?:\[CQ:[^\]]+\]\s*)*)(.*)$", raw_msg)
                cq_prefix, pure_msg = (match.group(1), match.group(2)) if match else ("", raw_msg)
                haruki, sakura, blocked = _route_for(pure_msg)
                if blocked or not (haruki or sakura):
                    continue

                if group_id:
                    _reply_routes[f"group_{group_id}"] = ws
                _reply_routes[f"user_{user_id}"] = ws

                if sakura and _backend_ws["sakura"]:
                    await _ws_send(_backend_ws["sakura"], _rewrite_for_sakura(message, user_id))
                if haruki and _backend_ws["haruki"]:
                    await _ws_send(_backend_ws["haruki"], _prepend_slash(message, pure_msg, cq_prefix))
            except Exception as exc:
                logger.warning(f"PJSK gateway ingress message skipped: {exc}")
    finally:
        _ingress_clients.discard(ws)
        stale = [key for key, value in _reply_routes.items() if value == ws]
        for key in stale:
            _reply_routes.pop(key, None)


async def start_gateway() -> None:
    global _server
    if _server:
        return
    try:
        _server = await websockets.serve(_handle_ingress, PJSK_GATEWAY_HOST, PJSK_GATEWAY_PORT, max_size=None)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 10048 or getattr(exc, "errno", None) == 10048:
            logger.warning(
                f"PJSK gateway port already in use, skip local listener: "
                f"ws://{PJSK_GATEWAY_HOST}:{PJSK_GATEWAY_PORT}"
            )
            return
        raise
    _tasks.extend([
        asyncio.create_task(_maintain_backend("haruki", HARUKI_WS_URL, HARUKI_TOKEN)),
        asyncio.create_task(_maintain_backend("sakura", SAKURA_WS_URL, SAKURA_TOKEN)),
    ])
    logger.info(f"PJSK gateway listening on ws://{PJSK_GATEWAY_HOST}:{PJSK_GATEWAY_PORT}")


async def stop_gateway() -> None:
    global _server
    for task in list(_tasks):
        task.cancel()
        done, _ = await asyncio.wait({task}, timeout=2)
        if task not in done:
            logger.warning("PJSK gateway backend task did not stop within 2 seconds; continuing shutdown")
        else:
            with suppress(asyncio.CancelledError, Exception):
                task.result()
    _tasks.clear()
    if _server:
        _server.close()
        try:
            await asyncio.wait_for(_server.wait_closed(), timeout=3)
        except asyncio.TimeoutError:
            logger.warning("PJSK gateway did not close within 3 seconds; continuing shutdown")
        _server = None
