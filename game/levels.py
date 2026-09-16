"""关卡数据。

用「字符画」描述箭头布局，好处是设计时能一眼看出箭头之间的阻挡关系，
也便于在代码里直接 review 和修改，不需要外部关卡编辑器。

符号约定：
    ^ 向上    v 向下    < 向左    > 向右    . 空位
    格子之间用空白分隔，列号 = 该行第几个 token

约束：每个关卡都必须存在合法通关顺序。改完关卡后请运行
      python tools/verify_levels.py
确认没有死锁（"关卡无法通关"是作业里明确的扣分项）。
"""

from .board import Board, parse_level

_RAW_LEVELS = [
    # 教学关：箭头少、出口明显，用来让玩家快速理解"前方无遮挡才能飞出"。
    (
        "第 1 关 · 顺藤摸瓜",
        """
        >  >  >  .  ^
        .  v  .  .  .
        .  .  .  <  .
        .  v  >  .  .
        .  .  .  .  .
        """,
    ),
    # 出现"必须先清掉下面才能放走上面"的纵向依赖。
    (
        "第 2 关 · 层层推进",
        """
        >  >  v  .  .
        .  .  v  .  .
        ^  .  .  >  v
        .  .  .  .  v
        >  >  .  .  .
        """,
    ),
    # 上下两排必须从两端往中间逐个清理，考的是"顺序感"。
    (
        "第 3 关 · 从两端突破",
        """
        >  >  >  >  ^
        .  .  .  .  .
        .  .  .  .  .
        .  .  .  .  .
        v  <  <  <  <
        """,
    ),
    # 箭头数量明显变多，可飞出的位置分散在四周。
    (
        "第 4 关 · 四面楚歌",
        """
        ^  ^  <  >  v
        <  .  .  .  v
        >  .  .  .  v
        .  <  .  ^  >
        .  >  .  .  v
        """,
    ),
    # 首轮只有少数几个箭头能飞出，依赖链最长，作为收尾关。
    (
        "第 5 关 · 天罗地网",
        """
        .  .  .  >  v
        <  <  >  .  >
        ^  .  .  .  v
        .  ^  .  .  <
        .  <  v  <  >
        """,
    ),
]


class Level:
    """一个关卡的静态定义：名称 + 初始棋盘。"""

    def __init__(self, name, board):
        self.name = name
        self.board = board

    @property
    def topic(self):
        """关卡主题名，即去掉「第 N 关 · 」前缀的部分（选关界面用）。"""
        return self.name.split("·", 1)[-1].strip()

    def new_board(self):
        """返回一份全新的棋盘，供开局和「重新开始」使用。"""
        return Board(self.board.rows, self.board.cols, self.board.arrows)


def load_levels():
    """解析并返回全部关卡。"""
    levels = []
    for name, text in _RAW_LEVELS:
        rows, cols, arrows = parse_level(text)
        levels.append(Level(name, Board(rows, cols, arrows)))
    return levels
