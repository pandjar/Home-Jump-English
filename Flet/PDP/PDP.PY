#v1.30.2
#Jared Hdz Ctr "Pandajar"
#python 3.14

import flet as ft
import random
import json
import os
import time
import threading

ANIMATION_FPS  = 10
TIME_PER_FRAME = 1.0 / ANIMATION_FPS
SECUENCIA_OJOS = [f"ojos_{i}.png" for i in range(30)]
MENU_IDLE_SECS = 15   # segundos sin actividad → reanima el menú
MAX_VISIBLE_LETTERS = 4   # máximo de fichas doradas visibles a la vez en pantalla

# ─── VOCABULARY
VOCABULARY = {
    "Bathroom":     ["SHOWER","BATHTUB","TOILET","SINK","MIRROR","TOWEL","TOOTHBRUSH"],
    "Kitchen":      ["FRIDGE","STOVE","OVEN","MICROWAVE","DISHWASHER","CUPBOARD","COUNTERTOP"],
    "Living Room":  ["SOFA","ARMCHAIR","RUG","BOOKSHELF","CURTAINS"],
    "Bedroom":      ["BED","PILLOW","WARDROBE","NIGHTSTAND","LAMP","BLANKET","HANGER"],
    "Dining Room":  ["CHAIR","TABLECLOTH","SILVERWARE","PLATE","GLASS"],
    "Laundry Room": ["DRYER","IRON","WASHER"],
}

TRANSLATIONS = {
    "SHOWER":"Ducha","BATHTUB":"Bañera","TOILET":"Inodoro","SINK":"Lavabo",
    "MIRROR":"Espejo","TOWEL":"Toalla","TOOTHBRUSH":"Cepillo de dientes",
    "FRIDGE":"Nevera","STOVE":"Estufa","OVEN":"Horno","MICROWAVE":"Microondas",
    "DISHWASHER":"Lavavajillas","CUPBOARD":"Alacena","COUNTERTOP":"Encimera",
    "SOFA":"Sofá","ARMCHAIR":"Sillón","RUG":"Alfombra",
    "BOOKSHELF":"Estantería","CURTAINS":"Cortinas",
    "BED":"Cama","PILLOW":"Almohada","WARDROBE":"Armario",
    "NIGHTSTAND":"Mesita de noche","LAMP":"Lámpara","BLANKET":"Manta","HANGER":"Percha",
    "CHAIR":"Silla","TABLECLOTH":"Mantel","SILVERWARE":"Cubiertos",
    "PLATE":"Plato","GLASS":"Vaso",
    "DRYER":"Secadora","IRON":"Plancha","WASHER":"Lavadora",
}

RECORD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "record.json")

def load_record():
    if os.path.exists(RECORD_FILE):
        try:
            with open(RECORD_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"best_height": 0, "words_found": [], "total_games": 0}

def save_record(r):
    with open(RECORD_FILE, "w") as f:
        json.dump(r, f, indent=2, ensure_ascii=False)

# ─── CONSTANTS
W, H         = 380, 620
PW, PH       = 32, 32
PLATW, PLATH = 80, 12
GRAVITY      = 0.58
JUMP         = -15.0
SPEED        = 5
TICK         = 0.032
BALL_R       = 10

