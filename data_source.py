from typing import Dict, Any, List

# ==================== 分页帮助菜单 ====================
# 每页包含：md_text(文案), buttons(按钮行)
# 每行最多2个按钮。导航按钮由 __init__.py 自动添加。
# 所有按钮使用扁平键名格式：{"render_data.label": "文字", "action.data": "指令"}
HELP_PAGE_ORDER: List[str] = [
    "main",
    "account_1", "account_2",
    "music_1", "music_2",
    "card_1", "card_2",
    "event_1", "event_2",
    "mysekai_1", "mysekai_2",
    "misc_1", "misc_2",
]

HELP_MD_MENUS: Dict[str, Dict[str, Any]] = {
    "main": {
        "md_text": "### 🌟 PJSK 综合帮助中心\n\n> 点击下方按钮查看各模块指令。\n> 提示：非官方 Bot 请发送 `pjsk帮助 模块名` 获取帮助图。",
        "buttons": [
            [
                {"render_data.label": "👤 账号", "action.data": "pjsk帮助 account_1", "action.enter": True},
                {"render_data.label": "🎵 乐曲", "action.data": "pjsk帮助 music_1", "action.enter": True},
            ],
            [
                {"render_data.label": "🃏 卡牌", "action.data": "pjsk帮助 card_1", "action.enter": True},
                {"render_data.label": "🏆 活动", "action.data": "pjsk帮助 event_1", "action.enter": True},
            ],
            [
                {"render_data.label": "🏝️ 烤森", "action.data": "pjsk帮助 mysekai_1", "action.enter": True},
                {"render_data.label": "🛠️ 杂项", "action.data": "pjsk帮助 misc_1", "action.enter": True},
            ],
        ]
    },
    "account_1": {
        "md_text": (
            "### 👤 账号与信息 (1/2)\n\n"
            "> **绑定**：`绑定 <ID>` (例: 绑定 123456789)\n"
            "> **验证**：`pjsk验证` (获取高级查询权限)\n"
            "> **详情**：`/个人信息` / `pjskdetail`\n"
            "> **高分统计**：`rk` / `b39` / `pjsk b30`\n"
            "> **过曲进度**：`进度` / `pjsk进度ex/apd`\n\n"
            "> 🔗 **上传数据**: Haruki <https://haruki.seiunx.com/> | Sakura <http://go.mikuware.top/>"
        ),
        "buttons": [
            [
                {"render_data.label": "账号验证", "action.data": "pjsk验证", "action.enter": True},
                {"render_data.label": "查详情", "action.data": "pjskdetail", "action.enter": True},
            ],
            [
                {"render_data.label": "查B30", "action.data": "cnpjsk b30", "action.enter": True},
                {"render_data.label": "查B39", "action.data": "cnpjsk b39", "action.enter": True},
            ],
        ]
    },
    "account_2": {
        "md_text": (
            "### 👤 账号与信息 (2/2)\n\n"
            "> **抓包状态**：`抓包数据` / `烤森抓包`\n"
            "> **绑定列表**：`绑定列表` (查看所有绑定)\n"
            "> **隐藏/显示**: `隐藏抓包` / `展示抓包` / `隐藏ID` / `显示ID`\n"
            "> **逮捕**：`逮捕` (查 EX/MASTER FC/AP 进度)\n"
            "> **注册时间**：`查时间` / `注册时间`\n"
            "> **设置主号**：`设置主账号`\n"
            "> **自定义背景**：`上传个人信息背景`\n"
            "> **他人信息**：`pjskprofile` / `视奸` (需对方 `给看`)"
        ),
        "buttons": [
            [
                {"render_data.label": "抓包状态", "action.data": "抓包数据", "action.enter": True},
                {"render_data.label": "绑定列表", "action.data": "绑定列表", "action.enter": True},
            ],
            [
                {"render_data.label": "逮捕", "action.data": "逮捕", "action.enter": True},
                {"render_data.label": "查注册时间", "action.data": "查时间", "action.enter": True},
            ],
        ]
    },
    "music_1": {
        "md_text": (
            "### 🎵 乐曲与谱面 (1/2)\n\n"
            "> **查单曲**：`/查曲 <名称>` (例: /查曲 六兆年)\n"
            "> **定数排行**：`难度排行 <等级> <难度>`\n"
            "> **谱面预览**：`<曲名> 谱面预览` (可加 ex/apd)\n"
            "> **技能预览**：`<曲名> 技能预览`\n"
            "> **自定义底色**：`设置谱面底色 black`\n"
            "> **听歌识曲**：`tf启动` / `听歌识曲`"
        ),
        "buttons": [
            [
                {"render_data.label": "查曲示例", "action.data": "/查曲 六兆年", "action.enter": True},
                {"render_data.label": "定数排行", "action.data": "难度排行 30 master", "action.enter": True},
            ],
            [
                {"render_data.label": "谱面预览", "action.data": "六兆年 谱面预览", "action.enter": True},
                {"render_data.label": "技能预览", "action.data": "六兆年 技能预览", "action.enter": True},
            ],
            [
                {"render_data.label": "听歌识曲", "action.data": "pjsk听歌识曲", "action.enter": True},
            ],
        ]
    },
    "music_2": {
        "md_text": (
            "### 🎵 乐曲与谱面 (2/2)\n\n"
            "> **定数表**：`定数表` (全谱面定数)\n"
            "> **查曲绘**：`查曲绘 <曲名>`\n"
            "> **歌曲列表**：`歌曲列表` / `乐曲列表`\n"
            "> **歌曲排行**：`歌曲排行 <模式> <条件>`\n"
            "> **歌曲meta**：`歌曲meta <曲名>`\n"
            "> **按参数筛**：`查物量 1000` / `查bpm 200`\n"
            "> **打歌奖励**：`打歌奖励` / `歌曲挖矿`\n"
            "> **随机选歌**：`随个 <难度>` / `葱什么`"
        ),
        "buttons": [
            [
                {"render_data.label": "定数表", "action.data": "定数表", "action.enter": True},
                {"render_data.label": "查曲绘", "action.data": "查曲绘 六兆年", "action.enter": True},
            ],
            [
                {"render_data.label": "查物量", "action.data": "查物量 1000", "action.enter": True},
                {"render_data.label": "查BPM", "action.data": "查bpm 200", "action.enter": True},
            ],
        ]
    },
    "card_1": {
        "md_text": (
            "### 🃏 卡牌与组队 (1/2)\n\n"
            "> **查卡**：`查卡 <参数>` (例: 查卡 miku 4星 蓝)\n"
            "> **图鉴**：`查箱` / `卡牌一览 <条件>`\n"
            "> **个人图鉴**：`pjskcard <花名>`\n"
            "> **查卡面**：`card <编号>` / `卡面 <编号>`\n"
            "> **查贴纸**：`查贴纸 <角色>`\n"
            "> **查卡池**：`查卡池` / `卡池列表`"
        ),
        "buttons": [
            [
                {"render_data.label": "查卡示例", "action.data": "查卡 miku 4星", "action.enter": True},
                {"render_data.label": "个人图鉴", "action.data": "pjskcard miku", "action.enter": True},
            ],
            [
                {"render_data.label": "卡牌一览", "action.data": "卡牌一览 miku", "action.enter": True},
                {"render_data.label": "查卡池", "action.data": "查卡池", "action.enter": True},
            ],
        ]
    },
    "card_2": {
        "md_text": (
            "### 🃏 卡牌与组队 (2/2)\n\n"
            "> **查箱获取**：`查箱`\n"
            "> **查贴纸**：`查贴纸 miku`\n"
            "> **模拟抽卡**：`抽卡 <数量>` / `反抽卡`\n"
            "> **猜卡面**：`猜卡面`\n"
            "> **组队系统**：`活动组卡` / `挑战组卡` / `加成组卡` / `烤森组卡`"
        ),
        "buttons": [
            [
                {"render_data.label": "查箱获取", "action.data": "查箱", "action.enter": True},
                {"render_data.label": "查贴纸", "action.data": "查贴纸 miku", "action.enter": True},
            ],
            [
                {"render_data.label": "模拟抽卡", "action.data": "pjsk抽卡", "action.enter": True},
                {"render_data.label": "猜卡面", "action.data": "pjsk猜卡面", "action.enter": True},
            ],
        ]
    },
    "event_1": {
        "md_text": (
            "### 🏆 活动与榜线 (1/2)\n\n"
            "> **查活动**：`/查活动 <ID/缩写>`\n"
            "> **档线**：`sk线` / `榜线`\n"
            "> **预测**：`sk预测` / `榜线预测`\n"
            "> **时速**：`时速` / `日速`\n"
            "> **查房**：`查房` / `ptr`\n"
            "> **玩家轨迹**：`玩家追踪` / `档线轨迹`\n"
            "> **sk查分**：`sk查分` / `sk查询`"
        ),
        "buttons": [
            [
                {"render_data.label": "当前活动", "action.data": "/查活动", "action.enter": True},
                {"render_data.label": "档线速报", "action.data": "sk线", "action.enter": True},
            ],
            [
                {"render_data.label": "榜线预测", "action.data": "sk预测", "action.enter": True},
                {"render_data.label": "时速查询", "action.data": "时速", "action.enter": True},
            ],
        ]
    },
    "event_2": {
        "md_text": (
            "### 🏆 活动与榜线 (2/2)\n\n"
            "> **5v5胜率**：`5v5胜率` / `5v5分数`\n"
            "> **分数线**：`分数线` / `ss` / `wlss`\n"
            "> **活动规划**：`活动规划 pt1000w 歌 虾ex 5火`\n"
            "> **csb**：`csb` (排名热力图)\n"
            "> **冲榜记录**：`冲榜记录` / `活动记录`\n"
            "> **活动组卡**：`活动组卡 <曲名> <难度>`\n"
            "> **挑战组卡**：`挑战组卡 <条件>` / `加成组卡`"
        ),
        "buttons": [
            [
                {"render_data.label": "玩家轨迹", "action.data": "玩家追踪", "action.enter": True},
                {"render_data.label": "5v5胜率", "action.data": "5v5胜率", "action.enter": True},
            ],
            [
                {"render_data.label": "活动组卡", "action.data": "活动组卡 独りんぼエンヴィー expert", "action.enter": True},
                {"render_data.label": "挑战组卡", "action.data": "挑战组卡 miku", "action.enter": True},
            ],
        ]
    },
    "mysekai_1": {
        "md_text": (
            "### 🏝️ 烤森 (MySekai) (1/2)\n\n"
            "> **综合实况**：`msam` (一键全部数据)\n"
            "> **资源天气**：`msa` / `烤森资源`\n"
            "> **地图实况**：`msm` / `烤森地图`\n"
            "> **家具/缺口**：`msf <关键字>` (例: msf 床)\n"
            "> **大门升级**：`msg` (进度及材料)"
        ),
        "buttons": [
            [
                {"render_data.label": "综合实况", "action.data": "msam", "action.enter": True},
                {"render_data.label": "查资源", "action.data": "msa", "action.enter": True},
            ],
            [
                {"render_data.label": "查地图", "action.data": "msm", "action.enter": True},
                {"render_data.label": "查家具", "action.data": "msf", "action.enter": True},
            ],
            [
                {"render_data.label": "查大门", "action.data": "msg", "action.enter": True},
            ],
        ]
    },
    "mysekai_2": {
        "md_text": (
            "### 🏝️ 烤森 (MySekai) (2/2)\n\n"
            "> **收集记录**：`msr`(唱片) / `msb`(蓝图)\n"
            "> **看照片**：`msp -1` (最新照片)\n"
            "> **百景排名**：`百景sk` / `bjsk 1-5`\n"
            "> **对话列表**：`烤森对话列表`\n"
            "> **家具详情**：`家具详情 <关键字>`"
        ),
        "buttons": [
            [
                {"render_data.label": "查蓝图", "action.data": "msb", "action.enter": True},
                {"render_data.label": "查唱片", "action.data": "msr", "action.enter": True},
            ],
            [
                {"render_data.label": "最新照片", "action.data": "msp -1", "action.enter": True},
                {"render_data.label": "百景排名", "action.data": "百景sk", "action.enter": True},
            ],
        ]
    },
    "misc_1": {
        "md_text": (
            "### 🛠️ 杂项功能 (1/2)\n\n"
            "> **别名系统**：`添加歌曲别名 <原名> <别名>`\n"
            "> **养成进度**：`每日挑战` / `角色加成` / `区域道具`\n"
            "> **角色统计**：`羁绊` / `队长统计` / `生日 miku`\n"
            "> **Live排期**：`虚拟live` / `vlive`\n"
            "> **随机选歌**：`随个 <难度>` / `葱什么`\n"
            "> **时区设置**：`pjsktz` / `tz`"
        ),
        "buttons": [
            [
                {"render_data.label": "随机歌曲", "action.data": "葱什么", "action.enter": True},
                {"render_data.label": "别名系统", "action.data": "歌曲别名", "action.enter": True},
            ],
            [
                {"render_data.label": "养成统计", "action.data": "角色加成", "action.enter": True},
                {"render_data.label": "羁绊等级", "action.data": "羁绊", "action.enter": True},
            ],
            [
                {"render_data.label": "虚拟Live", "action.data": "虚拟live", "action.enter": True},
                {"render_data.label": "生日查询", "action.data": "生日 miku", "action.enter": True},
            ],
        ]
    },
    "misc_2": {
        "md_text": (
            "### 🛠️ 杂项功能 (2/2)\n\n"
            "> **Sakura 注册**：`注册` (Sakura 账号注册)\n"
            "> **歌曲信息/花名**：`pinfo <歌名>` / `pset` / `pdel`\n"
            "> **角色花名**：`charinfo <角色>` / `charset` / `chardel`\n"
            "> **倍率/实效**：`倍率 <5个技能倍率>`\n"
            "> **队长统计**：`队长统计`"
        ),
        "buttons": [
            [
                {"render_data.label": "队长统计", "action.data": "队长统计", "action.enter": True},
                {"render_data.label": "注册", "action.data": "注册", "action.enter": True},
            ],
        ]
    },
}

