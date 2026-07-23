# Amia-plugin-pjskhelp

PJSK 综合帮助与后端指令网关。

## 项目定位

本插件同时提供 PJSK 帮助入口和 Haruki/Sakura 后端指令转发。帮助内容与后端转发是两个边界明确的部分：帮助命令由本插件本地生成，后端命令按路由规则通过本地 WebSocket 网关转发。

## 当前功能

- `pjsk帮助`、`pjskhelp` 及区域前缀命令；
- 官方 Bot ID `3889004352`、`3889047402` 使用 Markdown 和按钮菜单；
- 普通 Bot 使用 HTML 渲染的图片帮助；
- 帮助菜单支持分类和上一页/下一页按钮；
- `pjskhelp`、`pjsk表情`、`pjsk表情制作`、`pjsk -h` 等本地命令拦截，不转发到后端；
- 共享命令可同时发送到 Haruki 和 Sakura；
- Haruki、Sakura 独有命令按命令集合路由；
- Sakura 转发前可通过 QBind 将虚拟 user_id 改为真实 QQ；
- 启动本地 WebSocket 入口并维护两个后端连接；
- 后端断开后按 3 秒、30 秒、300 秒退避重连；
- NoneBot 关闭时取消后台任务并关闭本地监听。

## 指令路由

路由顺序是：本地拦截 → 共享命令 → Haruki 命令或 Sakura 命令。带 `pjsk` 前缀但未命中已知后端命令的消息会被视为本地未转发消息。后端未连接时，调用方收到“PJSK 后端暂未连接，请稍后重试”。

后端 API 还对 `get_login_info`、`get_version_info`、`get_status`、`get_group_list` 和 `get_friend_list` 提供网关层响应；其他带 echo 的请求按连接路由返回。

## 官方 Bot 与普通 Bot

| 场景 | 输出 |
| --- | --- |
| Bot ID 为 `3889004352` 或 `3889047402` | Markdown 文本、按钮和分页导航 |
| 其他 Bot | HTML 渲染图片，渲染失败时返回错误提示 |

官方 Bot ID 目前硬编码在 `__init__.py`，不是配置项；需要新增官方 Bot 时必须同步代码和测试。

## 配置

```env
PJSK_GATEWAY_HOST=127.0.0.1
PJSK_GATEWAY_PORT=8113
HARUKI_WS_URL=ws://127.0.0.1:8111
SAKURA_WS_URL=ws://101.34.19.31:13888/onebot/v11/ws
HARUKI_TOKEN=
SAKURA_TOKEN=
SAKURA_BOT_ID=3889004352
PJSK_GATEWAY_IDENTITY_QQS=
```

生产环境应通过环境变量覆盖地址、端口、Token、Sakura Bot ID 和身份列表；README 不记录真实 Token 或内网凭据。默认 Sakura 地址属于现有代码的默认值，不应视为可用性保证。

## 后端断线行为

启动后分别维护 Haruki 和 Sakura WebSocket。连接失败或断开会记录 warning，并使用 3 秒、30 秒、300 秒的退避继续连接；NoneBot 关闭时不等待无限重连。后端未连接不会阻止帮助菜单加载。

## 测试方法

当前仓库没有独立测试目录。至少应执行：

```powershell
python -m compileall -q .
```

并补充离线测试覆盖：官方/普通 Bot 分支、帮助分页、区域前缀、共享命令双路由、本地拦截、未知命令不转发、后端未连接提示、重连退避、Sakura 身份改写、echo 回包和关闭清理。

## 维护边界

- 不在帮助网关中复制 PJSK 业务插件的全部实现；
- 不直接读取 maimaidx、Economy 或其他业务数据库；
- 不把 Sakura 默认公网地址当成稳定服务承诺；
- 不把规划中的新路由、后端能力或官方 Bot ID 写成当前已实现。
