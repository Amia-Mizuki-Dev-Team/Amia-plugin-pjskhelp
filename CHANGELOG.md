# Changelog

## [Unreleased] - 2026-07-21

### Sakura / Haruki 双后端

- Sakura 使用最新 PJSK WebSocket：`ws://101.34.19.31:13888/onebot/v11/ws`。
- Haruki 保持本地 `ws://127.0.0.1:8111`，由 mzk-pjsk 提供服务。
- Sakura 转发使用稳定的 Sakura Bot 身份，并保留 NapCat/OneBot 兼容请求头。
- Haruki 区域指令及后续转发自动补 `/`，例如 `cn个人信息` 转发为 `/cn个人信息`。
- 私聊唤醒、媒体消息和原群上下文继续按后端响应路由回原会话。

### 指令过滤

- 正确识别 `pjskb39`、`cnpjskb39` 等紧凑写法，并路由到 Sakura。
- 保留 `pjsk b30`、`cnpjsk b30` 等 B30 写法。
- 拦截错误的 `pjsk b39`，避免被 Sakura 的 `b39` 或表情制作入口误触发。
- 继续过滤 `pjsk表情制作`、`pjsk -h` 等不应转发的本地指令。

### 验证

- `python -m unittest discover -s tests -v`：8/8 通过。
- 覆盖 B30/B39 路由、Haruki 斜杠补全、Sakura 身份重写、媒体消息保留、后端选择和 NapCat 请求头。
- 真实 Sakura 与 Haruki 的长连接状态仍以部署机日志为准；本文件不把未运行时复测的外部服务状态标记为已完成。
