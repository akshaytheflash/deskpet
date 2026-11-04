#!/usr/bin/env python3
"""
Pip - a very small pixel desk pet.

One file, no Electron. Frames are drawn as a 32x32 pixel grid and upscaled with
nearest-neighbour, so the art stays crisp and costs almost nothing. It walks the
bottom of the screen on its own, looks around, hops, and naps when you leave it
alone.

    pythonw deskpet.py            run it
    python  deskpet.py --preview  render a contact sheet instead of opening

Microinteractions
    walking with alternating feet, idle bob, blinking (and double blinks),
    pupils that follow the cursor, a pulsing antenna, hover-perk, click to hop,
    double-click for a bigger hop with hearts, drag to pick up, throw it at a
    wall and it fires a web and sticks there, drop it from a height and a
    parachute opens, squash landing, dozes off after a minute of no attention.
    Five synthesised sounds (no asset files), mutable from the right-click menu.
"""

import ctypes
import io
import json
import math
import os
import random
import struct
import sys
import time
import tkinter as tk
import wave

from PIL import Image, ImageDraw, ImageTk

try:
    import winsound
except ImportError:             # non-Windows: stay silent, keep working
    winsound = None

# ---------------------------------------------------------------- appearance

GRID = 32                       # pixel-art grid, 32x32
HEAD = 14                       # rows above the sprite: hops, parachute, web
KEY = "#0a0a0a"
KEY_RGB = (10, 10, 10)

BODY = (233, 138, 95)
BODY_DARK = (206, 113, 74)
BODY_LIGHT = (245, 165, 122)
LINE = (48, 35, 31)
WHITE = (255, 249, 240)
EYE = (44, 34, 30)
BLUSH = (242, 154, 142)
ACCENT = (255, 200, 110)
ACCENT_HI = (255, 240, 190)
ZED = (150, 158, 176)
HEART = (231, 96, 108)
SILK = (172, 180, 194)


# ---------------------------------------------------------------- art

def _flatten(img):
    bg = Image.new("RGB", img.size, KEY_RGB)
    bg.paste(img, (0, 0), img)
    return bg


