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
    self_id = 3889004352

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

    def test_known_regional_commands_route_but_unknown_pjsk_text_is_blocked(self) -> None:
        self.assertEqual(proxy._route_for("/cn逮捕"), (True, False, False))
        self.assertEqual(proxy._route_for("/cn抓包数据"), (True, False, False))
        self.assertEqual(proxy._route_for("/cn烤森抓包"), (True, False, False))
        self.assertEqual(proxy._route_for("/pjsk随便一段文本"), (False, False, True))
        self.assertEqual(proxy._route_for("/cn随便一段文本"), (False, False, True))
        self.assertEqual(proxy._route_for("/pjsk表情制作"), (False, False, True))
        self.assertEqual(proxy._route_for("/pjsk -h"), (False, False, True))

    def test_documented_haruki_aliases_are_loaded_and_prioritized(self) -> None:
        self.assertGreater(len(proxy.HARUKI_DOCUMENTED_CMDS), 250)
        self.assertEqual(proxy._route_for("/抓包状态"), (True, False, False))
        self.assertEqual(proxy._route_for("/自定义个人信息"), (True, False, False))
        self.assertEqual(proxy._route_for("/查卡"), (True, False, False))
        self.assertEqual(proxy._route_for("/pjsk表情"), (True, False, False))

    def test_sakura_legacy_and_dynamic_commands_are_selected(self) -> None:
        self.assertEqual(proxy._route_for("/rk"), (False, True, False))
        self.assertEqual(proxy._route_for("/id"), (False, True, False))
        self.assertEqual(proxy._route_for("/切绑定"), (False, True, False))
        self.assertEqual(proxy._route_for("/b30还原歌"), (False, True, False))
        self.assertEqual(proxy._route_for("/pjsk20连"), (False, True, False))
        self.assertEqual(proxy._route_for("/开启live订阅"), (False, True, False))

    def test_sakura_chunithm_commands_are_case_insensitive(self) -> None:
        for text in (
            "chusearch 初音未来",
            "/CHUSEARCH 初音未来",
            "chuinfo 12345",
            "/CHUINFO 12345",
            "chuchart 12345 ex",
            "chuchart 12345 MA",
            "/CHUCHART 12345 Ult",
            "chu b30",
            "/CHU B30 r10",
        ):
            with self.subTest(text=text):
                self.assertEqual(proxy._route_for(text), (False, True, False))

    def test_chunithm_command_dispatches_only_to_sakura(self) -> None:
        haruki = FakeWS()
        sakura = FakeWS()
        proxy._backend_ws["haruki"] = haruki
        proxy._backend_ws["sakura"] = sakura

        result = asyncio.run(proxy.dispatch_message(FakeBot(), FakeEvent("chuchart 12345 ma")))

        self.assertEqual(result["sent"], ["sakura"])
        self.assertEqual(len(haruki.sent), 0)
        self.assertEqual(len(sakura.sent), 1)
        payload = json.loads(sakura.sent[0])
        self.assertEqual(payload["raw_message"], "chuchart 12345 ma")

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

    def test_haruki_slash_normalization_preserves_leading_whitespace(self) -> None:
        payload = proxy._prepend_slash(
            json.dumps({
                "raw_message": "  cn抓包数据",
                "message": [{"type": "text", "data": {"text": "  cn抓包数据"}}],
            }),
            "cn抓包数据",
            "",
        )
        data = json.loads(payload)
        self.assertEqual(data["raw_message"], "/cn抓包数据")
        self.assertEqual(data["message"][0]["data"]["text"], "  /cn抓包数据")

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

    def test_plain_web_urls_are_markdownized_for_official_bots(self) -> None:
        bot = FakeBot()
        target = proxy.ReplyTarget(bot=bot, event=FakeEvent(), user_id="123", group_id="456")
        proxy._reply_routes["group_456"] = target
        backend = FakeWS()
        asyncio.run(proxy._process_backend_api(
            json.dumps({
                "action": "send_group_msg",
                "params": {
                    "group_id": 456,
                    "message": "请前往 https://upload.sakura-bot.cn 上传数据",
                },
                "echo": "url-1",
            }),
            "sakura",
            backend,
        ))
        message = bot.sent[0][1]
        self.assertEqual(message[0].type, "markdown")
        content = message[0].data["data"]["markdown"]["content"]
        self.assertIn("[打开链接](https://upload.sakura-bot.cn)", content)

    def test_backend_remote_image_is_materialized_as_base64(self) -> None:
        class FakeResponseContent:
            async def iter_chunked(self, _size: int):
                yield b"fake-image"

        class FakeResponse:
            status = 200
            content = FakeResponseContent()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

        class FakeSession:
            def __init__(self, **_kwargs):
                self.response = FakeResponse()

            def get(self, _url: str, **_kwargs):
                return self.response

            async def close(self):
                return None

        original_session = proxy.aiohttp.ClientSession
        proxy.aiohttp.ClientSession = FakeSession
        try:
            message = asyncio.run(proxy._message_from_api([
                {"type": "image", "data": {"file": "https://example.test/pjsk.jpg"}},
            ]))
            string_message = asyncio.run(proxy._message_from_api(
                "[CQ:image,file=https://example.test/pjsk.jpg]"
            ))
        finally:
            proxy.aiohttp.ClientSession = original_session

        self.assertEqual(message[0].type, "image")
        self.assertEqual(message[0].data["file"], "base64://ZmFrZS1pbWFnZQ==")
        self.assertEqual(message[0].data["cache"], "false")
        self.assertEqual(string_message[0].type, "image")
        self.assertEqual(string_message[0].data["file"], "base64://ZmFrZS1pbWFnZQ==")

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

    def test_backend_send_preserves_release010_openid(self) -> None:
        bot = FakeBot()
        target = proxy.ReplyTarget(
            bot=bot,
            event=FakeEvent(),
            user_id="openid-test-user",
            group_id=None,
        )
        proxy._reply_routes["user_openid-test-user"] = target
        backend = FakeWS()
        asyncio.run(proxy._process_backend_api(
            json.dumps({
                "action": "send_private_msg",
                "params": {
                    "user_id": "openid-test-user",
                    "message": [{"type": "text", "data": {"text": "ok"}}],
                },
                "echo": "openid-1",
            }),
            "haruki",
            backend,
        ))
        self.assertEqual(bot.private_sent[0][0], "openid-test-user")
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
