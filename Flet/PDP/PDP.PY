#v1.12
#Jared Hdz Ctr "Pandajar"
#python 3.14

import flet as ft
import random
import json
import os
import time
import threading

# ─── VOCABULARY
VOCABULARY = {
    "Bathroom":     ["SHOWER","BATHTUB","TOILET","SINK","MIRROR","TOWEL","TOOTHBRUSH"],
    "Kitchen":      ["FRIDGE","STOVE","OVEN","MICROWAVE","DISHWASHER","CUPBOARD","COUNTERTOP"],
    "Living Room":  ["SOFA","ARMCHAIR","RUG","BOOKSHELF","CURTAINS"],
    "Bedroom":      ["BED","PILLOW","WARDROBE","NIGHTSTAND","LAMP","BLANKET","HANGER"],
    "Dining Room":  ["CHAIR","TABLECLOTH","SILVERWARE","PLATE","GLASS"],
    "Laundry Room": ["DRYER","IRON","WASHER"],
}
ALL_WORDS = [w for cat in VOCABULARY.values() for w in cat]

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

# ─── RECORD
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

# ─── MAIN 
def main(page: ft.Page):
    page.title            = "Home Jump"
    page.bgcolor          = "#0d0d2b"
    page.padding          = 0
    page.window.width     = W + 20
    page.window.height    = H + 130
    page.window.resizable = False

    record = load_record()

    # scene: "menu" | "playing" | "over" | "restart"
    scene = {"v": "menu"}
    gs    = {}

    # ── state reset
    def reset_gs():
        gs.update({
            "px": float(W // 2 - PW // 2),
            "py": float(H - 160),
            "vy": 0.0, "cam": 0.0, "score": 0,
            "left": False, "right": False,
            "platforms": [], "letters": [],
            "target": None, "tidx": 0,
            "collected": [], "found": [], "notif": None,
        })

    def pick_target():
        rem = [w for w in ALL_WORDS if w not in gs["found"]] or ALL_WORDS[:]
        gs["target"] = random.choice(rem)
        gs["tidx"] = 0
        gs["collected"] = []

    # ── platforms
    def gen_platforms():
        gs["platforms"].append({"wx": 0, "wy": H - 30, "w": W, "type": "ground"})
        wy = H - 160
        for _ in range(22):
            wx = random.randint(10, W - PLATW - 10)
            gs["platforms"].append({"wx": wx, "wy": wy, "w": PLATW, "type": "normal"})
            wy -= random.randint(72, 112)

    def extend_platforms():
        if not gs["platforms"]: return
        top = min(p["wy"] for p in gs["platforms"])
        while top > gs["cam"] - 350:
            top -= random.randint(70, 120)
            wx    = random.randint(10, W - PLATW - 10)
            ptype = "bouncy" if random.random() < 0.18 else "normal"
            gs["platforms"].append({"wx": wx, "wy": top, "w": PLATW, "type": ptype})
            if gs["target"] and random.random() < 0.60:
                tw  = gs["target"]
                idx = gs["tidx"] % len(tw)
                gs["letters"].append({"wx": wx + PLATW//2 - 9,
                                      "wy": top - 34,
                                      "char": tw[idx], "lidx": idx})
        limit = gs["cam"] + H + 250
        gs["platforms"] = [p for p in gs["platforms"] if p["wy"] < limit]
        gs["letters"]   = [l for l in gs["letters"]   if l["wy"]  < limit]

    # ── physics 
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
                pb, pb_prev = wpy + PH, wpy + PH - gs["vy"]
                if (gs["px"] + PW > p["wx"] + 4 and
                    gs["px"]       < p["wx"] + p["w"] - 4 and
                    pb_prev <= p["wy"] <= pb):
                    gs["vy"] = JUMP * (1.4 if p["type"] == "bouncy" else 1.0)

        if gs["py"] < H * 0.42:
            d = H * 0.42 - gs["py"]
            gs["cam"] -= d; gs["py"] += d
            gs["score"] = max(gs["score"], int(-gs["cam"] / 10))

        wpy = gs["py"] + gs["cam"]
        keep = []
        for l in gs["letters"]:
            hit = (gs["px"] < l["wx"]+22 and gs["px"]+PW > l["wx"] and
                   wpy < l["wy"]+22 and wpy+PH > l["wy"])
            if hit and gs["target"] and l["lidx"] == gs["tidx"]:
                gs["collected"].append(l["char"])
                gs["tidx"] += 1
                if gs["tidx"] >= len(gs["target"]):
                    tw = gs["target"]
                    gs["found"].append(tw)
                    gs["notif"] = {"text": f"✓  {tw}  =  {TRANSLATIONS.get(tw,'')}", "ttl": 110}
                    pick_target()
            else:
                keep.append(l)
        gs["letters"] = keep

        if gs["notif"]:
            gs["notif"]["ttl"] -= 1
            if gs["notif"]["ttl"] <= 0:
                gs["notif"] = None

        extend_platforms()

        if gs["py"] > H + 90:
            do_end_game()

    def do_end_game():
        scene["v"] = "over"
        record["total_games"] = record.get("total_games", 0) + 1
        if gs["score"] > record["best_height"]:
            record["best_height"] = gs["score"]
        for w in gs["found"]:
            if w not in record["words_found"]:
                record["words_found"].append(w)
        save_record(record)

    # ── render 
    # game_stack is the ONLY thing we ever touch for rendering.
    # No page.overlay, no AlertDialog.
    game_stack = ft.Stack(width=W, height=H, clip_behavior=ft.ClipBehavior.HARD_EDGE)

    def render(is_over=False):
        items = []

        # background
        items.append(ft.Container(width=W, height=H,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                colors=["#0d0d2b", "#141450"])))

        # platforms
        for p in gs["platforms"]:
            sy = p["wy"] - gs["cam"]
            if -PLATH-4 < sy < H+PLATH:
                col  = "#ff6b35" if p["type"]=="bouncy" else "#00e5ff"
                gcol = "#22ff6b35" if p["type"]=="bouncy" else "#2200e5ff"
                items.append(ft.Container(left=p["wx"]-3, top=sy-3,
                    width=p["w"]+6, height=PLATH+6, bgcolor=gcol, border_radius=5))
                items.append(ft.Container(left=p["wx"], top=sy,
                    width=p["w"], height=PLATH, bgcolor=col, border_radius=3))
                items.append(ft.Container(left=p["wx"]+4, top=sy+2,
                    width=p["w"]-8, height=3, bgcolor="#66ffffff", border_radius=2))

        # letters
        for l in gs["letters"]:
            sy = l["wy"] - gs["cam"]
            if -30 < sy < H+30:
                items.append(ft.Container(left=l["wx"]-5, top=sy-5,
                    width=30, height=30, bgcolor="#55ffd700",
                    border_radius=15, border=ft.border.all(1,"#ffd700")))
                items.append(ft.Container(left=l["wx"]+1, top=sy-1,
                    content=ft.Text(l["char"], size=17, color="#ffd700",
                                    weight=ft.FontWeight.BOLD)))

        # player
        items.append(ft.Container(
            left=gs["px"], top=gs["py"], width=PW, height=PH,
            bgcolor="#ffffff", border_radius=6,
            border=ft.border.all(2,"#00e5ff"),
            content=ft.Column([
                ft.Container(height=4),
                ft.Row([
                    ft.Container(width=7, height=7, bgcolor="#000000", border_radius=4),
                    ft.Container(width=4),
                    ft.Container(width=7, height=7, bgcolor="#000000", border_radius=4),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=0),
            ], spacing=0),
        ))

        # HUD
        items.append(ft.Container(left=8, top=6, content=ft.Column([
            ft.Text(f"Altura: {gs['score']}", size=15, color="#ffffff",
                    weight=ft.FontWeight.BOLD),
            ft.Text(f"Récord: {record['best_height']}", size=12, color="#00e5ff"),
        ], spacing=0)))

        if gs["found"]:
            items.append(ft.Container(right=8, top=6,
                content=ft.Text(f"✓ {len(gs['found'])}", size=13,
                                color="#00ff88", weight=ft.FontWeight.BOLD)))

        # target word bar
        if gs["target"]:
            tw   = gs["target"]
            disp = " ".join(c if i < gs["tidx"] else "_" for i, c in enumerate(tw))
            items.append(ft.Container(left=0, top=H-58, width=W, bgcolor="#22000000",
                content=ft.Column([
                    ft.Text(f"Forma:  {disp}", size=15, color="#ffd700",
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Text(f"({TRANSLATIONS.get(tw,'')})", size=12,
                            color="#aaffffff", text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1)))

        # notification
        if gs["notif"]:
            items.append(ft.Container(left=0, top=H//2-30, width=W,
                content=ft.Row([ft.Container(
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    bgcolor="#cc003322", border_radius=12,
                    border=ft.border.all(1,"#00ff88"),
                    content=ft.Text(gs["notif"]["text"], size=17,
                                    color="#00ff88", weight=ft.FontWeight.BOLD),
                )], alignment=ft.MainAxisAlignment.CENTER)))

        # ── GAME OVER overlay — drawn directly in the stack, no dialog 
        if is_over:
            # dark tint
            items.append(ft.Container(width=W, height=H, bgcolor="#cc000015"))

            word_rows = []
            for w in gs["found"][:6]:
                word_rows.append(ft.Row([
                    ft.Text(w.capitalize(), width=110, color="#ffd700",
                            size=13, weight=ft.FontWeight.BOLD),
                    ft.Text(f"→  {TRANSLATIONS.get(w,'')}", color="#ffffff", size=13),
                ], tight=True))

            items.append(ft.Container(
                left=W//2 - 145, top=H//2 - 160,
                width=290,
                bgcolor="#f00d0d2b",   # near-opaque dark bg
                border_radius=16,
                border=ft.border.all(2, "#00e5ff"),
                padding=18,
                content=ft.Column([
                    ft.Text("GAME OVER", size=30, color="#ff4444",
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=2),
                    ft.Text(f"  Altura: {gs['score']}",
                            size=16, color="#ffffff",
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(f"  Palabras: {len(gs['found'])}",
                            size=14, color="#00ff88",
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(
                        content=ft.Column(word_rows, spacing=3),
                        visible=len(word_rows) > 0,
                        padding=ft.padding.symmetric(vertical=4)),
                    ft.Container(height=4),
                    # REINICIAR button — sets scene to "restart", render loop handles it
                    ft.ElevatedButton(
                        "▶  REINICIAR",
                        width=200,
                        style=ft.ButtonStyle(
                            bgcolor="#00e5ff", color="#000000",
                            text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
                            shape=ft.RoundedRectangleBorder(radius=10),
                        ),
                        on_click=lambda _: do_restart(),
                    ),
                    ft.Container(height=2),
                    ft.OutlinedButton(
                        "  Ir al menú",
                        width=200,
                        style=ft.ButtonStyle(
                            color="#00e5ff",
                            side=ft.BorderSide(1,"#00e5ff"),
                            shape=ft.RoundedRectangleBorder(radius=10),
                        ),
                        on_click=lambda _: show_menu(),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=7, tight=True),
            ))

        game_stack.controls = items
        try:
            game_stack.update()
        except Exception:
            pass

    # ── actions called by buttons
    def do_restart():
        """Button in the in-stack game-over overlay."""
        scene["v"] = "restart"

    # ── single persistent loop
    def game_loop():
        while True:
            s = scene["v"]

            if s == "playing":
                step()
                render(is_over=False)
                time.sleep(TICK)

            elif s == "over":
                # Render the game-over overlay on top of the frozen frame
                render(is_over=True)
                time.sleep(0.1)

            elif s == "restart":
                # Full reset — no sleep on UI thread, everything here
                reset_gs()
                gen_platforms()
                pick_target()
                render(is_over=False)   # draw first clean frame
                scene["v"] = "playing"

            else:  # "menu"
                time.sleep(0.1)

    threading.Thread(target=game_loop, daemon=True).start()

    # ── keyboard 
    def on_key(e: ft.KeyboardEvent):
        if scene["v"] == "playing":
            if e.key == "Arrow Left":
                gs["left"] = True; gs["right"] = False
            elif e.key == "Arrow Right":
                gs["right"] = True; gs["left"] = False
        elif scene["v"] == "over" and e.key == " ":
            do_restart()

    page.on_keyboard_event = on_key

    # ── game screen (static chrome, stack is reused)
    def show_game():
        page.controls.clear()
        page.add(ft.Column([
            game_stack,
            ft.Container(
                height=88, bgcolor="#0a0a22",
                border=ft.border.only(top=ft.BorderSide(1,"#22ffffff")),
                content=ft.Row([
                    ft.GestureDetector(
                        content=ft.Container(
                            width=130, height=86, bgcolor="#1a1a40",
                            border_radius=ft.border_radius.only(top_right=14, bottom_right=14),
                            content=ft.Icon(ft.Icons.ARROW_BACK_IOS_NEW, color="#00e5ff", size=36),
                            alignment=ft.alignment.center,
                        ),
                        on_tap_down=lambda _: gs.update({"left":True,  "right":False}),
                        on_tap_up=  lambda _: gs.update({"left":False}),
                        on_pan_end= lambda _: gs.update({"left":False}),
                    ),
                    ft.Container(expand=True, content=ft.Column([
                        ft.Text("◀  ▶", size=12, color="#44ffffff",
                                text_align=ft.TextAlign.CENTER),
                        ft.Text("mover", size=10, color="#33ffffff",
                                text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                       alignment=ft.MainAxisAlignment.CENTER, spacing=0)),
                    ft.GestureDetector(
                        content=ft.Container(
                            width=130, height=86, bgcolor="#1a1a40",
                            border_radius=ft.border_radius.only(top_left=14, bottom_left=14),
                            content=ft.Icon(ft.Icons.ARROW_FORWARD_IOS, color="#00e5ff", size=36),
                            alignment=ft.alignment.center,
                        ),
                        on_tap_down=lambda _: gs.update({"right":True, "left":False}),
                        on_tap_up=  lambda _: gs.update({"right":False}),
                        on_pan_end= lambda _: gs.update({"right":False}),
                    ),
                ], spacing=0),
            ),
        ], spacing=0))
        page.update()

    def start_game():
        reset_gs()
        gen_platforms()
        pick_target()
        show_game()
        scene["v"] = "playing"

    # ── menu
    def show_menu():
        scene["v"] = "menu"
        page.controls.clear()
        page.add(ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                colors=["#0d0d2b","#1a1a4e"]),
            content=ft.Column([
                ft.Container(height=36),
                ft.Text("HOME", size=54, weight=ft.FontWeight.BOLD,
                        color="#00e5ff", text_align=ft.TextAlign.CENTER),
                ft.Text("JUMP", size=54, weight=ft.FontWeight.BOLD,
                        color="#ffd700", text_align=ft.TextAlign.CENTER),
                ft.Container(height=4),
                ft.Text("Salta · Recoge letras · Forma palabras en inglés",
                        size=13, color="#88ffffff", text_align=ft.TextAlign.CENTER),
                ft.Container(height=20),
                ft.Container(
                    padding=16, bgcolor="#22ffffff", border_radius=14, width=270,
                    content=ft.Column([
                        ft.Text(f"  Récord: {record['best_height']}",
                                size=20, color="#ffd700", weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER),
                        ft.Text(f"  Palabras: {len(record['words_found'])} / {len(ALL_WORDS)}",
                                size=14, color="#00ff88", text_align=ft.TextAlign.CENTER),
                        ft.Text(f"  Partidas: {record.get('total_games',0)}",
                                size=13, color="#aaffffff", text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6)),
                ft.Container(height=22),
                ft.ElevatedButton("▶  JUGAR", width=230, height=58,
                    style=ft.ButtonStyle(
                        bgcolor="#00e5ff", color="#000000",
                        text_style=ft.TextStyle(size=21, weight=ft.FontWeight.BOLD),
                        shape=ft.RoundedRectangleBorder(radius=14)),
                    on_click=lambda _: start_game()),
                ft.Container(height=10),
                ft.OutlinedButton("  VER PALABRAS ENCONTRADAS", width=280,
                    style=ft.ButtonStyle(
                        color="#00e5ff", side=ft.BorderSide(1,"#00e5ff"),
                        shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: show_words_inline()),
                ft.Container(height=28),
                ft.Text("Cómo jugar", size=14, color="#00e5ff",
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Container(height=4),
                ft.Text("Las letras doradas aparecen en orden sobre\n"
                        "las plataformas. ¡Recógelas en secuencia!\n\n"
                        "🟦 Normal   🟧 Bouncy = salto extra",
                        size=12, color="#88ffffff", text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=6, scroll=ft.ScrollMode.AUTO),
        ))
        page.update()

    def show_words_inline():
        """Show found words inside the menu (no overlay/dialog)."""
        words = record.get("words_found", [])
        if not words:
            rows_content = ft.Text("Aún no has encontrado palabras.",
                                   color="#ffffff", size=14,
                                   text_align=ft.TextAlign.CENTER)
        else:
            rows_content = ft.Column([
                ft.Row([
                    ft.Text(w.capitalize(), width=120, color="#ffd700",
                            weight=ft.FontWeight.BOLD, size=14),
                    ft.Text(f"→  {TRANSLATIONS.get(w,'')}", color="#ffffff", size=14),
                ])
                for w in sorted(words)
            ], scroll=ft.ScrollMode.AUTO, height=340, spacing=4)

        page.controls.clear()
        page.add(ft.Container(
            expand=True, bgcolor="#0d0d2b",
            content=ft.Column([
                ft.Container(height=24),
                ft.Text(" Palabras Encontradas", size=22, color="#00e5ff",
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Container(height=12),
                ft.Container(rows_content, width=320, padding=10),
                ft.Container(height=20),
                ft.ElevatedButton("← Volver al menú", width=220,
                    style=ft.ButtonStyle(
                        bgcolor="#22ffffff", color="#ffffff",
                        shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: show_menu()),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=0, scroll=ft.ScrollMode.AUTO),
        ))
        page.update()

    show_menu()


ft.app(main)