def render_sprite(gaze=(0, 0), eyes="open", mouth="smile", bob=0, step=0,
                  lift=0, glow=0, chute=False, web=None, sway=0, ui=1.0):
    """One 32x32 pixel-art frame, upscaled. Returns an RGB image on the key."""
    p = max(3, int(round(3.2 * ui)))
    w, h = GRID * p, (GRID + HEAD) * p
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    oy = HEAD - bob - lift

    def R(x0, y0, x1, y1):
        return [x0 * p, (y0 + oy) * p, (x1 + 1) * p - 1, (y1 + 1 + oy) * p - 1]

    def rect(x0, y0, x1, y1, fill):
        d.rectangle(R(x0, y0, x1, y1), fill=fill)

    def rrect(x0, y0, x1, y1, r, fill):
        d.rounded_rectangle(R(x0, y0, x1, y1), radius=r * p, fill=fill)

    def shape(x0, y0, x1, y1, r, fill):
        """Filled rounded box with an exact one-pixel outline."""
        rrect(x0 - 1, y0 - 1, x1 + 1, y1 + 1, r + 1, LINE)
        rrect(x0, y0, x1, y1, r, fill)

    # parachute: canopy sits above the sprite, strings run down to the shoulders
    if chute:
        cx0 = 4 + sway
        d.pieslice([(cx0 - 1) * p, (-14 + oy) * p, (cx0 + 24) * p, (-2 + oy) * p],
                   180, 360, fill=LINE)
        d.pieslice([cx0 * p, (-13 + oy) * p, (cx0 + 23) * p, (-3 + oy) * p],
                   180, 360, fill=ACCENT)
        d.pieslice([(cx0 + 3) * p, (-12 + oy) * p, (cx0 + 11) * p, (-4 + oy) * p],
                   180, 360, fill=BODY)
        d.pieslice([(cx0 + 12) * p, (-12 + oy) * p, (cx0 + 20) * p, (-4 + oy) * p],
                   180, 360, fill=BODY)
        d.line([((cx0 + 2) * p, (-3 + oy) * p), (11 * p, (9 + oy) * p)],
               fill=SILK, width=max(1, p // 2))
        d.line([((cx0 + 21) * p, (-3 + oy) * p), (21 * p, (9 + oy) * p)],
               fill=SILK, width=max(1, p // 2))

    # web, when it is stuck to a wall
    if web:
        lw = max(1, int(round(0.8 * p)))
        if web == "top":
            for sx in (9, 13, 19, 23):
                d.line([(sx * p, 0), (16 * p, (8 + oy) * p)], fill=SILK, width=lw)
            d.ellipse([(14 * p, (7 + oy) * p), (18 * p, (11 + oy) * p)], fill=SILK)
        elif web == "left":
            for sy in (16, 21, 26, 31):
                d.line([(0, (sy + oy) * p), (6 * p, (23 + oy) * p)], fill=SILK, width=lw)
            d.ellipse([(4 * p, (21 + oy) * p), (8 * p, (25 + oy) * p)], fill=SILK)
        elif web == "right":
            for sy in (16, 21, 26, 31):
                d.line([(w - 1, (sy + oy) * p), ((w // p - 6) * p, (23 + oy) * p)],
                       fill=SILK, width=lw)
            d.ellipse([((w // p - 8) * p, (21 + oy) * p), ((w // p - 4) * p, (25 + oy) * p)],
                      fill=SILK)

    # antenna
    rect(15, 4, 15, 10, LINE)
    bulb = ACCENT if glow != 1 else ACCENT_HI
    shape(13, 0, 17, 4, 2, bulb)

    # feet (alternate while walking)
    fl, fr = (1, 0) if step == 1 else ((0, 1) if step == 2 else (0, 0))
    shape(8, 28 + fl, 12, 30 + fl, 1, BODY_DARK)
    shape(19, 28 + fr, 23, 30 + fr, 1, BODY_DARK)

    # body + side arms
    shape(2, 19, 4, 23, 1, BODY_DARK)
    shape(27, 19, 29, 23, 1, BODY_DARK)
    shape(6, 9, 25, 27, 8, BODY)
    rect(9, 11, 22, 11, BODY_LIGHT)

    # cheeks
    rect(8, 20, 10, 21, BLUSH)
    rect(21, 20, 23, 21, BLUSH)

    # eyes
    lx, rx, ey = 10, 18, 14
    for ex in (lx, rx):
        if eyes == "open":
            rect(ex, ey, ex + 3, ey + 3, WHITE)
            px = ex + 1 + max(-1, min(1, gaze[0]))
            py = ey + 1 + max(-1, min(1, gaze[1]))
            rect(px, py, px + 1, py + 1, EYE)
        elif eyes == "wide":
            rect(ex - 1, ey - 1, ex + 4, ey + 4, WHITE)
            px = ex + 1 + max(-1, min(1, gaze[0]))
            py = ey + 1 + max(-1, min(1, gaze[1]))
            rect(px, py, px + 1, py + 1, EYE)
        elif eyes == "blink" or eyes == "sleep":
            rect(ex, ey + 2, ex + 3, ey + 2, EYE)
        elif eyes == "happy":
            rect(ex, ey + 2, ex, ey + 2, EYE)
            rect(ex + 1, ey + 1, ex + 2, ey + 1, EYE)
            rect(ex + 3, ey + 2, ex + 3, ey + 2, EYE)

    # mouth
    if mouth == "smile":
        rect(15, 21, 16, 21, LINE)
        rect(14, 20, 14, 20, LINE)
        rect(17, 20, 17, 20, LINE)
    elif mouth == "open":
        rect(15, 21, 16, 22, (120, 62, 56))
    elif mouth == "flat":
        rect(15, 21, 16, 21, LINE)

    return _flatten(img)


def _heart(px):
    w = max(6, int(px))
    img = Image.new("RGBA", (w * 4, w * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = w * 0.85
    d.ellipse((w * 0.4, w * 0.5, w * 0.4 + 2 * r, w * 0.5 + 2 * r), fill=HEART)
    d.ellipse((w * 2.1, w * 0.5, w * 2.1 + 2 * r, w * 0.5 + 2 * r), fill=HEART)
    d.polygon([(w * 0.3, w * 1.35), (w * 3.7, w * 1.35), (w * 2.0, w * 3.6)], fill=HEART)
    return _flatten(img.resize((w, w), Image.LANCZOS))


def _zed(px):
    w = max(8, int(px))
    img = Image.new("RGBA", (w * 4, w * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(2, int(w * 0.18))
    pts = [(w * 0.7, w * 0.7), (w * 2.3, w * 0.7), (w * 0.7, w * 2.7), (w * 2.3, w * 2.7)]
    d.line(pts, fill=ZED, width=lw, joint="curve")
    return _flatten(img.resize((w, w), Image.LANCZOS))


# ---------------------------------------------------------------- sound

RATE = 22050


def _wav(samples):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767))))
                               for s in samples))
    return buf.getvalue()


def _env(i, n, attack=0.02, release=0.45):
    t = i / max(1, n - 1)
    a = min(1.0, t / attack) if attack > 0 else 1.0
    r = min(1.0, (1.0 - t) / release) if release > 0 else 1.0
    return a * r


def _sweep(f0, f1, dur, vol=0.2, kind="sine"):
    n = int(dur * RATE)
    out = []
    phase = 0.0
    for i in range(n):
        f = f0 + (f1 - f0) * (i / max(1, n - 1))
        phase += 2.0 * math.pi * f / RATE
        s = math.sin(phase)
        if kind == "tri":
            s = 2.0 / math.pi * math.asin(max(-1.0, min(1.0, s)))
        out.append(s * _env(i, n) * vol)
    return _wav(out)


def _hiss(dur, vol=0.14, smooth=0.2, rise=0.0):
    n = int(dur * RATE)
    out = []
    prev = 0.0
    for i in range(n):
        prev = prev * (1.0 - smooth) + random.uniform(-1.0, 1.0) * smooth
        e = _env(i, n, 0.01, 0.55)
        if rise:
            e *= min(1.0, i / max(1, int(rise * RATE)))
        out.append(prev * e * vol)
    return _wav(out)


def build_sounds():
    """Four tiny synthesised wavs, held in memory. No asset files."""
    return {
        "hop":   _sweep(520, 900, 0.09, 0.16),
        "land":  _sweep(320, 150, 0.12, 0.16, "tri"),
        "thwip": _hiss(0.12, 0.22, 0.5),
        "chute": _hiss(0.30, 0.12, 0.10, rise=0.05),
        "boing": _sweep(240, 620, 0.16, 0.14, "tri"),
    }


# ---------------------------------------------------------------- platform

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def work_area():
    r = RECT()
    try:
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0)
        if r.right > r.left and r.bottom > r.top:
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return 0, 0, 1536, 864


def state_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "PipDeskPet", "state.json")


# ---------------------------------------------------------------- the pet

class Pet:
    def __init__(self, root):
        self.root = root
        self.ui = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.p = max(3, int(round(3.2 * self.ui)))
        self.cw = GRID * self.p
        self.ch = (GRID + HEAD) * self.p

        self.wa = work_area()
        st = self._load_state()

        x = max(self.wa[0] + 2, min(st.get("x", self.wa[2] - self.cw - 60),
                                    self.wa[2] - self.cw - 2))
        y = self.wa[3] - self.ch + 2

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", KEY)
        root.configure(bg=KEY)
        root.geometry(f"{self.cw}x{self.ch}+{x}+{y}")

        self.canvas = tk.Canvas(root, width=self.cw, height=self.ch, bg=KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack()

        self.cache = {}
        self.part_cache = {}
        self.current = None
        self.particles = []

        self.gaze = (0, 0)
        self.eyes, self.mouth = "open", "smile"
        self.bob, self.step, self.lift, self.glow = 0, 0, 0, 0
        self.sway = 0
        self.chute, self.web = False, None
        self.pet_item = self.canvas.create_image(0, 0, anchor="nw",
                                                 image=self._img())

        now = time.time()
        self.mode = "idle"
        self.hover = False
        self.gaze = (0, 0)
        self.last_touch = now
        self.next_blink = now + random.uniform(2.0, 5.0)
        self.blink_until = 0.0
        self.double_blink = False

        self.next_think = now + 1.5
        self.next_look = now + 1.0
        self.look = (0, 0)
        self.dir = random.choice((-1, 1))
        self.walk_until = now
        self.step = 0
        self.walk_clock = 0.0
        self.wander = True

        self.hop_t0 = 0.0
        self.hop_power = 7
        self.hop_drift = 0.0

        self.drag_off = None
        self.press_at = (0, 0)
        self.moved = False
        self.last_click = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.track = []
        self.chute = False
        self.web = None
        self.stuck_at = 0.0
        self.land_t0 = 0.0
        self.zed_at = now

        self.muted = bool(st.get("muted", False))
        self.sounds = build_sounds()

        self.canvas.bind("<Enter>", self._enter)
        self.canvas.bind("<Leave>", self._leave)
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Button-3>", self._menu)

        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label="Nap", command=self._nap)
        self.menu.add_command(label="Wake up", command=self._wake)
        self.menu.add_separator()
        self.wander_var = tk.BooleanVar(value=True)
        self.menu.add_checkbutton(label="Wander on its own", variable=self.wander_var,
                                  command=self._toggle_wander)
        self.sound_var = tk.BooleanVar(value=not self.muted)
        self.menu.add_checkbutton(label="Sound", variable=self.sound_var,
                                  command=self._toggle_sound)
        self.menu.add_command(label="Reset position", command=self._reset_pos)
        self.menu.add_separator()
        self.menu.add_command(label="Quit", command=self.quit)

        self.last = time.time()
        self.root.after(50, self.tick)

    # ---------------------------------------------------------- helpers

    def _load_state(self):
        try:
            with open(state_path(), "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(state_path()), exist_ok=True)
            with open(state_path(), "w", encoding="utf-8") as fh:
                json.dump({"x": self.root.winfo_x(), "muted": self.muted}, fh)
        except Exception:
            pass

    def _move(self, x, y):
        self.root.geometry(f"+{int(x)}+{int(y)}")
        if os.environ.get("PIP_DEBUG"):
            try:
                path = os.path.join(os.environ.get("TEMP", "."), "opencode", "pip_dbg.log")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(f"{time.time():.3f} move {int(x)},{int(y)} mode={self.mode}\n")
            except Exception:
                pass

    def _img(self):
        k = (self.gaze, self.eyes, self.mouth, self.bob, self.step, self.lift,
             self.glow, self.chute, self.web, self.sway)
        photo = self.cache.get(k)
        if photo is None:
            if len(self.cache) > 90:
                self.cache.clear()
            img = render_sprite(gaze=k[0], eyes=k[1], mouth=k[2], bob=k[3],
                                step=k[4], lift=k[5], glow=k[6], chute=k[7],
                                web=k[8], sway=k[9], ui=self.ui)
            photo = ImageTk.PhotoImage(img)
            self.cache[k] = photo
        return photo

    def _play(self, name):
        if self.muted or winsound is None:
            return
        data = self.sounds.get(name)
        if not data:
            return
        try:
            winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_ASYNC
                               | winsound.SND_NODEFAULT)
        except Exception:
            pass

    def _toggle_sound(self):
        self.muted = not self.sound_var.get()
        self._save_state()

    # ---------------------------------------------------------- interaction

    def _enter(self, _e=None):
        self.hover = True
        self.last_touch = time.time()
        if self.mode == "sleep":
            self._wake()

    def _leave(self, _e=None):
        self.hover = False

    def _press(self, e):
        self.last_touch = time.time()
        if self.mode == "sleep":
            self._wake()
            return
        if self.mode == "stuck":
            # let go of the wall
            self.mode = "fall"
            self.web = None
            self.vy = 0.0
            self.vx = 0.0
            self._play("land")
            return
        self.press_at = (e.x_root, e.y_root)
        self.drag_off = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())
        self.moved = False
        self.track = [(time.time(), e.x_root, e.y_root)]

    def _motion(self, e):
        if self.drag_off is None:
            return
        if not self.moved and abs(e.x_root - self.press_at[0]) + abs(e.y_root - self.press_at[1]) < 5:
            return
        self.moved = True
        self.mode = "drag"
        self.chute, self.web = False, None
        self._move(e.x_root - self.drag_off[0], e.y_root - self.drag_off[1])
        self.track.append((time.time(), e.x_root, e.y_root))
        if len(self.track) > 8:
            self.track.pop(0)

    def _release(self, _e):
        if self.drag_off is None:
            return
        self.drag_off = None
        self.last_touch = time.time()
        if self.moved:
            now = time.time()
            self.web = None
            vx = vy = 0.0
            recent = [t for t in self.track if now - t[0] < 0.14]
            if len(recent) >= 2:
                t0, x0, y0 = recent[0]
                t1, x1, y1 = recent[-1]
                span = max(0.02, t1 - t0)
                vx = max(-3000, min(3000, (x1 - x0) / span))
                vy = max(-3000, min(3000, (y1 - y0) / span))
            speed = math.hypot(vx, vy)
            wy = self.root.winfo_y()
            floor_top = self.wa[3] - self.ch + 2
            height = floor_top - wy

            if speed > 850:
                self.mode = "throw"
                self.vx, self.vy = vx, vy
                self._play("boing")
            elif height > 150 * self.ui:
                self.mode = "chute"
                self.chute = True
                self.vx = vx * 0.15
                self.vy = 0.0
                self._play("chute")
            else:
                self.mode = "fall"
                self.vx = 0.0
                self.vy = 0.0
            self._save_state()
            return
        now = time.time()
        excited = now - self.last_click < 0.32
        self.last_click = now
        self.mode = "hop"
        self.hop_t0 = now
        self.hop_power = 9 if excited else 6
        self.hop_drift = 0.0
        self._play("hop")
        for _ in range(4 if excited else 2):
            self._spawn_heart()

    def _stick(self, side):
        self.mode = "stuck"
        self.web = side
        self.stuck_at = time.time()
        self.vx = self.vy = 0.0
        y = max(self.wa[1], min(self.root.winfo_y(), self.wa[3] - self.ch + 2))
        if side == "left":
            self._move(self.wa[0], y)
        elif side == "right":
            self._move(self.wa[2] - self.cw, y)
        else:
            self._move(self.root.winfo_x(), self.wa[1])
        self._play("thwip")

    def _menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def _nap(self):
        self.mode = "sleep"
        self.last_touch = time.time()

    def _wake(self):
        self.mode = "idle"
        self.last_touch = time.time()
        self.next_think = time.time() + 0.6
        self.next_blink = time.time() + random.uniform(1.5, 3.5)

    def _toggle_wander(self):
        self.wander = self.wander_var.get()
        if not self.wander and self.mode == "walk":
            self.mode = "idle"

    def _reset_pos(self):
        _l, _t, r, b = self.wa
        self.mode = "idle"
        self.chute, self.web = False, None
        self._move(r - self.cw - 60, b - self.ch + 2)

    # ---------------------------------------------------------- particles

    def _spawn_heart(self):
        self.particles.append({
            "kind": "heart", "x": self.cw * 0.5 + random.uniform(-22, 22),
            "y": self.ch * 0.55 + random.uniform(-8, 8),
            "vy": random.uniform(-46, -30), "vx": random.uniform(-10, 10),
            "life": 0.0, "ttl": 0.95, "item": None,
        })

    def _spawn_zed(self):
        self.particles.append({
            "kind": "zed", "x": self.cw * 0.68, "y": self.ch * 0.45,
            "vy": -20.0, "vx": 7.0, "life": 0.0, "ttl": 1.9, "item": None,
        })

    def _step_particles(self, dt):
        alive = []
        for q in self.particles:
            q["life"] += dt
            if q["life"] >= q["ttl"]:
                if q["item"] is not None:
                    self.canvas.delete(q["item"])
                continue
            q["x"] += q["vx"] * dt
            q["y"] += q["vy"] * dt
            q["vy"] *= 0.985
            frac = q["life"] / q["ttl"]
            size = (1.0 - 0.55 * frac) * (18 if q["kind"] == "heart" else 14) * self.ui
            bucket = max(6, int(round(size / 2.0)) * 2)
            ck = (q["kind"], bucket)
            photo = self.part_cache.get(ck)
            if photo is None:
                photo = ImageTk.PhotoImage(_heart(bucket) if q["kind"] == "heart" else _zed(bucket))
                self.part_cache[ck] = photo
            if q["item"] is None:
                q["item"] = self.canvas.create_image(q["x"], q["y"], image=photo, anchor="center")
            else:
                self.canvas.itemconfig(q["item"], image=photo)
                self.canvas.coords(q["item"], q["x"], q["y"])
            q["photo"] = photo
            alive.append(q)
        self.particles = alive

    # ---------------------------------------------------------- main loop

    def tick(self):
        now = time.time()
        dt = min(0.08, now - self.last)
        self.last = now

        ptr = self.root.winfo_pointerxy()
        wx, wy = self.root.winfo_x(), self.root.winfo_y()
        over = wx <= ptr[0] <= wx + self.cw and wy <= ptr[1] <= wy + self.ch
        if over:
            self.last_touch = now

        bob, step, lift, glow, sway = 0, 0, 0, 0, 0
        eyes, mouth = "open", "smile"

        if self.mode == "sleep":
            if now - self.zed_at > 1.05:
                self.zed_at = now
                self._spawn_zed()
            eyes, mouth = "sleep", "flat"
            bob = -1
            if over:
                self._wake()

        elif self.mode == "walk":
            speed = 34.0 * self.ui
            x = wx + self.dir * speed * dt
            lo, hi = self.wa[0] + 2, self.wa[2] - self.cw - 2
            if x <= lo:
                x = lo
                self.dir = 1
            elif x >= hi:
                x = hi
                self.dir = -1
            self._move(x, wy)
            self.walk_clock += dt * 7.0
            step = 1 if int(self.walk_clock) % 2 == 0 else 2
            bob = 0
            eyes = "open"
            if now >= self.walk_until:
                self.mode = "idle"
                self.next_think = now + random.uniform(0.7, 2.2)

        elif self.mode == "hop":
            t = (now - self.hop_t0) / 0.45
            if t >= 1.0:
                self.mode = "idle"
            else:
                lift = int(round(math.sin(math.pi * t) * self.hop_power))
                eyes, mouth = "happy", "open"
                bob = 0

        elif self.mode == "drag":
            eyes, mouth = "wide", "open"
            bob, step = -1, 0

        elif self.mode == "throw":
            self.vy += 2200 * dt
            nx = wx + self.vx * dt
            ny = wy + self.vy * dt
            left, top = self.wa[0], self.wa[1]
            right = self.wa[2] - self.cw
            floor_top = self.wa[3] - self.ch + 2
            if nx <= left:
                self._stick("left")
            elif nx >= right:
                self._stick("right")
            elif ny <= top:
                self._stick("top")
            elif ny >= floor_top:
                self._move(wx, floor_top)
                self.mode = "land"
                self.land_t0 = now
                self.vy = 0.0
                self.chute = False
                self.web = None
                self._play("land")
            else:
                self._move(nx, ny)
            eyes, mouth = "wide", "open"

        elif self.mode == "chute":
            self.vy = min(self.vy + 700 * dt, 110 * self.ui)
            self.vx *= 0.98
            nx = wx + (self.vx + math.sin(now * 1.7) * 26 * self.ui) * dt
            ny = wy + self.vy * dt
            floor_top = self.wa[3] - self.ch + 2
            if ny >= floor_top:
                self._move(wx, floor_top)
                self.mode = "land"
                self.land_t0 = now
                self.vy = 0.0
                self.chute = False
                self.web = None
                self._play("land")
            else:
                self._move(max(self.wa[0], min(nx, self.wa[2] - self.cw)), ny)
                sway = int(round(math.sin(now * 1.7)))
            eyes, mouth = "happy", "open"

        elif self.mode == "stuck":
            if now - self.stuck_at > 25:
                self.mode = "fall"
                self.web = None
                self.vy = 0.0
            else:
                lift = 1 if math.sin(now * 2.0) > 0 else 0
                eyes, mouth = "open", "smile"

        elif self.mode == "fall":
            self.vy += 2400 * dt
            ny = wy + self.vy * dt
            floor_top = self.wa[3] - self.ch + 2
            if ny >= floor_top:
                self._move(wx, floor_top)
                self.mode = "land"
                self.land_t0 = now
                self.vy = 0.0
                self.chute = False
                self.web = None
                self._play("land")
                eyes, mouth = "blink", "open"
                bob = -1
            else:
                self._move(wx, ny)
                eyes, mouth = "wide", "open"
                bob = 1

        elif self.mode == "land":
            t = (now - self.land_t0) / 0.22
            if t >= 1.0:
                self.mode = "idle"
            else:
                bob = -1 if t < 0.5 else 0
                eyes, mouth = "blink", "open"

        # idle: think, wander, blink, look about
        if self.mode == "idle":
            if now >= self.next_blink:
                self.blink_until = now + 0.13
                self.double_blink = random.random() < 0.22
                self.next_blink = now + random.uniform(3.0, 7.0)
            if self.double_blink and now > self.blink_until + 0.14:
                self.blink_until = now + 0.10
                self.double_blink = False

            bob = -1 if (math.sin(now * 1.4) > 0.72) else 0

            if now - self.last_touch > 60:
                self.mode = "sleep"
                self.zed_at = now
            elif now >= self.next_think and self.wander:
                self.next_think = now + random.uniform(1.6, 4.2)
                roll = random.random()
                if roll < 0.52:
                    self.mode = "walk"
                    self.dir = random.choice((-1, 1))
                    self.walk_until = now + random.uniform(1.1, 2.8)
                elif roll < 0.72:
                    self.mode = "hop"
                    self.hop_t0 = now
                    self.hop_power = random.choice((4, 5, 6))
                    self.hop_drift = 0.0
                else:
                    self.next_look = now + 0.1

        # gaze (steady while walking, it is already looking where it is going)
        if self.mode != "walk" and now >= self.next_look:
            self.next_look = now + random.uniform(0.8, 2.0)
            cxw, cyw = wx + self.cw * 0.5, wy + self.ch * 0.55
            dx, dy = ptr[0] - cxw, ptr[1] - cyw
            if math.hypot(dx, dy) < 260:
                self.look = (max(-1, min(1, int(dx / 90))), max(-1, min(1, int(dy / 90))))
            else:
                self.look = (random.choice((-1, 0, 1)), random.choice((-1, 0, 0)))
        self.gaze = self.look

        # blink overrides idle eyes
        if self.mode == "idle" and now < self.blink_until:
            eyes = "blink"

        glow = int(now / 0.9) % 3

        if self.mode == "sleep":
            eyes, mouth = "sleep", "flat"

        if os.environ.get("PIP_DEBUG") and getattr(self, "_pm", "") != self.mode:
            print(f"mode -> {self.mode} at {wx},{wy}")
            self._pm = self.mode

        self.eyes, self.mouth, self.bob, self.step, self.lift, self.glow = \
            eyes, mouth, bob, step, lift, glow
        self.sway = sway
        self.chute = self.mode == "chute"

        photo = self._img()
        if photo is not self.current:
            self.canvas.itemconfig(self.pet_item, image=photo)
            self.current = photo

        self._step_particles(dt)

        if self.mode in ("throw", "chute", "fall", "land", "drag") or self.particles:
            delay = 40
        elif self.mode in ("walk", "hop"):
            delay = 70
        else:
            delay = 110
        self.root.after(delay, self.tick)

    # ---------------------------------------------------------- lifecycle

    def quit(self):
        self._save_state()
        self.root.destroy()


def preview(path):
    states = [
        dict(eyes="open", mouth="smile", bob=0),
        dict(eyes="open", mouth="smile", bob=1),
        dict(eyes="blink", mouth="smile", bob=0),
        dict(eyes="happy", mouth="open", lift=5),
        dict(eyes="sleep", mouth="flat", bob=1),
        dict(eyes="open", mouth="smile", step=1, bob=1),
        dict(eyes="wide", mouth="open", bob=1),
        dict(eyes="happy", mouth="open", chute=True, sway=-1),
        dict(eyes="open", mouth="smile", web="left"),
        dict(eyes="open", mouth="smile", web="top"),
    ]
    p = 4
    tile_w, tile_h = GRID * p, (GRID + HEAD) * p
    pad = 8
    W = tile_w * len(states) + pad * 2
    H = tile_h * 2 + pad * 3
    sheet = Image.new("RGB", (W, H), (240, 240, 242))
    for row, bg in enumerate(((240, 240, 242), (30, 32, 36))):
        band = Image.new("RGB", (W, tile_h), bg)
        sheet.paste(band, (0, pad + row * (tile_h + pad)))
        for i, st in enumerate(states):
            frame = render_sprite(ui=1.0, **st)
            mask = Image.new("L", frame.size, 0)
            px = frame.load()
            mp = mask.load()
            for yy in range(frame.height):
                for xx in range(frame.width):
                    if px[xx, yy] != KEY_RGB:
                        mp[xx, yy] = 255
            sheet.paste(frame, (pad + i * tile_w, pad + row * (tile_h + pad)), mask)
    sheet.save(path)
    print("wrote", path)


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    if "--preview" in sys.argv:
        i = sys.argv.index("--preview")
        out = sys.argv[i + 1] if len(sys.argv) > i + 1 else "preview.png"
        preview(out)
        return

    root = tk.Tk()
    pet = Pet(root)

    if "--demo" in sys.argv:
        def throw_it():
            pet._move(320, pet.wa[1] + 160)
            root.after(80, start_throw)

        def start_throw():
            pet.mode = "throw"
            pet.vx, pet.vy = -1500.0, 0.0
            print("demo: thrown left")

        def report(tag):
            print(f"demo: {tag} mode={pet.mode} web={pet.web} chute={pet.chute} "
                  f"pos={pet.root.winfo_x()},{pet.root.winfo_y()}")

        def drop_high():
            pet.mode = "idle"
            pet._move(pet.wa[2] - pet.cw - 200, pet.wa[1] + 40)
            root.after(80, start_chute)

        def start_chute():
            pet.mode = "chute"
            pet.chute = True
            pet.vy = 0.0
            print("demo: dropped high")

        root.after(1200, throw_it)
        root.after(2600, lambda: report("after throw"))
        root.after(3000, drop_high)
        root.after(4200, lambda: report("after drop"))
        root.after(7000, pet.quit)

    for arg in sys.argv:
        if arg.startswith("--exit-after="):
            root.after(int(float(arg.split("=", 1)[1]) * 1000), pet.quit)
    root.mainloop()


if __name__ == "__main__":
    main()

