"""关卡求解器。

用途有两个：
    1. 开发期校验关卡是否真的能通关（"关卡无法通关"是明确的扣分项）；
    2. 为后续「提示」「自动求解」这类扩展功能提供现成算法。

算法说明（这是本项目的关键结论）：
    在本关卡的规则下，消除一个箭头只会让棋盘上的障碍变少，绝不会让
    原本可以飞出的箭头变得飞不出去 —— 也就是说"可飞出"这一性质对消除
    操作是单调的。因此可以放心地反复消除"当前所有可飞出的箭头"：
        最终清空棋盘  -> 关卡可解，记录的消除顺序就是一条合法通关路径；
        中途无箭头可消 -> 存在互相锁死的箭头，关卡无解。
"""

from .board import Board


def solve(board):
    """求解关卡。

    参数 board 不会被修改。返回一条合法通关顺序（Arrow 列表）；
    关卡存在死锁时返回 None。
    """
    work = Board(board.rows, board.cols, board.arrows)
    order = []

    while work.remaining:
        removable = [a for a in work.arrows if work.can_fly_out(a)]
        if not removable:
            return None
        for arrow in removable:
            work.remove(arrow)
            order.append(arrow)

    return order


def hint(board):
    """返回当前局面下可以安全点击的箭头（供「提示」功能使用）。"""
    return [a for a in board.arrows if board.can_fly_out(a)]
