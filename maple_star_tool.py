# -*- coding: utf-8 -*-
"""
楓星小工具 — Maplestory World 楓星 輔助小工具（PySide6）  v1.3.0.0

主視窗工具：
  A. 技能冷卻計時器
     • 小卡片 + 流式排版（拉寬→一排；拉窄→自動折多排）
     • 卡片縮放鈕、兩段透明度(背景/方塊)、分類頁籤、↺重置、🔁巡迴、全部重置
     • 秒數客製：留空用預設，填數字用你填的秒數
     • ⚔ 角色卡：角色技能/狀態倒數（劍士魔法消除 80 秒、藥水CD 30 秒），
       常駐顯示在 Boss 卡片上方，藍色標題與 BOSS 技能區別
     • 按鍵配置：每張卡下方的「按鍵配置」鈕——點一下、按下想綁的實體按鍵即完成
       （Esc 取消、右鍵清除）。之後按綁定鍵就觸發倒數（全域偵測、不攔截按鍵）。
       ⚡ 開關：開＝倒數中按鍵也直接重新倒數；關（預設）＝READY 時按鍵才會開始。
       綁定存到 maple_star_config.json，重啟後保留，預設全部未綁定
  C. 練等效率計算器（頁籤右側「📊 練等」）
     • 起始/結束經驗 + 倒數計時器 → 經驗差(含逗號)、每分鐘/每小時 效率
     • 選填「升級經驗」→ 升級總時 / 升級剩餘（精確到分鐘）

獨立浮動視窗：
  B. 尺規（頁籤右側「📏 尺規」開關鈕彈出，與主視窗共存、永遠置頂）
     • 像直尺：0–100%，每10%大刻度(標數字)、每5%小刻度；刻度可標記顏色
     • 極簡：左上「拖曳握把」+ 右上「✕」；透明度/顏色/清除在主視窗設定
     • 底冊透明度可調 → 拖到 Boss 血條上對齊看攻略進度

拖曳說明：背景/底冊透明時，請用「⠿ 拖曳握把」移動視窗（握把永遠可見可抓）。

之後修改下方 CATEGORIES 即可換成你自己的分類與技能。
安裝： pip install PySide6    執行： python 技能冷卻計時器.py
"""

import sys
import os
import time
import json
import threading
from PySide6.QtCore import Qt, QTimer, QRectF, QRect, QSize, QPoint, QPointF, Signal, QObject, QEvent
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath, QLinearGradient
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QHBoxLayout, QGridLayout, QSlider, QSizeGrip,
                               QFrame, QStackedWidget, QButtonGroup, QScrollArea, QLayout,
                               QColorDialog, QSizePolicy, QComboBox)

# =========================================================================
#  ★ 設定區
# =========================================================================
#   計時技能： {"name": 名稱, "cd": 冷卻秒數}
#   計次技能： {"name": 名稱, "type": "counter", "count": 預設次數}
CATEGORIES = [
    {"name": "普通/混沌炎魔", "skills": [
        {"name": "魔法無效化", "cd": 30},
        {"name": "物理無效化", "cd": 30},
        {"name": "誘惑", "cd": 90},
    ]},
    {"name": "凡雷恩", "skills": [
        {"name": "召喚豬魔", "type": "counter", "count": 7},
    ]},
    {"name": "普通/混沌龍王", "skills": [
        {"name": "魔法無效化", "cd": 40},
        {"name": "物理無效化", "cd": 40},
    ]},
    {"name": "阿卡伊農", "skills": [
        {"name": "尾段全圖殺", "cd": 70},
    ]},
    {"name": "皮卡啾", "skills": [
        {"name": "反盾", "cd": 45},
    ]},
    {"name": "女皇", "skills": [
        {"name": "反盾", "cd": 80},
        {"name": "變豬", "cd": 60},
        {"name": "鎖潛", "cd": 90},
        {"name": "活屍", "cd": 60},
        {"name": "傳送", "cd": 90},
    ]},
]

#   角色技能／狀態（「打Boss」模式中常駐顯示，可用 ⚔ 按鈕收合；標題為藍色以與 BOSS 技能區別）
#   劍士「魔法消除」：技能本身 CD 60 秒，但 BOSS 會抵抗 80 秒 → 實際要倒數 80 秒
#   「藥水CD」：部分 BOSS 戰喝藥後需等待才能再喝（預設 30 秒，可在卡片上客製）
PLAYER_SKILLS = [
    {"name": "魔法消除", "cd": 80},
    {"name": "藥水CD", "cd": 30},
]

CARD_W, CARD_H = 120, 158
CTRL_H = 22
ROOT_RGB = (18, 20, 27)
CARD_RGB = (34, 38, 49)
CTRL_RGB = (48, 52, 66)
C_READY  = QColor(46, 230, 166)
C_COOL_A = QColor(255, 196, 84)
C_COOL_B = QColor(255, 87, 87)
ACCENT   = "#2ee6a6"
TICK_MS  = 50


def fmt_int(n):
    try:
        return f"{int(round(n)):,}"
    except Exception:
        return "—"


def mmss(sec):
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def fmt_minutes(m):
    m = int(round(m))
    if m <= 0:
        return "0 分"
    if m < 60:
        return f"{m} 分"
    return f"{m // 60} 時 {m % 60} 分"


