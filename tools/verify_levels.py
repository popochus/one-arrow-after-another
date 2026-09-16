"""关卡可解性校验工具。

用法（在项目根目录执行）：
    python tools/verify_levels.py

作用：对每个关卡运行求解器，确认它真的能被通关，并打印出一条合法解法。
每次增删或修改关卡后都应该跑一遍，避免出现"关卡无法通关"这种硬伤。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.board import DIRECTION_TO_SYMBOL     # noqa: E402
from game.levels import load_levels            # noqa: E402
from game.solver import solve                  # noqa: E402


def main():
    levels = load_levels()
    print(f"共检查 {len(levels)} 个关卡\n")

    all_ok = True
    for level in levels:
        board = level.new_board()
        order = solve(board)

        if order is None:
            all_ok = False
            print(f"[失败] {level.name}：存在死锁，无法通关"
                  f"（尚有 {board.remaining} 个箭头无法消除）")
            continue

        print(f"[通过] {level.name}：可通关，共 {len(order)} 个箭头")
        print("       解法顺序（先行后列）：")
        print("       " + " -> ".join(
            f"({a.row},{a.col}){DIRECTION_TO_SYMBOL[a.direction]}" for a in order))
        print()

    print("结论：" + ("全部关卡均可通关" if all_ok else "存在无法通关的关卡，请修改"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
