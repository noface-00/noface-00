#!/usr/bin/env python3
"""
Componentes SVG del perfil (fondo negro, estilo terminal), generados por la Action.

  banner.svg  - saludo con efecto de escritura y subtitulos que rotan
  about.svg   - ventana de terminal con "sobre mi"
  mora.svg    - tarjetas del ecosistema MORA
  stack.svg   - tecnologias agrupadas
  stats.svg   - commits, PRs, issues, repos, estrellas y lenguajes (API de GitHub)
  footer.svg  - cierre con la frase

Uso:
  python components.py --out ../assets            # datos reales (GITHUB_TOKEN)
  python components.py --out ../assets --demo     # datos falsos
Edita la seccion CONTENIDO para cambiar textos.
"""
import argparse
import json
import os
import textwrap
import urllib.request
from xml.sax.saxutils import escape

# ---------------------------------------------------------------- CONTENIDO
NAME = "Kevin"
HANDLE = "noface-00"
TAGLINES = [
    "Full-stack developer & business owner",
    "Building the MORA ecosystem",
    "NestJS · Prisma · PostgreSQL · Expo",
    "Cuenca, Ecuador",
]
ABOUT = [
    ("cmd", "whoami"),
    ("out", "Kevin · full-stack developer & business owner · Cuenca, Ecuador"),
    ("cmd", "cat mora.txt"),
    ("out", "I design and maintain MORA, a suite of business apps for an"),
    ("out", "industrial workshop and a parts distributor."),
    ("cmd", "cat now.txt"),
    ("out", "Refactoring CarMora into Operación / Catálogos / Configuración modules."),
    ("cmd", "cat setup.txt"),
    ("out", "macOS + Arch Linux (Hyprland · Omarchy) · Obsidian + LaTeX/pandoc"),
    ("cmd", "cat studies.txt"),
    ("out", "Software Engineering student"),
]
MORA = [
    ("CarMora", "Workshop management system (monorepo) for an industrial mechanical workshop.",
     "NestJS · Prisma · PostgreSQL · Expo"),
    ("CarMora Seals", "Hydraulic seals & John Deere parts distributor app.",
     "Expo · React Native · Supabase"),
    ("AppSy", "Multi-tenant systems manager: centralizes Google OAuth and routes shared microservices.",
     "NestJS · OAuth2 · Microservices"),
    ("ServFacGmail", "Gmail invoice scanner for SRI Ecuador e-invoices, with Gemini as fallback.",
     "NestJS · Gmail API · Gemini"),
]
STACK = [
    ("backend", [("TypeScript", "#3178C6"), ("NestJS", "#E0234E"), ("Prisma", "#7C8AFF"),
                 ("PostgreSQL", "#4169E1"), ("Python", "#3776AB")]),
    ("mobile", [("React Native", "#61DAFB"), ("Expo", "#FFFFFF"), ("Supabase", "#3FCF8E")]),
    ("infra", [("Docker", "#2496ED"), ("Dokploy", "#FFB020"), ("Arch Linux", "#1793D1"),
               ("Hyprland", "#58E1FF")]),
    ("tools", [("Obsidian", "#A78BFA"), ("LaTeX", "#3FB950"), ("pandoc", "#E6EDF3")]),
]
QUOTE = '"La simplicidad es la máxima sofisticación." — Leonardo da Vinci'

# ---------------------------------------------------------------- estilo
W = 830
BG, BORDER = "#000000", "#1F1F1F"
TXT, DIM, FAINT = "#E6EDF3", "#7D8590", "#30363D"
GREEN, GOLD, RED, BLUE, MINT = "#4ADE80", "#FFD666", "#FF5C5C", "#5CA5FF", "#78FFC8"
ACCENTS = [GOLD, RED, BLUE, MINT]
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
CW = 0.6           # ancho de caracter monoespaciado (em)
STATIC = False     # True = sin animaciones (solo para previsualizar)


def e(s):
    return escape(s, {'"': "&quot;"})


def anim(s):
    return "" if STATIC else s


def card(h, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
            f'font-family="{MONO}">'
            f'<defs>{defs}</defs>'
            f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
            f'{body}</svg>')


def text(x, y, s, size=14, fill=TXT, weight=400, anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}" {extra}>{e(s)}</text>')


def section_title(x, y, label):
    return text(x, y, f"// {label}", 12, DIM)


