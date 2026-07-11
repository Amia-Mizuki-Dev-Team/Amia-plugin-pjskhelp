from typing import Any, Dict, List
from nonebot.adapters.onebot.v11 import MessageSegment


def _normalize_button(btn: Dict[str, Any]) -> Dict[str, Any]:
    """
    将扁平键名的按钮字典转换为标准的嵌套字典。
    例如 {"render_data.label": "文字"} -> {"render_data": {"label": "文字"}}
    """
    nested: Dict[str, Any] = {}
    for key, value in btn.items():
        parts = key.split(".")
        current = nested
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return nested


def build_pjsk_markdown(md_text: str, buttons_config: List[List[Dict[str, Any]]]) -> MessageSegment:
    """
    原生构建带有 Markdown 和底层按钮的 MessageSegment
    :param md_text: Markdown 文本内容
    :param buttons_config: 按钮配置二维列表，使用扁平键名格式：
        {"render_data.label": "按钮", "action.data": "指令"}
        也兼容旧版 {"label": "按钮", "data": "指令"} 简写格式。
    """
    rows = []
    for row_btns in buttons_config:
        btn_list = []
        for btn in row_btns:
            # 先标准化为嵌套结构
            b = _normalize_button(btn)

            # 兼容旧版简写格式 {"label": "...", "data": "..."}
            rd = b.setdefault("render_data", {})
            if "label" in btn and "label" not in rd:
                rd["label"] = btn["label"]
            label = rd.get("label", "按钮")
            rd.setdefault("visited_label", label)
            rd.setdefault("style", 1)

            action = b.setdefault("action", {})
            if "data" in btn and "data" not in action:
                action["data"] = btn["data"]
            action.setdefault("type", 2)
            action.setdefault("permission", {"type": 2})
            action.setdefault("data", "")
            action.setdefault("enter", False)
            action.setdefault("unsupport_tips", "请更新客户端以查看按钮")

            if "id" not in b:
                b["id"] = f"btn_{hash(label) & 0xffff}"

            btn_list.append(b)
        rows.append({"buttons": btn_list})

    md_data = {
        "markdown": {"content": md_text},
        "keyboard": {"content": {"rows": rows}}
    }
    return MessageSegment(type="markdown", data={"data": md_data})