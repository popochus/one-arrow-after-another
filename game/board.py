"""棋盘与箭头的数据模型，以及游戏最核心的路径检测逻辑。

坐标约定
    row 向下递增，col 向右递增，左上角为 (0, 0)。

方向约定
    四种方向用字符串表示：'up' / 'down' / 'left' / 'right'，
    对应的行列增量见 DIRECTIONS。
"""

from dataclasses import dataclass

# 方向 -> (行增量, 列增量)
DIRECTIONS = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}

# 字符画关卡里的符号 -> 方向
SYMBOL_TO_DIRECTION = {
    "^": "up",
    "v": "down",
    "<": "left",
    ">": "right",
}

# 方向 -> 符号（用于日志、测试输出等）
DIRECTION_TO_SYMBOL = {v: k for k, v in SYMBOL_TO_DIRECTION.items()}


@dataclass(frozen=True)
class Arrow:
    """棋盘上的一个箭头：一个格子、一个方向。

    frozen=True 让它可哈希，方便放进集合里做状态比较。
    """

    row: int
    col: int
    direction: str


class Board:
    """棋盘：负责存放箭头，并判断某个箭头当前能否飞出。

    内部用 dict 以 (row, col) 为键存放箭头，消除时直接删除即可；
    同时保留一份初始布局，供"重新开始"复原。
    """

    def __init__(self, rows, cols, arrows):
        self.rows = rows
        self.cols = cols
        self._arrows = {(a.row, a.col): a for a in arrows}
        self._initial = dict(self._arrows)

    # ---------------- 查询 ----------------
    @property
    def arrows(self):
        """当前仍在棋盘上的全部箭头。"""
        return list(self._arrows.values())

    @property
    def remaining(self):
        """剩余箭头数量。"""
        return len(self._arrows)

    def arrow_at(self, row, col):
        """取某格的箭头；该格为空时返回 None。"""
        return self._arrows.get((row, col))

    def is_inside(self, row, col):
        """判断坐标是否还在棋盘范围内。"""
        return 0 <= row < self.rows and 0 <= col < self.cols

    # ---------------- 核心：路径检测 ----------------
    def can_fly_out(self, arrow):
        """判断箭头能否飞出棋盘。

        从箭头的下一格出发，沿其朝向逐格前进：
            中途遇到任何箭头 -> 被阻挡，返回 False；
            一路走到棋盘外   -> 前方畅通，返回 True。
        """
        d_row, d_col = DIRECTIONS[arrow.direction]
        row = arrow.row + d_row
        col = arrow.col + d_col

        while self.is_inside(row, col):
            if (row, col) in self._arrows:
                return False
            row += d_row
            col += d_col

        return True

    # ---------------- 修改 ----------------
    def remove(self, arrow):
        """把箭头从棋盘上拿走。"""
        self._arrows.pop((arrow.row, arrow.col), None)

    def reset(self):
        """恢复为初始布局。"""
        self._arrows = dict(self._initial)


def parse_level(text):
    """把字符画关卡解析成 (rows, cols, arrows)。

    约定（详见 levels.py 顶部的说明）：
        ^ 向上   v 向下   < 向左   > 向右     . 空位
    格子之间用空白分隔，因此每行的列号 = 该行第几个 token。
    """
    grid = [line.split() for line in text.strip("\n").split("\n")]
    grid = [row for row in grid if row]

    rows = len(grid)
    cols = max(len(row) for row in grid)

    arrows = []
    for r, row in enumerate(grid):
        for c, token in enumerate(row):
            direction = SYMBOL_TO_DIRECTION.get(token)
            if direction is not None:
                arrows.append(Arrow(r, c, direction))

    return rows, cols, arrows
