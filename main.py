"""一箭又一箭 —— 程序入口。

运行方式：
    python main.py
"""

import sys

import pygame

from game import config
from game.app import Game


def main():
    pygame.init()
    screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
    pygame.display.set_caption(config.TITLE)

    # 关闭文本输入（SDL 的 IME 支持）。本游戏只用按键控制，不需要输入文字；
    # 而输入法一旦接管键盘，R / Esc 这类按键会被用于组字，游戏收不到 KEYDOWN，
    # 表现为"按键没反应"。这里显式关掉，保证按键全部直达游戏。
    pygame.key.stop_text_input()

    try:
        Game(screen).run()
    finally:
        pygame.quit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
