"""MailSolo 桌面界面：逐封独立发送邮件，收件人之间互不可见。"""

from __future__ import annotations

import csv
from datetime import datetime
import os
from pathlib import Path
import queue
import sys
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from mailer import MailSendWorker, SmtpSettings, parse_recipients, suggested_smtp

APP_NAME = "MailSolo"
APP_VERSION = "1.0.0"

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
ICON_PATH = BUNDLE_DIR / "logo" / "MailSolo.png"

C = {
    "bg": "#F4F6FA",
    "surface": "#FFFFFF",
    "border": "#E4E8EF",
    "border_strong": "#D5DBE5",
    "text": "#171B23",
    "muted": "#667085",
    "faint": "#98A2B3",
    "accent": "#2F6BFF",
    "accent_hover": "#1F55E0",
    "accent_soft": "#EDF2FF",
    "success": "#0E9F6E",
    "danger": "#D92D20",
    "warn": "#B54708",
}


def _resolve_log_dir() -> Path:
    """日志优先写在程序目录；目录不可写时回落到用户本地目录，保证绿色版可用。"""
    candidates = [
        APP_DIR / "logs",
        Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MailSolo" / "logs",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue
    return candidates[0]


class MailSoloApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.configure(bg=C["bg"])

        self._setup_fonts()
        self._setup_geometry()
        self._apply_window_icon()
        self._setup_styles()

        self.worker: MailSendWorker | None = None
        self.event_queue: queue.Queue[tuple] = queue.Queue()
        self.attachments: list[Path] = []
        self.log_rows: list[list[str]] = []
        self.log_dir = _resolve_log_dir()

        # 所有输入均为空，由用户自行填写；软件不预置任何邮箱或配置。
        self.sender_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar()
        self.security_var = tk.StringVar(value="SSL")
        self.interval_var = tk.StringVar(value="3")
        self.subject_var = tk.StringVar()

        self._build_header()
        self._build_footer()
        self._build_body()

        self._inner_scrolled = False
        for widget in (self.body_text, self.recipients_text, self.log_tree):
            widget.bind("<MouseWheel>", self._on_inner_wheel, add="+")

        self.after(100, self._process_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-Return>", lambda _event: self._start())
        self._update_recipient_count()
        self._set_status("就绪", "idle")

    # ---------- 基础设置 ----------

    def S(self, value: float) -> int:
        """按屏幕 DPI 缩放间距，保证高分屏下比例一致。"""
        return max(1, int(round(value * self.scale)))

    def _setup_fonts(self) -> None:
        families = set(tkfont.families(self))
        family = "Arial"
        for candidate in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI"):
            if candidate in families:
                family = candidate
                break
        self.family = family
        self.f_body = (family, 10)
        self.f_small = (family, 9)
        self.f_h1 = (family, 15, "bold")
        self.f_h2 = (family, 11, "bold")
        self.f_btn = (family, 10, "bold")
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkTooltipFont"):
            try:
                tkfont.nametofont(name).configure(family=family, size=10)
            except tk.TclError:
                pass

    def _setup_geometry(self) -> None:
        self.update_idletasks()
        self.scale = max(1.0, self.winfo_fpixels("1i") / 96.0)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(self.S(1120), screen_w - self.S(60))
        height = min(self.S(880), screen_h - self.S(90))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - self.S(20))
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(self.S(980), self.S(680))

    def _apply_window_icon(self) -> None:
        self._logo_full = None
        self._logo_small = None
        if not ICON_PATH.is_file():
            return
        try:
            self._logo_full = tk.PhotoImage(file=str(ICON_PATH))
            self.iconphoto(True, self._logo_full)
            factor = max(1, self._logo_full.width() // self.S(30))
            self._logo_small = self._logo_full.subsample(factor, factor)
        except tk.TclError:
            self._logo_full = None
            self._logo_small = None

    def _setup_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=self.f_body, background=C["surface"], foreground=C["text"])
        style.configure("TFrame", background=C["surface"])
        style.configure("TLabel", background=C["surface"], foreground=C["text"], font=self.f_body)

        style.configure(
            "Field.TEntry",
            padding=(self.S(10), self.S(7)),
            fieldbackground=C["surface"],
            background=C["surface"],
            foreground=C["text"],
            bordercolor=C["border_strong"],
            lightcolor=C["surface"],
            darkcolor=C["surface"],
            insertcolor=C["text"],
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Field.TEntry",
            bordercolor=[("focus", C["accent"])],
            lightcolor=[("focus", C["accent"])],
            darkcolor=[("focus", C["accent"])],
            fieldbackground=[("disabled", "#F7F8FB")],
        )

        style.configure(
            "Field.TCombobox",
            padding=(self.S(8), self.S(6)),
            fieldbackground=C["surface"],
            background=C["surface"],
            foreground=C["text"],
            bordercolor=C["border_strong"],
            arrowcolor=C["muted"],
            lightcolor=C["surface"],
            darkcolor=C["surface"],
            borderwidth=1,
        )
        style.map(
            "Field.TCombobox",
            fieldbackground=[("readonly", C["surface"]), ("disabled", "#F7F8FB")],
            foreground=[("readonly", C["text"])],
            selectbackground=[("readonly", C["surface"])],
            selectforeground=[("readonly", C["text"])],
            bordercolor=[("focus", C["accent"]), ("hover", C["border_strong"])],
            arrowcolor=[("active", C["accent"])],
        )

        style.configure(
            "Field.TSpinbox",
            padding=(self.S(8), self.S(6)),
            fieldbackground=C["surface"],
            background=C["surface"],
            foreground=C["text"],
            bordercolor=C["border_strong"],
            arrowcolor=C["muted"],
            lightcolor=C["surface"],
            darkcolor=C["surface"],
            borderwidth=1,
        )
        style.map(
            "Field.TSpinbox",
            bordercolor=[("focus", C["accent"])],
            arrowcolor=[("active", C["accent"])],
        )

        style.configure(
            "Primary.TButton",
            font=self.f_btn,
            background=C["accent"],
            foreground="#FFFFFF",
            bordercolor=C["accent"],
            lightcolor=C["accent"],
            darkcolor=C["accent"],
            focuscolor=C["accent"],
            borderwidth=0,
            relief="flat",
            padding=(self.S(22), self.S(9)),
        )
        style.map(
            "Primary.TButton",
            background=[("disabled", "#B7C8F4"), ("pressed", C["accent_hover"]), ("active", C["accent_hover"])],
            bordercolor=[("disabled", "#B7C8F4"), ("pressed", C["accent_hover"]), ("active", C["accent_hover"])],
            lightcolor=[("disabled", "#B7C8F4"), ("pressed", C["accent_hover"]), ("active", C["accent_hover"])],
            darkcolor=[("disabled", "#B7C8F4"), ("pressed", C["accent_hover"]), ("active", C["accent_hover"])],
            foreground=[("disabled", "#F4F7FF")],
        )

        style.configure(
            "Secondary.TButton",
            font=self.f_body,
            background=C["surface"],
            foreground=C["text"],
            bordercolor=C["border_strong"],
            lightcolor=C["surface"],
            darkcolor=C["surface"],
            focuscolor=C["surface"],
            borderwidth=1,
            relief="flat",
            padding=(self.S(16), self.S(8)),
        )
        style.map(
            "Secondary.TButton",
            background=[("disabled", "#F7F8FB"), ("pressed", "#E9EDF4"), ("active", "#F2F5F9")],
            foreground=[("disabled", C["faint"])],
        )

        style.configure(
            "Ghost.TButton",
            font=self.f_body,
            background=C["surface"],
            foreground=C["accent"],
            bordercolor=C["surface"],
            lightcolor=C["surface"],
            darkcolor=C["surface"],
            focuscolor=C["surface"],
            borderwidth=0,
            relief="flat",
            padding=(self.S(10), self.S(6)),
        )
        style.map(
            "Ghost.TButton",
            background=[("pressed", C["accent_soft"]), ("active", C["accent_soft"])],
            foreground=[("disabled", C["faint"])],
        )

        style.configure(
            "Log.Treeview",
            background=C["surface"],
            fieldbackground=C["surface"],
            foreground=C["text"],
            borderwidth=0,
            rowheight=self.S(30),
            font=self.f_small,
        )
        style.layout("Log.Treeview", [("Log.Treeview.treearea", {"sticky": "nswe"})])
        style.configure(
            "Log.Treeview.Heading",
            background="#F8FAFC",
            foreground=C["muted"],
            font=(self.family, 9, "bold"),
            relief="flat",
            padding=(self.S(10), self.S(8)),
            borderwidth=0,
        )
        style.map("Log.Treeview.Heading", background=[("active", "#F1F4F9")])
        style.map(
            "Log.Treeview",
            background=[("selected", C["accent_soft"])],
            foreground=[("selected", C["text"])],
        )

        style.configure(
            "Slim.Vertical.TScrollbar",
            gripcount=0,
            background="#D8DEE9",
            darkcolor=C["bg"],
            lightcolor=C["bg"],
            troughcolor=C["bg"],
            bordercolor=C["bg"],
            arrowcolor=C["faint"],
            arrowsize=self.S(12),
            width=self.S(10),
            relief="flat",
        )
        style.map("Slim.Vertical.TScrollbar", background=[("active", "#C2CAD8")])

    # ---------- 布局 ----------

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=C["surface"])
        header.pack(fill="x")
        inner = tk.Frame(header, bg=C["surface"])
        inner.pack(fill="x", padx=self.S(24), pady=(self.S(16), self.S(14)))

        brand = tk.Frame(inner, bg=C["surface"])
        brand.pack(side="left")
        if self._logo_small is not None:
            tk.Label(brand, image=self._logo_small, bg=C["surface"], bd=0).pack(side="left", padx=(0, self.S(10)))
        tk.Label(brand, text=APP_NAME, font=self.f_h1, fg=C["text"], bg=C["surface"]).pack(side="left")

        tk.Label(inner, text=f"v{APP_VERSION}", font=self.f_small, fg=C["faint"], bg=C["surface"]).pack(side="right")
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

    def _build_footer(self) -> None:
        footer = tk.Frame(self, bg=C["surface"])
        footer.pack(side="bottom", fill="x")
        tk.Frame(footer, bg=C["border"], height=1).pack(fill="x")
        inner = tk.Frame(footer, bg=C["surface"])
        inner.pack(fill="x", padx=self.S(24), pady=self.S(12))

        left = tk.Frame(inner, bg=C["surface"])
        left.pack(side="left")
        self.status_dot = tk.Canvas(left, width=self.S(10), height=self.S(10), bg=C["surface"], highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, self.S(8)))
        self._dot = self.status_dot.create_oval(1, 1, self.S(9), self.S(9), fill=C["muted"], outline="")
        self.status_label = tk.Label(left, text="就绪", font=self.f_body, fg=C["muted"], bg=C["surface"])
        self.status_label.pack(side="left")

        right = tk.Frame(inner, bg=C["surface"])
        right.pack(side="right")

        self.send_button = ttk.Button(right, text="开始发送", style="Primary.TButton", command=self._start)
        self.send_button.pack(side="right")
        tk.Frame(right, width=self.S(16), height=1, bg=C["surface"]).pack(side="right")

        interval_box = tk.Frame(right, bg=C["surface"])
        interval_box.pack(side="right", padx=(0, self.S(16)))
        tk.Label(interval_box, text="发送间隔", font=self.f_small, fg=C["muted"], bg=C["surface"]).pack(
            side="left", padx=(0, self.S(6))
        )
        ttk.Spinbox(
            interval_box, from_=0, to=3600, textvariable=self.interval_var, width=5, style="Field.TSpinbox"
        ).pack(side="left")
        tk.Label(interval_box, text="秒", font=self.f_small, fg=C["muted"], bg=C["surface"]).pack(
            side="left", padx=(self.S(6), 0)
        )

        self.stop_button = ttk.Button(right, text="停止", style="Secondary.TButton", command=self._stop, state="disabled")
        self.stop_button.pack(side="right", padx=(0, self.S(8)))
        self.pause_button = ttk.Button(
            right, text="暂停", style="Secondary.TButton", command=self._toggle_pause, state="disabled"
        )
        self.pause_button.pack(side="right", padx=(0, self.S(8)))
        ttk.Button(right, text="导出日志", style="Ghost.TButton", command=self._export_log).pack(
            side="right", padx=(0, self.S(8))
        )

    def _build_body(self) -> None:
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)

        self.page_canvas = tk.Canvas(body, bg=C["bg"], highlightthickness=0, bd=0)
        self.page_canvas.configure(yscrollincrement=self.S(20))
        vbar = ttk.Scrollbar(body, orient="vertical", command=self.page_canvas.yview, style="Slim.Vertical.TScrollbar")
        self.page_canvas.configure(yscrollcommand=vbar.set)
        self.page_canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        page = tk.Frame(self.page_canvas, bg=C["bg"])
        page_window = self.page_canvas.create_window((0, 0), window=page, anchor="nw")
        page.bind("<Configure>", lambda _event: self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all")))
        self.page_canvas.bind("<Configure>", lambda event: self.page_canvas.itemconfigure(page_window, width=event.width))
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

        holder = tk.Frame(page, bg=C["bg"])
        holder.pack(fill="both", expand=True, padx=self.S(24), pady=self.S(20))

        top_row = tk.Frame(holder, bg=C["bg"])
        top_row.pack(fill="x", pady=(0, self.S(12)))
        top_row.columnconfigure(0, weight=3, uniform="cards")
        top_row.columnconfigure(1, weight=2, uniform="cards")
        top_row.rowconfigure(0, weight=1)
        self._build_account_card(top_row)
        self._build_recipients_card(top_row)
        self._build_content_card(holder)
        self._build_log_card(holder)

    def _card(self, parent: tk.Widget, title: str) -> tuple[tk.Frame, tk.Frame]:
        outer = tk.Frame(parent, bg=C["surface"], highlightbackground=C["border"], highlightthickness=1, bd=0)
        inner = tk.Frame(outer, bg=C["surface"])
        inner.pack(fill="both", expand=True, padx=self.S(16), pady=self.S(14))

        head = tk.Frame(inner, bg=C["surface"])
        head.pack(fill="x", pady=(0, self.S(10)))
        tk.Label(head, text=title, font=self.f_h2, fg=C["text"], bg=C["surface"]).pack(side="left")

        body = tk.Frame(inner, bg=C["surface"])
        body.pack(fill="both", expand=True)
        return outer, body

    def _field(self, parent: tk.Widget, label: str, factory, **grid_kwargs) -> tk.Frame:
        box = tk.Frame(parent, bg=C["surface"])
        tk.Label(box, text=label, font=self.f_small, fg=C["muted"], bg=C["surface"], anchor="w").pack(
            fill="x", pady=(0, self.S(6))
        )
        widget = factory(box)
        widget.pack(fill="x")
        box.grid(**grid_kwargs)
        return box

    def _build_account_card(self, parent: tk.Widget) -> None:
        card, body = self._card(parent, "发件账号")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, self.S(12)))

        row0 = tk.Frame(body, bg=C["surface"])
        row0.pack(fill="x")
        row0.columnconfigure(0, weight=1, uniform="acct")
        row0.columnconfigure(1, weight=1, uniform="acct")
        self._field(
            row0,
            "发件人邮箱",
            lambda box: ttk.Entry(box, textvariable=self.sender_var, style="Field.TEntry"),
            row=0,
            column=0,
            sticky="ew",
            padx=(0, self.S(12)),
        )
        self._field(
            row0,
            "密码 / 授权码",
            lambda box: ttk.Entry(box, textvariable=self.password_var, style="Field.TEntry", show="•"),
            row=0,
            column=1,
            sticky="ew",
        )

        row1 = tk.Frame(body, bg=C["surface"])
        row1.pack(fill="x", pady=(self.S(14), 0))
        row1.columnconfigure(0, weight=3)
        row1.columnconfigure(1, weight=1)
        row1.columnconfigure(2, weight=1)
        self._field(
            row1,
            "SMTP 服务器",
            lambda box: ttk.Entry(box, textvariable=self.host_var, style="Field.TEntry"),
            row=0,
            column=0,
            sticky="ew",
            padx=(0, self.S(12)),
        )
        self._field(
            row1,
            "端口",
            lambda box: ttk.Entry(box, textvariable=self.port_var, style="Field.TEntry"),
            row=0,
            column=1,
            sticky="ew",
            padx=(0, self.S(12)),
        )
        self._field(
            row1,
            "加密方式",
            lambda box: ttk.Combobox(
                box,
                textvariable=self.security_var,
                values=("SSL", "STARTTLS"),
                state="readonly",
                style="Field.TCombobox",
            ),
            row=0,
            column=2,
            sticky="ew",
        )

        row2 = tk.Frame(body, bg=C["surface"])
        row2.pack(side="bottom", fill="x", pady=(self.S(12), 0))
        ttk.Button(row2, text="按常见邮箱自动填写", style="Ghost.TButton", command=self._apply_suggested_smtp).pack(
            side="left"
        )
        tk.Label(
            row2,
            text="支持 QQ、Gmail、Outlook、163、126 等域名，仅在你点击后填入",
            font=self.f_small,
            fg=C["faint"],
            bg=C["surface"],
        ).pack(side="left", padx=(self.S(10), 0))

    def _build_content_card(self, parent: tk.Widget) -> None:
        card, body = self._card(parent, "邮件内容")
        card.pack(fill="x", pady=(0, self.S(12)))

        tk.Label(body, text="邮件标题", font=self.f_small, fg=C["muted"], bg=C["surface"], anchor="w").pack(
            fill="x", pady=(0, self.S(6))
        )
        ttk.Entry(body, textvariable=self.subject_var, style="Field.TEntry").pack(fill="x")

        tk.Label(body, text="邮件正文", font=self.f_small, fg=C["muted"], bg=C["surface"], anchor="w").pack(
            fill="x", pady=(self.S(14), self.S(6))
        )
        body_wrap = tk.Frame(body, bg=C["surface"])
        body_wrap.pack(fill="both", expand=True)
        self.body_text = tk.Text(
            body_wrap,
            height=5,
            wrap="word",
            font=self.f_body,
            bg=C["surface"],
            fg=C["text"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=C["border_strong"],
            highlightcolor=C["accent"],
            insertbackground=C["text"],
            selectbackground=C["accent_soft"],
            selectforeground=C["text"],
            padx=self.S(10),
            pady=self.S(8),
            spacing1=1,
            spacing3=3,
        )
        self.body_text.pack(side="left", fill="both", expand=True)
        body_bar = ttk.Scrollbar(
            body_wrap, orient="vertical", command=self.body_text.yview, style="Slim.Vertical.TScrollbar"
        )
        body_bar.pack(side="right", fill="y", padx=(self.S(6), 0))
        self.body_text.configure(yscrollcommand=body_bar.set)

        attach_row = tk.Frame(body, bg=C["surface"])
        attach_row.pack(fill="x", pady=(self.S(12), 0))
        ttk.Button(attach_row, text="添加附件", style="Secondary.TButton", command=self._choose_attachments).pack(
            side="left"
        )
        self.attachment_label = tk.Label(
            attach_row, text="未添加附件", font=self.f_small, fg=C["faint"], bg=C["surface"], anchor="w"
        )
        self.attachment_label.pack(side="left", padx=(self.S(10), 0), fill="x", expand=True)
        self.clear_attach_button = ttk.Button(
            attach_row, text="清空", style="Ghost.TButton", command=self._clear_attachments, state="disabled"
        )
        self.clear_attach_button.pack(side="right")

    def _build_recipients_card(self, parent: tk.Widget) -> None:
        card, body = self._card(parent, "收件人")
        card.grid(row=0, column=1, sticky="nsew")

        wrap = tk.Frame(body, bg=C["surface"])
        wrap.pack(fill="both", expand=True)
        self.recipients_text = tk.Text(
            wrap,
            height=5,
            wrap="none",
            font=self.f_body,
            bg=C["surface"],
            fg=C["text"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=C["border_strong"],
            highlightcolor=C["accent"],
            insertbackground=C["text"],
            selectbackground=C["accent_soft"],
            selectforeground=C["text"],
            padx=self.S(10),
            pady=self.S(8),
        )
        self.recipients_text.pack(side="left", fill="both", expand=True)
        rec_bar = ttk.Scrollbar(
            wrap, orient="vertical", command=self.recipients_text.yview, style="Slim.Vertical.TScrollbar"
        )
        rec_bar.pack(side="right", fill="y", padx=(self.S(6), 0))
        self.recipients_text.configure(yscrollcommand=rec_bar.set)
        self.recipients_text.bind("<KeyRelease>", lambda _event: self._update_recipient_count())

        bottom = tk.Frame(body, bg=C["surface"])
        bottom.pack(side="bottom", fill="x", pady=(self.S(10), 0))
        tk.Label(
            bottom,
            text="空行自动忽略，重复地址只发送一次",
            font=self.f_small,
            fg=C["faint"],
            bg=C["surface"],
            anchor="w",
        ).pack(side="left")
        self.recipient_hint = tk.Label(bottom, text="", font=self.f_small, fg=C["muted"], bg=C["surface"])
        self.recipient_hint.pack(side="right")

    def _build_log_card(self, parent: tk.Widget) -> None:
        card, body = self._card(parent, "发送日志")
        card.pack(fill="x")

        wrap = tk.Frame(body, bg=C["surface"], highlightbackground=C["border"], highlightthickness=1, bd=0)
        wrap.pack(fill="both", expand=True)
        columns = ("time", "recipient", "status", "detail")
        self.log_tree = ttk.Treeview(
            wrap, columns=columns, show="headings", height=8, style="Log.Treeview", selectmode="browse"
        )
        headings = {"time": "时间", "recipient": "收件人", "status": "状态", "detail": "详情"}
        widths = {"time": 150, "recipient": 240, "status": 90, "detail": 520}
        for column in columns:
            self.log_tree.heading(column, text=headings[column])
            self.log_tree.column(
                column, width=self.S(widths[column]), anchor="w", stretch=(column == "detail"), minwidth=self.S(70)
            )
        self.log_tree.tag_configure("sending", background="#F7FAFF")
        self.log_tree.tag_configure("ok", background="#F4FBF7")
        self.log_tree.tag_configure("fail", background="#FEF5F4")
        self.log_tree.pack(side="left", fill="both", expand=True)
        log_bar = ttk.Scrollbar(wrap, orient="vertical", command=self.log_tree.yview, style="Slim.Vertical.TScrollbar")
        log_bar.pack(side="right", fill="y")
        self.log_tree.configure(yscrollcommand=log_bar.set)

    # ---------- 交互 ----------

    def _scroll_page(self, delta: int) -> None:
        step = max(1, abs(delta) // 40)
        # delta > 0 表示滚轮向上，内容需要往上回滚。
        self.page_canvas.yview_scroll(-step if delta > 0 else step, "units")

    def _on_inner_wheel(self, event: tk.Event) -> str | None:
        """文本框/日志表内部还能滚动时交给它自己，到边界后带动整页滚动。"""
        delta = int(getattr(event, "delta", 0))
        if not delta:
            return None
        widget = event.widget
        top, bottom = widget.yview()
        if (delta > 0 and top > 0.0) or (delta < 0 and bottom < 1.0):
            self._inner_scrolled = True
            return None
        self._scroll_page(delta)
        return "break"

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        if self._inner_scrolled:
            self._inner_scrolled = False
            return None
        delta = int(getattr(event, "delta", 0))
        if not delta:
            return None
        self._scroll_page(delta)
        return "break"

    def _set_status(self, text: str, tone: str = "idle") -> None:
        colors = {
            "idle": C["muted"],
            "running": C["accent"],
            "success": C["success"],
            "error": C["danger"],
            "warn": C["warn"],
        }
        color = colors.get(tone, C["muted"])
        self.status_label.configure(text=text, fg=color)
        self.status_dot.itemconfigure(self._dot, fill=color)

    def _update_recipient_count(self) -> None:
        recipients, invalid = parse_recipients(self.recipients_text.get("1.0", "end-1c"))
        if not recipients and not invalid:
            self.recipient_hint.configure(text="")
            return
        parts = [f"已识别 {len(recipients)} 个有效地址"]
        if invalid:
            parts.append(f"{len(invalid)} 行格式有误")
        self.recipient_hint.configure(text=" · ".join(parts), fg=C["warn"] if invalid else C["muted"])

    def _apply_suggested_smtp(self) -> None:
        settings = suggested_smtp(self.sender_var.get())
        if settings is None:
            messagebox.showinfo(
                "未识别的邮箱",
                "没有找到该域名的预设，请根据邮箱服务商帮助页手动填写 SMTP 服务器、端口和加密方式。",
                parent=self,
            )
            return
        self.host_var.set(settings.host)
        self.port_var.set(str(settings.port))
        self.security_var.set(settings.security)

    def _choose_attachments(self) -> None:
        selected = filedialog.askopenfilenames(title="选择要作为附件发送的本地文件", parent=self)
        if not selected:
            return
        existing = {str(path).casefold() for path in self.attachments}
        for filename in selected:
            path = Path(filename)
            if str(path).casefold() not in existing:
                self.attachments.append(path)
                existing.add(str(path).casefold())
        self._refresh_attachment_label()

    def _clear_attachments(self) -> None:
        self.attachments.clear()
        self._refresh_attachment_label()

    def _refresh_attachment_label(self) -> None:
        if not self.attachments:
            self.attachment_label.configure(text="未添加附件", fg=C["faint"])
            self.clear_attach_button.configure(state="disabled")
            return
        names = "、".join(path.name for path in self.attachments)
        self.attachment_label.configure(text=f"已添加 {len(self.attachments)} 个：{names}", fg=C["text"])
        self.clear_attach_button.configure(state="normal")

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        sender = self.sender_var.get().strip()
        password = self.password_var.get()
        host = self.host_var.get().strip()
        subject = self.subject_var.get().strip()
        body = self.body_text.get("1.0", "end-1c")
        recipients, invalid = parse_recipients(self.recipients_text.get("1.0", "end-1c"))

        try:
            port = int(self.port_var.get().strip())
            interval = float(self.interval_var.get().strip())
            if not 1 <= port <= 65535 or interval < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("配置有误", "端口需在 1–65535 之间，发送间隔需为大于等于 0 的数字。", parent=self)
            return
        if not sender or not password or not host or not subject or not body:
            messagebox.showerror(
                "信息不完整", "请填写发件人邮箱、密码/授权码、SMTP 服务器、邮件标题和正文。", parent=self
            )
            return
        if not recipients:
            messagebox.showerror("没有有效收件人", "请至少填写一个格式正确的收件人邮箱地址。", parent=self)
            return
        missing_files = [str(path) for path in self.attachments if not path.is_file()]
        if missing_files:
            messagebox.showerror("附件不可用", "以下附件已不存在或不是文件：\n" + "\n".join(missing_files), parent=self)
            return
        if invalid:
            preview = "、".join(invalid[:5])
            suffix = "……" if len(invalid) > 5 else ""
            if not messagebox.askyesno(
                "发现无效地址", f"将跳过 {len(invalid)} 个无效地址：\n{preview}{suffix}\n\n是否继续？", parent=self
            ):
                return

        self.log_rows.clear()
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)

        settings = SmtpSettings(host=host, port=port, security=self.security_var.get())
        self.worker = MailSendWorker(
            settings=settings,
            sender=sender,
            password=password,
            recipients=recipients,
            subject=subject,
            body=body,
            attachments=self.attachments.copy(),
            interval_seconds=interval,
            on_status=lambda recipient, status, detail: self.event_queue.put(("status", recipient, status, detail)),
            on_finished=lambda success, failure, stopped: self.event_queue.put(("finished", success, failure, stopped)),
        )
        self._set_sending_controls(True)
        self._set_status(f"正在发送 0/{len(recipients)}", "running")
        self.after(80, lambda: self.page_canvas.yview_moveto(1.0))
        self.worker.start()

    def _toggle_pause(self) -> None:
        if not self.worker or not self.worker.is_alive():
            return
        if self.worker.run_event.is_set():
            self.worker.pause()
            self.pause_button.configure(text="继续")
            self._set_status("已暂停（当前 SMTP 操作结束后生效）", "warn")
        else:
            self.worker.resume()
            self.pause_button.configure(text="暂停")
            self._set_status("继续发送中", "running")

    def _stop(self) -> None:
        if self.worker and self.worker.is_alive():
            self.worker.stop()
            self.stop_button.configure(state="disabled")
            self.pause_button.configure(state="disabled")
            self._set_status("正在停止（当前 SMTP 操作结束后生效）", "warn")

    def _process_events(self) -> None:
        try:
            while True:
                event = self.event_queue.get_nowait()
                if event[0] == "status":
                    _, recipient, status, detail = event
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.log_rows.append([timestamp, recipient, status, detail])
                    tag = {"成功": "ok", "失败": "fail"}.get(status, "sending")
                    self.log_tree.insert("", "end", values=(timestamp, recipient, status, detail), tags=(tag,))
                    self.log_tree.yview_moveto(1)
                    completed = sum(1 for row in self.log_rows if row[2] in {"成功", "失败"})
                    if status in {"成功", "失败"}:
                        total = len(self.worker.recipients) if self.worker else completed
                        self._set_status(f"正在发送 {completed}/{total}", "running")
                elif event[0] == "finished":
                    _, success, failure, stopped = event
                    self._set_sending_controls(False)
                    if stopped:
                        self._set_status(f"已停止：成功 {success}，失败 {failure}", "warn")
                    elif failure:
                        self._set_status(f"已完成：成功 {success}，失败 {failure}", "error")
                    else:
                        self._set_status(f"已完成：成功 {success}，失败 {failure}", "success")
                    self._save_session_log()
        except queue.Empty:
            pass
        self.after(100, self._process_events)

    def _set_sending_controls(self, is_sending: bool) -> None:
        self.send_button.configure(state="disabled" if is_sending else "normal")
        self.pause_button.configure(state="normal" if is_sending else "disabled", text="暂停")
        self.stop_button.configure(state="normal" if is_sending else "disabled")

    def _save_session_log(self) -> Path | None:
        if not self.log_rows:
            return None
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            path = self.log_dir / f"send_log_{datetime.now():%Y%m%d_%H%M%S}.csv"
            with path.open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["时间", "收件人", "状态", "详情"])
                writer.writerows(self.log_rows)
        except OSError:
            return None
        return path

    def _export_log(self) -> None:
        if not self.log_rows:
            messagebox.showinfo("没有日志", "目前没有可导出的发送日志。", parent=self)
            return
        filename = filedialog.asksaveasfilename(
            title="导出发送日志",
            defaultextension=".csv",
            initialfile=f"send_log_{datetime.now():%Y%m%d_%H%M%S}.csv",
            filetypes=[("CSV 文件", "*.csv")],
            parent=self,
        )
        if not filename:
            return
        with Path(filename).open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(["时间", "收件人", "状态", "详情"])
            writer.writerows(self.log_rows)
        messagebox.showinfo("导出成功", f"日志已导出到：\n{filename}", parent=self)

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("确认退出", "发送仍在进行。退出会请求停止发送，是否退出？", parent=self):
                return
            self.worker.stop()
        self.destroy()


if __name__ == "__main__":
    MailSoloApp().mainloop()
