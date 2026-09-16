"""自动化测试：覆盖作业要求的 T01 ~ T06 六项测试，并补充若干用例。

补充用例：
    P01 ~ P09  路径检测的边界情况
    T07        连续通关全部关卡
    T08        游戏中返回主菜单
    T09        关卡选择界面
    T10        继续游戏

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

from game import config, renderer                        # noqa: E402
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


def click_cell(game, row, col):
    """把网格坐标换算成屏幕坐标后模拟一次鼠标点击。"""
    game.on_click(renderer.cell_center(game.origin, row, col))


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
