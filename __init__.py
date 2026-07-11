import re
from nonebot import get_driver, logger, on_regex
from nonebot.plugin import PluginMetadata
from nonebot.exception import FinishedException  # 导入 Nonebot 结束异常
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment, Message

from .builder import build_pjsk_markdown
from .render import get_mizuki_help_image
from .data_source import HELP_MD_MENUS, HELP_IMG_DATA, HELP_PAGE_ORDER
from .proxy_core import start_gateway, stop_gateway


@get_driver().on_startup
async def _start_pjsk_gateway():
    try:
        await start_gateway()
    except Exception as exc:
        logger.exception(f"failed to start PJSK gateway: {exc}")


@get_driver().on_shutdown
async def _stop_pjsk_gateway():
    await stop_gateway()

__plugin_meta__ = PluginMetadata(
    name="Pjskhelp",
    description="Project Sekai 综合帮助菜单",
    usage=(
        "使用说明：\n"
        "1. 官方Bot环境 (3889004352 / 3889047402)：直接发送 [pjsk帮助] 唤起交互式 Markdown 菜单。\n"
        "2. 普通Bot环境：发送 [pjsk帮助] 获取总分类图。"
    ),
    extra={
        "author": "Mizuki Dev Team | HongXing(Jiangsu) Dev Team",
        "version": "1.0.3"
    }
)

# 官方 Bot ID 列表（支持 Markdown+按钮 交互的 Bot）
OFFICIAL_BOT_IDS = ["3889004352", "3889047402"]

# 中文 page key 映射（用于非官方 Bot 的图片模式）
PAGE_KEY_TO_CN = {
    "main": "main", "account_1": "账号", "account_2": "账号",
    "music_1": "乐曲", "music_2": "乐曲",
    "card_1": "卡牌", "card_2": "卡牌",
    "event_1": "活动", "event_2": "活动",
    "mysekai_1": "烤森", "mysekai_2": "烤森",
    "misc_1": "杂项", "misc_2": "杂项",
}

pjsk_help = on_regex(r"^[/\s]*(?:cn|tw|kr|en|jp)?pjsk(?:help|帮助)\s*(.*)", flags=re.IGNORECASE, priority=5, block=True)

# 吃掉 pjsk表情制作 / pjsk -h 等不应被后端响应的指令
_pjsk_block = on_regex(
    r"^[/\s]*(?:cn|tw|kr|en|jp)?\s*pjsk\s*(?:表情制作|-h)",
    flags=re.IGNORECASE, priority=4, block=True
)
@_pjsk_block.handle()
async def _block_pjsk_noise():
    # ponytail: 静默吃掉，不下发给后端
    pass

def _add_nav_buttons(buttons: list, page_key: str) -> list:
    """根据 HELP_PAGE_ORDER 自动添加上一页/下一页导航按钮"""
    if page_key == "main" or page_key not in HELP_PAGE_ORDER:
        return buttons
    idx = HELP_PAGE_ORDER.index(page_key)
    nav_row = []
    if idx > 0:
        prev_key = HELP_PAGE_ORDER[idx - 1]
        nav_row.append({"render_data.label": "⬅️ 上一页", "action.data": f"pjsk帮助 {prev_key}", "action.enter": True})
    if idx < len(HELP_PAGE_ORDER) - 1:
        next_key = HELP_PAGE_ORDER[idx + 1]
        nav_row.append({"render_data.label": "➡️ 下一页", "action.data": f"pjsk帮助 {next_key}", "action.enter": True})
    if nav_row:
        buttons = list(buttons) + [nav_row]
    return buttons

@pjsk_help.handle()
async def handle_pjsk_help(bot: Bot, event: MessageEvent):
    match = re.match(r"^[/\s]*(?:cn|tw|kr|en|jp)?pjsk(?:help|帮助)\s*(.*)", event.get_plaintext().strip(), re.IGNORECASE)
    category = match.group(1).strip() if match else ""
    
    # 分支 1：官方 Bot (走 Markdown + 按钮)
    if str(bot.self_id) in OFFICIAL_BOT_IDS:
        if not category or category not in HELP_MD_MENUS:
            category = "main"
            
        menu_data = HELP_MD_MENUS[category]
        buttons = _add_nav_buttons(menu_data["buttons"], category)
        md_msg = Message(build_pjsk_markdown(menu_data["md_text"], buttons))
        await pjsk_help.finish(md_msg)
        
    # 分支 2：普通 Bot (走 Htmlrender 长图)
    else:
        cn_key = PAGE_KEY_TO_CN.get(category, category)
        if cn_key not in HELP_IMG_DATA:
            cn_key = "main"
            
        cmd_list = HELP_IMG_DATA[cn_key]
        
        try:
            title_text = "综合模块导航" if cn_key == "main" else f"模块：{cn_key}"
            img_bytes = await get_mizuki_help_image(title_text, cmd_list)
            await pjsk_help.finish(MessageSegment.image(img_bytes))
        except FinishedException:
            # 关键修复：放行 Nonebot 的正常结束流
            raise
        except Exception as e:
            await pjsk_help.finish(f"渲染帮助图片失败: {str(e)}")
