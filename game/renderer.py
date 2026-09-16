"""全部绘制工作：开始界面、HUD、棋盘、箭头、动画与结算界面。

本模块只负责"把状态画出来"，不修改任何游戏状态。
"""

import math

import pygame

from . import config as C
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


def draw_button(surface, rect, text, secondary=False):
    """统一样式的按钮，鼠标悬停时颜色变化。

    secondary=True 画成次要按钮（白底描边），用于「主菜单」这类非主操作。
    """
    hovered = rect.collidepoint(pygame.mouse.get_pos())
    radius = rect.height // 3

    if secondary:
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
    hovered = rect.collidepoint(pygame.mouse.get_pos())
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
        status_text, status_color = "已通关", C.COLOR_CARD_DONE
    else:
        status_text, status_color = f"{level.board.remaining} 个箭头", C.COLOR_TEXT_MUTED
    status = C.get_font(24).render(status_text, True, status_color)
    surface.blit(status, status.get_rect(midright=(rect.right - 26, rect.centery)))


def _draw_hud(surface, game):
    """顶部信息栏：关卡名、剩余箭头、失误次数。"""
    level_name = game.levels[game.level_index].name
    title = C.get_font(40).render(level_name, True, C.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(C.WINDOW_WIDTH // 2, 104)))

    label_font = C.get_font(26)
    left = label_font.render(f"剩余箭头 {game.board.remaining}", True, C.COLOR_TEXT_MUTED)
    mistake_color = C.COLOR_DANGER if game.mistakes else C.COLOR_TEXT_MUTED
    right = label_font.render(
        f"失误 {game.mistakes} / {game.MAX_MISTAKES}", True, mistake_color)

    gap = 60
    x = (C.WINDOW_WIDTH - left.get_width() - gap - right.get_width()) // 2
    surface.blit(left, (x, 170))
    surface.blit(right, (x + left.get_width() + gap, 170))


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
    """碰撞时的文字提示，出现在棋盘上方并淡出。"""
    if not game.toast:
        return

    text, elapsed = game.toast
    t = elapsed / C.TOAST_DURATION
    if t >= 1.0:
        return

    label = C.get_font(24).render(text, True, C.COLOR_DANGER)
    pad_x, pad_y = 24, 14
    card = pygame.Surface(
        (label.get_width() + pad_x * 2, label.get_height() + pad_y * 2),
        pygame.SRCALPHA,
    )
    alpha = int(235 * (1 - t ** 3))
    card.fill((*C.COLOR_TOAST_BG, max(alpha, 0)))
    card.blit(label, (pad_x, pad_y))

    rect = card.get_rect(center=(C.WINDOW_WIDTH // 2, game.origin[1] - 30))
    surface.blit(card, rect)


def _draw_bottom_button(surface, game):
    """底部按钮行，按钮的内容与数量都随状态变化。"""
    for (_, text, secondary), rect in zip(
            bottom_actions(game), bottom_button_rects(game)):
        draw_button(surface, rect, text, secondary=secondary)


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
    surface.blit(title, title.get_rect(center=(C.WINDOW_WIDTH // 2, 540)))

    if win:
        if game.has_next_level:
            detail = f"本关 {game.arrow_total} 个箭头已全部清除"
        else:
            detail = f"全部 {len(game.levels)} 个关卡已通关，玩得不错"
    else:
        cleared = game.arrow_total - game.board.remaining
        detail = f"已清除 {cleared} 个，还剩 {game.board.remaining} 个"
    sub = C.get_font(26).render(detail, True, C.COLOR_TEXT_MUTED)
    surface.blit(sub, sub.get_rect(center=(C.WINDOW_WIDTH // 2, 620)))


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
    _draw_bottom_button(surface, game)
