from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import nonebot
import aiohttp
import websockets
from websockets.datastructures import Headers
from websockets.http11 import Response


MODULE_PATH = Path(__file__).resolve().parents[1] / "proxy_core.py"
SPEC = importlib.util.spec_from_file_location("pjsk_proxy_core_test", MODULE_PATH)
assert SPEC and SPEC.loader
proxy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = proxy
nonebot.require = lambda _name: SimpleNamespace(get_real_qq=lambda value: None)
SPEC.loader.exec_module(proxy)


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, value: str) -> None:
        self.sent.append(value)


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, object]] = []
        self.private_sent: list[tuple[int, object]] = []

    async def send_group_msg(self, *, group_id: int, message: object) -> dict[str, int]:
        self.sent.append((group_id, message))
        return {"message_id": 42}

    async def send_private_msg(self, *, user_id: int, message: object) -> dict[str, int]:
        self.private_sent.append((user_id, message))
        return {"message_id": 43}


class FakeEvent:
    user_id = 123
    group_id = 456

    def __init__(self, command: str = "pjsk b30") -> None:
        self.command = command

    def get_plaintext(self) -> str:
        return self.command

    def model_dump(self) -> dict:
        return {
            "post_type": "message",
            "self_id": 999,
            "user_id": self.user_id,
            "group_id": self.group_id,
            "message_type": "group",
            "message": [{"type": "text", "data": {"text": self.command}}],
            "original_message": [{"type": "text", "data": {"text": self.command}}],
            "raw_message": self.command,
        }


