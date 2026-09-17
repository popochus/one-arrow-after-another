"""游戏主流程：状态管理、事件处理、动画推进。

四个状态：
    menu    开始界面：「开始游戏」进入选关，通关过之后还会多一个「继续游戏」
    select  关卡选择界面：列出全部关卡，可任选一关开始
    playing 游戏界面，处理棋盘点击、动画、失误计数
    result  结果界面，显示通关 / 失败，并提供进入下一关或重试的按钮

游戏中还提供两个辅助功能（只在 playing 状态下出现）：
    撤销    退回上一步——飞出的箭头放回原位，失误计数一并退还；
    提示    高亮一个当前确实可以点掉的箭头，卡住时的出路。

返回开始界面的两条路：按 Esc，或点底部的「主菜单」按钮。
"""

import pygame

from . import audio
from . import config as C
from . import renderer
from . import view
from .board import DIRECTIONS
from .levels import load_levels
from .solver import hint as find_hint


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

    def __init__(self, screen, window=None):
        # screen 是固定 720x1280 的逻辑画布，界面代码只认它的坐标系；
        # window 是真实窗口。两者不同时，每帧由 view.present() 缩放呈现。
        # 自动化测试与录制脚本只传 screen，此时 window 即 screen，行为与从前一致。
        self.screen = screen
        self.window = window if window is not None else screen
        self.clock = pygame.time.Clock()
        self.levels = load_levels()

        self.running = True
        self.state = self.STATE_MENU
        self.hover = None
        self.result = None
        # 本次运行中已通关关卡的成绩：索引 -> {stars, score, time, mistakes, hints}
        # 重玩同一关时只保留更好的成绩（先比星级，再比得分）。
        self.records = {}
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

    @property
    def cleared_levels(self):
        """本次运行中已通关的关卡索引集合。

        由 records 推导而来，不单独存一份——成绩表才是唯一数据源，
        再存一个 set 就得时刻担心两者不同步。
        """
        return set(self.records)

    @property
    def total_stars(self):
        """本次运行累计获得的星数。"""
        return sum(record["stars"] for record in self.records.values())

    @property
    def total_score(self):
        """本次运行累计得分。"""
        return sum(record["score"] for record in self.records.values())

    @property
    def max_stars(self):
        """满星数：全部关卡都拿 3 星。"""
        return len(self.levels) * C.STAR_MAX

    @property
    def max_score(self):
        """满分：全部关卡都零失误且不超时。"""
        return len(self.levels) * C.SCORE_BASE

    @property
    def can_undo(self):
        """当前是否有可以撤销的步骤。"""
        return bool(self.history)

    # ---------------- 计时与评价 ----------------

    @property
    def elapsed(self):
        """本关用时（秒）。

        胜负判定后定格为 final_time，不再随帧增长——否则玩家赖在结算
        界面不走，用时也会一路涨上去。
        """
        return self.level_time if self.final_time is None else self.final_time

    @property
    def penalty_points(self):
        """本关惩罚点数 = 失误次数 + 提示次数，星级由它决定。

        撤销不在其中。撤销退还的是失误计数（见 undo()），它是"走错了退回来"
        的容错机制；而提示是主动向游戏要答案，所以计入惩罚。
        """
        return self.mistakes + self.hint_count

    @property
    def level_stars(self):
        """本关星级：惩罚点数每多 1 点降 1 星，最低 1 星（通关即有星）。"""
        return max(C.STAR_MIN,
                   C.STAR_MAX - self.penalty_points * C.STAR_LOSS_PER_PENALTY)

    @property
    def reference_time(self):
        """本关参考时长（秒），超过它才开始扣分。"""
        return self.arrow_total * C.SECONDS_PER_ARROW

    @property
    def level_score(self):
        """本关得分。

        游戏进行中取当前用时（可用于实时预览），结算后取定格用时。
        """
        overtime = max(0.0, self.elapsed - self.reference_time)
        score = (C.SCORE_BASE
                 - self.mistakes * C.SCORE_PER_MISTAKE
                 - overtime * C.SCORE_PER_SECOND)
        return max(C.SCORE_MIN, int(score))

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
        self.toast = None           # [文字, 已播放时长, 类型]
        self.result = None
        self.hover = None
        self.finish_delay = 0.0
        self.history = []           # 每步有效点击前压入的 (布局快照, 失误数)
        self.hint_cell = None       # 正在高亮的提示格
        self.hint_elapsed = 0.0

        # ---- 计时与评价 ----
        self.level_time = 0.0       # 本关已用时长（秒），只在游戏进行中累加
        self.hint_count = 0         # 本关用了多少次提示（评星依据之一）
        self.final_time = None      # 胜负判定那一刻的用时；一旦定格就不再走表

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
        self.hint_cell = None

    def on_result_button(self):
        """结果界面主按钮：失败重试，通关则进入下一关或重开一局。"""
        if self.result == "lose":
            self.restart()
        elif self.has_next_level:
            self.start_level(self.level_index + 1)
        else:
            self.start_game()

    # ---------------- 辅助功能 ----------------

    def undo(self):
        """撤销上一步点击。

        退回的是"上一步点击之前"的完整状态：飞出去的箭头回到原位，
        若是点错消耗掉的失误也一并退还——所以撤销本身不消耗失误次数。
        它的意义在于让玩家敢试错：试一个方向，不对就退回来。
        """
        if not self.history:
            return False

        snapshot, mistakes = self.history.pop()
        self.board.restore(snapshot)
        self.mistakes = mistakes

        # 上一步相关的动画与判定一并作废，
        # 否则会出现"棋盘已经退回去、箭头却还在飞"这类错位。
        self.fly_anims.clear()
        self.shake_anims.clear()
        self.hint_cell = None
        self.hint_elapsed = 0.0
        self.result = None
        self.finish_delay = 0.0
        self.toast = ["已撤销上一步", 0.0, "info"]
        audio.play("undo")
        return True

    def show_hint(self):
        """高亮一个当前可以点掉的箭头。

        直接复用求解器的 hint()：它返回当前局面下所有能飞出的箭头。
        在本关卡的规则下（消除只会让障碍变少、不会制造新障碍），
        只要关卡本身可解，任何时刻都至少有一个箭头可以飞出去，
        所以提示一定有答案，不存在"提示不出来"的情况。
        """
        candidates = find_hint(self.board)
        if not candidates:
            return False

        arrow = candidates[0]
        self.hint_cell = (arrow.row, arrow.col)
        self.hint_elapsed = 0.0
        self.hint_count += 1        # 提示是主动求助，计入评级惩罚
        return True

    def _record_result(self):
        """通关时结算本关成绩，记入 records。

        重玩同一关只保留更好的成绩：先比星级，星级相同再比得分。
        这样"回头把某关刷成三星"有意义，也不会把已有的好成绩弄差。
        """
        self.final_time = self.level_time      # 先定格用时，下面的得分才读得到
        entry = {
            "stars": self.level_stars,
            "score": self.level_score,
            "time": self.final_time,
            "mistakes": self.mistakes,
            "hints": self.hint_count,
        }
        previous = self.records.get(self.level_index)
        if previous is None or (entry["stars"], entry["score"]) > (
                previous["stars"], previous["score"]):
            self.records[self.level_index] = entry

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
                # 键盘快捷键同样要受"胜负已定"的约束：鼠标路径在
                # on_click 里已被 result 挡下，这里不加就是个漏洞——
                # 判定失败后按 U 能把 result 清掉接着玩（"失误用尽即失败"形同虚设），
                # 按 H 则会白白多记一次提示，把星级拉低。
                elif (event.key == pygame.K_u and self.state == self.STATE_PLAYING
                      and self.result is None):
                    self.undo()
                elif (event.key == pygame.K_h and self.state == self.STATE_PLAYING
                      and self.result is None):
                    self.show_hint()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.state == self.STATE_MENU:
                        self.state = self.STATE_SELECT
                    elif self.state == self.STATE_SELECT:
                        self.start_level(self.resume_level)
                    elif self.state == self.STATE_RESULT:
                        self.on_result_button()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # event.pos 是窗口坐标；窗口被缩放过时要换算回逻辑画布坐标，
                # 否则点击位置会整体偏移，越靠右下偏得越多。
                self.on_click(view.to_logical(event.pos))

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

        # 底部按钮行（游戏中和结算界面共用，按钮数量随状态变化）
        for (action, _text, _secondary), rect in zip(
                renderer.bottom_actions(self), renderer.bottom_button_rects(self)):
            if not rect.collidepoint(pos):
                continue
            if action == "menu":
                self.back_to_menu()
            elif action in ("restart", "replay"):
                self.restart()
            else:                       # "next"：下一关 / 再玩一次 / 失败重试
                self.on_result_button()
            return

        if self.state == self.STATE_RESULT:
            return

        # 胜负一旦判定，棋盘与辅助按钮立即全部锁死。
        #
        # 从判定到弹出结算界面之间还有一段动画延迟（finish_delay），这期间状态仍
        # 是 PLAYING。若继续接受点击，快速连点会把 finish_delay 一遍遍重置回满值，
        # 倒计时永远走不完，结算界面就再也不出现（失误数还会一路涨过上限）。
        # 更糟的是失败后继续点掉剩余箭头会命中 remaining == 0，把结果翻成胜利。
        if self.result is not None:
            return

        # 辅助按钮行（撤销 / 提示），只在游戏进行中出现
        for (action, _text, _disabled), rect in zip(
                renderer.assist_actions(self), renderer.assist_button_rects(self)):
            if not rect.collidepoint(pos):
                continue
            if action == "undo":
                self.undo()
            elif action == "hint":
                self.show_hint()
            return

        # ---- 游戏中：点击棋盘 ----

        cell = renderer.cell_at(self.origin, pos, self.board.rows, self.board.cols)
        if cell is None:
            return

        arrow = self.board.arrow_at(*cell)
        if arrow is None or cell in self.shake_anims:
            return        # 空格，或碰撞动画尚未播完（防连点）

        # 记下这一步之前的状态，供「撤销」回退
        self.history.append((self.board.snapshot(), self.mistakes))
        # 玩家自己动手了，先前的提示可能已经失效，先收起来
        self.hint_cell = None

        if self.board.can_fly_out(arrow):
            self.board.remove(arrow)
            distance = (max(self.board.rows, self.board.cols) + 1) * C.CELL_SIZE
            self.fly_anims.append(FlyOut(arrow, distance))
            if self.board.remaining == 0:
                self.result = "win"
                self._record_result()   # 结算本关星级与得分（「继续游戏」也据此查进度）
                self.finish_delay = C.FLY_OUT_DURATION + C.FINISH_DELAY
                # 最后一箭只响通关音。它的琶音本身已经表达了"完成了"，
                # 再叠一个飞出音只会让两段声音糊在一起。
                audio.play("win")
            else:
                audio.play("fly")
        else:
            self.mistakes += 1
            self.shake_anims[cell] = 0.0
            self.toast = ["前方有箭头挡路，换一个试试", 0.0, "danger"]
            audio.play("hit")
            if self.mistakes >= self.MAX_MISTAKES:
                self.result = "lose"
                self.final_time = self.level_time     # 失败也停表，结算里要显示用时
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
        # 只在"游戏进行中且胜负未定"时走表：结算界面、开始界面与选关界面
        # 都不计时，否则玩家在结算页停留也会被算进用时。
        if self.state == self.STATE_PLAYING and self.result is None:
            self.level_time += dt

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

        # 提示高亮到时间自动消失，不需要玩家手动关掉
        if self.hint_cell is not None:
            self.hint_elapsed += dt
            if self.hint_elapsed >= C.HINT_DURATION:
                self.hint_cell = None

        # 最后一个箭头飞出（或碰撞动画结束）后，稍等片刻再弹出结算界面
        if self.result is not None and self.state == self.STATE_PLAYING:
            self.finish_delay -= dt
            if self.finish_delay <= 0:
                self.state = self.STATE_RESULT

    def _update_hover(self):
        """只有游戏中、且鼠标不在按钮上时才高亮格子。"""
        # 胜负已定时棋盘不再响应点击，高亮也要跟着撤掉，
        # 否则会出现"格子亮着、点了却没反应"的错觉。
        if self.state != self.STATE_PLAYING or self.result is not None:
            self.hover = None
            return
        mouse = view.mouse_pos()
        if any(rect.collidepoint(mouse)
               for rect in renderer.bottom_button_rects(self)):
            self.hover = None
            return
        if any(rect.collidepoint(mouse)
               for rect in renderer.assist_button_rects(self)):
            self.hover = None
            return
        self.hover = renderer.cell_at(
            self.origin, mouse, self.board.rows, self.board.cols)

    def draw(self):
        renderer.render(self.screen, self)
        view.present(self.window, self.screen)
