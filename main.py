"""一箭又一箭 —— 程序入口。

运行方式：
    python main.py
"""

import sys

import pygame

from game import audio, config, view
from game.app import Game


def main():
    pygame.init()

    # 打开音频并合成音效（波形由代码生成，不读任何音频文件）。
    # 没有可用声卡时它自己会静默降级，游戏照常运行，只是没有声音。
    audio.init()

    # 窗口尺寸按屏幕可用区域决定。屏幕放得下 720x1280 就 1:1 显示；
    # 放不下（例如 1080p 笔记本去掉任务栏只剩 1032 高）就等比缩小，
    # 否则系统会把过高的窗口顶出屏幕，导致顶部内容被裁、标题栏够不着也拖不动。
    window = pygame.display.set_mode(view.install())
    pygame.display.set_caption(config.TITLE)

    # 关闭文本输入（SDL 的 IME 支持）。本游戏只用按键控制，不需要输入文字；
    # 而输入法一旦接管键盘，R / Esc 这类按键会被用于组字，游戏收不到 KEYDOWN，
    # 表现为"按键没反应"。这里显式关掉，保证按键全部直达游戏。
    pygame.key.stop_text_input()

    # 所有绘制都发生在固定大小的逻辑画布上，最后由 view.present() 整体缩放到窗口。
    # 这样界面代码只认 720x1280 一套坐标，不必为不同屏幕各写一遍布局。
    canvas = pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))

    try:
        Game(canvas, window).run()
    finally:
        pygame.quit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
