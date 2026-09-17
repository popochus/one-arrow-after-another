"""全部绘制工作：开始界面、HUD、棋盘、箭头、动画与结算界面。

本模块只负责"把状态画出来"，不修改任何游戏状态。
"""

import math

import pygame

from . import config as C
from . import view
from .board import DIRECTIONS

# 箭头基准形状以「朝右」定义，再按方向做 90° 整数倍旋转。
# 传入的是相对箭头中心的偏移量，旋转后加上中心坐标即为实际顶点。
_ARROW_BASE = [
    (1.00, 0.00),    # 尖端
    (0.58, -0.50),   # 上翼
    (0.58, -0.19),   # 上内凹
    (-1.00, -0.19),  # 左上
    (-1.00, 0.19),   # 左下
    (0.58, 0.19),    # 下内凹
    (0.58, 0.50),    # 下翼
]

# 朝右的基准形状 -> 各方向的坐标变换
_ROTATE = {
    "right": lambda dx, dy: (dx, dy),
    "down":  lambda dx, dy: (-dy, dx),
    "left":  lambda dx, dy: (-dx, -dy),
    "up":    lambda dx, dy: (dy, -dx),
}


# ==================== 几何换算 ====================

def board_origin(rows, cols):
    """棋盘左上角的屏幕坐标：在棋盘可用区域内居中。"""
    width = cols * C.CELL_SIZE
    height = rows * C.CELL_SIZE
    x = (C.WINDOW_WIDTH - width) // 2
    y = C.BOARD_AREA_TOP + (C.BOARD_AREA_BOTTOM - C.BOARD_AREA_TOP - height) // 2
    return x, y


def cell_center(origin, row, col):
    """格子中心的屏幕坐标。"""
    ox, oy = origin
    return (ox + col * C.CELL_SIZE + C.CELL_SIZE / 2,
            oy + row * C.CELL_SIZE + C.CELL_SIZE / 2)