def app_dir():
    """程式所在目錄：打包成 exe 時用 exe 的位置（__file__ 會指向臨時解壓目錄，不可用）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def bundled_dir():
    """打包進 exe 的資料檔位置（PyInstaller 執行時的臨時解壓目錄）；未打包時同 app_dir()"""
    return getattr(sys, "_MEIPASS", None) or app_dir()


def _parse_exp_csv(path):
    d = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 3:
                    continue
                try:
                    lv = int(parts[0])
                    val = parts[2].strip()
                    if val in ("-", ""):
                        continue
                    d[lv] = int(float(val))
                except (ValueError, IndexError):
                    continue
    except (FileNotFoundError, OSError):
        pass
    return d


def _load_exp_table():
    """讀取 CSV 第3欄（楓星調整版）的升級經驗，僅取整數，1-30無數據則略過。

    先找程式旁邊的 CSV（使用者可自行替換成別版數據），沒有才用打包進 exe 的那份，
    這樣單獨下載 exe 也能用「輸入等級自動帶入升級經驗」。
    """
    name = "經驗需求表(推測).csv"
    d = _parse_exp_csv(os.path.join(app_dir(), name))
    if not d:
        d = _parse_exp_csv(os.path.join(bundled_dir(), name))
    return d


EXP_TABLE = _load_exp_table()


# =========================================================================
#  設定檔（按鍵綁定等，存在程式同目錄，重啟後保留）
# =========================================================================
CONFIG_PATH = os.path.join(app_dir(), "maple_star_config.json")


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# =========================================================================
#  全域按鍵偵測（Windows 低階鍵盤鉤子）
#  只「監聽」按鍵、不攔截，遊戲仍會正常收到該按鍵。
# =========================================================================
IS_WINDOWS = sys.platform == "win32"

# Windows 虛擬鍵碼 → 顯示名稱（未列出的鍵顯示為 VK##，一樣可以綁定）
VK_ESC = 0x1B   # Esc 保留：設定按鍵時按 Esc = 取消，不可綁定
VK_NAMES = {}
VK_NAMES.update({0x70 + i: f"F{i + 1}" for i in range(24)})             # F1–F24
VK_NAMES.update({c: chr(c) for c in range(0x41, 0x5B)})                 # A–Z
VK_NAMES.update({c: chr(c) for c in range(0x30, 0x3A)})                 # 0–9
VK_NAMES.update({0x60 + i: f"Num{i}" for i in range(10)})               # 數字鍵盤 0–9
VK_NAMES.update({
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x13: "Pause", 0x14: "CapsLock",
    0x20: "Space", 0x21: "PgUp", 0x22: "PgDn", 0x23: "End", 0x24: "Home",
    0x25: "←", 0x26: "↑", 0x27: "→", 0x28: "↓",
    0x2D: "Insert", 0x2E: "Delete",
    0x5B: "LWin", 0x5C: "RWin",
    0x6A: "Num*", 0x6B: "Num+", 0x6D: "Num-", 0x6E: "Num.", 0x6F: "Num/",
    0x90: "NumLock", 0x91: "ScrLock",
    0xA0: "LShift", 0xA1: "RShift", 0xA2: "LCtrl", 0xA3: "RCtrl", 0xA4: "LAlt", 0xA5: "RAlt",
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/",
    0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
})
NAME_TO_VK = {name: vk for vk, name in VK_NAMES.items()}


def vk_name(vk):
    return VK_NAMES.get(vk, f"VK{vk}")


class GlobalKeyListener(QObject):
    """在背景執行緒掛 WH_KEYBOARD_LL 鉤子，偵測到按鍵按下時發出 key_pressed(vk)。"""
    key_pressed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._proc = None   # 保留 callback 參考，避免被 GC

    def start(self):
        if not IS_WINDOWS or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="GlobalKeyListener")
        self._thread.start()

    def _run(self):
        import ctypes
        from ctypes import wintypes

        WH_KEYBOARD_LL = 13
        WM_KEYDOWN, WM_SYSKEYDOWN = 0x0100, 0x0104

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_void_p)]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                                      wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HMODULE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        # 64 位元下 HMODULE 會被 ctypes 預設的 c_int 截斷 → 錯誤 126，必須明確宣告
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        def hook_proc(n_code, w_param, l_param):
            if n_code >= 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                self.key_pressed.emit(int(kb.vkCode))
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._proc = HOOKPROC(hook_proc)
        hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc,
                                        kernel32.GetModuleHandleW(None), 0)
        if not hook:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


# =========================================================================
#  跨螢幕（不同縮放比例）搬移時鎖住視窗尺寸
# =========================================================================
class DpiSizeKeeper(QObject):
    """跨螢幕搬移時鎖住「邏輯尺寸」。

    Windows 在視窗換到不同縮放比例的螢幕時（例：150% → 100%）會發 WM_DPICHANGED，
    並建議一個「實體像素大小不變」的矩形；Qt 照做之後，視窗的邏輯尺寸就被乘上
    舊/新 DPI 比例 —— 730x480 一到 100% 螢幕就變成 1095x720，看起來像整個爆開，
    卡片卻還是原本大小，於是留下一大片空白。這裡在 DPI 變更後把邏輯尺寸改回去。
    """

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.handle = win.windowHandle()
        self.dpr = self.handle.devicePixelRatio()
        self.size = win.size()
        self._settling = False    # 正在換 DPI（此期間的尺寸變化都是系統改的）
        self._busy = False        # 自己正在改尺寸
        # 拖過螢幕交界時 screenChanged 會連發好幾次，而且系統是「之後」才把視窗放大，
        # 所以用一個可重設的計時器，等拖曳／DPI 切換都安定下來再把尺寸改回去。
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._restore)
        self.handle.screenChanged.connect(self._on_screen_changed)
        win.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if (obj is self.win and ev.type() == QEvent.Resize
                and not self._busy and not self._settling):
            self.size = QSize(ev.size())                # 只記使用者自己調的尺寸
        return False

    def _on_screen_changed(self, screen):
        dpr = screen.devicePixelRatio()
        if abs(dpr - self.dpr) < 1e-3:
            return                      # 同縮放比例的螢幕，尺寸不會被動到
        self.dpr = dpr
        self._settling = True
        self._timer.start()

    def _restore(self):
        self._settling = False
        if self.win.size() == self.size:
            return
        self._busy = True
        try:
            self.win.resize(self.size)
        finally:
            self._busy = False


def keep_logical_size(win):
    """視窗 show() 之後呼叫；回傳 DpiSizeKeeper（或 None，表示原生視窗還沒建立）"""
    if getattr(win, "_dpi_keeper", None) is not None:
        return win._dpi_keeper
    if win.windowHandle() is None:
        return None
    win._dpi_keeper = DpiSizeKeeper(win)
    return win._dpi_keeper


# =========================================================================
#  永遠不透明的拖曳握把（解決透明背景無處可抓）
# =========================================================================
class DragHandle(QWidget):
    def __init__(self, parent=None, w=30, h=22):
        super().__init__(parent)
        self.setFixedSize(w, h)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip("拖曳移動視窗")
        self._g = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._g = e.globalPosition().toPoint()
            self._w = self.window().pos()

    def mouseMoveEvent(self, e):
        if self._g is not None:
            self.window().move(self._w + (e.globalPosition().toPoint() - self._g))

    def mouseReleaseEvent(self, e):
        self._g = None

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath(); path.addRoundedRect(QRectF(self.rect().adjusted(1, 1, -1, -1)), 6, 6)
        p.fillPath(path, QBrush(QColor(*CTRL_RGB, 240)))
        p.setBrush(QColor(200, 206, 218)); p.setPen(Qt.NoPen)
        cx = self.width() / 2; cy = self.height() / 2
        for gx in (cx - 5, cx + 1):
            for gy in (cy - 6, cy - 1, cy + 4):
                p.drawEllipse(QPointF(gx + 2, gy + 1), 1.6, 1.6)
        p.end()


# =========================================================================
#  流式排版
# =========================================================================
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=2, hspacing=12, vspacing=12, center=False, hfw=True):
        super().__init__(parent)
        self._h, self._v = hspacing, vspacing
        self._center = center
        # hfw=False：對外宣告不支援 heightForWidth（高度由外部自行設定），
        # 避免此列的折行高度被父層當成「最小高度」往上傳。
        self._hfw = hfw
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):       self._items.append(item)
    def count(self):               return len(self._items)
    def itemAt(self, i):           return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i):           return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self):   return self._hfw
    def heightForWidth(self, w):   return self._layout(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect); self._layout(rect, False)

    def sizeHint(self):            return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _layout(self, rect, test):
        m = self.contentsMargins()
        left = rect.x() + m.left()
        avail = (rect.right() - m.right()) - left
        y = rect.y() + m.top()
        # 先分行
        rows = []; cur = []; cur_w = 0; cur_h = 0
        for it in self._items:
            w, h = it.sizeHint().width(), it.sizeHint().height()
            add = w if not cur else self._h + w
            if cur and cur_w + add > avail:
                rows.append((cur, cur_w, cur_h)); cur = []; cur_w = 0; cur_h = 0
                add = w
            cur.append(it); cur_w += add; cur_h = max(cur_h, h)
        if cur:
            rows.append((cur, cur_w, cur_h))
        # 再擺放（可置中）
        for items, tot_w, max_h in rows:
            x = left + (max(0, (avail - tot_w) // 2) if self._center else 0)
            for it in items:
                if not test:
                    it.setGeometry(QRect(QPoint(int(x), y), it.sizeHint()))
                x += it.sizeHint().width() + self._h
            y += max_h + self._v
        if rows:
            y -= self._v
        return y - rect.y() + m.bottom()


# =========================================================================
#  A. 技能卡片
# =========================================================================
class RingCard(QFrame):
    def __init__(self, name, cd):
        super().__init__()
        self.default_cd = float(cd); self.total = float(cd)
        self.remaining = 0.0; self.active = False; self.loop = False
        self._deadline = 0.0
        self._hover = False; self.block_alpha = 240; self.zoom = 1.0
        self.hotkey_id = None; self.hotkey_vk = None; self._last_hotkey = 0.0

        lay = QVBoxLayout(self); lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(4)
        self.name_lbl = QLabel(name); self.name_lbl.setAlignment(Qt.AlignCenter)
        self.name_lbl.setObjectName("skillName"); lay.addWidget(self.name_lbl)
        lay.addStretch(1)
        row = QHBoxLayout(); row.setSpacing(4)
        self.sec_input = QLineEdit(); self.sec_input.setPlaceholderText(str(int(cd)))
        self.sec_input.setAlignment(Qt.AlignCenter); self.sec_input.setObjectName("secInput")
        self.sec_input.setToolTip("客製秒數：留空用預設，填數字用你填的秒數")
        self.loop_btn = QPushButton("🔁"); self.loop_btn.setObjectName("loopBtn")
        self.loop_btn.setCheckable(True); self.loop_btn.setCursor(Qt.PointingHandCursor)
        self.loop_btn.setToolTip("巡迴計時：計時結束後自動重新開始")
        self.loop_btn.toggled.connect(lambda on: setattr(self, "loop", on))
        self.reset_btn = QPushButton("↺"); self.reset_btn.setObjectName("resetBtn")
        self.reset_btn.setCursor(Qt.PointingHandCursor); self.reset_btn.setToolTip("重置此計時")
        self.reset_btn.clicked.connect(self.reset)
        row.addWidget(self.sec_input, 1); row.addWidget(self.loop_btn, 0); row.addWidget(self.reset_btn, 0)
        lay.addLayout(row)
        row2 = QHBoxLayout(); row2.setSpacing(4)
        self.key_btn = QPushButton("按鍵配置"); self.key_btn.setObjectName("keyBtn")
        self.key_btn.setCursor(Qt.PointingHandCursor); self.key_btn.setFocusPolicy(Qt.NoFocus)
        self.key_btn.setToolTip("點一下後按下要綁定的按鍵（Esc 取消、右鍵清除綁定）。\n"
                                "之後按綁定鍵即觸發倒數（全域偵測，遊戲視窗在最上層也有效）。")
        self.force_btn = QPushButton("⚡"); self.force_btn.setObjectName("forceBtn")
        self.force_btn.setCheckable(True); self.force_btn.setCursor(Qt.PointingHandCursor)
        self.force_btn.setFocusPolicy(Qt.NoFocus)
        self.force_btn.setToolTip("⚡開：倒數中按綁定鍵也會直接重新倒數\n"
                                  "⚡關（預設）：READY 時按綁定鍵才會開始倒數")
        row2.addWidget(self.key_btn, 1); row2.addWidget(self.force_btn, 0)
        lay.addLayout(row2)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("單擊：開始　·　快速雙擊：重新開始")
        self.apply_zoom(1.0)

    def apply_zoom(self, z):
        self.zoom = z
        self.setFixedSize(int(CARD_W * z), int(CARD_H * z))
        ch = max(18, int(CTRL_H * z))
        self.sec_input.setFixedHeight(ch)
        self.loop_btn.setFixedSize(ch, ch); self.reset_btn.setFixedSize(ch, ch)
        self.key_btn.setFixedHeight(ch); self.force_btn.setFixedSize(ch, ch)
        fn = QFont("Microsoft JhengHei"); fn.setPixelSize(max(11, int(14 * z))); fn.setBold(True)
        self.name_lbl.setFont(fn)
        fi = QFont("Microsoft JhengHei"); fi.setPixelSize(max(9, int(12 * z)))
        self.sec_input.setFont(fi)
        fk = QFont("Microsoft JhengHei"); fk.setPixelSize(max(9, int(11 * z)))
        self.key_btn.setFont(fk)
        fb = QFont(); fb.setPixelSize(max(9, int(12 * z)))
        self.loop_btn.setFont(fb); self.reset_btn.setFont(fb); self.force_btn.setFont(fb)
        self.updateGeometry(); self.update()

    def set_block_alpha(self, a):
        self.block_alpha = a; self.update()

    def set_hotkey_display(self, vk):
        """更新綁定鍵並讓按鍵配置鈕顯示按鍵名稱（None＝未綁定）"""
        self.hotkey_vk = vk
        self.key_btn.setText(vk_name(vk) if vk else "按鍵配置")

    def _resolve_secs(self):
        t = self.sec_input.text().strip()
        try:
            return float(t) if t else self.default_cd
        except ValueError:
            return self.default_cd

    def trigger(self):
        if self.active:
            return
        secs = self._resolve_secs()
        if secs <= 0:
            return
        self.total = secs; self.remaining = secs
        self._deadline = time.perf_counter() + secs
        self.active = True; self.update()

    def restart(self):
        """快速雙擊：不論當前狀態，直接歸位重新倒數"""
        secs = self._resolve_secs()
        if secs <= 0:
            return
        self.total = secs; self.remaining = secs
        self._deadline = time.perf_counter() + secs
        self.active = True; self.update()

    def reset(self):
        self.active = False; self.remaining = 0.0; self._deadline = 0.0; self.update()

    def hotkey_activate(self):
        """全域按鍵觸發。⚡開：隨時重新倒數；⚡關（預設）：READY 時才開始倒數。
        1 秒內重複按鍵忽略（防按住連發）"""
        now = time.perf_counter()
        if now - self._last_hotkey < 1.0:
            return
        self._last_hotkey = now
        if self.force_btn.isChecked():
            self.restart()
        else:
            self.trigger()

    def tick(self, dt):
        if not self.active:
            return
        self.remaining = max(0.0, self._deadline - time.perf_counter())
        if self.remaining <= 0:
            if self.loop:
                secs = self._resolve_secs()
                self.total = secs
                if secs > 0:
                    self._deadline = time.perf_counter() + secs
                    self.remaining = secs
                    self.active = True
                else:
                    self.remaining = 0.0; self.active = False; self._deadline = 0.0
            else:
                self.remaining = 0.0; self.active = False; self._deadline = 0.0
        self.update()

    def enterEvent(self, e): self._hover = True;  self.update()
    def leaveEvent(self, e): self._hover = False; self.update()

    def mousePressEvent(self, e):
        if self.childAt(e.position().toPoint()) in (self.sec_input, self.loop_btn, self.reset_btn,
                                                    self.key_btn, self.force_btn):
            return
        if e.button() == Qt.LeftButton:
            self.trigger()

    def mouseDoubleClickEvent(self, e):
        if self.childAt(e.position().toPoint()) in (self.sec_input, self.loop_btn, self.reset_btn,
                                                    self.key_btn, self.force_btn):
            return
        if e.button() == Qt.LeftButton:
            self.restart()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1); a = self.block_alpha
        base = QColor(*CARD_RGB, a)
        if self._hover:
            base = QColor(*(min(c + 14, 255) for c in CARD_RGB), a)
        path = QPainterPath(); path.addRoundedRect(QRectF(r), 14, 14)
        p.fillPath(path, QBrush(base))
        border = QColor(46, 230, 166, 220) if self.loop else QColor(255, 255, 255, int(0.12 * a))
        p.setPen(QPen(border, 2 if self.loop else 1)); p.drawPath(path)

        top = self.name_lbl.geometry().bottom() + 4
        bot = self.sec_input.geometry().top() - 4
        avail = max(28, bot - top)
        side = min(self.width() - 34, avail)
        cx, cy = self.width() / 2, top + avail / 2
        ring = QRectF(cx - side / 2, cy - side / 2, side, side)
        thick = max(4, side * 0.10)
        inner = ring.adjusted(thick / 2, thick / 2, -thick / 2, -thick / 2)
        p.setPen(QPen(QColor(255, 255, 255, int(0.16 * a)), thick, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(inner, 0, 360 * 16)
        if self.active and self.total > 0:
            frac = max(0.0, self.remaining / self.total)
            grad = QLinearGradient(ring.topLeft(), ring.bottomRight())
            grad.setColorAt(0, C_COOL_A); grad.setColorAt(1, C_COOL_B)
            p.setPen(QPen(QBrush(grad), thick, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(inner, 90 * 16, int(360 * frac * 16))
            main = C_COOL_B if frac < 0.4 else C_COOL_A
            txt, big = f"{int(self.remaining)}", 0.30
        else:
            p.setPen(QPen(C_READY, thick, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(inner, 90 * 16, 360 * 16)
            main = C_READY; txt, big = "READY", 0.22
        p.setPen(main)
        f = QFont("Arial"); f.setBold(True); f.setPixelSize(max(11, int(side * big)))
        p.setFont(f); p.drawText(ring, Qt.AlignCenter, txt)
        p.end()


# =========================================================================
#  A2. 計數卡（凡雷恩：點一下 +1，顯示 n/max，無巡迴）
# =========================================================================
class CounterCard(QFrame):
    def __init__(self, name, count):
        super().__init__()
        self.default_max = int(count)
        self.count = 0
        self._hover = False; self.block_alpha = 240; self.zoom = 1.0
        self.hotkey_id = None; self.hotkey_vk = None; self._last_hotkey = 0.0

        lay = QVBoxLayout(self); lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(4)
        self.name_lbl = QLabel(name); self.name_lbl.setAlignment(Qt.AlignCenter)
        self.name_lbl.setObjectName("skillName"); lay.addWidget(self.name_lbl)
        lay.addStretch(1)
        row = QHBoxLayout(); row.setSpacing(4)
        self.max_input = QLineEdit(); self.max_input.setPlaceholderText(str(int(count)))
        self.max_input.setAlignment(Qt.AlignCenter); self.max_input.setObjectName("secInput")
        self.max_input.setToolTip("客製次數：留空用預設")
        self.max_input.textChanged.connect(lambda _: self.update())
        self.reset_btn = QPushButton("↺"); self.reset_btn.setObjectName("resetBtn")
        self.reset_btn.setCursor(Qt.PointingHandCursor); self.reset_btn.setToolTip("次數歸零")
        self.reset_btn.clicked.connect(self.reset)
        row.addWidget(self.max_input, 1); row.addWidget(self.reset_btn, 0)
        lay.addLayout(row)
        row2 = QHBoxLayout(); row2.setSpacing(4)
        self.key_btn = QPushButton("按鍵配置"); self.key_btn.setObjectName("keyBtn")
        self.key_btn.setCursor(Qt.PointingHandCursor); self.key_btn.setFocusPolicy(Qt.NoFocus)
        self.key_btn.setToolTip("點一下後按下要綁定的按鍵（Esc 取消、右鍵清除綁定）。\n"
                                "之後按綁定鍵即次數 +1（全域偵測，遊戲視窗在最上層也有效）。")
        row2.addWidget(self.key_btn, 1)
        lay.addLayout(row2)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("單擊：次數 +1")
        self.apply_zoom(1.0)

    def apply_zoom(self, z):
        self.zoom = z
        self.setFixedSize(int(CARD_W * z), int(CARD_H * z))
        ch = max(18, int(CTRL_H * z))
        self.max_input.setFixedHeight(ch); self.reset_btn.setFixedSize(ch, ch)
        self.key_btn.setFixedHeight(ch)
        fn = QFont("Microsoft JhengHei"); fn.setPixelSize(max(11, int(14 * z))); fn.setBold(True)
        self.name_lbl.setFont(fn)
        fi = QFont("Microsoft JhengHei"); fi.setPixelSize(max(9, int(12 * z)))
        self.max_input.setFont(fi)
        fk = QFont("Microsoft JhengHei"); fk.setPixelSize(max(9, int(11 * z)))
        self.key_btn.setFont(fk)
        fb = QFont(); fb.setPixelSize(max(9, int(12 * z))); self.reset_btn.setFont(fb)
        self.updateGeometry(); self.update()

    def set_block_alpha(self, a):
        self.block_alpha = a; self.update()

    def set_hotkey_display(self, vk):
        """更新綁定鍵並讓按鍵配置鈕顯示按鍵名稱（None＝未綁定）"""
        self.hotkey_vk = vk
        self.key_btn.setText(vk_name(vk) if vk else "按鍵配置")

    def _resolve_max(self):
        t = self.max_input.text().strip()
        try:
            return int(t) if t else self.default_max
        except ValueError:
            return self.default_max

    def increment(self):
        mx = self._resolve_max()
        if mx <= 0:
            return
        if self.count < mx:
            self.count += 1
        self.update()

    def reset(self):
        self.count = 0; self.update()

    def hotkey_activate(self):
        """全域按鍵觸發：次數 +1；0.5 秒內重複按鍵忽略（防按住連發）"""
        now = time.perf_counter()
        if now - self._last_hotkey < 0.5:
            return
        self._last_hotkey = now
        self.increment()

    def tick(self, dt):
        pass  # 計數卡不倒數

    def enterEvent(self, e): self._hover = True;  self.update()
    def leaveEvent(self, e): self._hover = False; self.update()

    def mousePressEvent(self, e):
        if self.childAt(e.position().toPoint()) in (self.max_input, self.reset_btn, self.key_btn):
            return
        if e.button() == Qt.LeftButton:
            self.increment()

    def mouseDoubleClickEvent(self, e):
        # 快速連點時第二下由 doubleClick 送達，這裡補計一次，確保每次點擊都算到
        if self.childAt(e.position().toPoint()) in (self.max_input, self.reset_btn, self.key_btn):
            return
        if e.button() == Qt.LeftButton:
            self.increment()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1); a = self.block_alpha
        base = QColor(*CARD_RGB, a)
        if self._hover:
            base = QColor(*(min(c + 14, 255) for c in CARD_RGB), a)
        path = QPainterPath(); path.addRoundedRect(QRectF(r), 14, 14)
        p.fillPath(path, QBrush(base))
        mx = self._resolve_max()
        done = mx > 0 and self.count >= mx
        border = QColor(46, 230, 166, 220) if done else QColor(255, 255, 255, int(0.12 * a))
        p.setPen(QPen(border, 2 if done else 1)); p.drawPath(path)

        top = self.name_lbl.geometry().bottom() + 4
        bot = self.max_input.geometry().top() - 4
        avail = max(28, bot - top)
        side = min(self.width() - 34, avail)
        cx, cy = self.width() / 2, top + avail / 2
        ring = QRectF(cx - side / 2, cy - side / 2, side, side)
        thick = max(4, side * 0.10)
        inner = ring.adjusted(thick / 2, thick / 2, -thick / 2, -thick / 2)
        p.setPen(QPen(QColor(255, 255, 255, int(0.16 * a)), thick, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(inner, 0, 360 * 16)
        frac = max(0.0, min(1.0, self.count / mx)) if mx > 0 else 0.0
        arc_col = C_READY if done else QColor(91, 155, 255)
        if frac > 0:
            p.setPen(QPen(arc_col, thick, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(inner, 90 * 16, int(360 * frac * 16))
        p.setPen(C_READY if done else QColor(238, 240, 245))
        f = QFont("Arial"); f.setBold(True); f.setPixelSize(max(11, int(side * 0.26)))
        p.setFont(f); p.drawText(ring, Qt.AlignCenter, f"{self.count}/{mx}")
        p.end()


# =========================================================================
#  B. 尺規（極簡浮動視窗：左上握把 + 右上✕；設定在主視窗）
# =========================================================================
class RulerWidget(QWidget):
    MARGIN = 16; EDGE = 12; BASELINE = 20; MAJOR = 24; MINOR = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.marked = set()
        self.hi_color = QColor(230, 60, 60)
        self.base_alpha = 150
        self.setFixedHeight(64); self.setMinimumWidth(240)
        self._mode = None
        self.setMouseTracking(True); self.setCursor(Qt.OpenHandCursor)

    def set_base_alpha(self, a):
        self.base_alpha = a; self.update()

    def _tick_x(self, i):
        usable = self.width() - 2 * self.MARGIN
        return self.MARGIN + usable * i / 20

    def _nearest_tick(self, x):
        usable = self.width() - 2 * self.MARGIN
        if usable <= 0:
            return None
        i = round((x - self.MARGIN) / usable * 20)
        return i if 0 <= i <= 20 and abs(x - self._tick_x(i)) <= 6 else None

    def mousePressEvent(self, e):
        x, y = e.position().x(), e.position().y()
        win = self.window()
        if x <= self.EDGE:
            self._mode = "resL"
        elif x >= self.width() - self.EDGE:
            self._mode = "resR"
        else:
            i = self._nearest_tick(x)
            if i is not None and self.BASELINE <= y <= self.BASELINE + self.MAJOR + 2:
                self.marked.discard(i) if i in self.marked else self.marked.add(i)
                self.update(); return
            self._mode = "move"; self.setCursor(Qt.ClosedHandCursor)
        self._start_g = e.globalPosition().toPoint()
        self._start_win = win.pos(); self._start_w = win.width(); self._start_x = win.x()

    def mouseMoveEvent(self, e):
        win = self.window()
        if self._mode is None:
            x = e.position().x()
            if x <= self.EDGE or x >= self.width() - self.EDGE:
                self.setCursor(Qt.SizeHorCursor)
            elif self._nearest_tick(x) is not None and e.position().y() <= self.BASELINE + self.MAJOR:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.OpenHandCursor)
            return
        g = e.globalPosition().toPoint(); dx = g.x() - self._start_g.x()
        if self._mode == "move":
            win.move(self._start_win + (g - self._start_g))
        elif self._mode == "resR":
            win.resize(max(240, self._start_w + dx), win.height())
        elif self._mode == "resL":
            neww = max(240, self._start_w - dx)
            win.setGeometry(self._start_x + (self._start_w - neww), win.y(), neww, win.height())

    def mouseReleaseEvent(self, e):
        self._mode = None; self.setCursor(Qt.OpenHandCursor)

    def _halo(self, p, x, y1, y2):
        p.setPen(QPen(QColor(255, 255, 255, 175), 3.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x, y1), QPointF(x, y2))

    def _halo_text(self, p, rect, s):
        p.setPen(QColor(255, 255, 255, 195))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p.drawText(rect.adjusted(dx, dy, dx, dy), Qt.AlignCenter, s)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath(); path.addRoundedRect(QRectF(r), 10, 10)
        p.fillPath(path, QBrush(QColor(244, 240, 232, self.base_alpha)))
        if self.base_alpha > 20:
            p.setPen(QPen(QColor(0, 0, 0, min(60, self.base_alpha)), 1)); p.drawPath(path)
        M = self.MARGIN; b = self.BASELINE
        p.setPen(QPen(QColor(255, 255, 255, 175), 3.2)); p.drawLine(M, b, self.width() - M, b)
        p.setPen(QPen(QColor(45, 45, 45), 2)); p.drawLine(M, b, self.width() - M, b)
        fnt = QFont("Arial"); fnt.setPixelSize(11); fnt.setBold(True); p.setFont(fnt)
        for i in range(21):
            x = self._tick_x(i); major = (i % 2 == 0)
            ln = self.MAJOR if major else self.MINOR; mk = i in self.marked
            self._halo(p, x, b, b + ln)
            col = self.hi_color if mk else QColor(30, 30, 30)
            p.setPen(QPen(col, 2.8 if mk else 1.6)); p.drawLine(QPointF(x, b), QPointF(x, b + ln))
            if major:
                rect = QRectF(x - 16, b + ln + 1, 32, 14)
                self._halo_text(p, rect, f"{i * 5}")
                p.setPen(col if mk else QColor(35, 35, 35)); p.drawText(rect, Qt.AlignCenter, f"{i * 5}")
        p.setPen(QPen(QColor(120, 120, 120, 200), 2))
        for hx in (5, self.width() - 5):
            p.drawLine(QPointF(hx, b - 4), QPointF(hx, b + self.MAJOR + 6))
        p.end()


class RulerWindow(QWidget):
    closed = Signal()

    def __init__(self, base_alpha=138, hi_color=None):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(560, 92)
        v = QVBoxLayout(self); v.setContentsMargins(6, 4, 6, 2); v.setSpacing(2)
        top = QHBoxLayout(); top.setContentsMargins(0, 0, 0, 0)
        self.handle = DragHandle(self, 30, 20)
        self.close_btn = QPushButton("✕"); self.close_btn.setObjectName("rClose")
        self.close_btn.setFixedSize(22, 20); self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setToolTip("關閉刻度表"); self.close_btn.clicked.connect(self.close)
        top.addWidget(self.handle); top.addStretch(1); top.addWidget(self.close_btn)
        v.addLayout(top)
        self.ruler = RulerWidget(self)
        self.ruler.set_base_alpha(base_alpha)
        if hi_color is not None:
            self.ruler.hi_color = hi_color
        v.addWidget(self.ruler)
        self.setStyleSheet("""
            #rClose { background: rgba(48,52,66,240); color:#dfe3ea; border:none;
                      border-radius:6px; font-size:12px; }
            #rClose:hover { background:#ff5757; color:white; }
        """)

    def closeEvent(self, e):
        self.closed.emit(); super().closeEvent(e)


# =========================================================================
#  C. 練等效率計算器
# =========================================================================
class CalcPage(QWidget):
    def __init__(self):
        super().__init__()
        self.total = 0.0; self.remaining = 0.0; self.running = False; self._deadline = 0.0
        v = QVBoxLayout(self); v.setContentsMargins(6, 2, 6, 4); v.setSpacing(6)

        def field(label, ph):
            row = QHBoxLayout()
            lb = QLabel(label); lb.setObjectName("formLbl"); lb.setFixedWidth(58)
            le = QLineEdit(); le.setObjectName("expInput"); le.setPlaceholderText(ph)
            row.addWidget(lb); row.addWidget(le, 1)
            return row, le

        r1, self.start_in = field("起始經驗", "例如 1,234,567"); v.addLayout(r1)
        r2, self.end_in = field("結束經驗", "倒數結束後填入"); v.addLayout(r2)

        lv_row = QHBoxLayout()
        lv_lb = QLabel("等級"); lv_lb.setObjectName("formLbl"); lv_lb.setFixedWidth(58)
        self.lv_in = QLineEdit(); self.lv_in.setObjectName("expInput")
        self.lv_in.setPlaceholderText("31–200（自動帶入升級經驗）")
        lv_row.addWidget(lv_lb); lv_row.addWidget(self.lv_in, 1)
        v.addLayout(lv_row)

        r3, self.req_in = field("升級經驗", "升級所需總經驗（選填）"); v.addLayout(r3)

        dur = QHBoxLayout()
        dl = QLabel("計時"); dl.setObjectName("formLbl"); dl.setFixedWidth(58)
        self.min_in = QLineEdit("15"); self.min_in.setObjectName("timeInput"); self.min_in.setFixedWidth(46)
        self.min_in.setAlignment(Qt.AlignCenter)
        self.sec_in = QLineEdit("00"); self.sec_in.setObjectName("timeInput"); self.sec_in.setFixedWidth(46)
        self.sec_in.setAlignment(Qt.AlignCenter)
        dur.addWidget(dl); dur.addWidget(self.min_in); dur.addWidget(QLabel("分"))
        dur.addWidget(self.sec_in); dur.addWidget(QLabel("秒")); dur.addStretch(1)
        v.addLayout(dur)

        btns = QHBoxLayout()
        self.start_btn = QPushButton("開始"); self.start_btn.setObjectName("goBtn")
        self.start_btn.setCursor(Qt.PointingHandCursor); self.start_btn.clicked.connect(self._toggle)
        self.rst_btn = QPushButton("重置"); self.rst_btn.setObjectName("toolPill")
        self.rst_btn.setCursor(Qt.PointingHandCursor); self.rst_btn.clicked.connect(self._reset)
        btns.addWidget(self.start_btn, 1); btns.addWidget(self.rst_btn, 1)
        v.addLayout(btns)

        self.countdown = QLabel("15:00"); self.countdown.setObjectName("countdown")
        self.countdown.setAlignment(Qt.AlignCenter); v.addWidget(self.countdown)

        grid = QGridLayout(); grid.setHorizontalSpacing(14); grid.setVerticalSpacing(4)
        self.v_diff = self._result(grid, 0, "經驗差")
        self.v_time = self._result(grid, 1, "花費時間")
        self.v_min = self._result(grid, 2, "每分鐘")
        self.v_hr = self._result(grid, 3, "每小時")
        self.v_lvl_total = self._result(grid, 4, "升級總時")
        self.v_lvl_left = self._result(grid, 5, "升級剩餘")
        v.addLayout(grid); v.addStretch(1)

        for le in (self.start_in, self.end_in, self.req_in):
            le.textChanged.connect(self.recalc)
        self.lv_in.textChanged.connect(self._on_level_changed)
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(200)
        self.recalc()

    def _on_level_changed(self, text):
        t = text.strip()
        try:
            lv = int(t)
        except ValueError:
            return
        if lv in EXP_TABLE:
            self.req_in.setText(f"{EXP_TABLE[lv]:,}")

    def _result(self, grid, row, label):
        lb = QLabel(label); lb.setObjectName("resLbl")
        val = QLabel("—"); val.setObjectName("resVal"); val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lb, row, 0); grid.addWidget(val, row, 1); grid.setColumnStretch(1, 1)
        return val

    @staticmethod
    def _parse(le):
        t = le.text().replace(",", "").replace(" ", "").strip()
        return int(t) if t and t.lstrip("-").isdigit() else None

    def _dur(self):
        return max(0, (self._parse(self.min_in) or 0) * 60 + (self._parse(self.sec_in) or 0))

    def _toggle(self):
        if self.running:
            # 暫停：記錄當下剩餘秒數
            self.remaining = max(0.0, self._deadline - time.perf_counter())
            self.running = False; self.start_btn.setText("繼續")
        else:
            if self.remaining <= 0:
                self.total = self._dur(); self.remaining = self.total
            if self.remaining > 0:
                self._deadline = time.perf_counter() + self.remaining
                self.running = True
            self.start_btn.setText("暫停" if self.running else "開始")
        self._refresh()

    def _reset(self):
        self.running = False; self.total = self._dur(); self.remaining = self.total
        self._deadline = 0.0
        self.start_btn.setText("開始"); self._refresh(); self.recalc()

    def _tick(self):
        if self.running:
            self.remaining = max(0.0, self._deadline - time.perf_counter())
            if self.remaining <= 0:
                self.remaining = 0.0; self.running = False; self.start_btn.setText("開始")
            self._refresh(); self.recalc()

    def _refresh(self):
        self.countdown.setText(mmss(self.remaining if self.total else self._dur()))

    def recalc(self):
        used = self.total - self.remaining
        self.v_time.setText(mmss(used))
        s, e = self._parse(self.start_in), self._parse(self.end_in)
        if s is None or e is None:
            for lbl in (self.v_diff, self.v_min, self.v_hr, self.v_lvl_total, self.v_lvl_left):
                lbl.setText("—")
            return
        diff = e - s
        self.v_diff.setText(fmt_int(diff))
        rate_min = diff / (used / 60) if used > 0 else None
        if rate_min:
            self.v_min.setText(fmt_int(rate_min)); self.v_hr.setText(fmt_int(rate_min * 60))
        else:
            self.v_min.setText("—"); self.v_hr.setText("—")
        req = self._parse(self.req_in)
        if req and req > 0 and rate_min and rate_min > 0:
            self.v_lvl_total.setText(fmt_minutes(req / rate_min))
            remain = req - e
            self.v_lvl_left.setText(fmt_minutes(remain / rate_min) if remain > 0 else "已達成")
        else:
            self.v_lvl_total.setText("—"); self.v_lvl_left.setText("—")


# =========================================================================
#  主視窗
# =========================================================================
class TimerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.cards = []; self.flows = []; self._drag = None
        self.bg_alpha = 207; self.block_alpha = 240; self.zoom = 1.0
        self.ruler_window = None
        self.ruler_base_val = 60
        self.ruler_hi_color = QColor(230, 60, 60)

        # 設定檔與按鍵綁定：{卡片id: {"vk": 虛擬鍵碼, "force": ⚡開關}}
        self.cfg = load_config()
        self.hotkeys = {}
        for k, v in (self.cfg.get("hotkeys") or {}).items():
            if not isinstance(k, str):
                continue
            k = k.replace("玩家::", "角色::", 1)                      # 舊版 id 遷移
            if isinstance(v, dict) and isinstance(v.get("vk"), int):
                self.hotkeys[k] = {"vk": v["vk"], "force": bool(v.get("force", False))}
            elif isinstance(v, str) and v in NAME_TO_VK:              # 舊版格式（按鍵名稱字串）
                self.hotkeys[k] = {"vk": NAME_TO_VK[v], "force": False}
        self.card_by_id = {}          # hotkey_id → 卡片
        self.cat_cards = []           # 每個 Boss 分類各自的卡片清單
        self.player_cards = []        # 角色技能卡
        self._vk_map = {}             # 虛擬鍵碼 → 卡片清單
        self._capture_card = None     # 正在等待使用者按鍵的卡片
        self._loading_cfg = False
        self.key_listener = GlobalKeyListener(self)
        self.key_listener.key_pressed.connect(self._on_global_key)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("楓星小工具")
        max_cards = max(len(c["skills"]) for c in CATEGORIES)
        default_w = min(70 + max_cards * (CARD_W + 12), 900)
        self.resize(max(560, default_w), 480)
        # 最小寬度≈2張卡片多一些（底部列會折行、不再撐寬）；最小高度足夠完整顯示練功頁
        self.base_min_h = 450
        self.setMinimumSize(300, self.base_min_h)

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame(); self.frame.setObjectName("root"); root.addWidget(self.frame)
        outer = QVBoxLayout(self.frame); outer.setContentsMargins(14, 8, 14, 10); outer.setSpacing(8)

        outer.addLayout(self._titlebar())
        outer.addWidget(self._boss_bar())
        outer.addWidget(self._ruler_settings())

        self.main_stack = QStackedWidget(); outer.addWidget(self.main_stack, 1)
        exp_scroll = QScrollArea(); exp_scroll.setWidgetResizable(True); exp_scroll.setObjectName("scroll")
        exp_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.calc_page = CalcPage(); exp_scroll.setWidget(self.calc_page)
        self.main_stack.addWidget(exp_scroll)                  # 0 = 練功（可捲動，字不會被吃）
        boss_page = QWidget()
        bv = QVBoxLayout(boss_page); bv.setContentsMargins(0, 0, 0, 0); bv.setSpacing(4)
        bv.addWidget(self._player_row())
        self.boss_stack = QStackedWidget()
        for cat in CATEGORIES:
            self.boss_stack.addWidget(self._category_page(cat))
        bv.addWidget(self.boss_stack, 1)
        self.main_stack.addWidget(boss_page)                   # 1 = 打Boss
        self.boss_combo.currentIndexChanged.connect(self.boss_stack.setCurrentIndex)

        outer.addWidget(self._bottombar())
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(TICK_MS)
        self._apply_styles(); self._push_block_alpha()

        # 套用已儲存的按鍵綁定並啟動全域監聽
        self._loading_cfg = True
        for cid, ent in self.hotkeys.items():
            card = self.card_by_id.get(cid)
            if card:
                card.set_hotkey_display(ent["vk"])
                if getattr(card, "force_btn", None) is not None:
                    card.force_btn.setChecked(ent.get("force", False))
        self._loading_cfg = False
        self._rebuild_vk_map()
        self.key_listener.start()

        self.set_mode("exp")   # 預設：練功經驗計算
        # 縮放握把固定在視窗右下角（永遠在最右）
        self.size_grip = QSizeGrip(self.frame); self.size_grip.setFixedSize(16, 16)
        self.size_grip.raise_(); self._place_grip()

    def _titlebar(self):
        bar = QHBoxLayout(); bar.setSpacing(6)
        self.handle = DragHandle(self, 30, 22)
        bar.addWidget(self.handle)
        self.mode_group = QButtonGroup(self); self.mode_group.setExclusive(True)
        self.exp_btn = QPushButton("練功"); self.exp_btn.setObjectName("modeTab")
        self.exp_btn.setToolTip("練功經驗計算")
        self.exp_btn.setCheckable(True); self.exp_btn.setCursor(Qt.PointingHandCursor)
        self.exp_btn.clicked.connect(lambda: self.set_mode("exp"))
        self.boss_btn = QPushButton("打Boss"); self.boss_btn.setObjectName("modeTab")
        self.boss_btn.setCheckable(True); self.boss_btn.setCursor(Qt.PointingHandCursor)
        self.boss_btn.clicked.connect(lambda: self.set_mode("boss"))
        self.mode_group.addButton(self.exp_btn); self.mode_group.addButton(self.boss_btn)
        bar.addWidget(self.exp_btn); bar.addWidget(self.boss_btn)
        bar.addStretch(1)
        self.pin_btn = QPushButton("📌"); self.pin_btn.setObjectName("toolBtn")
        self.pin_btn.setCheckable(True); self.pin_btn.setChecked(True)
        self.pin_btn.setToolTip("永遠置頂"); self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.clicked.connect(self._toggle_pin); bar.addWidget(self.pin_btn)
        self.min_btn = QPushButton("—"); self.min_btn.setObjectName("toolBtn")
        self.min_btn.setCursor(Qt.PointingHandCursor); self.min_btn.clicked.connect(self.showMinimized)
        bar.addWidget(self.min_btn)
        self.mclose = QPushButton("✕"); self.mclose.setObjectName("closeBtn")
        self.mclose.setCursor(Qt.PointingHandCursor); self.mclose.clicked.connect(self.close)
        bar.addWidget(self.mclose)
        return bar

    def _boss_bar(self):
        f = QFrame(); f.setObjectName("bossBar")
        h = QHBoxLayout(f); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        self.boss_combo = QComboBox(); self.boss_combo.setObjectName("bossCombo")
        self.boss_combo.setCursor(Qt.PointingHandCursor)
        for cat in CATEGORIES:
            self.boss_combo.addItem(cat["name"])
        h.addWidget(self.boss_combo, 1)
        self.player_btn = QPushButton("⚔ 角色"); self.player_btn.setObjectName("toolTab")
        self.player_btn.setCheckable(True); self.player_btn.setCursor(Qt.PointingHandCursor)
        self.player_btn.setToolTip("顯示/隱藏角色技能/狀態卡（例：劍士魔法消除、藥水CD）")
        self.player_btn.setChecked(bool(self.cfg.get("show_player_skills", True)))
        self.player_btn.toggled.connect(self._toggle_player)
        h.addWidget(self.player_btn, 0)
        self.ruler_btn = QPushButton("📏 血量刻度"); self.ruler_btn.setObjectName("toolTab")
        self.ruler_btn.setCheckable(True); self.ruler_btn.setCursor(Qt.PointingHandCursor)
        self.ruler_btn.setToolTip("彈出 Boss 血量刻度浮窗（可拖到血條上）")
        self.ruler_btn.toggled.connect(self._toggle_ruler)
        h.addWidget(self.ruler_btn, 0)
        self.boss_bar = f
        return f

    def _ruler_settings(self):
        f = QFrame(); f.setObjectName("rulerSet")
        flow = FlowLayout(f, margin=6, hspacing=8, vspacing=4)
        sp = f.sizePolicy(); sp.setHeightForWidth(True); sp.setVerticalPolicy(QSizePolicy.Minimum)
        f.setSizePolicy(sp)

        lab = QLabel("刻度表"); lab.setObjectName("dim"); flow.addWidget(lab)

        baw = QWidget(); al = QHBoxLayout(baw); al.setContentsMargins(0, 0, 0, 0); al.setSpacing(6)
        al.addWidget(self._mini("底色"))
        self.rbase = QSlider(Qt.Horizontal); self.rbase.setRange(0, 100); self.rbase.setValue(self.ruler_base_val)
        self.rbase.setFixedWidth(90); self.rbase.setToolTip("刻度表底色透明度（拉低可透出血條）")
        self.rbase.valueChanged.connect(self._on_rbase)
        al.addWidget(self.rbase)
        flow.addWidget(baw)

        cw = QWidget(); cl = QHBoxLayout(cw); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(6)
        cl.addWidget(self._mini("刻度色"))
        self.rswatch = QLabel(); self.rswatch.setFixedSize(18, 18); cl.addWidget(self.rswatch)
        self.rcolor = QPushButton("選色"); self.rcolor.setObjectName("toolPill")
        self.rcolor.setCursor(Qt.PointingHandCursor); self.rcolor.clicked.connect(self._on_rcolor)
        cl.addWidget(self.rcolor)
        self.rclear = QPushButton("清除標記"); self.rclear.setObjectName("toolPill")
        self.rclear.setCursor(Qt.PointingHandCursor); self.rclear.clicked.connect(self._on_rclear)
        cl.addWidget(self.rclear)
        flow.addWidget(cw)

        self.ruler_set = f
        f.setVisible(False)
        self._paint_rswatch()
        return f

    def _mini(self, t):
        l = QLabel(t); l.setObjectName("dim"); return l

    def _sep(self):
        s = QFrame(); s.setFixedWidth(1); s.setObjectName("vsep"); return s

    def _paint_rswatch(self):
        c = self.ruler_hi_color
        self.rswatch.setStyleSheet(f"background:{c.name()}; border-radius:4px; border:1px solid rgba(255,255,255,70);")

    def _player_row(self):
        """角色技能/狀態卡（打Boss模式常駐顯示在 Boss 卡片上方，可用 ⚔ 按鈕收合）"""
        wrap = QWidget()
        flow = FlowLayout(wrap, margin=0, hspacing=12, vspacing=12, center=True, hfw=False)
        # 不用 heightForWidth：否則 QStackedWidget 會把「練功頁」的整頁高度也算進最小高度，
        # 一開角色列視窗最小高度就爆增（下方留一大片空白）。改成依目前寬度自己算固定高度。
        sp = wrap.sizePolicy(); sp.setHeightForWidth(False); sp.setVerticalPolicy(QSizePolicy.Fixed)
        wrap.setSizePolicy(sp)
        for sk in PLAYER_SKILLS:
            card = RingCard(sk["name"], sk["cd"])
            card.name_lbl.setObjectName("playerSkillName")   # 藍色標題，與 BOSS 技能區別
            card.hotkey_id = f"角色::{sk['name']}"
            self.card_by_id[card.hotkey_id] = card
            self._wire_card(card)
            self.cards.append(card); self.player_cards.append(card)
            flow.addWidget(card)
        self.flows.append(flow)
        self.player_wrap = wrap
        wrap.setFixedHeight(flow.heightForWidth(max(60, self.width() - 28)))
        wrap.setVisible(self.player_btn.isChecked())
        return wrap

    def _sync_player_height(self):
        """角色卡列高度依目前寬度重算（窄到需要折行時才變高，不會撐大最小高度）"""
        wrap = getattr(self, "player_wrap", None)
        if wrap is None:
            return
        avail = max(60, self.width() - 28)      # 扣掉外框左右邊界（14+14）
        h = wrap.layout().heightForWidth(avail)
        if h <= 0:
            return
        if wrap.minimumHeight() != h:
            wrap.setFixedHeight(h)
        # 只有真的折行（視窗太窄／卡片放很大）時才往上加最小高度，避免卡片被切掉
        extra = max(0, h - int(CARD_H * self.zoom)) if wrap.isVisible() else 0
        want = self.base_min_h + extra
        if self.minimumHeight() != want:
            self.setMinimumHeight(want)
            if self.height() < want:
                self.resize(self.width(), want)

    def _category_page(self, cat):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setObjectName("scroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget(); flow = FlowLayout(page, 2, 12, 12, center=True)
        cat_list = []
        for sk in cat["skills"]:
            if sk.get("type") == "counter":
                card = CounterCard(sk["name"], sk.get("count", 1))
            else:
                card = RingCard(sk["name"], sk["cd"])
            card.hotkey_id = f"{cat['name']}::{sk['name']}"
            self.card_by_id[card.hotkey_id] = card
            self._wire_card(card)
            self.cards.append(card); cat_list.append(card); flow.addWidget(card)
        self.cat_cards.append(cat_list)
        self.flows.append(flow); scroll.setWidget(page)
        return scroll

    def _bottombar(self):
        # 用可折行的流式排版：視窗變窄時控制列自動折成兩排，不會撐寬視窗
        wrap = QWidget()
        flow = FlowLayout(wrap, margin=0, hspacing=10, vspacing=4)
        sp = wrap.sizePolicy(); sp.setHeightForWidth(True); sp.setVerticalPolicy(QSizePolicy.Minimum)
        wrap.setSizePolicy(sp)

        self.reset_all_btn = QPushButton("全部重置"); self.reset_all_btn.setObjectName("resetAll")
        self.reset_all_btn.setCursor(Qt.PointingHandCursor); self.reset_all_btn.clicked.connect(self.reset_all)
        flow.addWidget(self.reset_all_btn)

        zoomw = QWidget(); zl = QHBoxLayout(zoomw); zl.setContentsMargins(0, 0, 0, 0); zl.setSpacing(4)
        zlbl = QLabel("卡片"); zlbl.setObjectName("dim")
        self.zoom_out = QPushButton("－"); self.zoom_out.setObjectName("toolBtn")
        self.zoom_out.setFixedSize(24, 24); self.zoom_out.setCursor(Qt.PointingHandCursor)
        self.zoom_out.setToolTip("縮小卡片"); self.zoom_out.clicked.connect(lambda: self.set_zoom(self.zoom - 0.1))
        self.zoom_lbl = QLabel("100%"); self.zoom_lbl.setObjectName("dim"); self.zoom_lbl.setFixedWidth(38)
        self.zoom_lbl.setAlignment(Qt.AlignCenter)
        self.zoom_in = QPushButton("＋"); self.zoom_in.setObjectName("toolBtn")
        self.zoom_in.setFixedSize(24, 24); self.zoom_in.setCursor(Qt.PointingHandCursor)
        self.zoom_in.setToolTip("放大卡片"); self.zoom_in.clicked.connect(lambda: self.set_zoom(self.zoom + 0.1))
        zl.addWidget(zlbl); zl.addWidget(self.zoom_out); zl.addWidget(self.zoom_lbl); zl.addWidget(self.zoom_in)
        flow.addWidget(zoomw)

        bgw = QWidget(); bl = QHBoxLayout(bgw); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(5)
        b1 = QLabel("背景"); b1.setObjectName("dim")
        self.bg_slider = QSlider(Qt.Horizontal); self.bg_slider.setRange(0, 100); self.bg_slider.setValue(88)
        self.bg_slider.setFixedWidth(58); self.bg_slider.setToolTip("背景透明度（可到全透明；透明時用左上握把移動）")
        self.bg_slider.valueChanged.connect(self._on_bg)
        bl.addWidget(b1); bl.addWidget(self.bg_slider)
        flow.addWidget(bgw)

        bkw = QWidget(); kl = QHBoxLayout(bkw); kl.setContentsMargins(0, 0, 0, 0); kl.setSpacing(5)
        k1 = QLabel("方塊"); k1.setObjectName("dim")
        self.block_slider = QSlider(Qt.Horizontal); self.block_slider.setRange(40, 100); self.block_slider.setValue(94)
        self.block_slider.setFixedWidth(58); self.block_slider.setToolTip("方塊透明度（最低 40%）")
        self.block_slider.valueChanged.connect(self._on_block)
        kl.addWidget(k1); kl.addWidget(self.block_slider)
        flow.addWidget(bkw)

        # 練功模式隱藏這些（卡片縮放 / 全部重置在練功頁用不到）
        self._boss_only_bottom = [self.reset_all_btn, zoomw]
        return wrap

    # ---------- 模式切換 ----------
    def set_mode(self, mode):
        self.mode = mode
        is_boss = (mode == "boss")
        self.main_stack.setCurrentIndex(1 if is_boss else 0)
        self.boss_bar.setVisible(is_boss)
        self.exp_btn.setChecked(not is_boss); self.boss_btn.setChecked(is_boss)
        for w in self._boss_only_bottom:
            w.setVisible(is_boss)
        self._sync_panels()

    def _sync_panels(self):
        is_boss = getattr(self, "mode", "exp") == "boss"
        self._set_panel_visible(self.ruler_set, is_boss and self.ruler_btn.isChecked())

    def _set_panel_visible(self, panel, show):
        # 顯示/隱藏設定列時，讓視窗高度隨之增減，避免壓縮到卡片區
        if show == panel.isVisible():
            return
        delta = self._panel_height(panel)
        if show:
            panel.setVisible(True)
            self.resize(self.width(), self.height() + delta)
        else:
            panel.setVisible(False)
            self.resize(self.width(), max(self.minimumHeight(), self.height() - delta))

    def _panel_height(self, panel):
        cw = max(60, self.width() - 28)      # 扣掉外層左右邊界
        return panel.layout().heightForWidth(cw) + 8   # +外層 spacing

    # ---------- 按鍵偵測 ----------
    def _wire_card(self, card):
        """接上卡片的「按鍵配置」鈕（左鍵＝設定、右鍵＝清除）與 ⚡ 開關"""
        card.key_btn.clicked.connect(lambda _=False, c=card: self._begin_capture(c))
        card.key_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        card.key_btn.customContextMenuRequested.connect(lambda _pos, c=card: self._clear_hotkey(c))
        if getattr(card, "force_btn", None) is not None:
            card.force_btn.toggled.connect(lambda on, c=card: self._on_force_toggled(c, on))

    def _begin_capture(self, card):
        if self._capture_card is card:      # 再點一次＝取消設定
            self._end_capture(); return
        self._end_capture()
        self._capture_card = card
        card.key_btn.setText("按任意鍵…")
        self.key_listener.start()

    def _end_capture(self):
        card, self._capture_card = self._capture_card, None
        if card is not None:
            card.set_hotkey_display(card.hotkey_vk)   # 還原顯示

    def _assign_hotkey(self, card, vk):
        # 一個按鍵只綁一張卡：解除其他卡上的相同按鍵
        for other_id in [k for k, e in self.hotkeys.items() if e["vk"] == vk and k != card.hotkey_id]:
            self.hotkeys.pop(other_id)
            other = self.card_by_id.get(other_id)
            if other:
                other.set_hotkey_display(None)
        force = getattr(card, "force_btn", None) is not None and card.force_btn.isChecked()
        self.hotkeys[card.hotkey_id] = {"vk": vk, "force": force}
        card.set_hotkey_display(vk)
        self._rebuild_vk_map(); self._save_config()

    def _clear_hotkey(self, card):
        if self._capture_card is card:
            self._end_capture()
        if card.hotkey_id in self.hotkeys:
            self.hotkeys.pop(card.hotkey_id)
            self._rebuild_vk_map(); self._save_config()
        card.set_hotkey_display(None)

    def _on_force_toggled(self, card, on):
        if self._loading_cfg:
            return
        ent = self.hotkeys.get(card.hotkey_id)
        if ent is not None:
            ent["force"] = bool(on)
            self._save_config()

    def _rebuild_vk_map(self):
        self._vk_map = {}
        for cid, ent in self.hotkeys.items():
            card = self.card_by_id.get(cid)
            if card:
                self._vk_map.setdefault(ent["vk"], []).append(card)

    def _on_global_key(self, vk):
        if self._capture_card is not None:   # 設定模式：這次按鍵拿來綁定
            card = self._capture_card
            self._end_capture()
            if vk != VK_ESC:                 # Esc＝取消設定
                self._assign_hotkey(card, vk)
            return
        cards = self._vk_map.get(vk)
        if not cards:
            return
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QComboBox)):
            return   # 正在本程式的輸入框/下拉選單打字時不觸發
        for card in cards:
            card.hotkey_activate()

    def _toggle_player(self, on):
        self.player_wrap.setVisible(on)
        self._sync_player_height()
        self.cfg["show_player_skills"] = bool(on)
        self._save_config()

    def _save_config(self):
        self.cfg["hotkeys"] = self.hotkeys
        save_config(self.cfg)

    def _place_grip(self):
        if hasattr(self, "size_grip"):
            self.size_grip.move(self.width() - self.size_grip.width() - 7,
                                self.height() - self.size_grip.height() - 7)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_grip()
        self._sync_player_height()

    # ---------- 尺規視窗 + 設定 ----------
    def _ralpha(self):
        return int(self.ruler_base_val / 100 * 230)

    def _toggle_ruler(self, on):
        if on:
            if self.ruler_window is None:
                self.ruler_window = RulerWindow(self._ralpha(), QColor(self.ruler_hi_color))
                self.ruler_window.closed.connect(lambda: self.ruler_btn.setChecked(False))
            else:
                self.ruler_window.ruler.set_base_alpha(self._ralpha())
                self.ruler_window.ruler.hi_color = QColor(self.ruler_hi_color)
            self._sync_panels()   # 先讓設定列出現、主視窗長高
            # 再放到「長高後」主視窗的下方，避免遮到透明度那一排
            self.ruler_window.move(self.x(), self.y() + self.height() + 16)
            self.ruler_window.show(); self.ruler_window.raise_()
            keep_logical_size(self.ruler_window)
        else:
            if self.ruler_window is not None:
                self.ruler_window.hide()
            self._sync_panels()

    def _on_rbase(self, v):
        self.ruler_base_val = v
        if self.ruler_window is not None:
            self.ruler_window.ruler.set_base_alpha(self._ralpha())

    def _on_rcolor(self):
        c = QColorDialog.getColor(self.ruler_hi_color, self, "選擇刻度表標記顏色")
        if c.isValid():
            self.ruler_hi_color = c; self._paint_rswatch()
            if self.ruler_window is not None:
                self.ruler_window.ruler.hi_color = QColor(c); self.ruler_window.ruler.update()

    def _on_rclear(self):
        if self.ruler_window is not None:
            self.ruler_window.ruler.marked.clear(); self.ruler_window.ruler.update()

    # ---------- 行為 ----------
    def set_zoom(self, z):
        self.zoom = max(0.7, min(1.7, round(z, 2)))
        for c in self.cards:
            c.apply_zoom(self.zoom)
        for f in self.flows:
            f.invalidate()
        self._sync_player_height()
        self.zoom_lbl.setText(f"{int(self.zoom * 100)}%")

    def _on_bg(self, v):
        self.bg_alpha = int(v / 100 * 235); self._apply_styles()

    def _on_block(self, v):
        self.block_alpha = int(v / 100 * 255); self._apply_styles(); self._push_block_alpha()

    def _push_block_alpha(self):
        for c in self.cards:
            c.set_block_alpha(self.block_alpha)

    def _tick(self):
        dt = TICK_MS / 1000.0
        for c in self.cards:
            c.tick(dt)

    def reset_all(self):
        for c in self.cards:
            c.reset()

    def _toggle_pin(self):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.pin_btn.isChecked()); self.show()

    def closeEvent(self, e):
        if self.ruler_window is not None:
            self.ruler_window.close()
        super().closeEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.position().y() < 40:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def _apply_styles(self):
        a = self.block_alpha
        ctrl = f"rgba({CTRL_RGB[0]},{CTRL_RGB[1]},{CTRL_RGB[2]},{a})"
        ctrl_h = f"rgba({min(CTRL_RGB[0]+16,255)},{min(CTRL_RGB[1]+16,255)},{min(CTRL_RGB[2]+16,255)},{a})"
        border = f"rgba(255,255,255,{int(0.12*a)})"
        rootbg = f"rgba({ROOT_RGB[0]},{ROOT_RGB[1]},{ROOT_RGB[2]},{self.bg_alpha})"
        self.setStyleSheet(f"""
        #root {{ background:{rootbg}; border-radius:18px;
                 border:1px solid rgba(255,255,255,{int(0.10*max(self.bg_alpha,60))}); }}
        #title {{ color:#eef0f5; font-size:15px; font-weight:bold; font-family:"Microsoft JhengHei"; }}
        #dim {{ color:#969caa; font-size:11px; font-family:"Microsoft JhengHei"; }}
        #vsep {{ background: rgba(255,255,255,40); }}
        #bossBar {{ background: transparent; }}
        #rulerSet {{ background: rgba(91,155,255,28); border:1px solid rgba(91,155,255,90); border-radius:10px; }}
        QLabel#skillName {{ color:rgb(241,201,74); background:transparent; }}
        QLabel#playerSkillName {{ color:#5b9bff; background:transparent; }}

        #keyBtn {{ background:rgba(91,155,255,36); color:#9dc1ff; border:1px solid rgba(91,155,255,90);
                border-radius:6px; padding:0 4px; }}
        #keyBtn:hover {{ background:rgba(91,155,255,70); color:#dfe9ff; }}
        #forceBtn {{ background:{ctrl}; color:#dfe3ea; border:none; border-radius:6px; padding:0; }}
        #forceBtn:hover {{ background:{ctrl_h}; }}
        #forceBtn:checked {{ background:#ffc454; color:#1a1206; }}

        #modeTab {{ background:{ctrl}; color:#b9bfcc; border:none; border-radius:11px;
                padding:5px 13px; font-size:13px; font-weight:bold; font-family:"Microsoft JhengHei"; }}
        #modeTab:hover {{ background:{ctrl_h}; color:#eef0f5; }}
        #modeTab:checked {{ background:{ACCENT}; color:#0c1a14; }}
        #bossCombo {{ background:{ctrl}; color:#eef0f5; border:1px solid {border}; border-radius:10px;
                padding:5px 12px; font-size:14px; font-weight:bold; font-family:"Microsoft JhengHei"; }}
        #bossCombo:hover {{ background:{ctrl_h}; }}
        #bossCombo::drop-down {{ border:none; width:20px; }}
        QComboBox QAbstractItemView {{ background:rgb(30,33,42); color:#eef0f5;
                selection-background-color:{ACCENT}; selection-color:#0c1a14;
                border:1px solid rgba(255,255,255,45); outline:none; padding:2px; }}

        #toolBtn, #closeBtn {{ background:{ctrl}; color:#dfe3ea; border:none; border-radius:7px;
                 font-size:13px; min-width:24px; min-height:24px; }}
        #toolBtn:hover {{ background:{ctrl_h}; }}
        #toolBtn:checked {{ background:{ACCENT}; color:#0c1a14; }}
        #closeBtn:hover {{ background:#ff5757; color:white; }}
        #loopBtn, #resetBtn {{ background:{ctrl}; color:#dfe3ea; border:none; border-radius:6px; padding:0; }}
        #loopBtn:hover, #resetBtn:hover {{ background:{ctrl_h}; }}
        #loopBtn:checked {{ background:{ACCENT}; color:#0c1a14; }}

        #tab, #toolTab {{ background:{ctrl}; color:#b9bfcc; border:none; border-radius:13px;
                padding:6px 13px; font-size:12px; font-family:"Microsoft JhengHei"; font-weight:bold; }}
        #tab:hover, #toolTab:hover {{ background:{ctrl_h}; color:#eef0f5; }}
        #tab:checked {{ background:{ACCENT}; color:#0c1a14; }}
        #toolTab:checked {{ background:#5b9bff; color:#04101f; }}

        #secInput {{ background:rgba(0,0,0,90); color:#eef0f5; border:1px solid {border};
                     border-radius:6px; padding:0 4px; }}
        #secInput:focus {{ border:1px solid {ACCENT}; }}

        #resetAll, #toolPill {{ background:{ctrl}; color:#dfe3ea; border:none; border-radius:9px;
                     padding:5px 12px; font-size:12px; font-family:"Microsoft JhengHei"; font-weight:bold; }}
        #resetAll:hover {{ background:#ff5757; color:white; }}
        #toolPill:hover {{ background:{ctrl_h}; }}

        #formLbl {{ color:#c7ccd8; font-size:13px; font-family:"Microsoft JhengHei"; }}
        #expInput, #timeInput {{ background:rgba(0,0,0,90); color:#eef0f5; border:1px solid {border};
                     border-radius:7px; padding:5px 8px; font-size:14px; }}
        #expInput:focus, #timeInput:focus {{ border:1px solid {ACCENT}; }}
        #goBtn {{ background:{ACCENT}; color:#08130e; border:none; border-radius:9px; padding:5px 16px;
                  font-size:13px; font-weight:bold; font-family:"Microsoft JhengHei"; }}
        #countdown {{ color:#eef0f5; font-size:34px; font-weight:bold; font-family:"Consolas","Arial"; }}
        #resLbl {{ color:#969caa; font-size:13px; font-family:"Microsoft JhengHei"; }}
        #resVal {{ color:{ACCENT}; font-size:15px; font-weight:bold; font-family:"Consolas","Arial"; }}

        QScrollArea#scroll {{ background:transparent; border:none; }}
        QScrollArea#scroll > QWidget > QWidget {{ background:transparent; }}
        QScrollBar:vertical {{ background:transparent; width:8px; margin:2px; }}
        QScrollBar::handle:vertical {{ background:rgba(255,255,255,50); border-radius:4px; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
        """)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("楓星小工具")
    app.setFont(QFont("Microsoft JhengHei", 10))
    w = TimerWindow(); w.show()
    keep_logical_size(w)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