# ══════════════════════════════════════════════════════════════════════════════
def main(page: ft.Page):
    page.title            = "Home Jump"
    page.bgcolor          = "#0d0d2b"
    page.padding          = 0
    page.window.width     = W + 20
    page.window.height    = H + 130
    page.window.resizable = False

    record      = load_record()
    cmd         = {"v": None}
    loop_paused = threading.Event()
    gs          = {"anim": {"index": 0, "last_time": 0, "complete": False}}

    # Idle tracker para el menú
    menu_idle  = {"last_action": 0.0, "in_menu": False}
    menu_state = {"htop": False}   # True = "Cómo jugar" desplegado

    sel_cats = {"v": list(VOCABULARY.keys())}

    def active_words():
        return [w for cat in sel_cats["v"] for w in VOCABULARY[cat]]

    # ── state ────────────────────────────────────────────────────────────────
    def reset_gs():
        gs.update({
            "px": float(W // 2 - PW // 2),
            "py": float(H - 160),
            "vy": 0.0, "cam": 0.0, "score": 0,
            "left": False, "right": False,
            "platforms": [], "letters": [], "balls": [], "powerups": [],
            "target": None, "tidx": 0,
            "collected": [], "found": [], "notif": None,
            "over": False, "paused": False,
            "shield_ttl": 0,   # ticks restantes de escudo (>0 = invulnerable)
        })

    def pick_target():
        words = active_words()
        rem = [w for w in words if w not in gs["found"]] or words[:]
        gs["target"]    = random.choice(rem)
        gs["tidx"]      = 0
        gs["collected"] = []

    # ── platforms, balls & power-ups ─────────────────────────────────────────
    def _rand_type():
        return random.choices(["normal", "bouncy"], weights=[79, 21])[0]

    def _spawn_ball(world_y):
        vx = random.choice([-1, 1]) * random.uniform(2.0, 4.0)
        gs["balls"].append({
            "wx": float(random.randint(BALL_R + 4, W - BALL_R - 4)),
            "wy": float(world_y), "vx": vx,
        })

    def _spawn_powerup(world_x, world_y):
        gs["powerups"].append({
            "wx": float(world_x), "wy": float(world_y),
            "type": random.choice(["shield", "jetpack"]),
        })

    def gen_platforms():
        gs["platforms"].append({"wx": 0, "wy": H - 30, "w": W, "type": "ground"})
        wy = H - 160
        for _ in range(22):
            wx    = random.randint(10, W - PLATW - 10)
            ptype = _rand_type()
            gs["platforms"].append({"wx": wx, "wy": wy, "w": PLATW, "type": ptype})
            wy -= random.randint(72, 112)

    def extend_platforms():
        if not gs["platforms"]: return
        top = min(p["wy"] for p in gs["platforms"])
        while top > gs["cam"] - 350:
            top  -= random.randint(70, 120)
            wx    = random.randint(10, W - PLATW - 10)
            ptype = _rand_type()
            gs["platforms"].append({"wx": wx, "wy": top, "w": PLATW, "type": ptype})

            # Letras doradas: solo para el índice actual (tidx),
            # máximo MAX_VISIBLE_LETTERS fichas visibles a la vez.
            if gs["target"] and gs["tidx"] < len(gs["target"]) and random.random() < 0.65:
                if len(gs["letters"]) < MAX_VISIBLE_LETTERS:
                    idx = gs["tidx"]
                    gs["letters"].append({
                        "wx": wx + PLATW // 2 - 9,
                        "wy": top - 34,
                        "char": gs["target"][idx],
                        "lidx": idx,
                    })

            if random.random() < 0.05:          # 5% bolita roja
                _spawn_ball(top - 40)
            if random.random() < 0.07:          # 7% power-up
                _spawn_powerup(wx + PLATW // 2, top - 45)

        limit = gs["cam"] + H + 300
        gs["platforms"] = [p for p in gs["platforms"] if p["wy"] < limit]
        gs["letters"]   = [l for l in gs["letters"]   if l["wy"] < limit]
        gs["balls"]     = [b for b in gs["balls"]     if b["wy"] < limit]
        gs["powerups"]  = [p for p in gs["powerups"]  if p["wy"] < limit]

    # ── physics ──────────────────────────────────────────────────────────────
    def step():
        if gs["left"]:  gs["px"] -= SPEED
        if gs["right"]: gs["px"] += SPEED
        if gs["px"] + PW < 0: gs["px"] = float(W)
        if gs["px"] > W:      gs["px"] = float(-PW)

        gs["vy"] += GRAVITY
        gs["py"] += gs["vy"]
        wpy = gs["py"] + gs["cam"]

        if gs["vy"] > 0:
            for p in gs["platforms"]:
                pb      = wpy + PH
                pb_prev = pb - gs["vy"]
                if (gs["px"] + PW > p["wx"] + 4 and
                        gs["px"] < p["wx"] + p["w"] - 4 and
                        pb_prev <= p["wy"] <= pb):
                    gs["vy"] = JUMP * (1.4 if p["type"] == "bouncy" else 1.0)

        if gs["py"] < H * 0.42:
            d = H * 0.42 - gs["py"]
            gs["cam"] -= d
            gs["py"]  += d
            gs["score"] = max(gs["score"], int(-gs["cam"] / 10))

        # ── Escudo tick-down
        if gs["shield_ttl"] > 0:
            gs["shield_ttl"] -= 1

        # ── Bolitas + colisión (respeta escudo)
        for b in gs["balls"]:
            b["wx"] += b["vx"]
            if b["wx"] <= BALL_R:
                b["wx"] = float(BALL_R);  b["vx"] = abs(b["vx"])
            elif b["wx"] >= W - BALL_R:
                b["wx"] = float(W - BALL_R); b["vx"] = -abs(b["vx"])
            bsx = b["wx"]; bsy = b["wy"] - gs["cam"]
            cx  = max(gs["px"], min(bsx, gs["px"] + PW))
            cy  = max(gs["py"], min(bsy, gs["py"] + PH))
            if (bsx - cx)**2 + (bsy - cy)**2 <= BALL_R**2:
                if gs["shield_ttl"] > 0:
                    # Escudo absorbe el golpe y se rompe
                    gs["shield_ttl"] = 0
                    gs["notif"] = {"text": "🛡️  ¡ESCUDO ROTO!", "ttl": 90, "col": "#ff4444"}
                else:
                    do_end_game(); return

        # ── Power-ups: recolección
        wpy = gs["py"] + gs["cam"]
        keep_pu = []
        for pu in gs["powerups"]:
            psy = pu["wy"] - gs["cam"]
            hit = (gs["px"] < pu["wx"] + 14 and gs["px"] + PW > pu["wx"] - 14 and
                   gs["py"] < psy + 14 and gs["py"] + PH > psy - 14)
            if hit:
                if pu["type"] == "shield":
                    gs["shield_ttl"] = 220
                    gs["notif"] = {"text": "🛡️  ¡ESCUDO ACTIVADO!", "ttl": 90, "col": "#00aaff"}
                else:  # jetpack
                    gs["vy"] = -32.0
                    gs["notif"] = {"text": "🚀  ¡JETPACK!", "ttl": 70, "col": "#ff8800"}
            else:
                keep_pu.append(pu)
        gs["powerups"] = keep_pu

        # ── Letras
        wpy = gs["py"] + gs["cam"]
        keep = []
        collected_lidx = None
        for l in gs["letters"]:
            hit = (gs["px"] < l["wx"] + 22 and gs["px"] + PW > l["wx"] and
                   wpy < l["wy"] + 22 and wpy + PH > l["wy"])
            if hit and gs["target"] and l["lidx"] == gs["tidx"] and collected_lidx is None:
                collected_lidx = l["lidx"]          # marca el índice recogido
                gs["collected"].append(l["char"])
                gs["tidx"] += 1
                if gs["tidx"] >= len(gs["target"]):  # ← palabra COMPLETA
                    tw = gs["target"]
                    gs["found"].append(tw)
                    gs["notif"] = {"text": f"✓  {tw}  =  {TRANSLATIONS.get(tw,'')}", "ttl": 110, "col": "#00ff88"}
                    pick_target()
                    gs["letters"] = []               # limpiar todas las letras al cambiar de palabra
                    break
            else:
                keep.append(l)

        if collected_lidx is not None and not gs.get("target") == gs.get("_last_target"):
            # Eliminar duplicados del mismo índice que acaba de recogerse
            gs["letters"] = [l for l in keep if l["lidx"] != collected_lidx]
        elif collected_lidx is not None:
            gs["letters"] = [l for l in keep if l["lidx"] != collected_lidx]
        else:
            gs["letters"] = keep

        if gs["notif"]:
            gs["notif"]["ttl"] -= 1
            if gs["notif"]["ttl"] <= 0:
                gs["notif"] = None

        extend_platforms()
        if gs["py"] > H + 90:
            do_end_game()

    def do_end_game():
        gs["over"] = True
        record["total_games"] = record.get("total_games", 0) + 1
        if gs["score"] > record["best_height"]:
            record["best_height"] = gs["score"]
        for w in gs["found"]:
            if w not in record["words_found"]:
                record["words_found"].append(w)
        save_record(record)

    # ── render ───────────────────────────────────────────────────────────────
    game_stack = ft.Stack(width=W, height=H, clip_behavior=ft.ClipBehavior.HARD_EDGE)

    def render():
        is_over   = gs.get("over", False)
        is_paused = gs.get("paused", False)
        items     = []

        # Fondo
        items.append(ft.Container(width=W, height=H,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                colors=["#0d0d2b", "#141450"])))

        # Plataformas
        for p in gs["platforms"]:
            sy = p["wy"] - gs["cam"]
            if -PLATH - 4 < sy < H + PLATH:
                col  = "#ff6b35" if p["type"] == "bouncy" else "#00e5ff"
                gcol = "#22ff6b35" if p["type"] == "bouncy" else "#2200e5ff"
                items.append(ft.Container(left=p["wx"]-3, top=sy-3,
                    width=p["w"]+6, height=PLATH+6, bgcolor=gcol, border_radius=5))
                items.append(ft.Container(left=p["wx"], top=sy,
                    width=p["w"], height=PLATH, bgcolor=col, border_radius=3))
                items.append(ft.Container(left=p["wx"]+4, top=sy+2,
                    width=p["w"]-8, height=3, bgcolor="#66ffffff", border_radius=2))

        # Bolitas rojas
        for b in gs["balls"]:
            bsy = b["wy"] - gs["cam"]
            if -BALL_R - 4 < bsy < H + BALL_R:
                d = BALL_R * 2
                items.append(ft.Container(left=b["wx"]-BALL_R-4, top=bsy-BALL_R-4,
                    width=d+8, height=d+8, bgcolor="#33ff0000", border_radius=BALL_R+4))
                items.append(ft.Container(left=b["wx"]-BALL_R, top=bsy-BALL_R,
                    width=d, height=d, bgcolor="#ff2222", border_radius=BALL_R,
                    border=ft.border.all(2, "#ff7777")))
                items.append(ft.Container(left=b["wx"]-BALL_R+3, top=bsy-BALL_R+3,
                    width=5, height=5, bgcolor="#ffbbbb", border_radius=3))

        # Power-ups — imágenes PNG desde assets/
        for pu in gs["powerups"]:
            psy = pu["wy"] - gs["cam"]
            if -40 < psy < H + 40:
                is_shield = pu["type"] == "shield"
                img_src   = "ESCUDO.png" if is_shield else "JETPACK.png"

                if is_shield:
                    # Escudo: halo azul, 56px
                    items.append(ft.Container(
                        left=pu["wx"] - 28, top=psy - 28,
                        width=56, height=56,
                        bgcolor="#880099ee", border_radius=28))
                    items.append(ft.Container(
                        left=pu["wx"] - 24, top=psy - 24,
                        width=48, height=48,
                        content=ft.Image(src=img_src, width=48, height=48,
                                         fit=ft.ImageFit.CONTAIN)))
                else:
                    # Jetpack: halo naranja, todo centrado en (wx, psy)
                    items.append(ft.Container(       # halo exterior  84×84
                        left=pu["wx"] - 42, top=psy - 42,
                        width=84, height=84,
                        bgcolor="#44ff7700", border_radius=42))
                    items.append(ft.Container(       # halo interior  68×68
                        left=pu["wx"] - 34, top=psy - 34,
                        width=68, height=68,
                        bgcolor="#99ff8800", border_radius=34,
                        border=ft.border.all(2, "#ffaa00")))
                    items.append(ft.Container(       # imagen: mismo tamaño que halo exterior
                        left=pu["wx"] - 42, top=psy - 42,
                        width=84, height=84,
                        alignment=ft.alignment.center,
                        content=ft.Image(src=img_src, width=72, height=72,
                                         fit=ft.ImageFit.CONTAIN)))

        # Letras
        for l in gs["letters"]:
            sy = l["wy"] - gs["cam"]
            if -30 < sy < H + 30:
                items.append(ft.Container(left=l["wx"]-5, top=sy-5,
                    width=30, height=30, bgcolor="#55ffd700",
                    border_radius=15, border=ft.border.all(1, "#ffd700")))
                items.append(ft.Container(left=l["wx"]+1, top=sy-1,
                    content=ft.Text(l["char"], size=17, color="#ffd700",
                                    weight=ft.FontWeight.BOLD)))

        # ── PERSONAJE ROBOT animado ──────────────────────────────────────────
        px, py = gs["px"], gs["py"]
        vy     = gs.get("vy", 0)

        # Estado de animación
        if vy < -4:   anim = "up"    # subiendo
        elif vy > 3:  anim = "down"  # bajando
        else:         anim = "idle"

        # Halo de escudo
        if gs.get("shield_ttl", 0) > 0:
            items.append(ft.Container(
                left=px - 8, top=py - 8,
                width=PW + 16, height=PH + 16,
                bgcolor="#220099ff", border_radius=22,
                border=ft.border.all(2, "#00aaff")))

        # Cuerpo trapezoidal (parte superior estrecha, inferior ancha)
        items.append(ft.Container(            # parte alta del cuerpo
            left=px + 10, top=py + 18,
            width=12, height=6,
            bgcolor="#ececec",
            border=ft.border.only(
                left=ft.BorderSide(2, "#33ee44"),
                right=ft.BorderSide(2, "#33ee44"),
                top=ft.BorderSide(2, "#33ee44"))))
        items.append(ft.Container(            # base ancha del cuerpo
            left=px + 4, top=py + 23,
            width=24, height=10,
            bgcolor="#e0e0e0",
            border_radius=ft.border_radius.only(bottom_left=7, bottom_right=7),
            border=ft.border.all(2, "#33ee44")))

        # Brazos — posición según estado
        if anim == "up":
            al, ar = py + 10, py + 10    # brazos arriba
        elif anim == "down":
            al, ar = py + 24, py + 24   # brazos abajo-abiertos
        else:
            al, ar = py + 18, py + 18   # posición normal

        # Brazo izquierdo
        items.append(ft.Container(
            left=px - 6, top=al,
            width=9, height=10,
            bgcolor="#d5d5d5", border_radius=4,
            border=ft.border.all(1, "#33ee44")))
        # Puño izquierdo (detalle)
        items.append(ft.Container(
            left=px - 6, top=al + 6,
            width=8, height=5,
            bgcolor="#bbbbbb", border_radius=3,
            border=ft.border.all(1, "#33ee44")))

        # Brazo derecho
        items.append(ft.Container(
            left=px + 29, top=ar,
            width=9, height=10,
            bgcolor="#d5d5d5", border_radius=4,
            border=ft.border.all(1, "#33ee44")))
        # Puño derecho
        items.append(ft.Container(
            left=px + 29, top=ar + 6,
            width=8, height=5,
            bgcolor="#bbbbbb", border_radius=3,
            border=ft.border.all(1, "#33ee44")))

        # Cabeza — oval negra con borde verde
        items.append(ft.Container(
            left=px, top=py,
            width=32, height=22,
            bgcolor="#0a0a0a", border_radius=12,
            border=ft.border.all(2, "#33ee44")))

        # Ojos — se cierran al saltar, se abren al caer
        eye_h   = 5 if anim == "up" else 13
        eye_top = py + (9 if anim == "up" else 4)

        items.append(ft.Container(             # ojo izquierdo
            left=px + 4, top=eye_top,
            width=10, height=eye_h,
            bgcolor="#1acc22", border_radius=5,
            border=ft.border.all(1, "#66ff77")))
        items.append(ft.Container(             # ojo derecho
            left=px + 18, top=eye_top,
            width=10, height=eye_h,
            bgcolor="#1acc22", border_radius=5,
            border=ft.border.all(1, "#66ff77")))

        # Pupilas
        if eye_h > 4:
            pup_h   = max(3, eye_h - 6)
            pup_top = eye_top + 3
            items.append(ft.Container(left=px+7,  top=pup_top, width=4, height=pup_h, bgcolor="#003300", border_radius=2))
            items.append(ft.Container(left=px+21, top=pup_top, width=4, height=pup_h, bgcolor="#003300", border_radius=2))

        # Sonrisa
        items.append(ft.Container(
            left=px + 9, top=py + 18,
            width=14, height=3,
            bgcolor="#33ee44", border_radius=2))

        # Bandana (diadema blanca con borde verde, tiras hacia la izquierda)
        items.append(ft.Container(             # cinta principal
            left=px + 2, top=py - 3,
            width=22, height=5,
            bgcolor="#f5f5f5", border_radius=3,
            border=ft.border.all(1, "#33ee44")))
        items.append(ft.Container(             # cola izquierda de la bandana
            left=px - 5, top=py - 9,
            width=7, height=9,
            bgcolor="#f5f5f5", border_radius=3,
            border=ft.border.all(1, "#33ee44")))
        items.append(ft.Container(             # punta de la cola
            left=px - 8, top=py - 12,
            width=5, height=6,
            bgcolor="#f5f5f5", border_radius=2,
            border=ft.border.all(1, "#33ee44")))

        # ── HUD ──────────────────────────────────────────────────────────────

        # Arriba izquierda: Altura + Récord
        items.append(ft.Container(left=8, top=6, content=ft.Column([
            ft.Text(f"Altura: {gs['score']}", size=15, color="#ffffff",
                    weight=ft.FontWeight.BOLD),
            ft.Text(f"Récord: {record['best_height']}", size=12, color="#00e5ff"),
        ], spacing=0)))

        # Arriba derecha: palabra en ESPAÑOL ← movida arriba
        if gs["target"]:
            tw = gs["target"]
            items.append(ft.Container(right=8, top=6,
                content=ft.Column([
                    ft.Text(f"({TRANSLATIONS.get(tw,'')})", size=13,
                            color="#ffee55", weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.RIGHT),
                    ft.Text(f"✓ {len(gs['found'])}" if gs["found"] else "",
                            size=12, color="#00ff88",
                            text_align=ft.TextAlign.RIGHT),
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END)))

        # Escudo activo — indicador top-center
        if gs.get("shield_ttl", 0) > 0:
            pct = gs["shield_ttl"] / 220
            items.append(ft.Container(
                left=W//2 - 40, top=6, width=80, height=20,
                bgcolor="#220099ff", border_radius=10,
                border=ft.border.all(1, "#00aaff"),
                content=ft.Row([
                    ft.Text("🛡️", size=13),
                    ft.Container(width=int(50 * pct), height=8,
                                 bgcolor="#00aaff", border_radius=4),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=3)))

        # Abajo: palabra en INGLÉS completa con guiones (todas las letras)
        if gs["target"]:
            tw   = gs["target"]
            disp = " ".join(c if i < gs["tidx"] else "_"
                            for i, c in enumerate(tw))   # palabra completa
            items.append(ft.Container(left=0, top=H - 52, width=W, bgcolor="#22000000",
                content=ft.Column([
                    ft.Text(f"Forma: {disp}", size=16, color="#ffd700",
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1)))

        # Notificación flotante (palabra completada / power-up)
        if gs["notif"]:
            col = gs["notif"].get("col", "#00ff88")
            items.append(ft.Container(left=0, top=H//2 - 30, width=W,
                content=ft.Row([ft.Container(
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    bgcolor="#cc001122", border_radius=12,
                    border=ft.border.all(1, col),
                    content=ft.Text(gs["notif"]["text"], size=17,
                                    color=col, weight=ft.FontWeight.BOLD),
                )], alignment=ft.MainAxisAlignment.CENTER)))

        # ── Panel PAUSA
        if is_paused and not is_over:
            items.append(ft.Container(width=W, height=H, bgcolor="#aa000030"))
            items.append(ft.Container(
                left=W//2-110, top=H//2-100, width=220, bgcolor="#ee0d0d2b",
                border_radius=16, border=ft.border.all(2, "#00e5ff"), padding=22,
                content=ft.Column([
                    ft.Text("⏸  PAUSA", size=28, color="#00e5ff",
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=14),
                    ft.GestureDetector(on_tap_down=lambda _: toggle_pause(),
                        content=ft.Container(width=170, height=44, border_radius=10,
                            bgcolor="#00e5ff", alignment=ft.alignment.center,
                            content=ft.Text("▶  Continuar", size=15, color="#000000",
                                            weight=ft.FontWeight.BOLD))),
                    ft.Container(height=8),
                    ft.GestureDetector(on_tap_down=lambda _: show_menu(),
                        content=ft.Container(width=170, height=44, border_radius=10,
                            border=ft.border.all(1, "#00e5ff"),
                            alignment=ft.alignment.center,
                            content=ft.Text("🏠  Ir al menú", size=15, color="#00e5ff"))),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4, tight=True)))

        # ── Panel GAME OVER
        if is_over:
            items.append(ft.Container(width=W, height=H, bgcolor="#bb000020"))
            word_rows = [
                ft.Row([
                    ft.Text(w.capitalize(), width=110, color="#ffd700",
                            size=13, weight=ft.FontWeight.BOLD),
                    ft.Text(f"→  {TRANSLATIONS.get(w,'')}", color="#ffffff", size=13),
                ], tight=True)
                for w in gs["found"][:6]
            ]
            items.append(ft.Container(
                left=W//2-145, top=H//2-160, width=290, bgcolor="#f00d0d2b",
                border_radius=16, border=ft.border.all(2, "#00e5ff"), padding=18,
                content=ft.Column([
                    ft.Text("GAME OVER", size=30, color="#ff4444",
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=2),
                    ft.Text(f"🏠  Altura: {gs['score']}", size=16,
                            color="#ffffff", text_align=ft.TextAlign.CENTER),
                    ft.Text(f"📚  Palabras: {len(gs['found'])}", size=14,
                            color="#00ff88", text_align=ft.TextAlign.CENTER),
                    ft.Container(content=ft.Column(word_rows, spacing=3),
                                 visible=len(word_rows) > 0,
                                 padding=ft.padding.symmetric(vertical=4)),
                    ft.Container(height=4),
                    ft.GestureDetector(on_tap_down=lambda _: btn_restart(),
                        content=ft.Container(width=200, height=44, border_radius=10,
                            bgcolor="#00e5ff", alignment=ft.alignment.center,
                            content=ft.Text("▶  REINICIAR", size=16, color="#000000",
                                            weight=ft.FontWeight.BOLD))),
                    ft.Container(height=2),
                    ft.GestureDetector(on_tap_down=lambda _: show_menu(),
                        content=ft.Container(width=200, height=44, border_radius=10,
                            border=ft.border.all(1, "#00e5ff"),
                            alignment=ft.alignment.center,
                            content=ft.Text("🏠  Ir al menú", size=15, color="#00e5ff"))),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=7, tight=True)))

        game_stack.controls = items
        try:
            game_stack.update()
        except Exception:
            pass

    # ── LOOP ─────────────────────────────────────────────────────────────────
    running = {"v": True}

    eyes_img  = ft.Image(src=SECUENCIA_OJOS[0], width=160, height=160,
                         opacity=1, animate_opacity=800)
    text_home = ft.Text("HOME", size=54, weight=ft.FontWeight.BOLD,
                        color="#00e5ff", opacity=0, animate_opacity=800)
    text_jump = ft.Text("JUMP", size=54, weight=ft.FontWeight.BOLD,
                        color="#ffd700", opacity=0, animate_opacity=800)

    def _restart_anim():
        """Reinicia la animación de ojos del menú."""
        gs["anim"].update({"index": 0, "last_time": 0, "complete": False})
        eyes_img.opacity  = 1
        eyes_img.src      = SECUENCIA_OJOS[0]
        text_home.opacity = 0
        text_jump.opacity = 0
        try:
            eyes_img.update(); text_home.update(); text_jump.update()
        except Exception:
            pass

    def game_loop():
        playing = False
        while running["v"]:
            c = cmd["v"]
            if c == "start":
                cmd["v"] = None; playing = True; loop_paused.clear()
                menu_idle["in_menu"] = False
            elif c == "stop":
                cmd["v"] = None; playing = False; loop_paused.set()

            if playing:
                if gs.get("over") or gs.get("paused"):
                    render(); time.sleep(0.1)
                else:
                    step(); render(); time.sleep(TICK)
            else:
                # ── Animación de ojos (primera vez o repetición por idle)
                if not gs["anim"]["complete"]:
                    now = time.time()
                    if gs["anim"]["last_time"] == 0:
                        gs["anim"]["last_time"] = now
                    if now - gs["anim"]["last_time"] >= TIME_PER_FRAME:
                        gs["anim"]["index"]    += 1
                        gs["anim"]["last_time"] = now
                        idx = gs["anim"]["index"]
                        if idx < len(SECUENCIA_OJOS):
                            eyes_img.src = SECUENCIA_OJOS[idx]
                            try: eyes_img.update()
                            except Exception: pass
                        else:
                            gs["anim"]["complete"] = True
                            eyes_img.opacity       = 0
                            text_home.opacity      = 1
                            text_jump.opacity      = 1
                            menu_idle["last_action"] = time.time()
                            try:
                                eyes_img.update()
                                text_home.update()
                                text_jump.update()
                            except Exception: pass

                # ── Idle 15 s → repetir animación
                elif menu_idle["in_menu"]:
                    if time.time() - menu_idle["last_action"] > MENU_IDLE_SECS:
                        _restart_anim()

                time.sleep(0.05)

    threading.Thread(target=game_loop, daemon=True).start()

    # ── Controles ─────────────────────────────────────────────────────────────
    def toggle_pause():
        if not gs.get("over"):
            gs["paused"] = not gs.get("paused", False)

    def btn_restart():
        reset_gs(); gen_platforms(); pick_target()
        cmd["v"] = "start"

    def on_key(e: ft.KeyboardEvent):
        menu_idle["last_action"] = time.time()   # reset idle
        if gs.get("over"):
            if e.key == " ": btn_restart()
        elif e.key in ("Escape", "P", "p"):
            toggle_pause()
        elif not gs.get("paused"):
            if e.key == "Arrow Left":
                gs["left"] = True;  gs["right"] = False
            elif e.key == "Arrow Right":
                gs["right"] = True; gs["left"]  = False

    page.on_keyboard_event = on_key

    # ── show_game ─────────────────────────────────────────────────────────────
    def show_game():
        menu_idle["in_menu"] = False
        page.controls.clear()
        page.add(ft.Column([
            game_stack,
            ft.Container(
                height=100, bgcolor="#0a0a22",
                border=ft.border.only(top=ft.BorderSide(1, "#22ffffff")),
                content=ft.Row([
                    ft.GestureDetector(expand=True,
                        content=ft.Container(height=100, bgcolor="#1a1a40",
                            alignment=ft.alignment.center,
                            border_radius=ft.border_radius.only(top_right=20, bottom_right=20),
                            content=ft.Icon(ft.Icons.ARROW_BACK_IOS_NEW,
                                            color="#00e5ff", size=45)),
                        on_tap_down=lambda _: gs.update({"left": True,  "right": False}),
                        on_tap_up=  lambda _: gs.update({"left": False}),
                        on_pan_end= lambda _: gs.update({"left": False})),
                    ft.GestureDetector(
                        content=ft.Container(width=90, height=90, bgcolor="#0f0f2e",
                            alignment=ft.alignment.center,
                            shape=ft.BoxShape.CIRCLE,
                            border=ft.border.all(2, "#33ffffff"),
                            content=ft.Column([
                                ft.Icon(ft.Icons.PAUSE_CIRCLE_OUTLINE,
                                        color="#00e5ff", size=35),
                                ft.Text("PAUSA", size=10, color="#44ffffff",
                                        weight=ft.FontWeight.BOLD),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                               alignment=ft.MainAxisAlignment.CENTER, spacing=-2)),
                        on_tap_down=lambda _: toggle_pause()),
                    ft.GestureDetector(expand=True,
                        content=ft.Container(height=100, bgcolor="#1a1a40",
                            alignment=ft.alignment.center,
                            border_radius=ft.border_radius.only(top_left=20, bottom_left=20),
                            content=ft.Icon(ft.Icons.ARROW_FORWARD_IOS,
                                            color="#00e5ff", size=45)),
                        on_tap_down=lambda _: gs.update({"right": True, "left": False}),
                        on_tap_up=  lambda _: gs.update({"right": False}),
                        on_pan_end= lambda _: gs.update({"right": False})),
                ], spacing=5, alignment=ft.MainAxisAlignment.CENTER, expand=True)),
        ], spacing=0))
        page.update()

    def start_game():
        reset_gs(); gen_platforms(); pick_target()
        show_game()
        cmd["v"] = "start"

    # ── Selección de categorías ───────────────────────────────────────────────
    def show_category_select():
        cmd["v"] = "stop"
        menu_idle["in_menu"] = False

        def toggle_cat(cat):
            if cat in sel_cats["v"]:
                if len(sel_cats["v"]) > 1: sel_cats["v"].remove(cat)
            else:
                sel_cats["v"].append(cat)
            show_category_select()

        def make_row(cat):
            selected = cat in sel_cats["v"]
            words    = VOCABULARY[cat]
            preview  = ", ".join(w.capitalize() for w in words[:3]) + "…"
            return ft.GestureDetector(
                on_tap_down=lambda _, c=cat: toggle_cat(c),
                content=ft.Container(
                    width=320, padding=9,
                    bgcolor="#22ffffff" if selected else "#0d0d2b",
                    border_radius=10,
                    border=ft.border.all(2 if selected else 1,
                                         "#00e5ff" if selected else "#33ffffff"),
                    content=ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE if selected
                                else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                color="#00ff88" if selected else "#44ffffff", size=22),
                        ft.Container(width=8),
                        ft.Column([
                            ft.Text(cat, size=14,
                                    color="#ffffff" if selected else "#88ffffff",
                                    weight=ft.FontWeight.BOLD),
                            ft.Text(f"{len(words)} palabras · {preview}",
                                    size=10, color="#55ffffff"),
                        ], spacing=1, tight=True),
                    ], tight=True)))

        page.controls.clear()
        page.add(ft.Container(expand=True, bgcolor="#0d0d2b",
            content=ft.Column([
                ft.Container(height=28),
                ft.Text("🏠  ¿Qué habitación practicar?", size=18,
                        color="#00e5ff", weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER),
                ft.Text("Selecciona una o más categorías", size=12,
                        color="#66ffffff", text_align=ft.TextAlign.CENTER),
                ft.Container(height=14),
                *[make_row(cat) for cat in VOCABULARY],
                ft.Container(height=18),
                ft.GestureDetector(on_tap_down=lambda _: start_game(),
                    content=ft.Container(width=230, height=52, border_radius=12,
                        bgcolor="#00e5ff", alignment=ft.alignment.center,
                        content=ft.Text("▶  JUGAR", size=18, color="#000000",
                                        weight=ft.FontWeight.BOLD))),
                ft.Container(height=8),
                ft.GestureDetector(on_tap_down=lambda _: show_menu(),
                    content=ft.Container(width=200, height=44, border_radius=10,
                        border=ft.border.all(1, "#44ffffff"),
                        alignment=ft.alignment.center,
                        content=ft.Text("← Volver al menú", size=14, color="#88ffffff"))),
                ft.Container(height=16),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=8, scroll=ft.ScrollMode.AUTO)))
        page.update()

    # ── Menú principal ────────────────────────────────────────────────────────
    def show_menu(restart_anim=True):
        cmd["v"] = "stop"
        if restart_anim:
            _restart_anim()
        menu_idle["in_menu"]     = True
        menu_idle["last_action"] = time.time()

        title_stack = ft.Stack([
            ft.Container(content=eyes_img,
                         alignment=ft.alignment.center, width=W, height=180),
            ft.Container(content=ft.Column([text_home, text_jump],
                             horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=-15),
                         alignment=ft.alignment.center, width=W, height=180),
        ], width=W, height=180)

        total_words = sum(len(v) for v in VOCABULARY.values())
        page.controls.clear()
        page.add(ft.Container(expand=True,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                colors=["#0d0d2b", "#1a1a4e"]),
            content=ft.Column([
                ft.Container(height=36),
                title_stack,
                ft.Container(height=4),
                ft.Text("Salta · Recoge letras · Forma palabras en inglés",
                        size=13, color="#88ffffff", text_align=ft.TextAlign.CENTER),
                ft.Container(height=20),
                ft.Container(padding=16, bgcolor="#22ffffff", border_radius=14, width=270,
                    content=ft.Column([
                        ft.Text(f"🏆  Récord: {record['best_height']}",
                                size=20, color="#ffd700", weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER),
                        ft.Text(f"📚  Palabras: {len(record['words_found'])} / {total_words}",
                                size=14, color="#00ff88", text_align=ft.TextAlign.CENTER),
                        ft.Text(f"🎮  Partidas: {record.get('total_games',0)}",
                                size=13, color="#aaffffff", text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6)),
                ft.Container(height=22),
                ft.GestureDetector(
                    on_tap_down=lambda _: (
                        menu_idle.update({"last_action": time.time()}),
                        show_category_select()
                    ),
                    content=ft.Container(width=230, height=58, border_radius=14,
                        bgcolor="#00e5ff", alignment=ft.alignment.center,
                        content=ft.Text("▶  JUGAR", size=21, color="#000000",
                                        weight=ft.FontWeight.BOLD))),
                ft.Container(height=10),
                ft.GestureDetector(
                    on_tap_down=lambda _: show_words_inline(),
                    content=ft.Container(width=280, height=44, border_radius=10,
                        border=ft.border.all(1, "#00e5ff"),
                        alignment=ft.alignment.center,
                        content=ft.Text("📖  VER PALABRAS ENCONTRADAS",
                                        size=13, color="#00e5ff"))),
                ft.Container(height=28),
                # ── Botón "Cómo jugar" desplegable
                ft.GestureDetector(
                    on_tap_down=lambda _: (
                        menu_state.update({"htop": not menu_state["htop"]}),
                        show_menu(False)      # ← False = no reinicia la animación del título
                    ),
                    content=ft.Container(
                        width=260, height=44, border_radius=12,
                        bgcolor="#1a1a4e",
                        border=ft.border.all(2, "#00e5ff"),
                        alignment=ft.alignment.center,
                        content=ft.Row([
                            ft.Text("Cómo jugar", size=15, color="#00e5ff",
                                    weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "  ▲" if menu_state["htop"] else "  ▼",
                                size=15, color="#00e5ff",
                                weight=ft.FontWeight.BOLD),
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=0))),

                # ── Contenido desplegable (visible solo si htop=True)
                *([ 
                    ft.Container(height=10),
                    ft.Text("Las letras doradas aparecen en orden sobre\n"
                            "las plataformas. ¡Recógelas en secuencia!",
                            size=12, color="#88ffffff",
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                    # Normal / Bouncy
                    ft.Row([
                        ft.Container(width=18, height=18, bgcolor="#00e5ff", border_radius=4),
                        ft.Text("  Normal  ", size=12, color="#ccffffff"),
                        ft.Container(width=18, height=18, bgcolor="#ff6b35", border_radius=4),
                        ft.Text("  Bouncy = salto extra", size=12, color="#ccffffff"),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                    ft.Container(height=8),
                    # Escudo
                    ft.Row([
                        ft.Image(src="ESCUDO.png", width=46, height=46,
                                 fit=ft.ImageFit.CONTAIN),
                        ft.Container(width=8),
                        ft.Text("Escudo\n¡Invulnerable!", size=13,
                                color="#ccffffff", text_align=ft.TextAlign.LEFT),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=0),
                    ft.Container(height=8),
                    # Jetpack
                    ft.Row([
                        ft.Image(src="JETPACK.png", width=68, height=68,
                                 fit=ft.ImageFit.CONTAIN),
                        ft.Container(width=8),
                        ft.Text("Jetpack\n¡Subida enorme!", size=13,
                                color="#ccffffff", text_align=ft.TextAlign.LEFT),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=0),
                    ft.Container(height=8),
                    # Bolita roja
                    ft.Row([
                        ft.Container(width=22, height=22, bgcolor="#ff2222",
                                     border_radius=11,
                                     border=ft.border.all(2, "#ff7777")),
                        ft.Container(width=8),
                        ft.Text("Bolita roja = ¡PELIGRO!", size=13,
                                color="#ccffffff"),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=0),
                    ft.Container(height=6),
                ] if menu_state["htop"] else []),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=6, scroll=ft.ScrollMode.AUTO)))
        page.update()

    # ── Palabras encontradas ─────────────────────────────────────────────────
    def show_words_inline():
        menu_idle["in_menu"] = False
        found_set   = set(record.get("words_found", []))
        total_words = sum(len(v) for v in VOCABULARY.values())
        sections    = []

        for cat, words in VOCABULARY.items():
            found_here = [w for w in words if w in found_set]
            sections.append(ft.Container(
                width=320,
                padding=ft.padding.symmetric(horizontal=12, vertical=7),
                bgcolor="#1a1a50", border_radius=8,
                margin=ft.margin.only(top=6),
                content=ft.Row([
                    ft.Text(cat, size=15, color="#00e5ff",
                            weight=ft.FontWeight.BOLD, expand=True),
                    ft.Text(f"{len(found_here)}/{len(words)}", size=13,
                            color="#00ff88" if len(found_here)==len(words) else "#ffd700"),
                ])))
            if found_here:
                for w in sorted(found_here):
                    sections.append(ft.Container(width=320,
                        padding=ft.padding.only(left=22, right=10, top=3, bottom=3),
                        content=ft.Row([
                            ft.Text("✓", color="#00ff88", size=13, width=18),
                            ft.Text(w.capitalize(), width=105, color="#ffd700",
                                    weight=ft.FontWeight.BOLD, size=13),
                            ft.Text(f"→  {TRANSLATIONS.get(w,'')}", color="#ffffff", size=13),
                        ], tight=True)))
            else:
                sections.append(ft.Container(width=320,
                    padding=ft.padding.only(left=22, top=3, bottom=3),
                    content=ft.Text("(ninguna encontrada aún)", size=12, color="#44ffffff")))

        page.controls.clear()
        page.add(ft.Container(expand=True, bgcolor="#0d0d2b",
            content=ft.Column([
                ft.Container(height=24),
                ft.Text("📚 Palabras Encontradas", size=22, color="#00e5ff",
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text(f"{len(found_set)} de {total_words} totales",
                        size=13, color="#88ffffff", text_align=ft.TextAlign.CENTER),
                ft.Container(height=8),
                ft.Container(width=340, height=460,
                    content=ft.Column(sections, scroll=ft.ScrollMode.AUTO, spacing=0)),
                ft.Container(height=12),
                ft.GestureDetector(on_tap_down=lambda _: show_menu(),
                    content=ft.Container(width=220, height=44, border_radius=10,
                        bgcolor="#22ffffff", alignment=ft.alignment.center,
                        content=ft.Text("← Volver al menú", size=14, color="#ffffff"))),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=0, scroll=ft.ScrollMode.AUTO)))
        page.update()

    show_menu()


ft.app(main, assets_dir="assets")