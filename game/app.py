"""游戏主流程：状态管理、事件处理、动画推进。

四个状态：
    menu    开始界面：「开始游戏」进入选关，通关过之后还会多一个「继续游戏」
    select  关卡选择界面：列出全部关卡，可任选一关开始
    playing 游戏界面，处理棋盘点击、动画、失误计数
    result  结果界面，显示通关 / 失败，并提供进入下一关或重试的按钮

返回开始界面的两条路：按 Esc，或点底部的「主菜单」按钮。
"""

import pygame

from . import config as C
from . import renderer
from .board import DIRECTIONS
from .levels import load_levels


class FlyOut:
    """正在飞出棋盘的箭头动画。"""

    def __init__(self, arrow, distance):
        self.arrow = arrow
        self.elapsed = 0.0
        self.distance = distance

    @property
    def finished(self):
        return self.elapsed >= C.FLY_OUT_DURATION

    def offset(self):
        """返回当前帧相对原始格心的像素偏移。"""
        t = min(self.elapsed / C.FLY_OUT_DURATION, 1.0)
        d_row, d_col = DIRECTIONS[self.arrow.direction]
        distance = self.distance * t
        return d_col * distance, d_row * distance


class Game:
    """整局游戏的控制器。"""

    MAX_MISTAKES = 3

    STATE_MENU = "menu"
    STATE_SELECT = "select"
    STATE_PLAYING = "playing"
    STATE_RESULT = "result"

    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.levels = load_levels()

        self.running = True
        self.state = self.STATE_MENU
        self.hover = None
        self.result = None
        self.cleared_levels = set()   # 本次运行中已经通关的关卡索引
        self.start_level(0)
        self.state = self.STATE_MENU      # 启动时停留在开始界面

    # ---------------- 状态查询 ----------------

    @property
    def has_next_level(self):
        """当前关卡之后是否还有关卡。"""
        return self.level_index + 1 < len(self.levels)

    @property
    def resume_level(self):
        """「继续游戏」应该进入的关卡：第一个尚未通关的关卡。"""
        for index in range(len(self.levels)):
            if index not in self.cleared_levels:
                return index
        return 0

    @property
    def has_progress(self):
        """是否已经通关过至少一关（决定开始界面要不要显示「继续游戏」）。"""
        return self.resume_level > 0

    # ---------------- 关卡控制 ----------------

    def start_level(self, index):
        """进入指定关卡。"""
        self.level_index = index
        self.board = self.levels[index].new_board()
        self.origin = renderer.board_origin(self.board.rows, self.board.cols)
        self.arrow_total = self.board.remaining

        self.mistakes = 0
        self.fly_anims = []
        self.shake_anims = {}       # (row, col) -> 已播放时长
        self.toast = None           # [文字, 已播放时长]
        self.result = None
        self.hover = None
        self.finish_delay = 0.0
        self.state = self.STATE_PLAYING

    def start_game(self):
        """从第一关开始新的一局。"""
        self.start_level(0)

    def restart(self):
        """把当前关卡恢复到初始状态。"""
        self.start_level(self.level_index)

    def back_to_menu(self):
        """回到开始界面。

        当前进度作废：回到开始界面后点「开始游戏」会从第 1 关重新开始。
        """
        self.state = self.STATE_MENU
        self.hover = None

    def on_result_button(self):
        """结果界面主按钮：失败重试，通关则进入下一关或重开一局。"""
        if self.result == "lose":
            self.restart()
        elif self.has_next_level:
            self.start_level(self.level_index + 1)
        else:
            self.start_game()

    # ---------------- 主循环 ----------------

    def run(self):
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Esc 逐级返回：游戏 / 结算 -> 开始界面；开始界面 -> 退出程序
                    if self.state == self.STATE_MENU:
                        self.running = False
                    else:
                        self.back_to_menu()
                elif event.key == pygame.K_r and self.state in (
                        self.STATE_PLAYING, self.STATE_RESULT):
                    self.restart()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.state == self.STATE_MENU:
                        self.state = self.STATE_SELECT
                    elif self.state == self.STATE_SELECT:
                        self.start_level(self.resume_level)
                    elif self.state == self.STATE_RESULT:
                        self.on_result_button()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.on_click(event.pos)

    def on_click(self, pos):
        """把一次鼠标左键点击分发到当前状态对应的处理逻辑。"""
        if self.state == self.STATE_MENU:
            if renderer.menu_button_rect().collidepoint(pos):
                self.state = self.STATE_SELECT
            elif self.has_progress and renderer.menu_continue_rect().collidepoint(pos):
                self.start_level(self.resume_level)
            return

        if self.state == self.STATE_SELECT:
            self._on_select_click(pos)
            return

        # 游戏中和结算界面都有底部「主菜单」按钮
        if renderer.secondary_button_rect().collidepoint(pos):
            self.back_to_menu()
            return

        if self.state == self.STATE_RESULT:
            if renderer.bottom_button_rect().collidepoint(pos):
                self.on_result_button()
            return

        # ---- 游戏中 ----
        if renderer.bottom_button_rect().collidepoint(pos):
            self.restart()
            return

        cell = renderer.cell_at(self.origin, pos, self.board.rows, self.board.cols)
        if cell is None:
            return

        arrow = self.board.arrow_at(*cell)
        if arrow is None or cell in self.shake_anims:
            return        # 空格，或碰撞动画尚未播完（防连点）

        if self.board.can_fly_out(arrow):
            self.board.remove(arrow)
            distance = (max(self.board.rows, self.board.cols) + 1) * C.CELL_SIZE
            self.fly_anims.append(FlyOut(arrow, distance))
            if self.board.remaining == 0:
                self.result = "win"
                self.cleared_levels.add(self.level_index)   # 记录进度，供「继续游戏」使用
                self.finish_delay = C.FLY_OUT_DURATION + C.FINISH_DELAY
        else:
            self.mistakes += 1
            self.shake_anims[cell] = 0.0
            self.toast = ["前方有箭头挡路，换一个试试", 0.0]
            if self.mistakes >= self.MAX_MISTAKES:
                self.result = "lose"
                self.finish_delay = C.SHAKE_DURATION + C.FINISH_DELAY

    def _on_select_click(self, pos):
        """关卡选择界面：点卡片直接开始该关，点「返回」回到开始界面。"""
        for index in range(len(self.levels)):
            if renderer.select_card_rect(index).collidepoint(pos):
                self.start_level(index)
                return
        if renderer.select_back_rect().collidepoint(pos):
            self.back_to_menu()

    def update(self, dt):
        """推进动画与计时器。"""
        self._update_hover()

        for anim in self.fly_anims:
            anim.elapsed += dt
        self.fly_anims = [a for a in self.fly_anims if not a.finished]

        for cell in list(self.shake_anims):
            self.shake_anims[cell] += dt
            if self.shake_anims[cell] >= C.SHAKE_DURATION:
                del self.shake_anims[cell]

        if self.toast is not None:
            self.toast[1] += dt
            if self.toast[1] >= C.TOAST_DURATION:
                self.toast = None

        # 最后一个箭头飞出（或碰撞动画结束）后，稍等片刻再弹出结算界面
        if self.result is not None and self.state == self.STATE_PLAYING:
            self.finish_delay -= dt
            if self.finish_delay <= 0:
                self.state = self.STATE_RESULT

    def _update_hover(self):
        """只有游戏中、且鼠标不在按钮上时才高亮格子。"""
        if self.state != self.STATE_PLAYING:
            self.hover = None
            return
        mouse = pygame.mouse.get_pos()
        if renderer.bottom_button_rect().collidepoint(mouse) \
                or renderer.secondary_button_rect().collidepoint(mouse):
            self.hover = None
            return
        self.hover = renderer.cell_at(
            self.origin, mouse, self.board.rows, self.board.cols)

    def draw(self):
        renderer.render(self.screen, self)
        pygame.display.flip()
