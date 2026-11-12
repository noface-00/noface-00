#!/usr/bin/env python3
"""
Arbol de Navidad ASCII que se arma solo y brilla segun tus commits.

Secuencia (en loop):
  1. escena vacia con nieve
  2. el arbol crece desde el suelo (capa de nieve en el borde superior)
  3. aparecen estrella, guirnalda, adornos y regalos
  4. se encienden las luces: UNA LUZ POR COMMIT (el contador sube hasta el total)
  5. el arbol gira con las luces parpadeando

Colores: cada cuenta tiene su color de luz y su regalo. Las luces mas recientes brillan mas.

Uso:
  python render.py --accounts noface-00,otra --days 360 --out ../assets/tree.gif
  python render.py --demo --accounts a,b,c        # datos falsos, sin red
Token: GITHUB_TOKEN o GH_TOKEN (para la API GraphQL).
"""
import argparse
import datetime as dt
import json
import math
import os
import urllib.request

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- parametros
CW, CH = 6, 10
COLS, ROWS = 107, 66
W, H = COLS * CW, ROWS * CH
G_FR, B_FR, HOLD_FR = 36, 30, 42          # crecimiento / encendido de luces / giro
F = G_FR + B_FR + HOLD_FR
FRAME_MS = 80
TURNS = 1.5                                # vueltas totales durante el loop
SX, SY, TILT = 385.0, 500.0, 62.0
BASE = H - 95
BG = (5, 8, 20)
RAMP = ".,:;=+*o%#@"
ACCOUNT_COLORS = [(255, 214, 102), (255, 92, 92), (92, 165, 255), (120, 255, 200), (220, 130, 255)]
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    "/Library/Fonts/Menlo.ttc",
    "C:/Windows/Fonts/consola.ttf",
]
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0

# geometria del arbol (pisos que se solapan)
TIERS = 7
HGT = 0.90 / TIERS * 1.9
TIER_YB = [0.05 + 0.90 * t / TIERS for t in range(TIERS)]
TIER_RB = [0.47 * (1 - (yb - 0.05) / 0.98) ** 0.9 + 0.05 for yb in TIER_YB]


