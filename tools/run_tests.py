"""自动化测试：覆盖作业要求的 T01 ~ T06 六项测试，并补充若干用例。

补充用例：
    P01 ~ P09  路径检测的边界情况
    T07        连续通关全部关卡
    T08        游戏中返回主菜单
    T09        关卡选择界面
    T10        继续游戏
    T11        「重玩本关」按钮
    T12        键盘 R 重新开始
    T13 ~ T14  撤销（退回飞出的箭头 / 退回失误）
    T15        提示
    T16        无历史时撤销按钮置灰且点击无副作用
    T17        键盘 U / H 快捷键
    T18        窗口自适应缩放（屏幕放不下时等比缩小）
    T19        四个界面渲染冒烟（含缩放呈现路径）
    T20        音效合成与无声卡降级
    T21        胜负判定后输入锁定（连点不会推迟结算）
    T22        计时（游戏中走表、判定后定格、重开归零）
    T23        星级评价（由失误次数 + 提示次数决定）
    T24        得分（失误与用时共同决定，含保底）
    T25        判定后键盘 U / H 同样失效

用法（项目根目录）：
    python tools/run_tests.py

脚本使用 SDL 的 dummy 视频驱动，不会弹出游戏窗口，可以直接在命令行跑完。
测试同时覆盖两层：
    逻辑层 —— Board.can_fly_out 的路径判断；
    交互层 —— Game.on_click 的完整点击链路（含动画状态与失误计数）。

跑完会额外输出 docs/test_report.md，里面是一张「编号 / 测试内容 / 预期结果 /
实际结果 / 是否通过」的表格，可以直接贴进博客的「测试结果」一节。
"""

import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pygame                                            # noqa: E402

from game import audio, config, renderer, view        # noqa: E402
from game.app import Game                                # noqa: E402
from game.board import Arrow, Board, parse_level         # noqa: E402
from game.solver import solve                            # noqa: E402

_RESULTS = []
_screen = None


def get_screen():
    """惰性创建测试用窗口表面（dummy 驱动，不可见）。"""
    global _screen
    if _screen is None:
        pygame.init()
        _screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
    return _screen


def new_game():
    """新建一局并跳过开始界面直接进入游戏状态。"""
    game = Game(get_screen())
    game.start_game()
    return game


def make_board(text):
    rows, cols, arrows = parse_level(text)
    return Board(rows, cols, arrows)


def check(case_id, title, expected, actual, passed):
    _RESULTS.append((case_id, title, expected, actual, passed))


# 渲染冒烟测试用的哨兵色：先把画布涂成它，再看渲染有没有把它盖住。
# 挑洋红是因为游戏配色里完全不含这种颜色，不会和任何界面元素撞色。
_SENTINEL = (255, 0, 255)


def sentinel_left(surface):
    """渲染后仍残留哨兵色的像素占比。

    先缩小再抽样，避免逐像素遍历整张 720x1280 的画布。
    这里用最近邻的 transform.scale 而不是 smoothscale：
    平滑插值会把洋红和邻近像素混成粉色，反而把"没画到"判成"画到了"。
    """
    tiny = pygame.transform.scale(surface, (60, 106))
    hits = 0
    for x in range(60):
        for y in range(106):
            r, g, b = tiny.get_at((x, y))[:3]
            if r > 243 and g < 12 and b > 243:
                hits += 1
    return hits / (60 * 106)


def click_cell(game, row, col):
    """把网格坐标换算成屏幕坐标后模拟一次鼠标点击。"""
    game.on_click(renderer.cell_center(game.origin, row, col))


def assist_rect(game, action):
    """取辅助按钮行（撤销 / 提示）里某个动作的矩形。"""
    pairs = zip(renderer.assist_actions(game), renderer.assist_button_rects(game))
    return next(rect for (key, _text, _disabled), rect in pairs if key == action)


def first_flyable(game):
    """当前局面下第一个确实能飞出的箭头（不依赖具体关卡布局）。"""
    return next(a for a in game.board.arrows if game.board.can_fly_out(a))


# ==================== 逻辑层：路径检测 ====================

