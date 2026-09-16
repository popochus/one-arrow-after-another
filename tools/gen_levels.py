"""关卡候选生成器（开发辅助工具，不参与游戏运行）。

为什么需要它
    随机撒箭头很容易撒出"死锁"布局（箭头互相指着、谁也飞不出去），
    手工试错成本高。这里用「反向放置」直接构造出保证可解的布局。

反向放置原理
    设最终消除顺序为 a1, a2, ..., an（a1 最先被消除）。
    倒着往棋盘上放：放 a_i 时棋盘上只有 a_i .. a_n。
    只要 a_i 沿自己的朝向到边界之间没有已放置的箭头，它在那一刻就能飞出。
    而真实对局里 a_i 被消除时，棋盘上恰好也只剩 a_i .. a_n 这一批，
    所以按 a1 -> an 的顺序点击必然合法 —— 布局一定可通关。

    放置完成后仍会调用 game.solver.solve() 独立复验一遍，防止推导有误。

用法（在项目根目录执行）：
    python tools/gen_levels.py
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.board import Arrow, Board, DIRECTIONS, DIRECTION_TO_SYMBOL   # noqa: E402
from game.solver import solve                                          # noqa: E402

ROWS = 5
COLS = 5
SEED = 20260916


def placeable(placed, rows, cols):
    """列出所有「放上去就能立刻飞出」的 (row, col, direction) 组合。

    条件：沿该方向到边界之间的格子都还没有箭头。
    """
    options = []
    for r in range(rows):
        for c in range(cols):
            if (r, c) in placed:
                continue
            for direction, (d_row, d_col) in DIRECTIONS.items():
                rr, cc = r + d_row, c + d_col
                clear = True
                while 0 <= rr < rows and 0 <= cc < cols:
                    if (rr, cc) in placed:
                        clear = False
                        break
                    rr += d_row
                    cc += d_col
                if clear:
                    options.append((r, c, direction))
    return options


def generate(count, rows=ROWS, cols=COLS, rng=None):
    """反向放置生成一个含 count 个箭头、且保证可解的布局。"""
    rng = rng or random.Random()
    placed = {}
    for _ in range(count):
        options = placeable(placed, rows, cols)
        if not options:
            break
        r, c, direction = rng.choice(options)
        placed[(r, c)] = direction
    return Board(rows, cols, [Arrow(r, c, d) for (r, c), d in placed.items()])


def removal_rounds(board):
    """统计贪心消除需要几轮（轮数越多，依赖链越长、越难）。"""
    work = Board(board.rows, board.cols, board.arrows)
    rounds = 0
    first_round = None
    while work.remaining:
        removable = [a for a in work.arrows if work.can_fly_out(a)]
        if not removable:
            return None, None
        if first_round is None:
            first_round = len(removable)
        for arrow in removable:
            work.remove(arrow)
        rounds += 1
    return rounds, first_round


def to_art(board):
    """把棋盘画成字符画，方便直接粘进 levels.py。"""
    symbol = {(a.row, a.col): DIRECTION_TO_SYMBOL[a.direction] for a in board.arrows}
    lines = []
    for r in range(board.rows):
        lines.append("  ".join(symbol.get((r, c), ".") for c in range(board.cols)))
    return "\n".join(lines)


def main():
    total = 14
    rng = random.Random(SEED)

    seen = set()
    results = []
    for _ in range(4000):
        board = generate(total, rng=rng)
        if board.remaining < 10:
            continue
        key = tuple(sorted((a.row, a.col, a.direction) for a in board.arrows))
        if key in seen:
            continue
        seen.add(key)

        rounds, first_round = removal_rounds(board)
        if rounds is None:
            continue                      # 理论上不会发生，留作双保险
        if solve(board) is None:
            continue
        results.append((rounds, first_round, board))

    # 难度排序：先看依赖链轮数，再看首轮可飞比例（比例越低越需要思考）
    results.sort(key=lambda item: (-item[0], item[1] / item[2].remaining))

    print(f"共生成 {len(seen)} 个不重复布局，其中可解 {len(results)} 个\n")
    for index, (rounds, first_round, board) in enumerate(results[:6], 1):
        print(f"--- 候选 {index}：{board.remaining} 个箭头，"
              f"需 {rounds} 轮消除，首轮可飞 {first_round} 个 ---")
        print(to_art(board))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
