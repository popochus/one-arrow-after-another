"""全局配置：窗口尺寸、网格布局、配色、动画参数与中文字体。

所有"可以调的数字"都集中在这里，方便统一调整而不必翻遍代码。
界面采用手机竖屏比例（9:16），与同类休闲小游戏的观感保持一致。
"""

import os
from functools import lru_cache

import pygame

# ---------------- 窗口（手机竖屏 9:16）----------------
WINDOW_WIDTH = 720
WINDOW_HEIGHT = 1280
FPS = 60
TITLE = "一箭又一箭"

# ---------------- 布局 ----------------
CELL_SIZE = 120             # 单个格子的边长（像素）
BOARD_AREA_TOP = 240        # 棋盘可用区域的上边界（顶部 HUD 之下）
BOARD_AREA_BOTTOM = 950     # 棋盘可用区域的下边界（底部按钮之上）
BOARD_PADDING = 12          # 棋盘底板相对网格向外扩出的留白

BUTTON_TOP = 1030           # 底部按钮行：左「主菜单」+ 右主操作（重新开始 / 下一关 / 重试）
BUTTON_WIDTH = 240          # 主操作按钮宽度
SECONDARY_BUTTON_WIDTH = 240    # 次要按钮（主菜单）宽度
BUTTON_GAP = 40             # 两个按钮之间的间距
BUTTON_HEIGHT = 88

# ---------------- 开始界面 ----------------
MENU_TITLE_Y = 400          # 标题中心
MENU_SUBTITLE_Y = 488       # 一句话玩法说明
MENU_DECOR_Y = 600          # 装饰箭头所在行
MENU_BUTTON_TOP = 690       # 「开始游戏」按钮
MENU_BUTTON_WIDTH = 380
MENU_BUTTON_HEIGHT = 100
MENU_CONTINUE_TOP = 812     # 「继续游戏 · 第 N 关」（仅在已有进度时显示）
MENU_CONTINUE_HEIGHT = 96
MENU_TIP_Y = 972            # 玩法提示
MENU_HINT_Y = 1016          # 返回操作提示

# ---------------- 关卡选择界面 ----------------
SELECT_TITLE_Y = 200
SELECT_CARD_TOP = 340       # 第一张关卡卡片的上边界
SELECT_CARD_WIDTH = 560
SELECT_CARD_HEIGHT = 100
SELECT_CARD_GAP = 20

# ---------------- 配色（浅色主题）----------------
COLOR_BG            = (244, 246, 250)   # 窗口背景
COLOR_BOARD_BG      = (255, 255, 255)   # 棋盘底板
COLOR_GRID_LINE     = (231, 234, 240)   # 网格线
COLOR_CELL_HOVER    = (232, 240, 255)   # 鼠标悬停格
COLOR_TEXT          = (38, 42, 51)
COLOR_TEXT_MUTED    = (132, 140, 154)
COLOR_ARROW         = (56, 108, 222)    # 箭头常态
COLOR_ARROW_HOVER   = (96, 146, 246)    # 悬停高亮
COLOR_ARROW_BLOCKED = (226, 74, 66)     # 碰撞瞬间
COLOR_DANGER        = (226, 74, 66)
COLOR_SUCCESS       = (44, 168, 108)
COLOR_BTN           = (56, 108, 222)
COLOR_BTN_HOVER     = (86, 136, 246)
COLOR_BTN_TEXT      = (255, 255, 255)
COLOR_BTN_2ND       = (255, 255, 255)   # 次要按钮（主菜单 / 继续游戏 / 返回）底色
COLOR_BTN_2ND_HOVER = (236, 241, 251)
COLOR_BTN_2ND_BORDER = (203, 212, 228)
COLOR_BTN_2ND_TEXT  = (86, 96, 116)

# ---------------- 配色（关卡选择卡片）----------------
COLOR_CARD_BG           = (255, 255, 255)
COLOR_CARD_BG_HOVER     = (240, 245, 255)
COLOR_CARD_BORDER       = (228, 233, 242)
COLOR_CARD_BORDER_HOVER = (56, 108, 222)
COLOR_CARD_INDEX_BG     = (238, 243, 253)
COLOR_CARD_INDEX_TEXT   = (56, 108, 222)
COLOR_CARD_DONE         = (44, 168, 108)    # 已通关标记

COLOR_TOAST_BG      = (255, 236, 235)

# ---------------- 动画 ----------------
FLY_OUT_DURATION = 0.40     # 飞出动画时长（秒）
SHAKE_DURATION   = 0.34     # 碰撞晃动时长（秒）
SHAKE_AMPLITUDE  = 9        # 晃动幅度（像素）
TOAST_DURATION   = 1.00     # 碰撞文字提示停留时长（秒）
FINISH_DELAY     = 0.20     # 最后一个箭头消失后，再隔多久弹出结算界面

# ---------------- 中文字体 ----------------
# pygame 自带字体不含中文字形，必须显式加载系统字体，否则中文会显示成方块。
_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyhbd.ttc",   # 微软雅黑 Bold
    r"C:\Windows\Fonts\msyh.ttc",     # 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",   # 黑体
    r"C:\Windows\Fonts\simsun.ttc",   # 宋体
)


@lru_cache(maxsize=32)
def get_font(size):
    """按尺寸取中文字体；系统字体缺失时退回 pygame 默认字体。"""
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    return pygame.font.SysFont(None, size)