# ---------------------------------------------------------------- banner
def banner():
    h = 190
    defs = ('<pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse">'
            f'<circle cx="1" cy="1" r="1" fill="{FAINT}"/></pattern>')
    body = f'<rect x="1" y="1" width="{W - 2}" height="{h - 2}" rx="12" fill="url(#dots)" opacity="0.55"/>'
    # copos que titilan
    import random
    rnd = random.Random(3)
    for i in range(26):
        x, y, d = rnd.randint(20, W - 20), rnd.randint(14, h - 14), rnd.uniform(2, 5)
        body += (f'<circle cx="{x}" cy="{y}" r="{rnd.choice([1, 1, 1.5])}" fill="{TXT}" opacity="0.5">'
                 + anim(f'<animate attributeName="opacity" values="0.1;0.8;0.1" dur="{d:.1f}s" '
                        f'begin="{rnd.uniform(0, 3):.1f}s" repeatCount="indefinite"/>') + '</circle>')
    body += f'<rect x="40" y="48" width="3" height="94" rx="1.5" fill="{GREEN}"/>'
    body += text(60, 66, f"~/{HANDLE}", 13, DIM)

    # titulo con efecto de escritura
    title = f"Hey, I'm {NAME}"
    fs = 40
    tw = len(title) * CW * fs
    defs += f'<clipPath id="ct"><rect x="60" y="70" width="{tw:.0f}" height="56">' + anim(
        f'<animate attributeName="width" from="0" to="{tw:.0f}" dur="1.4s" fill="freeze"/>') + '</rect></clipPath>'
    body += (f'<g clip-path="url(#ct)">' + text(60, 112, title, fs, TXT, 700,
             extra=f'textLength="{tw:.0f}" lengthAdjust="spacingAndGlyphs"') + '</g>')
    body += text(60 + tw + 14, 112, "👋", 34)

    # subtitulos que rotan + cursor que sigue al texto
    fs2 = 17
    slot = 3.6
    total = slot * len(TAGLINES)
    x0 = 62
    cur_v, cur_k = [], []
    for i, line in enumerate(TAGLINES):
        full = (len(line) + 2) * CW * fs2
        s0, s1 = i * slot / total, (i + 1) * slot / total
        kt = [0, s0, s0 + 0.30 * (s1 - s0), s1 - 0.12 * (s1 - s0), s1, 1]
        vals = [0, 0, full, full, 0, 0]
        base = full if i == 0 else 0
        defs += (f'<clipPath id="cs{i}"><rect x="{x0}" y="124" width="{base:.0f}" height="26">'
                 + anim(f'<animate attributeName="width" values="{";".join(f"{v:.0f}" for v in vals)}" '
                        f'keyTimes="{";".join(f"{k:.4f}" for k in kt)}" dur="{total}s" '
                        f'begin="1.6s" repeatCount="indefinite"/>') + '</rect></clipPath>')
        body += (f'<g clip-path="url(#cs{i})">' + text(x0, 143, "> " + line, fs2, GREEN,
                 extra=f'textLength="{full:.0f}" lengthAdjust="spacingAndGlyphs"') + '</g>')
        for k, v in zip(kt[1:5], vals[1:5]):
            cur_k.append(k)
            cur_v.append(x0 + v + 3)
    cur_k = [0] + cur_k + [1]
    cur_v = [x0 + 3] + cur_v + [x0 + 3]
    if not STATIC:
        body += (f'<rect x="{x0 + 3}" y="129" width="9" height="18" fill="{GREEN}">'
                 f'<animate attributeName="x" values="{";".join(f"{v:.0f}" for v in cur_v)}" '
                 f'keyTimes="{";".join(f"{k:.4f}" for k in cur_k)}" dur="{total}s" begin="1.6s" '
                 f'repeatCount="indefinite"/>'
                 '<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" dur="0.9s" '
                 'repeatCount="indefinite"/></rect>')
    body += text(W - 40, 66, "● online", 12, GREEN, anchor="end")
    return card(h, body, defs)