def test_path_detection():
    """先行验证路径检测本身，这是后续所有交互测试的基础。"""
    # 一行四个格子：(0,0) 朝右，右侧有箭头 -> 不能飞出
    board = make_board("> > . .")
    check("P01", "朝右且右侧有箭头", "被阻挡",
          "被阻挡" if not board.can_fly_out(board.arrow_at(0, 0)) else "可飞出",
          not board.can_fly_out(board.arrow_at(0, 0)))

    # 最右侧箭头朝右，右边是边界 -> 可以飞出
    board = make_board(". . > .")
    check("P02", "朝右且右侧通畅", "可飞出",
          "可飞出" if board.can_fly_out(board.arrow_at(0, 2)) else "被阻挡",
          board.can_fly_out(board.arrow_at(0, 2)))

    # 列方向：上方有箭头 -> 不能飞出
    board = make_board("v\n^")
    check("P03", "朝上且上方有箭头", "被阻挡",
          "被阻挡" if not board.can_fly_out(board.arrow_at(1, 0)) else "可飞出",
          not board.can_fly_out(board.arrow_at(1, 0)))

    # 列方向：上方通畅 -> 可以飞出
    board = make_board(".\n^")
    check("P04", "朝上且上方通畅", "可飞出",
          "可飞出" if board.can_fly_out(board.arrow_at(1, 0)) else "被阻挡",
          board.can_fly_out(board.arrow_at(1, 0)))

    # 朝向与阻挡不在同一条线上时，不应互相影响
    board = make_board("> .\n. ^")
    right_ok = board.can_fly_out(board.arrow_at(0, 0))
    up_ok = board.can_fly_out(board.arrow_at(1, 1))
    check("P05", "阻挡不在同一行列", "两个都能飞出",
          f"朝右者可飞出={right_ok}，朝上者可飞出={up_ok}",
          right_ok and up_ok)

    # 单格棋盘上的箭头，四个方向都能直接飞出（边界处理）
    labels = {"up": "上", "down": "下", "left": "左", "right": "右"}
    for direction, symbol in (("up", "^"), ("down", "v"),
                              ("left", "<"), ("right", ">")):
        board = make_board(symbol)
        check(f"P06-{direction}", f"单格棋盘、朝{labels[direction]}",
              "可飞出",
              "可飞出" if board.can_fly_out(board.arrow_at(0, 0)) else "被阻挡",
              board.can_fly_out(board.arrow_at(0, 0)))


# ==================== T01 ~ T06 ====================

def test_t01():
    """T01 点击前方无阻挡的箭头 -> 箭头飞出棋盘并消失。"""
    game = new_game()
    before = game.board.remaining
    click_cell(game, 0, 4)          # (0,4) 朝上，位于最上排，前方畅通

    check("T01", "点击前方无阻挡的箭头", "箭头飞出棋盘并消失",
          f"剩余 {before} → {game.board.remaining}，失误 {game.mistakes}",
          game.board.remaining == before - 1 and game.mistakes == 0)


def test_t02():
    """T02 点击前方有阻挡的箭头 -> 箭头不消失，失误次数减 1。"""
    game = new_game()
    before = game.board.remaining
    click_cell(game, 0, 0)          # (0,0) 朝右，被 (0,1) 挡住

    check("T02", "点击前方有阻挡的箭头", "箭头不消失，失误次数减 1",
          f"剩余 {before} → {game.board.remaining}，失误 {game.mistakes}",
          game.board.remaining == before and game.mistakes == 1)


def test_t03():
    """T03 点击位于边缘且朝向棋盘外的箭头 -> 正常消失，不越界报错。"""
    game = new_game()
    before = game.board.remaining
    crashed = False
    try:
        click_cell(game, 0, 4)      # 最上排、朝上，直接顶到边界
        click_cell(game, 3, 2)      # 最右两格、朝右，直接顶到边界
    except Exception as exc:        # noqa: BLE001
        crashed = True
        print("       异常：", exc)

    check("T03", "点击位于边缘且朝向棋盘外的箭头", "箭头正常消失，不发生越界错误",
          f"剩余 {before} → {game.board.remaining}，越界异常={crashed}",
          not crashed and game.board.remaining == before - 2)


def test_t04():
    """T04 消除本关全部箭头 -> 显示通关并进入下一关。"""
    game = new_game()
    order = solve(game.board)       # 求解器给出一条合法通关顺序

    if order is None:
        check("T04", "消除本关全部箭头", "显示通关并进入下一关",
              "关卡无解，无法测试", False)
        return

    for arrow in order:
        click_cell(game, arrow.row, arrow.col)

    cleared = (game.result == "win" and game.board.remaining == 0)

    # 通关后点击结果界面的按钮，应当进入下一关，并且新关卡是完整的初始状态
    advanced = False
    if cleared:
        game.on_result_button()
        advanced = (game.level_index == 1
                    and game.state == game.STATE_PLAYING
                    and game.mistakes == 0
                    and game.board.remaining == game.arrow_total > 0)

    check("T04", "消除本关全部箭头", "显示通关并进入下一关",
          f"本关清空={cleared}，点按钮进入第 2 关={advanced}",
          cleared and advanced)


