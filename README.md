# Amia-plugin-pjskhelp

PJSK 综合帮助、Haruki/Sakura 命令路由和 Release010 消息兼容网关。正式本地源码来自 `H:\Amia-Develop\src\plugins\pjskhelp`。

## 功能边界

插件包含两部分：

1. 本地帮助：生成 PJSK 分类帮助、分页菜单和图片；
2. 后端网关：把已知命令按规则转发到 Haruki、Sakura 或两者。

它不复制后端完整业务实现，也不直接读取 maimaidx、Economy 或其他插件数据库。

## 帮助指令

```text
pjsk帮助
pjskhelp
pjsk -h
pjsk表情
pjsk表情制作
```

官方 Bot ID 使用 Markdown 与按钮菜单；其他 Bot 使用 HTML 渲染图片，渲染失败时返回带 `HX-PJSK-*` 错误码的中文提示和脱敏诊断文件。

## 后端路由

路由顺序：

```text
本地拦截 → 共享命令 → Haruki 专属 → Sakura 专属 → 不转发
```

后端未连接时不会阻止帮助菜单加载。连接会按 3 秒、30 秒、300 秒退避重试，NoneBot 关闭时取消后台任务和本地监听。

## Chunithm（Sakura 13888）

以下命令只路由到 Sakura：

```text
chusearch <歌曲名>
chuinfo <歌曲ID>
chuchart <歌曲ID> [ex|ma|ult]
chu b30
```

- `chusearch` 不区分大小写，只按歌曲名称匹配；
- `chuinfo` 只接受歌曲 ID；
- `chuchart` 只接受歌曲 ID，可追加 Expert、Master、Ultima 难度后缀；
- `chu b30` 查询 B30、R10 和总 Rating；
- 当前仅支持国服，数据来源于 DivingFish；
- 图片设计归属按上游说明保留，不在本仓库删除署名。

## Release010 身份与消息

- `self_id`、`user_id` 保留字符串/OpenID，不强制转为整数；
- Sakura 转发可通过 QBind 将平台身份映射为真实 QQ；
- 后端图片 URL 会重新下载并转换为 `base64://`，避免 QQ 复用旧 URL 上传缓存；
- 普通网页链接在官方 Bot 路径转换为 Markdown；
- 后端错误不会把长 traceback 直接发给用户；
- `HX-PJSK-*` 错误会附带脱敏诊断文件，并提示将错误移交开发者群 `1053964431`。

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

Token 只能通过本地环境变量提供，不得写入 README、日志、诊断文件或 Git 历史。默认公网地址仅表示当前路由默认值，不是可用性承诺。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .
git diff --check
```

离线测试覆盖命令路由、Chunithm 大小写、Sakura 独占转发、OpenID、官方 Bot Markdown、远端图片重上传、WebSocket 头、回包和错误降级。真实 13888 后端、QQ Markdown/Keyboard、图片展示和诊断文件发送未执行时保持 `NOT RUN`。

## 发布边界

仓库发布代码、模板、脱敏命令目录、测试和兼容状态。不得提交 Token、真实用户映射、原始聊天日志、缓存、截图或生产配置。