# ==================== 非官方 Bot 的图片渲染数据 ====================
HELP_IMG_DATA: Dict[str, List[dict]] = {
    "main": [
        {"name": "账号", "desc": "绑定、验证、详情、B30、逮捕、抓包等。"},
        {"name": "乐曲", "desc": "查曲、定数、谱面、打歌奖励、猜歌等。"},
        {"name": "卡牌", "desc": "查卡、图鉴、卡池、抽卡、猜卡面、组队。"},
        {"name": "活动", "desc": "查活动、档线/预测/时速、5v5、组卡。"},
        {"name": "烤森", "desc": "MySekai 资源/地图/家具/唱片/照片/百景。"},
        {"name": "杂项", "desc": "别名、养成、角色统计、花名管理、注册。"},
    ],
    "账号": [
        {"name": "绑定/解绑 <ID>", "desc": "例：绑定 123456789 (全服通用)。"},
        {"name": "pjsk验证", "desc": "获取所有权验证，开启高级功能。"},
        {"name": "/个人信息 | pjskdetail", "desc": "生成图文版个人信息。"},
        {"name": "rk | b39/b30", "desc": "查询排位及最高分歌曲平均分。"},
        {"name": "进度 | pjsk进度ex/apd", "desc": "查询对应难度的过曲完成度。"},
        {"name": "抓包数据/烤森抓包", "desc": "查看 Suite 抓包数据同步状态。"},
        {"name": "逮捕", "desc": "查 EX/MASTER FC/AP 进度。"},
        {"name": "查时间/注册时间", "desc": "查询游戏账号注册时间。"},
        {"name": "绑定列表", "desc": "查看所有已绑定账号。"},
        {"name": "隐藏/显示抓包", "desc": "控制 Suite 抓包数据可见性。"},
        {"name": "隐藏/显示ID", "desc": "控制游戏 ID 可见性。"},
        {"name": "设置主账号", "desc": "设置默认查询主账号。"},
        {"name": "pjskprofile/视奸", "desc": "查看他人信息 (需对方开启给看)。"},
        {"name": "给看/不给看", "desc": "控制是否允许被视奸。"},
        {"name": "上传数据页面", "desc": "Haruki: https://haruki.seiunx.com/\nSakura: http://go.mikuware.top/"}
    ],
    "乐曲": [
        {"name": "/查曲 <名称/别名>", "desc": "查询单曲详情。"},
        {"name": "难度排行 <level> <难度>", "desc": "查定数排行。"},
        {"name": "<曲名> 谱面预览", "desc": "可加 ex/apd 后缀。"},
        {"name": "<曲名> 技能预览", "desc": "谱面技能分布及分数占比。"},
        {"name": "设置谱面底色", "desc": "自定义预览图色调。"},
        {"name": "定数表", "desc": "查看全谱面定数。"},
        {"name": "查曲绘", "desc": "获取曲目封面原图。"},
        {"name": "歌曲列表/歌曲排行", "desc": "筛选/排序歌曲。"},
        {"name": "查物量/查bpm", "desc": "按条件筛选歌曲。"},
        {"name": "打歌奖励/挖矿", "desc": "查看打歌收益与完成度。"},
        {"name": "歌曲meta", "desc": "查询歌曲各项数据指标。"},
        {"name": "随个/葱什么", "desc": "随机选歌。"},
        {"name": "听歌识曲", "desc": "猜歌游戏 (tf启动)。"}
    ],
    "卡牌": [
        {"name": "查卡 <条件参数>", "desc": "例如: 查卡 miku 4星 蓝。"},
        {"name": "查箱/卡牌一览", "desc": "图鉴形式显示获取状态。"},
        {"name": "pjskcard <花名>", "desc": "查看个人拥有图鉴。"},
        {"name": "查卡池/卡池列表", "desc": "历史及当期卡池。"},
        {"name": "查贴纸", "desc": "查看角色贴纸。"},
        {"name": "抽卡/反抽卡", "desc": "模拟抽卡 (支持 XX连)。"},
        {"name": "猜卡面", "desc": "猜卡面游戏。"},
        {"name": "findcard/cardinfo", "desc": "按条件查找卡牌。"},
        {"name": "活动组卡/挑战组卡", "desc": "各种场景的组队计算。"}
    ],
    "活动": [
        {"name": "/查活动 <ID/缩写>", "desc": "查询指定或当期活动。"},
        {"name": "sk线/榜线", "desc": "档线速报。"},
        {"name": "sk预测/榜线预测", "desc": "档线走势预测。"},
        {"name": "时速/日速", "desc": "追踪档线增长速度。"},
        {"name": "查房/ptr", "desc": "追踪房间时速。"},
        {"name": "玩家追踪/档线轨迹", "desc": "追踪玩家或榜线历史走向。"},
        {"name": "sk查分/sk查询", "desc": "查看 SK 排名/分数。"},
        {"name": "5v5胜率/分数", "desc": "5v5 模式数据统计。"},
        {"name": "分数线/ss/wlss", "desc": "分数线查询。"},
        {"name": "活动规划", "desc": "目标PT/排名生成规划图。"},
        {"name": "csb", "desc": "排名热力图数据。"},
        {"name": "冲榜记录/活动记录", "desc": "活动冲榜历史。"},
        {"name": "活动组卡/挑战组卡", "desc": "计算当期最优卡组。"}
    ],
    "烤森": [
        {"name": "msam", "desc": "一键合并设施、资源与地图。"},
        {"name": "msa/烤森资源", "desc": "查询 MySekai 资源及天气。"},
        {"name": "msm/烤森地图", "desc": "展示地图实况。"},
        {"name": "msf/家具列表", "desc": "查询家具及材料缺口。"},
        {"name": "msg/msgate", "desc": "大门升级进度及材料。"},
        {"name": "msb/蓝图", "desc": "蓝图收集记录。"},
        {"name": "msr/烤森唱片", "desc": "唱片收集记录。"},
        {"name": "msp/mysekai照片", "desc": "照片列表 (msp -1 最新)。"},
        {"name": "百景sk/bjsk", "desc": "烤森百景投稿排名线。"},
        {"name": "烤森对话列表", "desc": "MySekai 角色对话。"},
        {"name": "家具详情", "desc": "查看特定家具详细信息。"}
    ],
    "杂项": [
        {"name": "添加歌曲/角色别名", "desc": "提交审核。"},
        {"name": "每日挑战/角色加成", "desc": "核心养成系统进度。"},
        {"name": "羁绊等级/队长统计", "desc": "角色连结等级及队长次数。"},
        {"name": "注册", "desc": "Sakura 账号注册。"},
        {"name": "pinfo/pset/pdel", "desc": "查歌曲信息/设花名。"},
        {"name": "charinfo/charset/chardel", "desc": "查角色花名/管理。"},
        {"name": "虚拟live/vlive", "desc": "Live 排期查询。"},
        {"name": "角色生日/查生日", "desc": "查询角色生日。"},
        {"name": "随个/葱什么", "desc": "随机选歌。"},
        {"name": "pjsktz/tz", "desc": "时区设置。"},
    ],
}
