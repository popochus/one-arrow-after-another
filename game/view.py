"""窗口自适应：把固定的 720x1280 逻辑画布缩放到真实屏幕上。

游戏内部所有坐标——布局常量、点击判定、绘制——都基于 720x1280 的「逻辑画布」，
界面代码因此不必关心窗口实际有多大。真实窗口尺寸由本模块按屏幕可用区域算出：

    屏幕放得下  -> 1:1 显示，行为与从前完全一致
    屏幕放不下  -> 等比缩小到刚好放得下

为什么需要它：1080p 笔记本去掉任务栏只剩 1032 像素高，而窗口高 1280。
Windows 放不下这么大的窗口，就把它整体上移——标题栏被顶到屏幕外，
于是既看不到顶部内容（关卡标题被裁掉一半），也没法用鼠标拖动窗口。
等比缩小后窗口能完整落在屏幕内，两个问题一起解决。

渲染时把逻辑画布整体缩放到窗口，鼠标坐标再反向换算回逻辑坐标，
因此游戏逻辑与界面代码对缩放完全无感。

注意本模块的默认状态是 scale = 1.0（1:1），此时所有函数都退化为直通操作，
自动化测试、截图脚本与演示录制脚本因此不受影响。
"""

import ctypes
import ctypes.wintypes as wintypes

import pygame

from . import config as C

# 当前缩放比例：真实窗口像素 / 逻辑画布像素。1.0 表示 1:1 显示。
_scale = 1.0

# Windows 窗口标题栏与边框占掉的高度。win10/11 常见约 39px，取 48 留些余量，
# 免得算出来的窗口加上标题栏后正好顶满屏幕、又差几个像素放不下。
_WINDOW_CHROME_HEIGHT = 48

# 缩放下限：屏幕再小也不缩到看不清，宁可让窗口略微超出屏幕。
_MIN_SCALE = 0.35


def desktop_work_area():
    """返回主显示器的可用区域 (宽, 高)，即去掉任务栏之后的部分。

    优先用 Win32 查询：pygame 的 get_desktop_sizes() 依赖 SDL 视频驱动，
    在无头(SDL dummy)环境下会返回兜底的假值，不能作为可靠来源。
    """
    try:
        rect = wintypes.RECT()
        ok = ctypes.windll.user32.SystemParametersInfoW(
            0x0030, 0, ctypes.byref(rect), 0)          # SPI_GETWORKAREA
        if ok:
            width, height = rect.right - rect.left, rect.bottom - rect.top
            if width > 0 and height > 0:
                return width, height
    except Exception:
        pass

    sizes = pygame.display.get_desktop_sizes()
    if sizes and sizes[0][0] > 0 and sizes[0][1] > 0:
        width, height = sizes[0]
        return width, max(height - _WINDOW_CHROME_HEIGHT, 1)
    return C.WINDOW_WIDTH, C.WINDOW_HEIGHT


def choose_scale(work_area=None):
    """选出窗口能用的最大缩放比例，上限 1.0（只缩小，不放大）。

    work_area 允许显式指定可用区域，仅供自动化测试注入各种屏幕尺寸；
    正常运行时留空，由 desktop_work_area() 去问系统。
    """
    avail_width, avail_height = work_area or desktop_work_area()
    scale = min(
        1.0,
        (avail_height - _WINDOW_CHROME_HEIGHT) / C.WINDOW_HEIGHT,
        avail_width / C.WINDOW_WIDTH,
    )
    return max(scale, _MIN_SCALE)


def install(work_area=None):
    """按屏幕情况定下缩放比例，返回真实窗口尺寸（供 set_mode 使用）。"""
    global _scale
    _scale = choose_scale(work_area)
    return window_size()


def scale():
    """当前缩放比例。"""
    return _scale


def window_size():
    """真实窗口的像素尺寸（客户区，不含标题栏与边框）。"""
    return (max(1, round(C.WINDOW_WIDTH * _scale)),
            max(1, round(C.WINDOW_HEIGHT * _scale)))


def to_logical(pos):
    """把窗口客户区坐标换算回逻辑画布坐标。"""
    if _scale == 1.0:
        return pos
    return (int(pos[0] / _scale), int(pos[1] / _scale))


def mouse_pos():
    """鼠标在逻辑画布上的位置。

    先取 pygame.mouse.get_pos()（窗口坐标）再换算，而不是直接读系统鼠标——
    离屏录制脚本正是通过替换 pygame.mouse.get_pos 来注入虚拟光标的，
    这样两套机制可以共存。
    """
    return to_logical(pygame.mouse.get_pos())


def present(window, canvas):
    """把逻辑画布呈现在窗口上，并提交显示。

    1:1 且画布就是窗口时直接提交，省掉一次整体拷贝（测试与录制脚本走的就是这条路）。
    """
    if window is not canvas:
        if _scale == 1.0:
            window.blit(canvas, (0, 0))
        else:
            # 缩小场景下 smoothscale 的双线性取样比最近邻更耐看：
            # 最近邻会让中文细笔画断掉，双线性只是略微柔化。
            pygame.transform.smoothscale(canvas, window.get_size(), window)
    pygame.display.flip()