def test_t05():
    """T05 失误次数耗尽 -> 显示失败并允许重新开始。"""
    game = new_game()
    for _ in range(Game.MAX_MISTAKES):
        click_cell(game, 0, 0)      # 反复点击同一个被挡箭头
        game.update(1.0)            # 推进时间，让碰撞动画结束，避免防抖拦截

    # 注意：必须在 restart 之前记录失败状态，重开会把 result 清空
    failed_as_expected = game.result == "lose"

    after_restart_ok = False
    if failed_as_expected:
        game.restart()
        after_restart_ok = (game.mistakes == 0
                            and game.result is None
                            and game.board.remaining == game.arrow_total)

    check("T05", "失误次数耗尽", "显示失败并允许重新开始",
          f"耗尽后结果={'lose' if failed_as_expected else '未失败'}，"
          f"重开恢复正常={after_restart_ok}",
          failed_as_expected and after_restart_ok)


def test_t06():
    """T06 游戏进行中重新开始 -> 箭头布局和失误次数恢复。"""
    game = new_game()
    click_cell(game, 0, 4)          # 消掉一个箭头
    click_cell(game, 0, 0)          # 制造一次失误
    game.restart()

    check("T06", "游戏进行中重新开始", "箭头布局和失误次数恢复",
          f"剩余 {game.board.remaining}/{game.arrow_total}，失误 {game.mistakes}",
          game.board.remaining == game.arrow_total
          and game.mistakes == 0
          and game.result is None)


def test_t07():
    """T07（补充）连续通关全部关卡 -> 多关卡流程与「全部通关」判定正确。"""
    game = new_game()
    total = len(game.levels)
    ok = True
    detail = f"共 {total} 关全部通关，末关不再有下一关"

    for index in range(total):
        order = solve(game.board)
        if order is None:
            ok, detail = False, f"第 {index + 1} 关无解"
            break

        for arrow in order:
            click_cell(game, arrow.row, arrow.col)

        if game.result != "win":
            ok, detail = False, f"第 {index + 1} 关未能通关"
            break

        if index == total - 1:
            # 最后一关：此时不应再存在下一关，界面会显示「全部通关！」
            if game.has_next_level:
                ok, detail = False, "最后一关仍被认为有下一关"
            break

        game.on_result_button()
        if game.level_index != index + 1:
            ok, detail = False, f"第 {index + 1} 关通关后未进入下一关"
            break

    check("T07", "连续通关全部关卡", f"{total} 关全部可通关，末关标记为全部通关",
          detail if ok else detail, ok)


def test_t08():
    """T08（补充）游戏中返回主菜单 -> Esc 键与「主菜单」按钮都要有效。"""
    game = new_game()
    click_cell(game, 0, 4)          # 先消掉一个箭头，制造一点进度

    # 1) 键盘 Esc
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    game.handle_events()
    esc_ok = game.state == game.STATE_MENU

    # 2) 鼠标点底部的「主菜单」按钮
    game.start_game()
    game.on_click(renderer.secondary_button_rect().center)
    click_ok = game.state == game.STATE_MENU

    # 3) 返回开始界面后再开始游戏，应当从第 1 关的完整初始状态开始
    game.start_game()
    fresh_ok = (game.level_index == 0
                and game.mistakes == 0
                and game.board.remaining == game.arrow_total > 0)

    check("T08", "游戏中返回主菜单", "Esc 与「主菜单」按钮均可返回，且能重新开始",
          f"Esc 返回={esc_ok}，按钮返回={click_ok}，重新开始正常={fresh_ok}",
          esc_ok and click_ok and fresh_ok)


def test_t09():
    """T09（补充）关卡选择界面：可从开始界面进入，并直接选择任意关卡。"""
    game = new_game()
    game.back_to_menu()

    game.on_click(renderer.menu_button_rect().center)
    entered = game.state == game.STATE_SELECT

    target = 2                      # 直接挑第 3 关，验证不受通关进度限制
    game.on_click(renderer.select_card_rect(target).center)
    picked = (game.state == game.STATE_PLAYING
              and game.level_index == target
              and game.board.remaining == game.arrow_total > 0
              and game.mistakes == 0)

    check("T09", "关卡选择界面", "可进入选关界面并直达第 3 关",
          f"进入选关界面={entered}，选中第 {target + 1} 关={picked}",
          entered and picked)


def test_t10():
    """T10（补充）继续游戏：通关一关后，可从开始界面直接续玩下一关。"""
    game = new_game()
    for arrow in solve(game.board):        # 打通第 1 关
        click_cell(game, arrow.row, arrow.col)
    recorded = 0 in game.cleared_levels

    game.back_to_menu()
    shown = game.has_progress and game.resume_level == 1

    game.on_click(renderer.menu_continue_rect().center)
    resumed = game.state == game.STATE_PLAYING and game.level_index == 1

    check("T10", "继续游戏", "通关后可从开始界面直接进入下一关",
          f"记录通关={recorded}，显示继续按钮={shown}，续玩第 2 关={resumed}",
          recorded and shown and resumed)


