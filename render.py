#!/usr/bin/env python3
"""
Arbol de Navidad ASCII que brilla segun los commits de una o varias cuentas de GitHub.

- Cada luz = un dia de actividad de una cuenta (viejo abajo -> reciente arriba).
- Brillo/parpadeo de la luz = commits (contribuciones) de ese dia. Sin commits = brasa tenue.
- Cada cuenta tiene su color de luz y su regalo (mas grande = mas actividad).
- La estrella brilla mas con la actividad total.

Uso:
  python render.py --accounts noface-00,otra-cuenta --days 56 --out ../assets/tree.gif
  python render.py --demo --accounts a,b,c            # datos falsos, sin red
Token: variable de entorno GITHUB_TOKEN o GH_TOKEN (necesario para la API GraphQL).
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
CW, CH = 6, 10                 # tamano de celda (px)
COLS, ROWS = 107, 66
W, H = COLS * CW, ROWS * CH
F = 90                         # frames (una vuelta completa)
FRAME_MS = 80
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


def load_font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ---------------------------------------------------------------- datos
def fetch_calendar(login, token, days):
    to = dt.datetime.now(dt.timezone.utc)
    frm = to - dt.timedelta(days=days + 1)
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
    """Devuelve {cuenta: [commits por dia, del mas viejo al mas reciente]}."""
    today = dt.datetime.now(dt.timezone.utc).date()
    dates = [(today - dt.timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
    out = {}
    if demo:
        rng = np.random.default_rng(7)
        for k, a in enumerate(accounts):
            lam = [2.5, 1.2, 4.0, 0.8, 2.0][k % 5]
            v = rng.poisson(lam, days) * (rng.random(days) > 0.25)
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
def radius(y):
    tiers = 6
    t = (y * tiers) % 1.0
    base = 0.46 * (1 - y) ** 0.95 + 0.03
    return base * (0.62 + 0.38 * (1 - t))


def norm(v):
    return v / np.linalg.norm(v, axis=1, keepdims=True)


class Cloud:
    """Puntos con sombreado (arbol, adornos, regalos, base)."""

    def __init__(self):
        self.pos, self.nrm, self.col, self.m, self.spec = [], [], [], [], []

    def add(self, pos, nrm, col, m=None, spec=0.0):
        n = len(pos)
        self.pos.append(pos)
        self.nrm.append(nrm)
        self.col.append(np.broadcast_to(np.asarray(col, float), (n, 3)).copy())
        self.m.append(np.ones(n) if m is None else m)
        self.spec.append(np.full(n, spec))

    def done(self):
        self.pos = np.concatenate(self.pos)
        self.nrm = np.concatenate(self.nrm)
        self.col = np.concatenate(self.col)
        self.m = np.concatenate(self.m)
        self.spec = np.concatenate(self.spec)


def build_cloud(rng, n_acct, shares):
    c = Cloud()
    # --- arbol: pisos con borde festoneado, sombra entre pisos y puntas claras
    tiers = 7
    n = 42000
    tier = rng.integers(0, tiers, n)
    u = rng.random(n)                         # 0 = borde inferior del piso, 1 = parte alta
    yb = 0.05 + 0.90 * (tier / tiers) ** 1.0
    hgt = 0.90 / tiers * 1.9                  # los pisos se solapan
    y = np.minimum(yb + u * hgt, 0.995)
    a = 2 * np.pi * rng.random(n)
    rb = 0.47 * (1 - (yb - 0.05) / 0.98) ** 0.9 + 0.05
    scallop = 0.80 + 0.20 * np.abs(np.sin(a * (5 + tier % 3) + tier))   # puntas de rama
    r = rb * scallop * (1 - u) ** 0.85 + 0.01
    r = r * (1 - 0.40 * rng.random(n) ** 3)   # algo de profundidad interior
    pos = np.stack([r * np.cos(a), y, r * np.sin(a)], 1)
    nrm = norm(np.stack([np.cos(a), 0.55 + 0.4 * u, np.sin(a)], 1))
    ao = 0.40 + 0.60 * (1 - u) ** 0.6          # la parte alta del piso queda bajo el piso superior
    ao *= 0.80 + 0.20 * (r / (rb * scallop + 1e-6))
    shade = ao * (0.88 + 0.12 * rng.random(n))
    g = rng.random(n) * 0.08
    green = np.stack([0.16 + g, 0.50 + g * 1.5, 0.20 + g], 1)
    tip = (u < 0.10) & (rng.random(n) < 0.35)
    flake = rng.random(n) < 0.035
    green[tip | flake] = (0.88, 0.94, 0.90)
    shade[tip | flake] = 1.0
    c.add(pos, nrm, green, shade)
    # --- adornos
    for k in range(16):
        yy = 0.14 + 0.72 * rng.random()
        aa = 2 * np.pi * rng.random()
        rr = radius(yy) * 0.97
        ctr = np.array([rr * np.cos(aa), yy, rr * np.sin(aa)])
        d = norm(rng.normal(size=(60, 3)))
        col = (0.85, 0.12, 0.12) if k % 4 else (0.95, 0.75, 0.25)
        c.add(ctr + d * 0.03, d, col, spec=0.9)
    # --- falda / base del arbol
    n = 900
    a = 2 * np.pi * rng.random(n)
    r = 0.50 * np.sqrt(rng.random(n))
    pos = np.stack([r * np.cos(a), 0.035 * rng.random(n), r * np.sin(a)], 1)
    nrm = np.tile([0, 1.0, 0], (n, 1))
    c.add(pos, nrm, (0.55, 0.45, 0.33), 0.7 + 0.1 * rng.random(n))
    # --- regalos (uno por cuenta)
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
        c.add(np.concatenate(pts), np.concatenate(nrms), np.concatenate(cols))
    c.done()
    return c


# ---------------------------------------------------------------- render
def render(activity, out_path, demo=False):
    accounts = list(activity)
    n_acct = len(accounts)
    days = len(next(iter(activity.values())))
    totals = [sum(v) for v in activity.values()]
    shares = [t / max(1, max(totals)) for t in totals]
    total_commits = sum(totals)
    recent = sum(sum(v[-14:]) for v in activity.values())

    rng = np.random.default_rng(2026)
    cloud = build_cloud(rng, n_acct, shares)

    # --- luces: una por (dia, cuenta); viejo abajo -> reciente arriba, espiral
    N = days * n_acct
    L_pos = np.zeros((N, 3))
    L_col = np.zeros((N, 3))
    L_base = np.zeros(N)
    L_k = np.zeros(N)
    L_ph = rng.random(N)
    cmax = max(1, max(max(v) for v in activity.values()))
    for d in range(days):
        for a in range(n_acct):
            i = d * n_acct + a
            u = (i + 0.5) / N
            yy = 0.10 + 0.84 * u
            ang = i * 2.39996
            rr = radius(yy) * 0.99
            L_pos[i] = (rr * math.cos(ang), yy, rr * math.sin(ang))
            L_col[i] = np.array(ACCOUNT_COLORS[a % 5]) / 255
            cnt = activity[accounts[a]][d]
            L_base[i] = 0.14 if cnt == 0 else 0.42 + 0.58 * min(1, math.log1p(cnt) / math.log1p(min(cmax, 8)))
            L_k[i] = 0 if cnt == 0 else int(rng.integers(1, 4))

    # --- estrella
    star = norm(rng.normal(size=(70, 3))) * 0.028 * rng.random((70, 1)) ** 0.5 + [0, 1.03, 0]
    star_int = 0.65 + 0.35 * min(1.0, recent / max(20, 6 * n_acct))

    # --- fondo estatico: estrellas y nieve
    bg_stars = [(int(rng.integers(0, COLS)), int(rng.integers(0, ROWS)), rng.random()) for _ in range(70)]
    snow = [(rng.random() * W, rng.random() * H, int(rng.integers(1, 4)), rng.random()) for _ in range(140)]

    font = load_font(10)
    lfont = load_font(17)
    hud = load_font(12)
    Ldir = np.array([-0.5, 0.5, 0.7])
    Ldir /= np.linalg.norm(Ldir)
    Hh = Ldir + np.array([0, 0, 1.0])
    Hh /= np.linalg.norm(Hh)

    def rot(x, z, c, s):
        return x * c + z * s, -x * s + z * c

    frames = []
    for f in range(F):
        th = 2 * np.pi * f / F
        c, s = math.cos(th), math.sin(th)

        # solidos
        xr, zr = rot(cloud.pos[:, 0], cloud.pos[:, 2], c, s)
        nxr, nzr = rot(cloud.nrm[:, 0], cloud.nrm[:, 2], c, s)
        diff = np.clip(nxr * Ldir[0] + cloud.nrm[:, 1] * Ldir[1] + nzr * Ldir[2], 0, 1)
        hv = np.clip(nxr * Hh[0] + cloud.nrm[:, 1] * Hh[1] + nzr * Hh[2], 0, 1)
        spec = hv ** 24 * cloud.spec
        b = (0.30 + 0.70 * diff) * cloud.m
        col_s = np.clip(cloud.col * b[:, None] * 1.3 + spec[:, None] * 0.9, 0, 1)
        val = np.clip(b * 0.9 + spec, 0, 1)
        ch_s = val * (len(RAMP) - 1)               # float: se cuantiza con dither al dibujar
        px_s = W / 2 + xr * SX
        py_s = BASE - cloud.pos[:, 1] * SY + zr * TILT
        z_s, glow_s = zr, np.zeros(len(zr))

        # luces
        lx, lz = rot(L_pos[:, 0], L_pos[:, 2], c, s)
        tw = np.where(L_k > 0, 0.82 + 0.18 * np.sin(2 * np.pi * (L_k * f / F + L_ph)), 1.0)
        inten = np.clip(L_base * tw, 0, 1)
        col_l = L_col * (0.30 + 0.70 * inten)[:, None] * np.where(inten > 0.2, 1.0, 0.45)[:, None]
        ch_l = np.where(inten > 0.75, 10, np.where(inten > 0.45, 7, np.where(inten > 0.2, 3, 0))).astype(float)
        px_l = W / 2 + lx * SX
        py_l = BASE - L_pos[:, 1] * SY + lz * TILT
        z_l = lz + 0.05

        # estrella
        sx_, sz_ = rot(star[:, 0], star[:, 2], c, s)
        px_t = W / 2 + sx_ * SX
        py_t = BASE - star[:, 1] * SY + sz_ * TILT
        col_t = np.tile(np.array([1.0, 0.86, 0.45]) * star_int, (len(star), 1))
        ch_t = np.full(len(star), 10.0)
        z_t = sz_ + 0.05

        n_solid = len(px_s)
        px = np.concatenate([px_s, px_l, px_t])
        py = np.concatenate([py_s, py_l, py_t])
        z = np.concatenate([z_s, z_l, z_t])
        col = np.concatenate([col_s, col_l, col_t])
        chs = np.concatenate([ch_s, ch_l, ch_t])
        glow = np.concatenate([glow_s, inten, np.full(len(star), star_int)])

        ci = (px // CW).astype(int)
        ri = (py // CH).astype(int)
        ok = (ci >= 0) & (ci < COLS) & (ri >= 0) & (ri < ROWS)
        idx = np.nonzero(ok)[0]
        order = idx[np.argsort(z[idx], kind="stable")]
        grid = -np.ones((ROWS, COLS), dtype=int)
        grid[ri[order], ci[order]] = order

        # rayos de la estrella
        scol = int(W / 2 // CW)
        srow = int((BASE - 1.03 * SY) // CH)
        extra = {}
        ray_c = tuple(int(255 * v) for v in np.array([1.0, 0.86, 0.45]) * (0.5 + 0.5 * star_int))
        for k in range(1, 9):
            extra[(srow - k - 1, scol)] = ("|", ray_c)
        for k in range(2, 6):
            extra[(srow - k, scol - int(k * 1.7))] = ("\\", ray_c)
            extra[(srow - k, scol + int(k * 1.7))] = ("/", ray_c)
        for k in range(4, 13):
            extra[(srow, scol - k)] = ("-", ray_c)
            extra[(srow, scol + k)] = ("-", ray_c)

        # brillo (glow) en celdas
        cell_glow = np.zeros((ROWS, COLS, 3))
        win_r, win_c = np.nonzero(grid >= 0)
        wi = grid[win_r, win_c]
        em = glow[wi] > 0
        cell_glow[win_r[em], win_c[em]] += col[wi[em]] * glow[wi[em], None] ** 1.5
        if 0 <= srow < ROWS:
            cell_glow[max(0, srow - 1):srow + 2, scol - 1:scol + 2] += np.array([1.0, 0.8, 0.35]) * star_int * 0.8
        cg = np.clip(cell_glow * 2.6, 0, 1)
        glow_img = Image.fromarray((cg * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
        glow_img = ImageChops.add(glow_img.filter(ImageFilter.GaussianBlur(6)),
                                  glow_img.filter(ImageFilter.GaussianBlur(16)).point(lambda v: min(255, v * 2)))
        glow_img = ImageChops.multiply(glow_img, Image.new("RGB", (W, H), (255, 255, 255)))

        img = Image.new("RGB", (W, H), BG)
        img = ImageChops.add(img, glow_img)
        dr = ImageDraw.Draw(img)

        # estrellas de fondo
        for (cx_, cy_, ph) in bg_stars:
            if grid[cy_, cx_] < 0:
                v = int(70 + 60 * (0.5 + 0.5 * math.sin(2 * math.pi * (f / F * 2 + ph))))
                dr.text((cx_ * CW, cy_ * CH), ".", font=font, fill=(v, v, v + 20))

        # nieve
        for (x0, y0, k, ph) in snow:
            yy = (y0 + k * H * f / F) % H
            xx = (x0 + 12 * math.sin(2 * math.pi * (f / F * k + ph))) % W
            cx_, cy_ = int(xx // CW), int(yy // CH)
            if 0 <= cx_ < COLS and 0 <= cy_ < ROWS and grid[cy_, cx_] < 0 and (cy_, cx_) not in extra:
                v = 120 + 45 * k
                dr.text((cx_ * CW, cy_ * CH), "*" if k == 3 else ".", font=font, fill=(v, v, min(255, v + 15)))

        # piso (lineas tenues)
        base_row = int(BASE // CH)
        for j in range(0, 7):
            rr = base_row + 1 + j
            if rr >= ROWS - 3:
                break
            half = int(38 - j * 4)
            for cc_ in range(COLS // 2 - half, COLS // 2 + half):
                if grid[rr, cc_] < 0 and (cc_ + j) % 2 == 0:
                    dr.text((cc_ * CW, rr * CH), "-", font=font, fill=(52, 58, 76))

        # texto de los sólidos
        for r_, c_ in zip(win_r, win_c):
            i = grid[r_, c_]
            colr = tuple(int(v * 255) for v in col[i])
            v = chs[i]
            if glow[i] <= 0:
                v = v + (BAYER[r_ % 4, c_ % 4] - 0.5) * 1.6
            ch = RAMP[int(min(len(RAMP) - 1, max(0, round(v))))]
            if glow[i] > 0.25 and i < n_solid + N:
                dr.text((c_ * CW + CW / 2, r_ * CH + CH / 2), "●" if glow[i] > 0.6 else "o", font=lfont,
                        fill=tuple(min(255, int(v * 255 * 1.1)) for v in col[i]), anchor="mm")
            else:
                dr.text((c_ * CW, r_ * CH), ch, font=font, fill=colr)
        for (r_, c_), (ch, colr) in extra.items():
            if 0 <= r_ < ROWS and 0 <= c_ < COLS and grid[r_, c_] < 0:
                dr.text((c_ * CW, r_ * CH), ch, font=font, fill=colr)

        # HUD
        dr.text((W - 90, 8), f"t {f * FRAME_MS / 1000:5.2f}s", font=hud, fill=(255, 100, 100))
        names = " ".join(f"@{a}" for a in accounts)
        dr.text((14, H - 62), f"{names} · {dt.date.today().year}", font=hud, fill=(150, 160, 175))
        dr.text((14, H - 44),
                f"rotation {math.degrees(th):6.2f}°   lights {N}   commits {total_commits}",
                font=hud, fill=(150, 160, 175))
        # leyenda de colores
        xx = 14
        for a_i, a in enumerate(accounts):
            colr = ACCOUNT_COLORS[a_i % 5]
            dr.text((xx, H - 26), "●", font=hud, fill=colr)
            lab = f"{a}: {totals[a_i]}"
            dr.text((xx + 14, H - 26), lab, font=hud, fill=(150, 160, 175))
            xx += 24 + int(hud.getlength(lab)) + 10
        frames.append(img)

    # --- guardar GIF
    pal = frames[F // 3].quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in frames]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    q[0].save(out_path, save_all=True, append_images=q[1:], duration=FRAME_MS, loop=0, optimize=True, disposal=1)
    frames[F // 3].save(out_path.rsplit(".", 1)[0] + "_preview.png")
    print(f"OK {out_path}  {os.path.getsize(out_path) / 1e6:.2f} MB  luces={N} commits={total_commits}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", default=os.environ.get("ACCOUNTS", "noface-00"))
    ap.add_argument("--days", type=int, default=int(os.environ.get("DAYS", 56)))
    ap.add_argument("--out", default="../assets/tree.gif")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    accounts = [x.strip() for x in a.accounts.split(",") if x.strip()][:5]
    render(load_activity(accounts, a.days, a.demo), a.out, a.demo)


if __name__ == "__main__":
    main()
