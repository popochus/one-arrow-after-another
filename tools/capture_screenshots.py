"""生成 README / 博客所需的游戏截图。

用法（项目根目录）：
    python tools/capture_screenshots.py

脚本用 SDL dummy 驱动离屏渲染，不弹窗，直接把画面存到 docs/screenshots/。
改动界面后重新跑一次，截图就会同步更新。
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame                                     # noqa: E402

from game import config, renderer                 # noqa: E402
from game.app import Game                         # noqa: E402
from game.solver import solve                     # noqa: E402

OUT_DIR = ROOT / "docs" / "screenshots"


def capture(filename, setup=None):
    screen = pygame.display.get_surface()
    game = Game(screen)
    if setup is not None:
        setup(game)
    renderer.render(screen, game)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / filename
    pygame.image.save(screen, str(path))
    print(f"已保存 {path.relative_to(ROOT)}")


def setup_menu(game):
    """开始界面：Game 初始化后默认就停在这里，无需额外操作。"""


def setup_playing(game):
    """游戏中：进入第一关，鼠标悬停在右上角的箭头上。"""
    game.start_game()
    game.hover = (0, 4)


def setup_collision(game):
    """碰撞反馈：点击被阻挡的箭头，取晃动动画中间的一帧。"""
    game.start_game()
    game.on_click(renderer.cell_center(game.origin, 0, 0))
    game.update(0.17)


def setup_win(game):
    """通关界面：按求解器给出的顺序清空棋盘，并等结算延迟走完。"""
    game.start_game()
    for arrow in solve(game.board):
        game.on_click(renderer.cell_center(game.origin, arrow.row, arrow.col))
    game.update(1.0)


def setup_lose(game):
    """失败界面：连续点错直到失误次数耗尽。"""
    game.start_game()
    for _ in range(Game.MAX_MISTAKES):
        game.on_click(renderer.cell_center(game.origin, 0, 0))
        game.update(1.0)


def setup_level5(game):
    """第 5 关：箭头最密集、依赖链最长的一关。"""
    game.start_level(len(game.levels) - 1)
    game.hover = (4, 4)


def setup_all_clear(game):
    """全部通关：一次性打通所有关卡，停在最后一关的结算界面。"""
    game.start_game()
    last = len(game.levels) - 1
    for index in range(len(game.levels)):
        for arrow in solve(game.board):
            game.on_click(renderer.cell_center(game.origin, arrow.row, arrow.col))
        game.update(1.0)              # 走完"最后的箭头飞出"延迟，切到结算界面
        if index < last:
            game.on_result_button()


def clear_level(game):
    """按求解器给出的顺序打通当前关卡，并把结算延迟走完。"""
    for arrow in solve(game.board):
        game.on_click(renderer.cell_center(game.origin, arrow.row, arrow.col))
    game.update(1.0)


def setup_select(game):
    """关卡选择界面：先通关前两关，让卡片上出现「已通关」标记。"""
    game.start_game()
    for _ in range(2):
        clear_level(game)
        game.on_result_button()
    game.back_to_menu()
    game.on_click(renderer.menu_button_rect().center)     # 开始界面 -> 选关界面


def setup_menu_progress(game):
    """开始界面（已有进度）：比初始状态多出一个「继续游戏」按钮。"""
    game.start_game()
    clear_level(game)
    game.back_to_menu()


def main():
    pygame.init()
    pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))

    capture("00_menu.png", setup_menu)
    capture("01_playing.png", setup_playing)
    capture("02_collision.png", setup_collision)
    capture("03_win.png", setup_win)
    capture("04_lose.png", setup_lose)
    capture("05_level5.png", setup_level5)
    capture("06_all_clear.png", setup_all_clear)
    capture("07_select.png", setup_select)
    capture("08_menu_progress.png", setup_menu_progress)

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