def test_t11():
    """T11（补充）结算界面的「重玩本关」按钮：重开本关，而不是跳到下一关。"""
    game = new_game()
    for arrow in solve(game.board):        # 打通第 1 关，进入结算界面
        click_cell(game, arrow.row, arrow.col)
    game.update(1.0)

    actions = renderer.bottom_actions(game)
    rects = renderer.bottom_button_rects(game)
    replay_rect = next(rect for (action, _text, _sec), rect
                       in zip(actions, rects) if action == "replay")

    game.on_click(replay_rect.center)
    replayed = (game.state == game.STATE_PLAYING
                and game.level_index == 0
                and game.board.remaining == game.arrow_total
                and game.mistakes == 0
                and game.result is None)

    check("T11", "结算界面点击「重玩本关」", "回到本关初始状态，且不会跳到下一关",
          f"当前第 {game.level_index + 1} 关，剩余 {game.board.remaining}"
          f"/{game.arrow_total}，失误 {game.mistakes}",
          replayed)


def test_t12():
    """T12（补充）键盘 R 重新开始：游戏中与结算界面都应生效。"""
    game = new_game()
    click_cell(game, 0, 4)                 # 先消掉一个箭头，制造进度
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
    game.handle_events()
    in_play = (game.board.remaining == game.arrow_total and game.mistakes == 0)

    game = new_game()
    for arrow in solve(game.board):
        click_cell(game, arrow.row, arrow.col)
    game.update(1.0)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
    game.handle_events()
    in_result = (game.state == game.STATE_PLAYING
                 and game.board.remaining == game.arrow_total
                 and game.result is None)

    check("T12", "键盘 R 重新开始", "游戏中与结算界面按 R 都能重置本关",
          f"游戏中重置={in_play}，结算界面重置={in_result}",
          in_play and in_result)


def test_t13():
    """T13（补充）撤销：把刚飞出的箭头放回原位。"""
    game = new_game()
    total = game.board.remaining
    arrow = first_flyable(game)

    click_cell(game, arrow.row, arrow.col)
    flown = game.board.remaining == total - 1
    game.update(1.0)                       # 让飞出动画播完，更接近真实节奏

    game.on_click(assist_rect(game, "undo").center)
    back = game.board.arrow_at(arrow.row, arrow.col)
    restored = (game.board.remaining == total
                and back is not None
                and back.direction == arrow.direction
                and game.mistakes == 0)

    check("T13", "撤销已飞出的箭头",
          "箭头回到原格，剩余数量与朝向都恢复",
          f"飞出后剩余 {total - 1}；撤销后剩余 {game.board.remaining}，"
          f"原格箭头{'已恢复' if back else '缺失'}",
          flown and restored)


def test_t14():
    """T14（补充）撤销一次失误：失误计数退还，撤销本身不吃失误。"""
    game = new_game()
    blocked = next(a for a in game.board.arrows if not game.board.can_fly_out(a))

    click_cell(game, blocked.row, blocked.col)
    after_mistake = game.mistakes
    game.update(1.0)

    game.on_click(assist_rect(game, "undo").center)
    refunded = (game.mistakes == 0 and game.board.remaining == game.arrow_total)

    check("T14", "撤销一次失误",
          "失误计数退还，且撤销这个动作本身不消耗失误",
          f"点错后失误 {after_mistake}；撤销后失误 {game.mistakes}，"
          f"剩余箭头 {game.board.remaining}/{game.arrow_total}",
          after_mistake == 1 and refunded)


def test_t15():
    """T15（补充）提示：高亮的必须是当前真的能飞出的箭头。"""
    game = new_game()
    game.on_click(assist_rect(game, "hint").center)

    cell = game.hint_cell
    arrow = game.board.arrow_at(*cell) if cell else None
    valid = arrow is not None and game.board.can_fly_out(arrow)

    # 玩家按提示点掉它之后，提示应当收起，不能留在原地误导人
    if valid:
        click_cell(game, arrow.row, arrow.col)
    cleared = game.hint_cell is None

    check("T15", "提示功能",
          "高亮一个当前确实能飞出的箭头，点掉后提示自动收起",
          f"提示格 {cell}，该箭头可飞出={valid}，点击后提示已收起={cleared}",
          valid and cleared)


def test_t16():
    """T16（补充）没有可撤销步骤时，撤销按钮禁用且点击无副作用。"""
    game = new_game()
    disabled = renderer.assist_actions(game)[0] == ("undo", "撤销", True)

    before = (game.board.remaining, game.mistakes, game.state, game.level_index)
    game.on_click(assist_rect(game, "undo").center)      # 按钮是灰的，仍模拟一次点击
    after = (game.board.remaining, game.mistakes, game.state, game.level_index)

    check("T16", "无历史时的「撤销」",
          "按钮显示为禁用状态，点击后棋盘与失误计数都不变",
          f"按钮禁用={disabled}；点击前后状态一致={before == after}",
          disabled and before == after)