def load_font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ---------------------------------------------------------------- datos
def fetch_calendar(login, token, days):
    to = dt.datetime.now(dt.timezone.utc)
    frm = to - dt.timedelta(days=days)
    query = """query($login:String!,$from:DateTime!,$to:DateTime!){
      user(login:$login){contributionsCollection(from:$from,to:$to){
        contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    body = json.dumps({"query": query, "variables": {
        "login": login, "from": frm.isoformat(), "to": to.isoformat()}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json",
        "User-Agent": "commit-tree"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("errors") or not data["data"]["user"]:
        raise SystemExit(f"Error consultando '{login}': {data.get('errors')}")
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in cal for d in w["contributionDays"]}


def load_activity(accounts, days, demo):
    """{cuenta: [contribuciones por dia, del mas viejo al mas reciente]}"""
    today = dt.datetime.now(dt.timezone.utc).date()
    dates = [(today - dt.timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
    out = {}
    if demo:
        rng = np.random.default_rng(7)
        for k, a in enumerate(accounts):
            lam = [1.6, 0.7, 2.2, 0.5, 1.2][k % 5]
            v = rng.poisson(lam, days) * (rng.random(days) > 0.35)
            out[a] = [int(x) for x in v]
        return out
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Falta GITHUB_TOKEN / GH_TOKEN (o usa --demo).")
    for a in accounts:
        cal = fetch_calendar(a, token, days)
        out[a] = [int(cal.get(d, 0)) for d in dates]
    return out


# ---------------------------------------------------------------- geometria
def surface_r(y, a):
    """Radio de la superficie del arbol a altura y y angulo a (vectorizado)."""
    y = np.asarray(y, float)
    a = np.asarray(a, float)
    best = np.zeros(np.broadcast(y, a).shape)
    for t in range(TIERS):
        u = (y - TIER_YB[t]) / HGT
        ok = (u >= 0) & (u <= 1)
        sc = 0.80 + 0.20 * np.abs(np.sin(a * (5 + t % 3) + t))
        r = TIER_RB[t] * sc * np.clip(1 - u, 0, 1) ** 0.85 + 0.01
        best = np.maximum(best, np.where(ok, r, 0.0))
    return best


def norm(v):
    return v / np.linalg.norm(v, axis=1, keepdims=True)


class Cloud:
    """Puntos con sombreado. 'appear' = altura a la que aparecen mientras crece el arbol."""

    def __init__(self):
        self.pos, self.nrm, self.col, self.m, self.spec, self.appear, self.white = [], [], [], [], [], [], []

    def add(self, pos, nrm, col, m=None, spec=0.0, appear=0.0, white=False):
        n = len(pos)
        self.pos.append(pos)
        self.nrm.append(nrm)
        self.col.append(np.broadcast_to(np.asarray(col, float), (n, 3)).copy())
        self.m.append(np.ones(n) if m is None else np.broadcast_to(np.asarray(m, float), (n,)).copy())
        self.spec.append(np.full(n, spec))
        self.appear.append(np.broadcast_to(np.asarray(appear, float), (n,)).copy())
        self.white.append(np.full(n, white))

    def done(self):
        for k in ("pos", "nrm", "col", "m", "spec", "appear", "white"):
            setattr(self, k, np.concatenate(getattr(self, k)))


def build_cloud(rng, n_acct, shares):
    c = Cloud()
    # --- follaje: pisos con borde festoneado, sombra entre pisos y puntas claras
    n = 42000
    tier = rng.integers(0, TIERS, n)
    u = rng.random(n)
    yb = np.array(TIER_YB)[tier]
    y = np.minimum(yb + u * HGT, 0.995)
    a = 2 * np.pi * rng.random(n)
    rb = np.array(TIER_RB)[tier]
    scallop = 0.80 + 0.20 * np.abs(np.sin(a * (5 + tier % 3) + tier))
    r = rb * scallop * (1 - u) ** 0.85 + 0.01
    r = r * (1 - 0.40 * rng.random(n) ** 3)
    pos = np.stack([r * np.cos(a), y, r * np.sin(a)], 1)
    nrm = norm(np.stack([np.cos(a), 0.55 + 0.4 * u, np.sin(a)], 1))
    ao = (0.40 + 0.60 * (1 - u) ** 0.6) * (0.80 + 0.20 * (r / (rb * scallop + 1e-6)))
    shade = ao * (0.88 + 0.12 * rng.random(n))
    g = rng.random(n) * 0.08
    green = np.stack([0.16 + g, 0.50 + g * 1.5, 0.20 + g], 1)
    tip = (u < 0.10) & (rng.random(n) < 0.35)
    flake = rng.random(n) < 0.035
    green[tip | flake] = (0.88, 0.94, 0.90)
    shade[tip | flake] = 1.0
    c.add(pos, nrm, green, shade, appear=y, white=True)

    # --- guirnalda dorada en espiral
    n = 2600
    uu = np.linspace(0, 1, n)
    yg = 0.13 + 0.77 * uu
    ag = 2 * np.pi * 3.6 * uu
    rg = surface_r(yg, ag) * 1.03 + 0.006
    c.add(np.stack([rg * np.cos(ag), yg, rg * np.sin(ag)], 1),
          norm(np.stack([np.cos(ag), 0.3 * np.ones(n), np.sin(ag)], 1)),
          (0.95, 0.72, 0.20), 0.95, spec=0.8, appear=yg, white=False)

    # --- adornos
    for k in range(22):
        yy = 0.14 + 0.70 * rng.random()
        aa = 2 * np.pi * rng.random()
        rr = float(surface_r(yy, aa)) * 1.02
        ctr = np.array([rr * np.cos(aa), yy, rr * np.sin(aa)])
        d = norm(rng.normal(size=(70, 3)))
        col = (0.85, 0.12, 0.12) if k % 3 else (0.95, 0.75, 0.25)
        c.add(ctr + d * 0.032, d, col, spec=0.9, appear=yy)

    # --- falda de nieve / base
    n = 900
    a = 2 * np.pi * rng.random(n)
    r = 0.50 * np.sqrt(rng.random(n))
    yy = 0.035 * rng.random(n)
    c.add(np.stack([r * np.cos(a), yy, r * np.sin(a)], 1), np.tile([0, 1.0, 0], (n, 1)),
          (0.55, 0.45, 0.33), 0.7 + 0.1 * rng.random(n), appear=yy, white=True)

    # --- regalos (uno por cuenta); aparecen al terminar de crecer
    for i in range(n_acct):
        ang = 2 * np.pi * i / n_acct + 0.7
        s = 0.040 + 0.030 * shares[i]
        ctr = np.array([0.52 * np.cos(ang), 0.0, 0.52 * np.sin(ang)])
        col = np.array(ACCOUNT_COLORS[i % 5]) / 255 * 0.85
        pts, nrms, cols = [], [], []
        for ax in range(3):
            for sign in (-1, 1):
                m = 220
                uv = (rng.random((m, 2)) - 0.5) * 2 * s
                p = np.zeros((m, 3))
                idx = [j for j in range(3) if j != ax]
                p[:, idx[0]] = uv[:, 0]
                p[:, idx[1]] = uv[:, 1]
                p[:, ax] = sign * s
                nn = np.zeros((m, 3))
                nn[:, ax] = sign
                ribbon = (np.abs(uv[:, 0]) < s * 0.16) | (np.abs(uv[:, 1]) < s * 0.16)
                cc = np.tile(col, (m, 1))
                cc[ribbon] = (0.95, 0.92, 0.85)
                pts.append(p + ctr + [0, s, 0])
                nrms.append(nn)
                cols.append(cc)
        c.add(np.concatenate(pts), np.concatenate(nrms), np.concatenate(cols), appear=1.0)
    c.done()
    return c


def build_lights(rng, activity, accounts, max_lights):
    """Una luz por contribucion (agrupadas de k en k si hay mas de max_lights)."""
    total = sum(sum(v) for v in activity.values())
    k = max(1, math.ceil(total / max_lights))
    days = len(next(iter(activity.values())))
    carry = [0] * len(accounts)
    acc, rec = [], []
    for d in range(days):
        for a, name in enumerate(accounts):
            carry[a] += activity[name][d]
            n = carry[a] // k
            carry[a] -= n * k
            acc += [a] * n
            rec += [d / max(1, days - 1)] * n
    N = len(acc)
    acc = np.array(acc, int)
    rec = np.array(rec, float)
    i = np.arange(N)
    u = (i + 0.5) / max(1, N)
    yg = np.linspace(0.10, 0.94, 400)
    w = np.mean([surface_r(yg, a_) for a_ in np.linspace(0, 2 * np.pi, 9)[:-1]], axis=0)
    cdf = np.cumsum(w) / w.sum()
    yy = np.interp(u, cdf, yg)
    ang = i * 2.39996
    rr = surface_r(yy, ang) * 1.03 + 0.004
    pos = np.stack([rr * np.cos(ang), yy, rr * np.sin(ang)], 1) if N else np.zeros((0, 3))
    col = np.array([ACCOUNT_COLORS[a % 5] for a in acc], float).reshape(-1, 3) / 255
    base = 0.55 + 0.45 * rec                     # recientes brillan mas
    kk = rng.integers(1, 4, N)
    ph = rng.random(N)
    rank = rng.permutation(N)
    t_on = G_FR + 2 + rank / max(1, N) * (B_FR - 6)
    return dict(N=N, k=k, total=total, pos=pos, col=col, base=base, kk=kk, ph=ph, t_on=t_on)


# ---------------------------------------------------------------- render
def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def render(activity, out_path, max_lights=400):
    accounts = list(activity)
    n_acct = len(accounts)
    totals = [sum(v) for v in activity.values()]
    shares = [t / max(1, max(totals)) for t in totals]

    rng = np.random.default_rng(2026)
    cloud = build_cloud(rng, n_acct, shares)
    LT = build_lights(rng, activity, accounts, max_lights)
    N = LT["N"]

    star = norm(rng.normal(size=(70, 3))) * 0.028 * rng.random((70, 1)) ** 0.5 + [0, 1.03, 0]
    bg_stars = [(int(rng.integers(0, COLS)), int(rng.integers(0, ROWS)), rng.random()) for _ in range(70)]
    snow = [(rng.random() * W, rng.random() * H, int(rng.integers(1, 4)), rng.random()) for _ in range(140)]

    font = load_font(10)
    lfont = load_font(13)
    hud = load_font(12)
    Ldir = np.array([-0.5, 0.5, 0.7])
    Ldir /= np.linalg.norm(Ldir)
    Hh = Ldir + np.array([0, 0, 1.0])
    Hh /= np.linalg.norm(Hh)

    def rot(x, z, c, s):
        return x * c + z * s, -x * s + z * c

    frames = []
    for f in range(F):
        th = 2 * np.pi * TURNS * f / F + 0.6
        c, s = math.cos(th), math.sin(th)
        h = smoothstep(f / G_FR)                 # altura del arbol revelada
        grown = f >= G_FR

        # --- solidos visibles (clip por altura) y capa de nieve en el borde
        vis = cloud.appear <= h + 1e-9
        cap = cloud.white & vis & (cloud.appear > h - 0.045) & (not grown)
        P, Nn = cloud.pos[vis], cloud.nrm[vis]
        base_col = cloud.col[vis].copy()
        mm = cloud.m[vis].copy()
        capv = cap[vis]
        base_col[capv] = (0.92, 0.97, 0.94)
        mm[capv] = 1.0
        xr, zr = rot(P[:, 0], P[:, 2], c, s)
        nxr, nzr = rot(Nn[:, 0], Nn[:, 2], c, s)
        diff = np.clip(nxr * Ldir[0] + Nn[:, 1] * Ldir[1] + nzr * Ldir[2], 0, 1)
        diff[capv] = 0.8                          # la tapa de nieve se ve plana y luminosa
        hv = np.clip(nxr * Hh[0] + Nn[:, 1] * Hh[1] + nzr * Hh[2], 0, 1)
        spec = hv ** 24 * cloud.spec[vis]
        b = (0.30 + 0.70 * diff) * mm
        col_s = np.clip(base_col * b[:, None] * 1.3 + spec[:, None] * 0.9, 0, 1)
        val = np.clip(b * 0.9 + spec, 0, 1)
        ch_s = val * (len(RAMP) - 1)
        px_s = W / 2 + xr * SX
        py_s = BASE - P[:, 1] * SY + zr * TILT
        z_s = zr
        n_solid = len(px_s)

        # --- luces encendidas
        on = LT["t_on"] <= f if N else np.zeros(0, bool)
        n_on = int(on.sum())
        if N:
            lp = LT["pos"][on]
            lx, lz = rot(lp[:, 0], lp[:, 2], c, s)
            tw = 0.82 + 0.18 * np.sin(2 * np.pi * (LT["kk"][on] * f / F + LT["ph"][on]))
            flash = 1 + 0.9 * np.exp(-np.maximum(0, f - LT["t_on"][on]) / 4.0)   # destello al encender
            inten = np.clip(LT["base"][on] * tw * flash, 0, 1)
            col_l = LT["col"][on] * (0.30 + 0.70 * inten)[:, None]
            ch_l = np.where(inten > 0.75, 10, np.where(inten > 0.45, 7, 3)).astype(float)
            px_l = W / 2 + lx * SX
            py_l = BASE - lp[:, 1] * SY + lz * TILT
            z_l = lz + 0.05
        else:
            inten = col_l = ch_l = px_l = py_l = z_l = np.zeros(0)
            col_l = np.zeros((0, 3))

        # --- estrella (aparece al terminar de crecer)
        s_fade = smoothstep((f - G_FR) / 10.0) if grown else 0.0
        if s_fade > 0:
            sx_, sz_ = rot(star[:, 0], star[:, 2], c, s)
            px_t = W / 2 + sx_ * SX
            py_t = BASE - star[:, 1] * SY + sz_ * TILT
            col_t = np.tile(np.array([1.0, 0.86, 0.45]) * s_fade, (len(star), 1))
            ch_t = np.full(len(star), 10.0)
            z_t = sz_ + 0.05
            g_t = np.full(len(star), s_fade)
        else:
            px_t = py_t = z_t = ch_t = g_t = np.zeros(0)
            col_t = np.zeros((0, 3))

        px = np.concatenate([px_s, px_l, px_t])
        py = np.concatenate([py_s, py_l, py_t])
        z = np.concatenate([z_s, z_l, z_t])
        col = np.concatenate([col_s, col_l, col_t])
        chs = np.concatenate([ch_s, ch_l, ch_t])
        glow = np.concatenate([np.zeros(n_solid), inten, g_t])

        ci = (px // CW).astype(int)
        ri = (py // CH).astype(int)
        ok = (ci >= 0) & (ci < COLS) & (ri >= 0) & (ri < ROWS)
        idx = np.nonzero(ok)[0]
        order = idx[np.argsort(z[idx], kind="stable")]
        grid = -np.ones((ROWS, COLS), dtype=int)
        if len(order):
            grid[ri[order], ci[order]] = order

        # --- rayos de la estrella
        scol = int(W / 2 // CW)
        srow = int((BASE - 1.03 * SY) // CH)
        extra = {}
        if s_fade > 0.3:
            ray_c = tuple(int(255 * v) for v in np.array([1.0, 0.86, 0.45]) * (0.5 + 0.5 * s_fade))
            for k_ in range(1, 9):
                extra[(srow - k_ - 1, scol)] = ("|", ray_c)
            for k_ in range(2, 6):
                extra[(srow - k_, scol - int(k_ * 1.7))] = ("\\", ray_c)
                extra[(srow - k_, scol + int(k_ * 1.7))] = ("/", ray_c)
            for k_ in range(4, 13):
                extra[(srow, scol - k_)] = ("-", ray_c)
                extra[(srow, scol + k_)] = ("-", ray_c)

        # --- brillo
        cell_glow = np.zeros((ROWS, COLS, 3))
        win_r, win_c = np.nonzero(grid >= 0)
        wi = grid[win_r, win_c]
        em = glow[wi] > 0
        cell_glow[win_r[em], win_c[em]] += col[wi[em]] * glow[wi[em], None] ** 1.5
        if s_fade > 0 and 0 <= srow < ROWS:
            cell_glow[max(0, srow - 1):srow + 2, scol - 1:scol + 2] += np.array([1.0, 0.8, 0.35]) * s_fade * 0.8
        cg = np.clip(cell_glow * 2.6, 0, 1)
        glow_img = Image.fromarray((cg * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
        glow_img = ImageChops.add(glow_img.filter(ImageFilter.GaussianBlur(6)),
                                  glow_img.filter(ImageFilter.GaussianBlur(16)).point(lambda v: min(255, v * 2)))
        img = ImageChops.add(Image.new("RGB", (W, H), BG), glow_img)
        dr = ImageDraw.Draw(img)

        for (cx_, cy_, ph) in bg_stars:
            if grid[cy_, cx_] < 0:
                v = int(70 + 60 * (0.5 + 0.5 * math.sin(2 * math.pi * (f / F * 2 + ph))))
                dr.text((cx_ * CW, cy_ * CH), ".", font=font, fill=(v, v, v + 20))

        for (x0, y0, k_, ph) in snow:
            yy = (y0 + k_ * H * f / F) % H
            xx = (x0 + 12 * math.sin(2 * math.pi * (f / F * k_ + ph))) % W
            cx_, cy_ = int(xx // CW), int(yy // CH)
            if 0 <= cx_ < COLS and 0 <= cy_ < ROWS and grid[cy_, cx_] < 0 and (cy_, cx_) not in extra:
                v = 120 + 45 * k_
                dr.text((cx_ * CW, cy_ * CH), "*" if k_ == 3 else ".", font=font, fill=(v, v, min(255, v + 15)))

        base_row = int(BASE // CH)
        for j in range(0, 7):
            rr = base_row + 1 + j
            if rr >= ROWS - 3:
                break
            half = int(38 - j * 4)
            for cc_ in range(COLS // 2 - half, COLS // 2 + half):
                if grid[rr, cc_] < 0 and (cc_ + j) % 2 == 0:
                    dr.text((cc_ * CW, rr * CH), "-", font=font, fill=(52, 58, 76))

        for r_, c_ in zip(win_r, win_c):
            i = grid[r_, c_]
            colr = tuple(int(v * 255) for v in col[i])
            v = chs[i]
            if glow[i] <= 0:
                v = v + (BAYER[r_ % 4, c_ % 4] - 0.5) * 1.6
            ch = RAMP[int(min(len(RAMP) - 1, max(0, round(v))))]
            if glow[i] > 0.25 and n_solid <= i < n_solid + len(px_l):
                dr.text((c_ * CW + CW / 2, r_ * CH + CH / 2), "●" if glow[i] > 0.6 else "o", font=lfont,
                        fill=tuple(min(255, int(vv * 255 * 1.1)) for vv in col[i]), anchor="mm")
            else:
                dr.text((c_ * CW, r_ * CH), ch, font=font, fill=colr)
        for (r_, c_), (ch, colr) in extra.items():
            if 0 <= r_ < ROWS and 0 <= c_ < COLS and grid[r_, c_] < 0:
                dr.text((c_ * CW, r_ * CH), ch, font=font, fill=colr)

        # --- HUD
        dr.text((W - 90, 8), f"t {f * FRAME_MS / 1000:5.2f}s", font=hud, fill=(255, 100, 100))
        names = " ".join(f"@{a}" for a in accounts)
        dr.text((14, H - 62), f"{names} · {dt.date.today().year}", font=hud, fill=(150, 160, 175))
        unit = f" (1 = {LT['k']} commits)" if LT["k"] > 1 else ""
        dr.text((14, H - 44),
                f"rotation {math.degrees(th) % 360:6.2f}°   lights {n_on}{unit}   commits {LT['total']}",
                font=hud, fill=(150, 160, 175))
        xx = 14
        for a_i, a in enumerate(accounts):
            colr = ACCOUNT_COLORS[a_i % 5]
            dr.text((xx, H - 26), "●", font=hud, fill=colr)
            lab = f"{a}: {totals[a_i]}"
            dr.text((xx + 14, H - 26), lab, font=hud, fill=(150, 160, 175))
            xx += 24 + int(hud.getlength(lab)) + 10
        frames.append(img)

    # --- guardar GIF (y WebP, mucho mas liviano)
    pal = frames[G_FR + B_FR + 8].quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in frames]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    q[0].save(out_path, save_all=True, append_images=q[1:], duration=FRAME_MS, loop=0, optimize=True, disposal=1)
    stem = out_path.rsplit(".", 1)[0]
    try:
        frames[0].save(stem + ".webp", save_all=True, append_images=frames[1:], duration=FRAME_MS,
                       loop=0, quality=65, method=4)
    except Exception as e:  # webp opcional
        print("WebP omitido:", e)
    for name, fr in (("_build", G_FR // 2), ("_full", F - 10)):
        frames[fr].save(stem + name + ".png")
    print(f"OK {out_path} {os.path.getsize(out_path) / 1e6:.2f} MB | luces={N} (1={LT['k']}) commits={LT['total']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", default=os.environ.get("ACCOUNTS", "noface-00"))
    ap.add_argument("--days", type=int, default=int(os.environ.get("DAYS", 360)))
    ap.add_argument("--max-lights", type=int, default=int(os.environ.get("MAX_LIGHTS", 400)))
    ap.add_argument("--out", default="../assets/tree.gif")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    accounts = [x.strip() for x in a.accounts.split(",") if x.strip()][:5]
    days = min(a.days, 364)                     # limite de GitHub: 1 año por consulta
    render(load_activity(accounts, days, a.demo), a.out, a.max_lights)


if __name__ == "__main__":
    main()
