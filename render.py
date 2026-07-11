from pathlib import Path

TEMPLATE_PATH = str(Path(__file__).parent / "templates")

async def get_mizuki_help_image(category_name: str, commands_list: list) -> bytes:
    # ponytail: 惰性导入避免 nonebot_plugin_htmlrender 模块级插件上下文检测
    from nonebot_plugin_htmlrender import template_to_pic
    """
    渲染带有指定分类名和指令列表的帮助图片
    """
    template_data = {
        "category_name": category_name,
        "commands": commands_list
    }
    
    # 移除了 viewport 参数，交由模板内部的 CSS 控制图片尺寸
    image_bytes = await template_to_pic(
        template_path=TEMPLATE_PATH,
        template_name="mizuki_help.html",
        templates=template_data
    )
    
    return image_bytes