class TestProxyCore(unittest.TestCase):
    def tearDown(self) -> None:
        proxy._backend_ws["haruki"] = None
        proxy._backend_ws["sakura"] = None
        proxy._reply_routes.clear()
        proxy._message_cache.clear()

    def test_route_aliases_and_local_filters(self) -> None:
        self.assertEqual(proxy._route_for("pjsk b30")[:2], (False, True))
        self.assertEqual(proxy._route_for("cnpjsk b30")[:2], (False, True))
        self.assertEqual(proxy._route_for("pjskb39"), (False, True, False))
        self.assertEqual(proxy._route_for("cnpjskb39"), (False, True, False))
        self.assertEqual(proxy._route_for("pjsk b39"), (False, False, True))
        self.assertEqual(proxy._route_for("pjsk帮助")[2], True)
        self.assertEqual(proxy._route_for("pjsk表情制作")[2], True)

    def test_napcat_headers_are_stable_and_token_is_optional(self) -> None:
        first = proxy._headers("3889004352")
        second = proxy._headers("3889004352")
        self.assertEqual(first, second)
        self.assertEqual(first["X-Self-ID"], "3889004352")
        self.assertEqual(first["X-Client-Role"], "Universal")
        self.assertNotIn("Authorization", first)
        self.assertEqual(proxy._headers("1", "secret")["Authorization"], "Bearer secret")

    def test_sakura_rewrite_always_uses_stable_bot_identity(self) -> None:
        payload = proxy._rewrite_for_sakura(
            json.dumps({"post_type": "message", "self_id": 9, "user_id": 123, "sender": {"user_id": 123}}),
            123,
        )
        data = json.loads(payload)
        self.assertEqual(data["self_id"], int(proxy.SAKURA_BOT_ID))
        self.assertEqual(data["user_id"], 123)

    def test_internal_dispatch_sends_only_to_selected_backend(self) -> None:
        haruki = FakeWS()
        sakura = FakeWS()
        proxy._backend_ws["haruki"] = haruki
        proxy._backend_ws["sakura"] = sakura
        result = asyncio.run(proxy.dispatch_message(FakeBot(), FakeEvent()))
        self.assertEqual(result["sent"], ["sakura"])
        self.assertEqual(len(haruki.sent), 0)
        self.assertEqual(len(sakura.sent), 1)
        self.assertEqual(json.loads(sakura.sent[0])["self_id"], int(proxy.SAKURA_BOT_ID))

    def test_haruki_regional_commands_always_receive_slash(self) -> None:
        command = "cn\u4e2a\u4eba\u4fe1\u606f"
        haruki = FakeWS()
        proxy._backend_ws["haruki"] = haruki

        result = asyncio.run(proxy.dispatch_message(FakeBot(), FakeEvent(command)))

        self.assertEqual(result["sent"], ["haruki"])
        payload = json.loads(haruki.sent[0])
        self.assertEqual(payload["raw_message"], "/" + command)
        self.assertEqual(payload["message"][0]["data"]["text"], "/" + command)

        proxy._backend_ws["haruki"] = FakeWS()
        slash_result = asyncio.run(proxy.dispatch_message(FakeBot(), FakeEvent("/" + command)))
        self.assertEqual(slash_result["sent"], ["haruki"])
        slash_payload = json.loads(proxy._backend_ws["haruki"].sent[0])
        self.assertEqual(slash_payload["raw_message"], "/" + command)

    def test_backend_send_api_returns_to_original_group(self) -> None:
        bot = FakeBot()
        target = proxy.ReplyTarget(bot=bot, event=FakeEvent(), user_id="123", group_id="456")
        proxy._reply_routes["group_456"] = target
        backend = FakeWS()
        asyncio.run(proxy._process_backend_api(
            json.dumps({
                "action": "send_group_msg",
                "params": {"group_id": 456, "message": [{"type": "text", "data": {"text": "ok"}}]},
                "echo": "e1",
            }),
            "sakura",
            backend,
        ))
        self.assertEqual(len(bot.sent), 1)
        self.assertEqual(bot.sent[0][0], 456)
        self.assertEqual(json.loads(backend.sent[0])["retcode"], 0)

    def test_backend_private_wakeup_preserves_media_segments(self) -> None:
        bot = FakeBot()
        target = proxy.ReplyTarget(bot=bot, event=FakeEvent(), user_id="123", group_id=None)
        proxy._reply_routes["user_123"] = target
        backend = FakeWS()
        asyncio.run(proxy._process_backend_api(
            json.dumps({
                "action": "send_private_msg_wakeup",
                "params": {
                    "user_id": 123,
                    "message": [
                        {"type": "record", "data": {"file": "https://example.test/a.silk"}},
                        {"type": "file", "data": {"file": "file:///tmp/a.txt", "file_name": "a.txt"}},
                    ],
                },
                "echo": "wake-1",
            }),
            "haruki",
            backend,
        ))
        self.assertEqual(len(bot.private_sent), 1)
        self.assertEqual(bot.private_sent[0][0], 123)
        message = bot.private_sent[0][1]
        self.assertEqual(message[0].type, "record")
        self.assertEqual(message[1].type, "file")
        self.assertEqual(message[1].data["file_name"], "a.txt")
        self.assertEqual(json.loads(backend.sent[0])["retcode"], 0)

    def test_strict_reverse_ws_accepts_napcat_profile(self) -> None:
        async def run() -> None:
            accepted: asyncio.Future[dict[str, str]] = asyncio.get_running_loop().create_future()

            async def process_request(connection, request):
                headers = request.headers
                expected = proxy._headers("3889004352")
                missing = [key for key, value in expected.items() if headers.get(key) != value]
                if missing:
                    return Response(403, "Forbidden", Headers([("Content-Type", "text/plain")]), b"strict")
                if not accepted.done():
                    accepted.set_result({key: headers.get(key, "") for key in expected})
                return None

            async def handler(connection) -> None:
                await connection.recv()

            server = await websockets.serve(handler, "127.0.0.1", 0, process_request=process_request)
            port = server.sockets[0].getsockname()[1]
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(
                        f"ws://127.0.0.1:{port}/onebot/v11/ws",
                        headers=proxy._headers("3889004352"),
                    ) as ws:
                        await proxy._mock_lifecycle(ws, "3889004352")
                        headers = await asyncio.wait_for(accepted, timeout=2)
                        self.assertEqual(headers["X-Self-ID"], "3889004352")
                        self.assertEqual(headers["X-Client-Role"], "Universal")
                        self.assertEqual(headers["X-Impl"], proxy.WS_IMPL)
            finally:
                server.close()
                await server.wait_closed()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