def cell_at(origin, pos, rows, cols):
    """屏幕坐标 -> 网格坐标；落在棋盘外返回 None。"""
    ox, oy = origin
    x, y = pos
    col = int((x - ox) // C.CELL_SIZE)
    row = int((y - oy) // C.CELL_SIZE)
    if 0 <= row < rows and 0 <= col < cols:
        return row, col
    return None


def bottom_actions(game):
    """底部按钮行的内容：返回 [(动作键, 按钮文字, 是否次要按钮), ...]。

    游戏中和失败时是两个按钮；通关结算时多一个「重玩本关」，共三个。
    """
    if game.state == game.STATE_PLAYING:
        return [
            ("menu", "主菜单", True),
            ("restart", "重新开始", False),
        ]
    if game.result == "lose":
        return [
            ("menu", "主菜单", True),
            ("restart", "重试本关", False),
        ]
    # 通关：无论还有没有下一关，都提供「重玩本关」
    return [
        ("menu", "主菜单", True),
        ("replay", "重玩本关", True),
        ("next", "下一关" if game.has_next_level else "再玩一次", False),
    ]


def bottom_button_rects(game):
    """按当前状态算出底部按钮行的矩形列表，整行水平居中。"""
    count = len(bottom_actions(game))
    width = C.SECONDARY_BUTTON_WIDTH if count == 2 else C.BUTTON_COMPACT_WIDTH
    total = width * count + C.BUTTON_GAP * (count - 1)
    x0 = (C.WINDOW_WIDTH - total) // 2
    return [
        pygame.Rect(x0 + i * (width + C.BUTTON_GAP), C.BUTTON_TOP,
                    width, C.BUTTON_HEIGHT)
        for i in range(count)
    ]


def bottom_buttons():
    """「主菜单 + 主操作」两按钮布局，供静态场景（游戏中）使用。"""
    width = C.SECONDARY_BUTTON_WIDTH
    total = width + C.BUTTON_GAP + C.BUTTON_WIDTH
    x = (C.WINDOW_WIDTH - total) // 2
    secondary = pygame.Rect(x, C.BUTTON_TOP, width, C.BUTTON_HEIGHT)
    primary = pygame.Rect(
        x + width + C.BUTTON_GAP, C.BUTTON_TOP, C.BUTTON_WIDTH, C.BUTTON_HEIGHT)
    return secondary, primary


def secondary_button_rect():
    """底部次要按钮（主菜单）在「两按钮」布局下的位置。"""
    return bottom_buttons()[0]


def bottom_button_rect():
    """底部主操作按钮在「两按钮」布局下的位置。"""
    return bottom_buttons()[1]


def assist_actions(game):
    """辅助按钮行的内容：返回 [(动作键, 按钮文字, 是否禁用), ...]。

    只在游戏进行中出现；已经无可撤销的步骤时，「撤销」置灰不可点。
    胜负判定后（动画播完前）两个按钮一起置灰，与锁死的棋盘保持一致。
    「提示」按钮上带本关已用次数——提示会拉低星级，得让玩家看得见用量。
    """
    if game.state != game.STATE_PLAYING:
        return []
    locked = game.result is not None
    hint_text = "提示" if not game.hint_count else f"提示 ×{game.hint_count}"
    return [
        ("undo", "撤销", locked or not game.can_undo),
        ("hint", hint_text, locked),
    ]


def assist_button_rects(game):
    """辅助按钮行的矩形列表，整行水平居中。"""
    count = len(assist_actions(game))
    if count == 0:
        return []
    total = count * C.ASSIST_BUTTON_WIDTH + (count - 1) * C.ASSIST_BUTTON_GAP
    x0 = (C.WINDOW_WIDTH - total) // 2
    return [
        pygame.Rect(x0 + i * (C.ASSIST_BUTTON_WIDTH + C.ASSIST_BUTTON_GAP),
                    C.ASSIST_BUTTON_TOP, C.ASSIST_BUTTON_WIDTH,
                    C.ASSIST_BUTTON_HEIGHT)
        for i in range(count)
    ]


def menu_button_rect():
    """开始界面的「开始游戏」按钮（点击后进入关卡选择界面）。"""
    return pygame.Rect(
        (C.WINDOW_WIDTH - C.MENU_BUTTON_WIDTH) // 2, C.MENU_BUTTON_TOP,
        C.MENU_BUTTON_WIDTH, C.MENU_BUTTON_HEIGHT,
    )


def menu_continue_rect():
    """开始界面的「继续游戏」按钮（仅在已通关过至少一关时显示）。"""
    return pygame.Rect(
        (C.WINDOW_WIDTH - C.MENU_BUTTON_WIDTH) // 2, C.MENU_CONTINUE_TOP,
        C.MENU_BUTTON_WIDTH, C.MENU_CONTINUE_HEIGHT,
    )


def select_card_rect(index):
    """关卡选择界面里第 index 张关卡卡片的矩形。"""
    x = (C.WINDOW_WIDTH - C.SELECT_CARD_WIDTH) // 2
    y = C.SELECT_CARD_TOP + index * (C.SELECT_CARD_HEIGHT + C.SELECT_CARD_GAP)
    return pygame.Rect(x, y, C.SELECT_CARD_WIDTH, C.SELECT_CARD_HEIGHT)


def select_back_rect():
    """关卡选择界面的「返回」按钮。"""
    return pygame.Rect(
        (C.WINDOW_WIDTH - C.SECONDARY_BUTTON_WIDTH) // 2, C.BUTTON_TOP,
        C.SECONDARY_BUTTON_WIDTH, C.BUTTON_HEIGHT,
    )


def lerp_color(color_a, color_b, t):
    """两个颜色之间线性插值，t 取 0~1。"""
    t = max(0.0, min(1.0, t))
    return tuple(round(a + (b - a) * t) for a, b in zip(color_a, color_b))


# ==================== 基础绘制 ====================

def draw_arrow(surface, center, direction, color):
    """在 center 处按 direction 画一个箭头。"""
    cx, cy = center
    half = C.CELL_SIZE * 0.31          # 箭头半长
    transform = _ROTATE[direction]
    points = []
    for dx, dy in _ARROW_BASE:
        tx, ty = transform(dx * half, dy * half)
        points.append((cx + tx, cy + ty))
    pygame.draw.polygon(surface, color, points)


def _draw_hint_glow(surface, center, pulse):
    """提示箭头外圈的呼吸光晕，pulse 取 0~1。"""
    radius = int(C.CELL_SIZE * (0.36 + 0.05 * pulse))
    size = radius * 2 + 14
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    pygame.draw.circle(layer, (*C.COLOR_ARROW_HINT, 26), (cx, cy), radius)
    pygame.draw.circle(layer, (*C.COLOR_ARROW_HINT, int(70 + 85 * pulse)),
                       (cx, cy), radius, width=5)
    surface.blit(layer, layer.get_rect(center=center))


def draw_star(surface, center, radius, filled=True):
    """画一颗五角星（外顶点与内顶点交替，共 10 个点）。

    自己画多边形而不依赖字体里的 ★ 字形——中文字体对这类符号的支持并不一致，
    缺字形时会渲染成方块。filled=False 画成灰色的"未点亮"状态。
    """
    cx, cy = center
    inner = radius * 0.42
    points = []
    for index in range(10):
        r = radius if index % 2 == 0 else inner
        angle = -math.pi / 2 + index * math.pi / 5      # 从正上方起，顺时针
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

    color = C.COLOR_STAR if filled else C.COLOR_STAR_EMPTY
    pygame.draw.polygon(surface, color, points)
    if filled:
        pygame.draw.polygon(surface, C.COLOR_STAR_EDGE, points, width=2)


def draw_star_row(surface, center, stars, total=3, radius=30, gap=26):
    """一排星，前 stars 颗点亮，其余画成灰色。"""
    if total <= 0:
        return
    step = radius * 2 + gap
    x0 = center[0] - step * (total - 1) / 2
    for index in range(total):
        draw_star(surface, (x0 + index * step, center[1]), radius,
                  filled=index < stars)


def draw_button(surface, rect, text, secondary=False, disabled=False):
    """统一样式的按钮，鼠标悬停时颜色变化。

    secondary=True 画成次要按钮（白底描边），用于「主菜单」这类非主操作；
    disabled=True 画成灰色且不响应悬停，表示当前不可用（如无历史时的「撤销」）。
    """
    # 取逻辑画布坐标而非窗口坐标：窗口被缩放过时，两者差一个比例。
    hovered = rect.collidepoint(view.mouse_pos()) and not disabled
    radius = rect.height // 3

    if disabled:
        pygame.draw.rect(surface, C.COLOR_BTN_DISABLED_BG, rect, border_radius=radius)
        pygame.draw.rect(surface, C.COLOR_BTN_DISABLED_BORDER, rect,
                         width=2, border_radius=radius)
        label = C.get_font(26).render(text, True, C.COLOR_BTN_DISABLED_TEXT)
    elif secondary:
        color = C.COLOR_BTN_2ND_HOVER if hovered else C.COLOR_BTN_2ND
        pygame.draw.rect(surface, color, rect, border_radius=radius)
        pygame.draw.rect(surface, C.COLOR_BTN_2ND_BORDER, rect,
                         width=2, border_radius=radius)
        label = C.get_font(26).render(text, True, C.COLOR_BTN_2ND_TEXT)
    else:
        color = C.COLOR_BTN_HOVER if hovered else C.COLOR_BTN
        pygame.draw.rect(surface, color, rect, border_radius=radius)
        label = C.get_font(30).render(text, True, C.COLOR_BTN_TEXT)

    surface.blit(label, label.get_rect(center=rect.center))


# ==================== 各界面绘制 ====================

def _draw_menu(surface, game):
    """开始界面：标题、玩法说明、「开始游戏」与「继续游戏」。"""
    title = C.get_font(76).render("一箭又一箭", True, C.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(C.WINDOW_WIDTH // 2, C.MENU_TITLE_Y)))

    subtitle = C.get_font(26).render(
        "看准方向与遮挡，按顺序把箭头送出棋盘", True, C.COLOR_TEXT_MUTED)
    surface.blit(subtitle,
                 subtitle.get_rect(center=(C.WINDOW_WIDTH // 2, C.MENU_SUBTITLE_Y)))

    _draw_menu_decoration(surface)

    draw_button(surface, menu_button_rect(), "开始游戏")

    # 通关过至少一关之后，才开始提供「继续游戏」的快捷入口
    if game.has_progress:
        draw_button(surface, menu_continue_rect(),
                    f"继续游戏 · 第 {game.resume_level + 1} 关", secondary=True)

    # 已有成绩时显示累计战绩。这里判 records 而不是 has_progress：
    # 玩家若从选关界面直接通关了靠后的关卡、第 1 关反而没打，
    # has_progress 会是 False（「继续游戏」按第一个未通关关卡算），
    # 但成绩确实存在，不该藏起来。
    if game.records:
        stat = C.get_font(24).render(
            f"已得 {game.total_stars} / {game.max_stars} 星"
            f"   ·   总分 {game.total_score} / {game.max_score}",
            True, C.COLOR_SCORE_VALUE)
        surface.blit(stat, stat.get_rect(center=(C.WINDOW_WIDTH // 2, 934)))

    tip = C.get_font(22).render(
        f"每关 {game.MAX_MISTAKES} 次失误机会，用尽即失败", True, C.COLOR_TEXT_MUTED)
    surface.blit(tip, tip.get_rect(center=(C.WINDOW_WIDTH // 2, C.MENU_TIP_Y)))

    hint = C.get_font(22).render(
        "游戏中按 Esc 或点「主菜单」可返回这里", True, C.COLOR_TEXT_MUTED)
    surface.blit(hint, hint.get_rect(center=(C.WINDOW_WIDTH // 2, C.MENU_HINT_Y)))


def _draw_menu_decoration(surface):
    """开始界面的一排示例箭头，纯装饰。"""
    y = C.MENU_DECOR_Y
    spacing = 120
    directions = ["up", "right", "down", "left"]
    total = spacing * (len(directions) - 1)
    x0 = (C.WINDOW_WIDTH - total) // 2
    for index, direction in enumerate(directions):
        draw_arrow(surface, (x0 + index * spacing, y), direction, C.COLOR_ARROW)


def _draw_select(surface, game):
    """关卡选择界面：列出全部关卡，已通关的标出状态。"""
    title = C.get_font(52).render("选择关卡", True, C.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(C.WINDOW_WIDTH // 2, C.SELECT_TITLE_Y)))

    for index, level in enumerate(game.levels):
        _draw_level_card(surface, game, index, level)

    draw_button(surface, select_back_rect(), "返回", secondary=True)


def _draw_level_card(surface, game, index, level):
    """单张关卡卡片：序号 + 主题名 + 状态（已通关 / 箭头数）。"""
    rect = select_card_rect(index)
    hovered = rect.collidepoint(view.mouse_pos())
    cleared = index in game.cleared_levels

    pygame.draw.rect(surface, C.COLOR_CARD_BG_HOVER if hovered else C.COLOR_CARD_BG,
                     rect, border_radius=18)
    pygame.draw.rect(surface,
                     C.COLOR_CARD_BORDER_HOVER if hovered else C.COLOR_CARD_BORDER,
                     rect, width=2, border_radius=18)

    badge = pygame.Rect(rect.x + 20, rect.centery - 28, 56, 56)
    pygame.draw.rect(surface, C.COLOR_CARD_INDEX_BG, badge, border_radius=14)
    number = C.get_font(30).render(str(index + 1), True, C.COLOR_CARD_INDEX_TEXT)
    surface.blit(number, number.get_rect(center=badge.center))

    name = C.get_font(30).render(level.topic, True, C.COLOR_TEXT)
    surface.blit(name, (badge.right + 22, rect.centery - name.get_height() // 2))

    if cleared:
        # 已通关：右侧放该关的最佳成绩——三颗小星 + 得分。
        # 星星本身已经表达了"通关了"，就不必再写一遍「已通关」。
        record = game.records[index]
        score_label = C.get_font(22).render(f"{record['score']} 分", True,
                                            C.COLOR_TEXT_MUTED)
        surface.blit(score_label,
                     score_label.get_rect(midright=(rect.right - 26, rect.centery)))

        radius, gap = 11, 8
        step = radius * 2 + gap
        right_center = rect.right - 26 - score_label.get_width() - 24 - radius
        for i in range(C.STAR_MAX):
            x = right_center - (C.STAR_MAX - 1 - i) * step
            draw_star(surface, (x, rect.centery), radius,
                      filled=i < record["stars"])
    else:
        status = C.get_font(24).render(
            f"{level.board.remaining} 个箭头", True, C.COLOR_TEXT_MUTED)
        surface.blit(status, status.get_rect(midright=(rect.right - 26, rect.centery)))


def _draw_hud(surface, game):
    """顶部信息栏：关卡名、剩余箭头、用时、失误次数。"""
    level_name = game.levels[game.level_index].name
    title = C.get_font(40).render(level_name, True, C.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(C.WINDOW_WIDTH // 2, 104)))

    # 用时夹在中间：它每帧都在变，放两侧会让另外两项跟着左右晃动。
    label_font = C.get_font(26)
    labels = [
        label_font.render(f"剩余箭头 {game.board.remaining}", True, C.COLOR_TEXT_MUTED),
        label_font.render(f"用时 {game.elapsed:.1f} 秒", True, C.COLOR_TEXT_MUTED),
        label_font.render(
            f"失误 {game.mistakes} / {game.MAX_MISTAKES}", True,
            C.COLOR_DANGER if game.mistakes else C.COLOR_TEXT_MUTED),
    ]

    gap = 44
    total = sum(label.get_width() for label in labels) + gap * (len(labels) - 1)
    x = (C.WINDOW_WIDTH - total) // 2
    for label in labels:
        surface.blit(label, (x, 170))
        x += label.get_width() + gap


def _draw_board(surface, game):
    """棋盘底板、网格线、鼠标悬停高亮。"""
    board = game.board
    ox, oy = game.origin
    width = board.cols * C.CELL_SIZE
    height = board.rows * C.CELL_SIZE
    pad = C.BOARD_PADDING

    pygame.draw.rect(
        surface, C.COLOR_BOARD_BG,
        pygame.Rect(ox - pad, oy - pad, width + pad * 2, height + pad * 2),
        border_radius=22,
    )

    for col in range(1, board.cols):
        x = ox + col * C.CELL_SIZE
        pygame.draw.line(surface, C.COLOR_GRID_LINE, (x, oy), (x, oy + height))
    for row in range(1, board.rows):
        y = oy + row * C.CELL_SIZE
        pygame.draw.line(surface, C.COLOR_GRID_LINE, (ox, y), (ox + width, y))

    if game.hover:
        row, col = game.hover
        if game.board.arrow_at(row, col):
            highlight = pygame.Rect(
                ox + col * C.CELL_SIZE + 4,
                oy + row * C.CELL_SIZE + 4,
                C.CELL_SIZE - 8, C.CELL_SIZE - 8,
            )
            pygame.draw.rect(surface, C.COLOR_CELL_HOVER, highlight, border_radius=14)


def _draw_arrows(surface, game):
    """棋盘上的箭头，以及飞出、碰撞两种动画效果。"""
    # ---- 静止 / 晃动中的箭头 ----
    for arrow in game.board.arrows:
        center = cell_center(game.origin, arrow.row, arrow.col)
        color = C.COLOR_ARROW

        if game.hover == (arrow.row, arrow.col):
            color = C.COLOR_ARROW_HOVER

        if game.hint_cell == (arrow.row, arrow.col):
            # 提示高亮：在常态箭头与琥珀色之间脉动，外面套一圈同步呼吸的光晕
            pulse = 0.5 + 0.5 * math.sin(game.hint_elapsed * 9.0)
            color = lerp_color(C.COLOR_ARROW, C.COLOR_ARROW_HINT, pulse)
            _draw_hint_glow(surface, center, pulse)

        elapsed = game.shake_anims.get((arrow.row, arrow.col))
        if elapsed is not None:
            # 碰撞反馈：先变色（蓝 -> 红 -> 蓝），再沿朝向前后抖动
            t = min(elapsed / C.SHAKE_DURATION, 1.0)
            color = lerp_color(C.COLOR_ARROW_HOVER, C.COLOR_ARROW_BLOCKED,
                               math.sin(t * math.pi))
            d_row, d_col = DIRECTIONS[arrow.direction]
            offset = C.SHAKE_AMPLITUDE * math.sin(t * math.pi * 4)
            center = (center[0] + d_col * offset, center[1] + d_row * offset)

        draw_arrow(surface, center, arrow.direction, color)

    # ---- 正在飞出棋盘的箭头 ----
    for anim in game.fly_anims:
        center = cell_center(game.origin, anim.arrow.row, anim.arrow.col)
        dx, dy = anim.offset()
        t = min(anim.elapsed / C.FLY_OUT_DURATION, 1.0)
        color = lerp_color(C.COLOR_ARROW, C.COLOR_BG, t * 0.85)
        draw_arrow(surface, (center[0] + dx, center[1] + dy), anim.arrow.direction, color)


def _draw_toast(surface, game):
    """棋盘上方的浮动提示，出现后淡出。

    两种类型：碰撞提示用红色（危险），撤销这类中性提示用蓝色。
    """
    if not game.toast:
        return

    text, elapsed, kind = game.toast
    t = elapsed / C.TOAST_DURATION
    if t >= 1.0:
        return

    if kind == "info":
        bg, fg = C.COLOR_TOAST_INFO_BG, C.COLOR_TOAST_INFO_TEXT
    else:
        bg, fg = C.COLOR_TOAST_BG, C.COLOR_DANGER

    label = C.get_font(24).render(text, True, fg)
    pad_x, pad_y = 24, 14
    card = pygame.Surface(
        (label.get_width() + pad_x * 2, label.get_height() + pad_y * 2),
        pygame.SRCALPHA,
    )
    alpha = int(235 * (1 - t ** 3))
    card.fill((*bg, max(alpha, 0)))
    card.blit(label, (pad_x, pad_y))

    rect = card.get_rect(center=(C.WINDOW_WIDTH // 2, game.origin[1] - 30))
    surface.blit(card, rect)


def _draw_bottom_button(surface, game):
    """底部按钮行，按钮的内容与数量都随状态变化。"""
    for (_, text, secondary), rect in zip(
            bottom_actions(game), bottom_button_rects(game)):
        draw_button(surface, rect, text, secondary=secondary)


def _draw_assist_button(surface, game):
    """辅助按钮行（撤销 / 提示），只在游戏进行中绘制。"""
    for (_, text, disabled), rect in zip(
            assist_actions(game), assist_button_rects(game)):
        draw_button(surface, rect, text, secondary=True, disabled=disabled)


def _draw_result(surface, game):
    """通关 / 失败界面：独立铺底，不叠在棋盘之上，避免残留影。"""
    win = game.result == "win"
    if win and not game.has_next_level:
        title_text, title_color = "全部通关！", C.COLOR_SUCCESS
    elif win:
        title_text, title_color = "过关！", C.COLOR_SUCCESS
    else:
        title_text, title_color = "失误次数用完了", C.COLOR_DANGER

    title = C.get_font(58).render(title_text, True, title_color)
    surface.blit(title, title.get_rect(center=(C.WINDOW_WIDTH // 2, 470)))

    if not win:
        # 失败不评星：星级衡量的是"通关质量"，没通关就不该有星。
        clear_count = game.arrow_total - game.board.remaining
        detail = (f"已清除 {clear_count} 个，还剩 {game.board.remaining} 个"
                  f"   ·   用时 {game.elapsed:.1f} 秒")
        sub = C.get_font(26).render(detail, True, C.COLOR_TEXT_MUTED)
        surface.blit(sub, sub.get_rect(center=(C.WINDOW_WIDTH // 2, 590)))
        return

    # ---- 通关：星级 + 本关得分 + 成绩明细 ----
    # 这里显示的是"本次"成绩而非历史最佳：重玩打得更差时，卡片上的星星
    # 会保留更好的那次（见 _record_result），但结算当面要如实反映这一局。
    draw_star_row(surface, (C.WINDOW_WIDTH // 2, 570), game.level_stars,
                  C.STAR_MAX, radius=34, gap=30)

    score = C.get_font(46).render(f"得分 {game.level_score}", True,
                                  C.COLOR_SCORE_VALUE)
    surface.blit(score, score.get_rect(center=(C.WINDOW_WIDTH // 2, 660)))

    detail = (f"用时 {game.elapsed:.1f} 秒   ·   失误 {game.mistakes} 次"
              f"   ·   提示 {game.hint_count} 次")
    sub = C.get_font(26).render(detail, True, C.COLOR_TEXT_MUTED)
    surface.blit(sub, sub.get_rect(center=(C.WINDOW_WIDTH // 2, 730)))

    if game.has_next_level:
        note = f"本关 {game.arrow_total} 个箭头已全部清除"
    else:
        note = (f"总分 {game.total_score} / {game.max_score}"
                f"   ·   星数 {game.total_stars} / {game.max_stars}")
    foot = C.get_font(26).render(note, True, C.COLOR_TEXT_MUTED)
    surface.blit(foot, foot.get_rect(center=(C.WINDOW_WIDTH // 2, 790)))


def render(surface, game):
    """完整渲染一帧。"""
    surface.fill(C.COLOR_BG)

    if game.state == game.STATE_MENU:
        _draw_menu(surface, game)
        return

    if game.state == game.STATE_SELECT:
        _draw_select(surface, game)
        return

    if game.state == game.STATE_RESULT:
        _draw_result(surface, game)
        _draw_bottom_button(surface, game)
        return

    _draw_hud(surface, game)
    _draw_board(surface, game)
    _draw_arrows(surface, game)
    _draw_toast(surface, game)
    _draw_assist_button(surface, game)
    _draw_bottom_button(surface, game)
