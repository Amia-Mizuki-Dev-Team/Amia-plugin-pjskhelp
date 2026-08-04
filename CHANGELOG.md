# Changelog

## [Unreleased] - 2026-07-28

### Haruki NEO 官方命令目录

- 从 `https://neo.haruki.seiunx.com/bot-help/` 的服务端渲染页面提取命令目录。
- 新增可重复运行的 `scrape_haruki_help.py`，当前目录包含 385 个文档别名。
- `pjskhelp` 启动时加载本地目录；未明确属于 Sakura 的文档命令统一路由到 Haruki。
- 修复 `/pjsk表情` 被旧的 `/pjsk表情制作` 过滤规则误伤。
- Haruki 转发继续统一补 `/`，Sakura 专属的 B30/B39 路由保持不变。
- 补齐 Sakura 的切绑定、B30 还原、花名管理、Live 订阅及动态 `pjskXX连` 路由。
- 未登记的 `pjsk xxx` 与区域文本不再唤醒后端，`pjsk表情制作`、`pjsk -h` 继续强制拦截。
- 官方 Bot 收到后端纯文本网页 URL 时自动转换为 Markdown 链接；CQ 图片 URL 仍下载为 base64 图片。
- 新增无真实 QQ 发送行为的 OneBot WebSocket 后端探针。

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
## Release010 compatibility - 2026-08-01

- preserved the local latest Haruki/Sakura command routing implementation;
- kept card, input_notify, stream, and file message segments when relaying backend output;
- preserved non-numeric Release010 OpenID-like user IDs instead of coercing them to `int`;
- added `HX-PJSK-002` diagnostics when a relay backend is unavailable or help rendering fails.

### Sakura 中二节奏（Chunithm）

- 新增 `chusearch`、`chuinfo`、`chuchart`、`chu b30` 的 Sakura 13888 路由。
- `chusearch` 仅按歌曲名称做不区分大小写匹配；`chuinfo` 和 `chuchart` 仅接受歌曲 ID。
- `chuchart` 支持 `ex`、`ma`、`ult` 后缀；`chu b30` 查询 B30、R10 及总 Rating。
- 参数不在 Amia 本地改写，统一交由 Sakura 使用 DivingFish 国服数据处理；本地不缓存或捆绑该数据。
- 图片设计归属 Uni（GitHub：`@watagashi-uni`）。
