"""Probe a OneBot reverse-WebSocket backend without sending to real QQ.

The probe injects fake group events, captures backend ``send_*`` actions, and
acknowledges them locally. It is intended for Haruki/Sakura routing and output
compatibility checks.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from typing import Any

import aiohttp


URL_RE = re.compile(r"https?://[^\s\]>)\"']+", re.IGNORECASE)


def dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def event_payload(
    command: str,
    self_id: int,
    message_id: int,
    user_id: int,
    group_id: int,
) -> dict[str, Any]:
    return {
        "time": int(time.time()),
        "self_id": self_id,
        "post_type": "message",
        "message_type": "group",
        "sub_type": "normal",
        "user_id": user_id,
        "group_id": group_id,
        "message_id": message_id,
        "message": [{"type": "text", "data": {"text": command}}],
        "original_message": [{"type": "text", "data": {"text": command}}],
        "raw_message": command,
        "sender": {
            "user_id": user_id,
            "nickname": "pjskhelp-probe",
            "card": "",
            "role": "member",
            "sex": "unknown",
            "age": 0,
        },
    }


def flatten_message(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                data = item.get("data") or {}
                parts.append(str(data.get("text") or data.get("url") or data.get("file") or ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(value or "")


async def acknowledge(ws: aiohttp.ClientWebSocketResponse, data: dict[str, Any]) -> None:
    echo = data.get("echo")
    if echo is None:
        return
    action = data.get("action", "")
    response_data: Any = {"message_id": int(time.time() * 1000)}
    if action == "get_login_info":
        response_data = {"user_id": 999_999_998, "nickname": "pjskhelp-probe"}
    elif action in {"get_group_list", "get_friend_list"}:
        response_data = []
    elif action == "get_status":
        response_data = {"online": True, "good": True}
    await ws.send_str(dumps({"status": "ok", "retcode": 0, "data": response_data, "echo": echo}))


async def run_probe(
    url: str,
    self_id: int,
    commands: list[str],
    *,
    user_id: int,
    group_id: int,
    connect_timeout: float,
    command_timeout: float,
) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "NapCat/OneBot11",
        "X-Self-ID": str(self_id),
        "X-Client-Role": "Universal",
        "X-Impl": "napcat",
    }
    results = []
    timeout = aiohttp.ClientTimeout(total=None, connect=connect_timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.ws_connect(url, headers=headers) as ws:
            await ws.send_str(dumps({
                "post_type": "meta_event",
                "meta_event_type": "lifecycle",
                "sub_type": "connect",
                "time": int(time.time()),
                "self_id": self_id,
            }))
            for index, command in enumerate(commands, start=1):
                await ws.send_str(dumps({
                    "post_type": "meta_event",
                    "meta_event_type": "heartbeat",
                    "time": int(time.time()),
                    "self_id": self_id,
                    "status": {"online": True, "good": True},
                    "interval": 5000,
                }))
                await ws.send_str(dumps(event_payload(
                    command,
                    self_id,
                    700_000 + index,
                    user_id,
                    group_id,
                )))
                outputs: list[str] = []
                actions: list[str] = []
                deadline = asyncio.get_running_loop().time() + command_timeout
                while asyncio.get_running_loop().time() < deadline:
                    remaining = deadline - asyncio.get_running_loop().time()
                    try:
                        message = await ws.receive(timeout=min(1.2, max(0.05, remaining)))
                    except asyncio.TimeoutError:
                        if outputs:
                            break
                        continue
                    if message.type != aiohttp.WSMsgType.TEXT:
                        break
                    data = json.loads(message.data)
                    action = str(data.get("action") or "")
                    if action:
                        actions.append(action)
                    if action.startswith("send"):
                        outputs.append(flatten_message((data.get("params") or {}).get("message")))
                    await acknowledge(ws, data)

                joined = "\n".join(output for output in outputs if output)
                results.append({
                    "command": command,
                    "actions": actions,
                    "output": joined,
                    "urls": sorted(set(URL_RE.findall(joined))),
                })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--self-id", required=True, type=int)
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    parser.add_argument("--command-timeout", type=float, default=8.0)
    parser.add_argument("--user-id", type=int, default=999_999_999)
    parser.add_argument("--group-id", type=int, default=999_999_999)
    parser.add_argument("commands", nargs="+")
    args = parser.parse_args()
    results = asyncio.run(run_probe(
        args.url,
        args.self_id,
        args.commands,
        user_id=args.user_id,
        group_id=args.group_id,
        connect_timeout=args.connect_timeout,
        command_timeout=args.command_timeout,
    ))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
