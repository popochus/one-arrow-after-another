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

    try:
        Game(screen).run()
    finally:
        pygame.quit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