# ---------------------------------------------------------------- about (terminal)
def about():
    lh = 22
    h = 64 + len(ABOUT) * lh + 30
    body = ""
    for i, c in enumerate([RED, GOLD, GREEN]):
        body += f'<circle cx="{26 + i * 18}" cy="22" r="6" fill="{c}"/>'
    body += text(W / 2, 27, f"kevin@mora: ~/{HANDLE}", 12, DIM, anchor="middle")
    body += f'<line x1="0" y1="42" x2="{W}" y2="42" stroke="{BORDER}"/>'
    y = 72
    for i, (kind, s) in enumerate(ABOUT):
        op = "1" if STATIC else "0"
        a = anim(f'<animate attributeName="opacity" from="0" to="1" begin="{0.3 + i * 0.28:.2f}s" '
                 f'dur="0.25s" fill="freeze"/>')
        if kind == "cmd":
            body += (f'<g opacity="{op}">{a}' + text(26, y, "$", 14, GREEN, 700)
                     + text(44, y, s, 14, TXT) + '</g>')
        else:
            body += f'<g opacity="{op}">{a}' + text(44, y, s, 14, DIM) + '</g>'
        y += lh
    body += text(26, y, "$", 14, GREEN, 700)
    body += (f'<rect x="44" y="{y - 13}" width="9" height="16" fill="{TXT}">'
             + anim('<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" dur="1s" '
                    'repeatCount="indefinite"/>') + '</rect>')
    return card(h, body)


