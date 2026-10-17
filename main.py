"""MailSolo 启动入口。"""

import sys


def _enable_high_dpi() -> None:
    """让 Windows 高分屏下的界面保持清晰（未启用时会被系统位图拉伸而模糊）。"""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


if __name__ == "__main__":
    _enable_high_dpi()
    from app import MailSoloApp

    MailSoloApp().mainloop()
