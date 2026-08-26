"""养成猫的配置内容（猫的定义 + 台词）。

与业务逻辑分离：改文案只动这个文件。
texts 是数组，客户端按「日期种子」在其中轮换——同一天内稳定、跨天变化，
避免同一句话天天出现变成墙纸。
移植自 weapp/cloudfunctions/pet/seed.js。
"""

CATS = [
    {"code": "orange", "name": "橘猫", "persona": "元气", "order": 1, "unlock": []},
    {
        "code": "cow",
        "name": "奶牛猫",
        "persona": "毒舌",
        "order": 2,
        "unlock": [{"field": "_total", "op": "gte", "value": 50}],
    },
    {
        "code": "calico",
        "name": "三花",
        "persona": "温柔",
        "order": 3,
        "unlock": [{"field": "_total", "op": "gte", "value": 150}],
    },
]


def _line(code, page, priority, conditions, texts, unlock=None):
    return {
        "code": code,
        "cat_code": None,  # 云函数里 cat_id 全是 '*'（通用），移植阶段保持一致
        "page": page,
        "priority": priority,
        "conditions": conditions,
        "texts": texts,
        "unlock": unlock or [],
    }


LINES = [
    # ---- 今日 ----
    _line(
        "t_overdue",
        "today",
        30,
        [{"field": "overdue", "op": "gte", "value": 1}],
        [
            "有 {overdue} 件事已经过期了，别再拖啦喵",
            "{overdue} 件事在等你喵…要不先挑最简单的那个？",
            "过期 {overdue} 件。没关系，今天补回来就好喵",
        ],
    ),
    _line(
        "t_habits",
        "today",
        20,
        [{"field": "pending_habits", "op": "gte", "value": 3}],
        [
            "还有 {pending_habits} 个习惯没打卡，去点一下喵",
            "{pending_habits} 个习惯在排队等你喵～",
        ],
    ),
    _line(
        "t_clear",
        "today",
        10,
        [{"field": "pending", "op": "eq", "value": 0}],
        [
            "今天的事都做完了，好好歇会儿喵～",
            "全部清空！今天的你很厉害喵",
        ],
    ),
    _line(
        "t_deep",
        "today",
        25,
        [{"field": "pending", "op": "gte", "value": 5}],
        ["今天排了 {pending} 件事…确定做得完吗喵？挑三件最重要的就好"],
        [{"field": "_total", "op": "gte", "value": 20}],
    ),
    # ---- 四象限 ----
    _line(
        "q_ui",
        "quadrant",
        30,
        [{"field": "urgent_important", "op": "gte", "value": 3}],
        [
            "有 {urgent_important} 件又重要又急的事压着，先处理它们喵～",
            "{urgent_important} 件急事排队呢，挑一个开始吧喵",
            "第一象限有点满了（{urgent_important} 件），别硬扛喵",
        ],
    ),
    _line(
        "q_overdue",
        "quadrant",
        20,
        [{"field": "overdue", "op": "gte", "value": 5}],
        [
            "积压了 {overdue} 件过期任务，抽空清理一下喵",
            "{overdue} 件过期的…要不要删掉几个其实不重要的喵？",
        ],
    ),
    _line(
        "q_clear",
        "quadrant",
        10,
        [{"field": "total", "op": "eq", "value": 0}],
        [
            "四象限都清空啦，太厉害喵！",
        ],
    ),
    # ---- 习惯 ----
    _line(
        "h_pending",
        "habit",
        10,
        [{"field": "pending", "op": "gte", "value": 1}],
        [
            "还有 {pending} 个习惯待打卡喵",
            "{pending} 个习惯还没完成，一起加油喵～",
        ],
    ),
    _line(
        "h_done",
        "habit",
        20,
        [{"field": "pending", "op": "eq", "value": 0}],
        [
            "今天习惯全完成，真自律喵！",
            "一个不落，厉害喵～",
        ],
    ),
    # ---- 猫窝页 ----
    _line(
        "p_visit",
        "pet",
        40,
        [{"field": "visit_streak", "op": "gte", "value": 3}],
        [
            "你已经连着 {visit_streak} 天来看我啦喵～",
        ],
    ),
    _line(
        "p_big",
        "pet",
        30,
        [{"field": "_total", "op": "gte", "value": 150}],
        [
            "我们一起完成很多事啦，谢谢你喵～",
        ],
    ),
    _line(
        "p_small",
        "pet",
        20,
        [{"field": "_total", "op": "lt", "value": 10}],
        [
            "我还小，陪着我一起长大喵～",
        ],
    ),
    _line(
        "p_idle",
        "pet",
        10,
        [],
        [
            "喵～我在呢，今天也要加油呀",
            "今天想做点什么喵？",
        ],
    ),
]