def test_t17():
    """T17（补充）键盘 U / H：撤销与提示的快捷键。"""
    game = new_game()
    arrow = first_flyable(game)
    click_cell(game, arrow.row, arrow.col)
    game.update(1.0)

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_u))
    game.handle_events()
    undone = game.board.remaining == game.arrow_total

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h))
    game.handle_events()
    hinted = game.hint_cell is not None

    check("T17", "键盘 U / H 快捷键",
          "U 撤销上一步，H 给出提示",
          f"U 撤销生效={undone}；H 提示生效={hinted}",
          undone and hinted)


def test_t18():
    """T18（补充）窗口自适应：屏幕放得下就 1:1，放不下就等比缩小。"""
    original = view._scale
    try:
        # 足够大的屏幕：保持 1:1，窗口即逻辑画布的原始尺寸
        big_screen = (1920, 1440)
        view.install(big_screen)
        big_window = view.window_size()
        stays_1to1 = big_window == (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        # 比窗口矮的屏幕（1080p 去掉任务栏就是 1032）：
        # 应等比缩小，且窗口加上标题栏后仍完整落在屏幕内
        small_screen = (1920, 1032)
        view.install(small_screen)
        small_window = view.window_size()
        shrunk = small_window[1] < config.WINDOW_HEIGHT
        aspect_kept = abs(small_window[0] / small_window[1]
                          - config.WINDOW_WIDTH / config.WINDOW_HEIGHT) < 0.01
        fits = small_window[1] + view._WINDOW_CHROME_HEIGHT <= small_screen[1]

        # 坐标换算：窗口坐标换回逻辑坐标，往返误差不超过 1 像素
        factor = view.scale()
        back = view.to_logical((round(360 * factor), round(640 * factor)))
        roundtrip = abs(back[0] - 360) <= 1 and abs(back[1] - 640) <= 1
    finally:
        view._scale = original

    check("T18", "窗口自适应缩放",
          "屏幕放得下时 1:1 显示；放不下时等比缩小，窗口加标题栏后仍在屏幕内",
          f"大屏 {big_screen} -> 窗口 {big_window}，1:1={stays_1to1}；"
          f"小屏 {small_screen} -> 窗口 {small_window}，缩小={shrunk}、"
          f"宽高比不变={aspect_kept}、完整放得下={fits}；坐标往返准确={roundtrip}",
          stays_1to1 and shrunk and aspect_kept and fits and roundtrip)


def test_t19():
    """T19（补充）渲染冒烟：四个界面各渲染一帧，缩放呈现路径同样可用。

    这条用例是为了补上一个真实的漏网之鱼：在此之前测试只覆盖逻辑与点击链路，
    renderer 的绘制函数一次都没被调用过——界面代码里引用了不存在的名字、
    或者传递了错误的参数，测试全都发现不了。
    """
    game = Game(get_screen())

    def shot():
        """涂上哨兵色再渲染，渲染完还剩下多少哨兵色就说明有多少没画到。"""
        surface = pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        surface.fill(_SENTINEL)
        renderer.render(surface, game)
        return surface

    screens = []
    game.state = Game.STATE_MENU
    screens.append(("开始界面", shot()))
    game.state = Game.STATE_SELECT
    screens.append(("选关界面", shot()))
    game.start_level(0)
    screens.append(("游戏界面", shot()))
    game.result = "win"
    game.state = Game.STATE_RESULT
    screens.append(("结算界面", shot()))

    blank = [name for name, surface in screens if sentinel_left(surface) > 0.02]
    sizes_ok = all(surface.get_size() == (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
                   for _name, surface in screens)

    # 缩放呈现：窗口比画布小时也要能正常输出，而不是报错或尺寸不对
    window = None
    original = view._scale
    try:
        view.install((1920, 1032))
        window = pygame.Surface(view.window_size())
        view.present(window, screens[2][1])
    finally:
        view._scale = original
    present_ok = (window is not None
                  and window.get_size() != screens[2][1].get_size())

    check("T19", "四个界面渲染冒烟（含缩放呈现）",
          "开始 / 选关 / 游戏 / 结算都能完整渲染一帧，缩放呈现也不报错",
          f"没画满的界面={blank or '无'}；画布尺寸正确={sizes_ok}；"
          f"缩放后窗口尺寸={window.get_size() if window else '未生成'}，正常={present_ok}",
          not blank and sizes_ok and present_ok)


def test_t20():
    """T20（补充）音效：波形合成、播放，以及没有音频设备时的静默降级。

    测试跑在 SDL 的 dummy 音频驱动上，所以不会真的发出声音。
    """
    started = audio.init()
    expected = ("fly", "hit", "undo", "win")
    synthesized = audio.loaded() == expected

    # 四个音效都应当可以播放（dummy 驱动下 play() 也会如实返回结果）
    played = all(audio.play(name) for name in expected) if synthesized else False

    # 降级路径：模拟这台机器没有声卡，播放应变成空操作而不是抛异常
    skipped = False
    try:
        audio.shutdown()
        skipped = (not audio.enabled()) and audio.play("fly") is False
    finally:
        audio.init()          # 恢复，避免影响后续用例

    check("T20", "音效合成与无声卡降级",
          "四个音效都能合成并播放；没有音频设备时播放变成空操作、不报错",
          f"初始化={started}；已合成={list(audio.loaded())}；全部可播放={played}；"
          f"无声卡时静默跳过={skipped}",
          started and synthesized and played and skipped)


def test_t21():
    """T21（补充）胜负判定后立即锁死输入。

    用例来自真实试玩反馈：失误数显示成 11/3，结算界面始终不出现，只要点得够快。
    根因是判定到弹出结算之间还有一段动画延迟（finish_delay），这期间状态仍是
    「游戏中」，每次误点都把倒计时重置回满值，永远走不完。

    顺带覆盖同源的另一个隐患：判定失败后把剩余箭头点光，会命中 remaining == 0
    的分支，把已经确定的失败改写成胜利。

    用时间步区分两段：判定前用略大于晃动时长的大步长，保证每帧都点得动；
    判定后用细小步长逼近真实连点频率，专门冲击那段延迟窗口。
    """
    coarse = 0.35        # 略大于晃动时长（0.34 秒），每帧都能再次点到同一格
    fine = 0.02          # 判定之后的连点，模拟玩家高频点击

    def hittable(game):
        """当前点下去必然失误、且不在晃动保护中的箭头。"""
        return [a for a in game.board.arrows
                if not game.board.can_fly_out(a)
                and (a.row, a.col) not in game.shake_anims]

    def spam(game, seconds, step):
        """按给定步长连点，持续 seconds 秒。"""
        spent = 0.0
        while spent < seconds:
            pool = hittable(game)
            if pool:
                arrow = pool[0]
                game.on_click(
                    renderer.cell_center(game.origin, arrow.row, arrow.col))
            game.update(step)
            spent += step

    # ---- 判定前：连点直到失误达上限 ----
    game = new_game()
    spam(game, 2.0, coarse)
    reached = game.result == "lose" and game.mistakes == game.MAX_MISTAKES
    mistakes_at_verdict = game.mistakes

    # ---- 判定后：继续高频连点 4 秒 ----
    spam(game, 4.0, fine)
    locked_ok = (game.mistakes == mistakes_at_verdict
                 and game.result == "lose"
                 and game.state == game.STATE_RESULT)

    # ---- 通关后连点，胜负同样不该被改写 ----
    other = new_game()
    for arrow in solve(other.board):
        other.on_click(renderer.cell_center(other.origin, arrow.row, arrow.col))
        other.update(0.7)
    won = other.result == "win"
    spam(other, 4.0, fine)
    win_kept = won and other.result == "win" and other.mistakes == 0

    # ---- 结算界面的按钮必须仍然可用（锁定不能连按钮一起锁死）----
    third = new_game()
    spam(third, 2.0, coarse)
    buttons = list(zip(renderer.bottom_actions(third),
                       renderer.bottom_button_rects(third)))
    retry = next(rect for (action, _text, _secondary), rect in buttons
                 if action == "restart")
    third.on_click(retry.center)
    retry_ok = (third.state == Game.STATE_PLAYING
                and third.result is None and third.mistakes == 0)

    check("T21", "胜负判定后输入锁定",
          "判定后继续快速连点：结算照常弹出、失误数不再增长、胜负不被改写、"
          "结算按钮仍然可用",
          f"判定时失误={mistakes_at_verdict}/{game.MAX_MISTAKES}，"
          f"连点 4 秒后失误={game.mistakes}、结果={game.result}、状态={game.state}；"
          f"通关后连点结果={other.result}、失误={other.mistakes}；"
          f"「重试本关」可重开={retry_ok}",
          reached and locked_ok and win_kept and retry_ok)


def graded_game(mistakes=0, hints=0, seconds=0.0, level_index=0):
    """构造一个"刚通关"的局面，直接给定时长、失误与提示次数。

    评级只看这几个量，逐格点击打通一关太慢；直接设定更明确，
    也让"超时 15 秒"这类边界值可以精确构造。
    """
    game = Game(get_screen())
    game.start_level(level_index)
    game.level_time = seconds
    game.mistakes = mistakes
    game.hint_count = hints
    game._record_result()
    return game


def test_t22():
    """T22（补充）计时：只在游戏进行中走表，胜负判定即定格。"""
    game = new_game()
    zero_at_start = game.level_time == 0.0
    for _ in range(30):
        game.update(0.1)
    ticking = abs(game.elapsed - 3.0) < 1e-6

    game.back_to_menu()
    for _ in range(10):
        game.update(0.1)
    paused_in_menu = abs(game.elapsed - 3.0) < 1e-6

    game = new_game()
    for arrow in solve(game.board):
        click_cell(game, arrow.row, arrow.col)
        game.update(0.7)
    frozen_at = game.elapsed
    game.update(5.0)
    frozen = game.elapsed == frozen_at

    game.restart()
    reset = game.level_time == 0.0

    check("T22", "计时系统",
          "开局为 0；游戏进行中累加；回到开始界面或胜负判定后停表；重开归零",
          f"开局={zero_at_start}；走表 3 秒={ticking}；"
          f"回到开始界面后停表={paused_in_menu}；"
          f"判定后定格在 {frozen_at:.1f} 秒={frozen}；重开归零={reset}",
          zero_at_start and ticking and paused_in_menu and frozen and reset)


def test_t23():
    """T23（补充）星级评价：由「失误次数 + 提示次数」决定。

    撤销不计入其中——它退还的是失误计数，属于"走错了退回来"的容错机制；
    而提示是主动向游戏要答案，所以计入惩罚。
    """
    cases = [(0, 0, 3), (1, 0, 2), (0, 1, 2), (1, 1, 1), (2, 0, 1), (2, 3, 1)]
    got = []
    stars_ok = True
    for mistakes, hints, want in cases:
        game = graded_game(mistakes=mistakes, hints=hints)
        got.append(game.level_stars)
        stars_ok = stars_ok and game.level_stars == want

    game = new_game()
    game.show_hint()
    game.undo()
    undo_ok = game.hint_count == 1 and game.level_stars == 2

    check("T23", "星级评价（失误 + 提示）",
          "惩罚点数 0 → 3 星，1 → 2 星，2 及以上 → 1 星；最低 1 星；"
          "提示计入惩罚，撤销不计入",
          "失误+提示 " + "、".join(f"{m}+{h}→{s}星"
                                   for (m, h, _), s in zip(cases, got))
          + f"；用一次提示后撤销，仍为 {game.level_stars} 星、提示次数 {game.hint_count}",
          stars_ok and undo_ok)


def test_t24():
    """T24（补充）得分：失误与用时共同决定，且有保底。"""
    full = graded_game().level_score == config.SCORE_BASE
    one_mistake = (graded_game(mistakes=1).level_score
                   == config.SCORE_BASE - config.SCORE_PER_MISTAKE)

    # 第 1 关 8 个箭头，参考时长 8 × 5 = 40 秒；用 55 秒即超时 15 秒
    over = graded_game(seconds=55.0)
    overtime_ok = (over.level_score
                   == config.SCORE_BASE - 15 * config.SCORE_PER_SECOND)

    floored = (graded_game(seconds=200.0, mistakes=2).level_score
               == config.SCORE_MIN)

    # 提示只降星、不扣分
    hinted = graded_game(hints=3)
    hint_free = (hinted.level_score == config.SCORE_BASE
                 and hinted.level_stars == 1)

    first, last = Game(get_screen()), Game(get_screen())
    first.start_level(0)
    last.start_level(len(first.levels) - 1)
    scaled = (first.reference_time == first.arrow_total * config.SECONDS_PER_ARROW
              and last.reference_time > first.reference_time)

    check("T24", "得分（失误与用时）",
          f"满分 {config.SCORE_BASE}；每次失误 -{config.SCORE_PER_MISTAKE}；"
          f"超出参考时长后每秒 -{config.SCORE_PER_SECOND}，"
          f"保底 {config.SCORE_MIN} 分；提示只降星不扣分",
          f"满分={full}；1 次失误={one_mistake}；超时 15 秒→{over.level_score} 分"
          f"={overtime_ok}；扣到下限保底={floored}；"
          f"3 次提示仍 {hinted.level_score} 分/{hinted.level_stars} 星={hint_free}；"
          f"参考时长随箭头数缩放={scaled}",
          full and one_mistake and overtime_ok and floored and hint_free and scaled)


def test_t25():
    """T25（补充）判定后键盘 U / H 也必须失效。

    鼠标路径在 on_click 里已被 result 拦下，键盘路径原先没有这层守卫：
    判定失败后按 U 能把 result 清掉接着玩（"失误用尽即失败"形同虚设），
    按 H 则会多记一次提示、白白拉低星级。两条路径的行为必须一致。
    """
    def press(game, key):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        game.handle_events()

    game = new_game()
    game.mistakes = game.MAX_MISTAKES - 1
    blocked = next(a for a in game.board.arrows if not game.board.can_fly_out(a))
    click_cell(game, blocked.row, blocked.col)
    lost = game.result == "lose"

    press(game, pygame.K_u)
    undo_blocked = game.result == "lose"
    press(game, pygame.K_h)
    hint_blocked = game.hint_count == 0

    live = new_game()
    press(live, pygame.K_h)
    live_ok = live.hint_count == 1

    check("T25", "判定后键盘 U / H 失效",
          "胜负判定后按 U 不能撤销翻盘、按 H 不再计次；游戏进行中两者仍正常",
          f"已判定失败={lost}；按 U 后结果仍为 {game.result}={undo_blocked}；"
          f"按 H 后提示次数={game.hint_count}={hint_blocked}；"
          f"游戏中按 H 计次={live.hint_count}",
          lost and undo_blocked and hint_blocked and live_ok)


# ==================== 报告输出 ====================

# 作业第 5 节点名要求的六项测试，单独成表，方便直接贴进博客
REQUIRED_CASES = [f"T{index:02d}" for index in range(1, 7)]


def _markdown_table(rows):
    """把若干条测试结果渲染成 Markdown 表格。"""
    lines = ["| 编号 | 测试内容 | 预期结果 | 实际结果 | 是否通过 |",
             "| --- | --- | --- | --- | --- |"]
    for case_id, title, expected, actual, passed in rows:
        lines.append(f"| {case_id} | {title} | {expected} | {actual} | "
                     f"{'通过' if passed else '未通过'} |")
    return lines


def write_report(results, path):
    """输出 Markdown 报告，可直接复制进博客的「测试结果」一节。"""
    required = [row for row in results if row[0] in REQUIRED_CASES]
    extra = [row for row in results if row[0] not in REQUIRED_CASES]
    passed = sum(1 for row in results if row[4])

    lines = [
        "# 「一箭又一箭」自动化测试报告",
        "",
        f"- 运行方式：在项目根目录执行 `python tools/run_tests.py`",
        f"- 测试环境：Python {sys.version.split()[0]} / pygame {pygame.version.ver}",
        f"- 运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 结果汇总：共 {len(results)} 项，通过 {passed} 项，"
        f"未通过 {len(results) - passed} 项",
        "",
        "## 一、作业要求的用例（T01 ~ T06）",
        "",
    ]
    lines += _markdown_table(required)
    lines += [
        "",
        "## 二、补充用例",
        "",
        "在 T01 ~ T06 之外自行追加，覆盖路径检测的边界情况与后续新增的界面流程。",
        "",
    ]
    lines += _markdown_table(extra)
    lines += [
        "",
        "## 三、测试说明",
        "",
        "- 全程无窗口运行：使用 SDL 的 dummy 视频驱动，不需要人工操作，"
        "可在命令行一次跑完。",
        "- 覆盖两层：逻辑层直接调用 `Board.can_fly_out()` 验证路径判断；"
        "交互层调用 `Game.on_click()` 模拟真实鼠标点击，"
        "连动画状态与失误计数一起验证。",
        "- 通关类用例（T04、T07）的点击顺序由 `game/solver.py` 求解器现场算出，"
        "不是手工写死的步骤，因此关卡改动后测试仍然有效。",
        "",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ==================== 主流程 ====================

def main():
    pygame.init()

    test_path_detection()
    test_t01()
    test_t02()
    test_t03()
    test_t04()
    test_t05()
    test_t06()
    test_t07()
    test_t08()
    test_t09()
    test_t10()
    test_t11()
    test_t12()
    test_t13()
    test_t14()
    test_t15()
    test_t16()
    test_t17()
    test_t18()
    test_t19()
    test_t20()
    test_t21()
    test_t22()
    test_t23()
    test_t24()
    test_t25()

    width = 78
    print("=" * width)
    print("一箭又一箭 · 自动化测试报告")
    print("=" * width)
    passed_count = 0
    for case_id, title, expected, actual, passed in _RESULTS:
        flag = "PASS" if passed else "FAIL"
        if passed:
            passed_count += 1
        print(f"[{flag}] {case_id:<8} {title}")
        print(f"         预期：{expected}")
        print(f"         实际：{actual}")
    print("-" * width)
    print(f"合计 {len(_RESULTS)} 项，通过 {passed_count} 项，"
          f"失败 {len(_RESULTS) - passed_count} 项")

    report_path = write_report(_RESULTS, PROJECT_ROOT / "docs" / "test_report.md")
    print(f"Markdown 报告已写入：{report_path.relative_to(PROJECT_ROOT)}")

    pygame.quit()
    return 0 if passed_count == len(_RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