# ---------------------------------------------------------------- MORA
def mora():
    pad, gap = 24, 16
    cw_ = (W - 2 * pad - gap) / 2
    ch_ = 122
    rows = (len(MORA) + 1) // 2
    h = 56 + rows * ch_ + (rows - 1) * gap + pad
    body = section_title(pad, 34, "the MORA ecosystem")
    for i, (name, desc, stack) in enumerate(MORA):
        x = pad + (i % 2) * (cw_ + gap)
        y = 52 + (i // 2) * (ch_ + gap)
        acc = ACCENTS[i % len(ACCENTS)]
        body += (f'<g opacity="{1 if STATIC else 0}">'
                 + anim(f'<animate attributeName="opacity" from="0" to="1" begin="{0.2 + i * 0.25:.2f}s" '
                        f'dur="0.4s" fill="freeze"/>')
                 + f'<rect x="{x}" y="{y}" width="{cw_}" height="{ch_}" rx="10" fill="#0A0A0A" stroke="{BORDER}"/>'
                 + f'<rect x="{x}" y="{y + 16}" width="3" height="{ch_ - 32}" rx="1.5" fill="{acc}"/>'
                 + text(x + 20, y + 32, name, 16, acc, 700))
        for j, ln in enumerate(textwrap.wrap(desc, 46)[:3]):
            body += text(x + 20, y + 56 + j * 18, ln, 12.5, DIM)
        body += text(x + 20, y + ch_ - 14, stack, 11.5, TXT, extra='opacity="0.85"') + '</g>'
    return card(h, body)


# ---------------------------------------------------------------- stack
def stack():
    pad = 24
    rowh = 44
    h = 50 + len(STACK) * rowh + 10
    body = section_title(pad, 34, "stack")
    k = 0
    for r, (group, items) in enumerate(STACK):
        y = 52 + r * rowh
        body += text(pad, y + 21, group, 12.5, DIM)
        x = pad + 92
        for label, col in items:
            wch = len(label) * CW * 13 + 38
            body += (f'<g opacity="{1 if STATIC else 0}">'
                     + anim(f'<animate attributeName="opacity" from="0" to="1" begin="{0.1 + k * 0.07:.2f}s" '
                            f'dur="0.3s" fill="freeze"/>')
                     + f'<rect x="{x}" y="{y}" width="{wch:.0f}" height="30" rx="15" fill="#0D0D0D" stroke="{BORDER}"/>'
                     + f'<circle cx="{x + 16}" cy="{y + 15}" r="4.5" fill="{col}"/>'
                     + text(x + 28, y + 20, label, 13, TXT) + '</g>')
            x += wch + 10
            k += 1
    return card(h, body)


# ---------------------------------------------------------------- stats
def fetch_stats(accounts, token):
    q = """query($login:String!){user(login:$login){
      contributionsCollection{totalCommitContributions totalPullRequestContributions totalIssueContributions
        restrictedContributionsCount}
      repositories(first:100, ownerAffiliations:OWNER, isFork:false){totalCount
        nodes{stargazerCount languages(first:8, orderBy:{field:SIZE, direction:DESC}){edges{size node{name color}}}}}}}"""
    agg = dict(commits=0, prs=0, issues=0, repos=0, stars=0, private=0, langs={})
    for login in accounts:
        body = json.dumps({"query": q, "variables": {"login": login}}).encode()
        req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
            "Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-components"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        u = (data.get("data") or {}).get("user")
        if not u:
            raise SystemExit(f"Error consultando '{login}': {data.get('errors')}")
        c = u["contributionsCollection"]
        agg["commits"] += c["totalCommitContributions"]
        agg["prs"] += c["totalPullRequestContributions"]
        agg["issues"] += c["totalIssueContributions"]
        agg["private"] += c["restrictedContributionsCount"]
        agg["repos"] += u["repositories"]["totalCount"]
        for n in u["repositories"]["nodes"]:
            agg["stars"] += n["stargazerCount"]
            for ed in n["languages"]["edges"]:
                nm = ed["node"]["name"]
                size, col = agg["langs"].get(nm, (0, ed["node"]["color"] or "#888888"))
                agg["langs"][nm] = (size + ed["size"], col)
    return agg


def demo_stats():
    return dict(commits=1024, prs=38, issues=12, repos=14, stars=3, private=0, langs={
        "TypeScript": (580, "#3178C6"), "JavaScript": (140, "#F1E05A"), "Python": (120, "#3572A5"),
        "Shell": (80, "#89E051"), "HTML": (50, "#E34C26"), "CSS": (30, "#663399")})


def stats(st):
    pad = 24
    h = 192
    body = section_title(pad, 34, "github · last 12 months")
    metrics = [("commits", st["commits"] + st["private"], GREEN), ("pull requests", st["prs"], BLUE),
               ("issues", st["issues"], GOLD), ("repos", st["repos"], MINT), ("stars", st["stars"], RED)]
    for i, (lab, val, col) in enumerate(metrics):
        x = pad + (i % 3) * 128
        y = 76 + (i // 3) * 64
        body += text(x, y, f"{val:,}", 26, col, 700)
        body += text(x, y + 20, lab, 12, DIM)
    # lenguajes
    lx, lw = 430, W - 430 - pad
    body += text(lx, 60, "top languages", 12, DIM)
    langs = sorted(st["langs"].items(), key=lambda kv: -kv[1][0])[:6]
    tot = sum(v[0] for _, v in langs) or 1
    defs = f'<clipPath id="bar"><rect x="{lx}" y="72" width="{lw}" height="10" rx="5"/></clipPath>'
    x = lx
    bar = ""
    for nm, (sz, col) in langs:
        wseg = lw * sz / tot
        bar += f'<rect x="{x:.1f}" y="72" width="{wseg + 0.5:.1f}" height="10" fill="{col}"/>'
        x += wseg
    body += f'<rect x="{lx}" y="72" width="{lw}" height="10" rx="5" fill="{FAINT}"/>'
    body += f'<g clip-path="url(#bar)">{bar}</g>'
    for i, (nm, (sz, col)) in enumerate(langs):
        x = lx + (i % 2) * (lw / 2)
        y = 112 + (i // 2) * 26
        body += f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{col}"/>'
        body += text(x + 18, y, nm, 13, TXT)
        body += text(x + lw / 2 - 16, y, f"{100 * sz / tot:.1f}%", 12, DIM, anchor="end")
    return card(h, body, defs)


# ---------------------------------------------------------------- footer
def footer():
    h = 70
    body = text(W / 2, 42, QUOTE, 13, DIM, anchor="middle", extra='font-style="italic"')
    return card(h, body)


def main():
    global STATIC
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", default=os.environ.get("ACCOUNTS", HANDLE))
    ap.add_argument("--out", default="../assets")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--static", action="store_true", help="sin animaciones (previsualizar)")
    a = ap.parse_args()
    STATIC = a.static
    accounts = [x.strip() for x in a.accounts.split(",") if x.strip()]
    if a.demo:
        st = demo_stats()
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("Falta GITHUB_TOKEN / GH_TOKEN (o usa --demo).")
        st = fetch_stats(accounts, token)
    os.makedirs(a.out, exist_ok=True)
    for name, svg in [("banner", banner()), ("about", about()), ("mora", mora()), ("stack", stack()),
                      ("stats", stats(st)), ("footer", footer())]:
        with open(os.path.join(a.out, f"{name}.svg"), "w", encoding="utf-8") as fh:
            fh.write(svg)
    print("OK componentes en", a.out)


if __name__ == "__main__":
    main()
