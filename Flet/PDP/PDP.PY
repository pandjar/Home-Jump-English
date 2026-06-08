# -*- coding: utf-8 -*-
#v1.40.1
#Jared Hdz Ctr "Pandajar"
#python 3.14

import flet as ft
import random
import json
import os
import time
import threading
import unicodedata

# ─── Constants for game timing, animation, and display limits
ANIMATION_FPS  = 10
TIME_PER_FRAME = 1.0 / ANIMATION_FPS
SECUENCIA_OJOS = [f"ojos_{i}.png" for i in range(30)]
MENU_IDLE_SECS = 15   # segundos sin actividad → reanima el menú
MAX_VISIBLE_LETTERS = 4   # máximo de fichas doradas visibles a la vez en pantalla

# ─── Nueva animación del menú (velocidad reducida)
SECUENCIA_NUEVA = []
for i in range(1, 32):
    if i == 6:
        SECUENCIA_NUEVA.append((f"Animacion_nueva/frame{i}.png", 2.0))  # Hold de 2 segundos
    else:
        SECUENCIA_NUEVA.append((f"Animacion_nueva/frame{i}.png", 0.11))  # Más lento

# ─── Animación infinita del menú
SECUENCIA_INFINITA = [("Animacion_Infinita/frame32.png", 5.0)] + [
    (f"Animacion_Infinita/frame{i}.png", 0.10) for i in range(33, 36)
]

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

# Guardar/leer récords locales para mostrar estadísticas de juego.
# ─── CONSTANTS
W, H         = 380, 720
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
    page.window.height    = H + 20
    page.window.resizable = False

    record      = load_record()
    cmd         = {"v": None}  # mensajes simples para el bucle principal
    loop_paused = threading.Event()  # pausa del hilo del juego
    gs          = {
        "anim": {"index": 0, "last_time": 0, "complete": False},
        "anim_nueva": {"index": 0, "last_time": 0, "mode": "normal"}
    }

    # Estado compartido del juego: posiciones, plataformas, objetos y flags.
    # Se actualiza desde múltiples funciones y se renderiza en `render()`.
    
    # Idle tracker para el menú
    menu_idle  = {"last_action": 0.0, "in_menu": False}
    help_state = {"open": False}
    review_state = {"open": False, "cards": [], "answers": {}, "error": "", "already_reviewed": False}
    admin_state = {
        "open": False,
        "skip_review": False,
        "ghost": False,
        "mouse_control": False,
        "return_to_game": False,
    }  # modo administrador oculto

    admin_controls = {
        "info": None,
        "skip_text": None,
        "ghost_text": None,
        "mouse_text": None,
    }

    sel_cats = {"v": list(VOCABULARY.keys())}

    def safe_update(control):
        """Actualizar un control sin causar errores de socket."""
        if control is None:
            return
        try:
            control.update()
        except (OSError, BrokenPipeError, ConnectionResetError, Exception):
            pass

    def safe_page_update():
        """Actualizar la página sin causar errores de socket."""
        try:
            page.update()
        except (OSError, BrokenPipeError, ConnectionResetError, Exception):
            pass

    def active_words():
        words = [w for cat in sel_cats["v"] for w in VOCABULARY[cat]]
        return sorted(words, key=len)

    def normalize_answer(text: str) -> str:
        value = unicodedata.normalize("NFD", text or "")
        value = ''.join(ch for ch in value if unicodedata.category(ch) != 'Mn')
        return value.strip().lower()

    def start_review_session():
        if review_state["already_reviewed"] or admin_state["skip_review"]:
            start_game()
            return

        found_words = list(record.get("words_found", []))
        if not found_words:
            review_state.update({"open": False, "cards": [], "answers": {}, "error": ""})
            show_category_select()
            return

        review_state.update({
            "open": True,
            "cards": random.sample(found_words, min(3, len(found_words))),
            "answers": {},
            "error": "",
        })
        show_menu(False)

    def close_review_modal():
        review_state["open"] = False
        review_state["error"] = ""
        show_category_select()

    def confirm_review_answers():
        missing = [word for word in review_state["cards"] if not review_state["answers"].get(word, "").strip()]
        if missing:
            review_state["error"] = "Completa todas las respuestas para poder jugar."
            show_menu(False)
            return

        incorrect = []
        for word in review_state["cards"]:
            expected = normalize_answer(TRANSLATIONS.get(word, ""))
            answer = normalize_answer(review_state["answers"].get(word, ""))
            if answer != expected:
                incorrect.append(word)

        if incorrect:
            review_state["error"] = "Hay respuestas incorrectas. Vuelve a intentarlo."
            review_state["open"] = True
            show_menu(False)
            return

        review_state["open"] = False
        review_state["error"] = ""
        review_state["already_reviewed"] = True
        show_category_select()

    def open_help_modal():
        help_state["open"] = True
        show_menu(False)

    def close_help_modal():
        help_state["open"] = False
        show_menu(False)

    def _refresh_admin_overlay():
        if admin_controls["info"] is not None:
            admin_controls["info"].value = get_admin_info()
            admin_controls["skip_text"].value = f"Saltar repaso: {'ON' if admin_state['skip_review'] else 'OFF'}"
            admin_controls["ghost_text"].value = f"Modo invisible: {'ON' if admin_state['ghost'] else 'OFF'}"
            admin_controls["mouse_text"].value = f"Mover con ratón: {'ON' if admin_state['mouse_control'] else 'OFF'}"
            try:
                admin_controls["info"].update()
                admin_controls["skip_text"].update()
                admin_controls["ghost_text"].update()
                admin_controls["mouse_text"].update()
                return
            except Exception:
                pass
        show_menu(False)

    def open_admin_modal():
        admin_state["open"] = True
        admin_state["return_to_game"] = bool(gs.get("platforms")) and not gs.get("over")
        show_menu(False)

    def close_admin_modal():
        admin_state["open"] = False
        admin_state["return_to_game"] = False
        show_menu(False)

    def admin_apply_powerup(kind: str):
        if kind == "shield":
            gs["shield_ttl"] = 220
            gs["notif"] = {"text": "🛡️  ESCUDO ADMINISTRADOR", "ttl": 120, "col": "#00aaff"}
        else:
            gs["vy"] = -32.0
            gs["notif"] = {"text": "🚀  JETPACK ADMINISTRADOR", "ttl": 120, "col": "#ffaa00"}

        should_return = admin_state.get("return_to_game") and not gs.get("over")
        admin_state["open"] = False
        admin_state["return_to_game"] = False
        if should_return:
            show_game()
            cmd["v"] = "start"
        else:
            show_menu(False)

    def toggle_admin_skip_review():
        admin_state["skip_review"] = not admin_state["skip_review"]
        _refresh_admin_overlay()

    def toggle_admin_ghost():
        admin_state["ghost"] = not admin_state["ghost"]
        _refresh_admin_overlay()

    def toggle_admin_mouse_control():
        admin_state["mouse_control"] = not admin_state["mouse_control"]
        try:
            mo = gs.get("mouse_overlay")
            if mo is not None:
                mo.visible = bool(admin_state.get("mouse_control") and not gs.get("paused") and not gs.get("over"))
                try:
                    mo.update()
                except Exception:
                    pass
        except Exception:
            pass
        _refresh_admin_overlay()

    def _mouse_pos(e):
        x = getattr(e, "local_x", None)
        y = getattr(e, "local_y", None)
        if x is None or y is None:
            for attr in ("x", "client_x", "page_x"):
                if x is None:
                    x = getattr(e, attr, None)
            for attr in ("y", "client_y", "page_y"):
                if y is None:
                    y = getattr(e, attr, None)
        if x is None or y is None:
            return None, None
        return float(x), float(y)

    def _player_hit_test(px, py, x, y):
        return px <= x <= px + PW and py <= y <= py + PH

    def _mouse_control_hover(e):
        # No se mueva al pasar el ratón: solo activar el arrastre si se pulsa sobre el personaje.
        return

    def _mouse_control_start(e):
        if not admin_state.get("mouse_control") or gs.get("paused") or gs.get("over"):
            return
        x, y = _mouse_pos(e)
        if x is None or y is None:
            return
        if not _player_hit_test(gs["px"], gs["py"], x, y):
            return
        gs["mouse_dragging"] = True
        gs["mouse_drag_offset"] = x - gs["px"]

    def _mouse_control_pan(e):
        if not admin_state.get("mouse_control") or gs.get("paused") or gs.get("over"):
            return
        if not gs.get("mouse_dragging"):
            return
        x, y = _mouse_pos(e)
        if x is None:
            return
        gs["px"] = max(-PW, min(W, x - gs["mouse_drag_offset"]))

    def _mouse_control_end(e):
        gs["mouse_dragging"] = False

    def get_admin_info() -> str:
        target = gs.get("target") or "(ninguna)"
        score = gs.get("score", 0)
        letters = len(gs.get("letters", []))
        platforms = len(gs.get("platforms", []))
        state = "PAUSA" if gs.get("paused") else "GAME OVER" if gs.get("over") else "JUGANDO" if cmd.get("v") == "start" else "MENU"
        return (
            "Palabra objetivo: " + str(target) + "\n"
            + "Puntaje: " + str(score) + "\n"
            + "Letras en pantalla: " + str(letters) + "\n"
            + "Plataformas: " + str(platforms) + "\n"
            + "Estado: " + str(state) + "\n"
            + "Saltar repaso: " + ("SI" if admin_state["skip_review"] else "NO") + "\n"
            + "Invisibilidad: " + ("SI" if admin_state["ghost"] else "NO") + "\n"
            + "Control raton: " + ("SI" if admin_state["mouse_control"] else "NO")
        )

    def clear_progress():
        # Borra el fichero de récords y limpia el estado en memoria
        try:
            record.clear()
            record.update({"best_height": 0, "words_found": [], "total_games": 0})
            save_record(record)
            gs["notif"] = {"text": "Progreso borrado.", "ttl": 120, "col": "#00ff88"}
        except Exception:
            pass
        # Actualizar la vista del menú para reflejar cambios
        try:
            show_menu()
        except Exception:
            try:
                safe_render()
            except Exception:
                pass

    # ── state ────────────────────────────────────────────────────────────────
    def reset_gs():
        # Restaurar el estado principal del juego al iniciar una partida nueva.
        # Cada clave describe el estado de movimiento, cámara, objetos y powerups.
        gs.update({
            "px": float(W // 2 - PW // 2),
            "py": float(H - 160),
            "vy": 0.0, "cam": 0.0, "score": 0,
            "left": False, "right": False,
            "platforms": [], "letters": [], "balls": [], "powerups": [],
            "target": None, "tidx": 0, "next_letter_idx": 0,
            "collected": [], "collected_positions": set(), "visible_positions": set(), "found": [], "notif": None,
            "over": False, "paused": False,
            "shield_ttl": 0,   # ticks restantes de escudo (>0 = invulnerable)
            "detectors": None,
            "detectors_visible": True,
            "pause_btn_inner": None,
            "mouse_dragging": False,
            "mouse_drag_offset": 0.0,
        })

    def pick_target():
        words = active_words()
        already = set(record.get("words_found", []))
        rem = [w for w in words if w not in already and w not in gs["found"]]
        if not rem:
            gs["target"] = None
            gs["letters"] = []
            return
        gs["target"]    = rem[0]
        gs["tidx"]      = 0
        gs["next_letter_idx"] = 0
        gs["letters"]   = []
        gs["collected"] = []
        gs["collected_positions"] = set()
        gs["visible_positions"] = set()

    # ── platforms, balls & power-ups ─────────────────────────────────────────
    def _rand_type():
        return random.choices(["normal", "bouncy"], weights=[79, 21])[0]

    def _spawn_good_letter(wx, wy, idx):
        if not gs["target"]:
            return
        if idx in gs["visible_positions"]:
            return
        if idx >= len(gs["target"]):
            return
        if len([l for l in gs["letters"] if l["kind"] == "good"]) >= MAX_VISIBLE_LETTERS:
            return

        spawn_x = wx + PLATW // 2 - 9
        spawn_y = wy - 34
        if _overlaps_letter(spawn_x, spawn_y):
            return

        gs["letters"].append({
            "wx": spawn_x,
            "wy": spawn_y,
            "char": gs["target"][idx],
            "lidx": idx,
            "kind": "good",
        })
        gs["visible_positions"].add(idx)

    def _spawn_pending_good_letter(wx, wy):
        if not gs["target"]:
            return
        if len([l for l in gs["letters"] if l["kind"] == "good"]) >= MAX_VISIBLE_LETTERS:
            return

        remaining = [idx for idx in range(len(gs["target"])) if idx not in gs["collected_positions"]]
        if not remaining:
            return

        idx = random.choice(remaining)
        _spawn_good_letter(wx, wy, idx)

    def _spawn_rescue_platform(wx, wy):
        # Genera una plataforma de rescate segura cerca de la plataforma `wx, wy`
        # para darle al jugador una segunda oportunidad después de una letra trampa.
        candidates = []
        for _ in range(60):
            px = random.randint(10, W - PLATW - 10)
            py = wy + random.choice([-110, -90, -70, -40, 40, 70, 90, 110])
            if not (10 <= px <= W - PLATW - 10):
                continue
            if not (0 <= py <= H - 20):
                continue
            if abs(px - wx) < PLATW + 96 and abs(py - wy) < 40:
                continue
            if any(abs(px - p["wx"]) < PLATW - 10 and abs(py - p["wy"]) < 8 for p in gs["platforms"]):
                continue
            candidates.append((px, py))

        if not candidates:
            rescue_x = random.randint(10, W - PLATW - 10)
            rescue_y = max(20, min(H - 20, wy + random.choice([-110, -90, -70, -40, 40, 70, 90, 110])))
            candidates.append((rescue_x, rescue_y))

        rescue_x, rescue_y = random.choice(candidates)
        gs["platforms"].append({
            "wx": rescue_x,
            "wy": rescue_y,
            "w": PLATW,
            "type": "rescue",
        })
        return rescue_x, rescue_y

    def _spawn_trap_letter(wx, wy):
        # Inserta una letra incorrecta sobre una plataforma y crea una plataforma
        # de rescate segura cerca para que el jugador pueda recuperarse.
        if not gs["target"]:
            return
        if any(l["kind"] == "wrong" for l in gs["letters"]):
            return

        lx = wx + PLATW // 2 - 9
        ly = wy - 34
        if any(l["wx"] == lx and l["wy"] == ly for l in gs["letters"]):
            return

        wrong_char = random.choice([c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in gs["target"]])
        gs["letters"].append({
            "wx": lx,
            "wy": ly,
            "char": wrong_char,
            "kind": "wrong",
        })

        rescue_x, rescue_y = _spawn_rescue_platform(wx, wy)

        # Agrupa la trampa con letras correctas cercanas para que no aparezca sola.
        cluster_xs = []
        for offset in (-26, 0, 26):
            candidate = rescue_x + offset
            if 10 <= candidate <= W - PLATW - 10:
                cluster_xs.append(candidate)

        for extra_x in cluster_xs[:2]:
            _spawn_pending_good_letter(extra_x, rescue_y)

    def _spawn_ball(world_y):
        vx = random.choice([-1, 1]) * random.uniform(2.0, 4.0)
        gs["balls"].append({
            "wx": float(random.randint(BALL_R + 4, W - BALL_R - 4)),
            "wy": float(world_y), "vx": vx,
        })

    def _overlaps_letter(wx, wy):
        for l in gs["letters"]:
            if abs(wx - l["wx"]) < 24 and abs(wy - l["wy"]) < 24:
                return True
        return False

    def _spawn_powerup(world_x, world_y):
        base_x = max(24, min(W - 24, int(world_x)))
        base_y = float(world_y)
        candidates = [
            (base_x, base_y),
            (base_x - 20, base_y),
            (base_x + 20, base_y),
            (base_x, base_y - 10),
            (base_x - 12, base_y - 10),
            (base_x + 12, base_y - 10),
        ]

        for cand_x, cand_y in candidates:
            px = max(18, min(W - 18, cand_x))
            py = float(cand_y)
            if _overlaps_letter(px, py):
                continue
            if any(abs(px - pu["wx"]) < 18 and abs(py - pu["wy"]) < 18 for pu in gs["powerups"]):
                continue
            gs["powerups"].append({
                "wx": float(px), "wy": py,
                "type": random.choice(["shield", "jetpack"]),
            })
            return

    def gen_platforms():
        gs["platforms"].append({"wx": 0, "wy": H - 30, "w": W, "type": "ground"})
        wy = H - 50  # Cambiar altura inicial a 50
        for _ in range(22):
            wx    = random.randint(10, W - PLATW - 10)
            ptype = _rand_type()
            gs["platforms"].append({"wx": wx, "wy": wy, "w": PLATW, "type": ptype})

            if gs["target"]:
                _spawn_pending_good_letter(wx, wy)

            wy -= random.randint(72, 112)

        gs["platforms"] = [p for p in gs["platforms"] if not (p["type"] != "ground" and p["wy"] == H - 50)]

    def extend_platforms():
        if not gs["platforms"]: return
        top = min(p["wy"] for p in gs["platforms"])
        while top > gs["cam"] - 350:
            top  -= random.randint(70, 120)
            wx    = random.randint(10, W - PLATW - 10)
            ptype = _rand_type()
            gs["platforms"].append({"wx": wx, "wy": top, "w": PLATW, "type": ptype})

            if gs["target"]:
                _spawn_pending_good_letter(wx, top)

            if gs["target"] and not any(l["kind"] == "wrong" for l in gs["letters"]):
                if random.random() < 0.20:
                    _spawn_trap_letter(wx, top)

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
        # Movimiento horizontal de jugador y wrap-around cuando sale del borde.
        if gs["left"]:  gs["px"] -= SPEED
        if gs["right"]: gs["px"] += SPEED
        if gs["px"] + PW < 0: gs["px"] = float(W)
        if gs["px"] > W:      gs["px"] = float(-PW)

        # Aplicar gravedad y actualizar posición vertical.
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
            # Subida de cámara: mantener al jugador dentro de la zona superior.
            d = H * 0.42 - gs["py"]
            gs["cam"] -= d
            gs["py"]  += d
            gs["score"] = max(gs["score"], int(-gs["cam"] / 10))

        # ── Escudo tick-down
        if gs["shield_ttl"] > 0:
            gs["shield_ttl"] -= 1

        # ── Power-ups: recolección (antes de peligros para que el escudo proteja en el mismo cuadro)
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

        # ── Bolitas + colisión (respeta escudo)
        keep_balls = []
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
                if admin_state.get("ghost"):
                        continue
                if gs["shield_ttl"] > 0:
                    # Escudo absorbe el golpe y se rompe
                    gs["shield_ttl"] = 0
                    gs["notif"] = {"text": "🛡️  ¡ESCUDO ROTO!", "ttl": 90, "col": "#ff4444"}
                    continue
                else:
                    do_end_game(); return
            keep_balls.append(b)
        gs["balls"] = keep_balls

        # ── Letras
        wpy = gs["py"] + gs["cam"]
        keep = []
        for l in gs["letters"]:
            hit = (gs["px"] < l["wx"] + 22 and gs["px"] + PW > l["wx"] and
                   wpy < l["wy"] + 22 and wpy + PH > l["wy"])
            if hit:
                if l["kind"] == "wrong":
                    if admin_state.get("ghost"):
                        continue
                    if gs["shield_ttl"] > 0:
                        gs["shield_ttl"] = 0
                        gs["notif"] = {"text": "🛡️  ¡ESCUDO ROTO!", "ttl": 90, "col": "#ff4444"}
                        continue

                    gs["notif"] = {"text": "☠️  Letra incorrecta. GAME OVER", "ttl": 80, "col": "#ff4444"}
                    do_end_game()
                    return

                if gs["target"] and l["kind"] == "good" and "lidx" in l:
                    idx = l["lidx"]
                    if idx not in gs["collected_positions"]:
                        gs["collected_positions"].add(idx)
                        gs["collected"].append(l["char"])
                        gs["tidx"] = len(gs["collected_positions"])
                        if len(gs["collected_positions"]) >= len(gs["target"]):
                            tw = gs["target"]
                            gs["found"].append(tw)
                            gs["notif"] = {"text": f"✓  {tw}  =  {TRANSLATIONS.get(tw,'')}", "ttl": 110, "col": "#00ff88"}
                            pick_target()
                            gs["letters"] = []
                            break
                    # cualquiera que choque se elimina de pantalla
                    continue

            keep.append(l)

        gs["letters"] = keep
        gs["visible_positions"] = {l["lidx"] for l in gs["letters"] if l["kind"] == "good" and "lidx" in l}

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
        try:
            mo = gs.get("mouse_overlay")
            if mo is not None:
                mo.visible = False
                try:
                    mo.update()
                except Exception:
                    pass
        except Exception:
            pass
        save_record(record)

    # ── render ───────────────────────────────────────────────────────────────
    # Renderiza la escena de juego completa y actualiza los controles visibles.
    game_stack = ft.Stack(width=W, height=H, clip_behavior=ft.ClipBehavior.HARD_EDGE)

    def render():
        is_over   = gs.get("over", False)
        is_paused = gs.get("paused", False)
        items     = []

        # Asegurar que los detectores táctiles no intercepten taps cuando
        # el juego está en pausa o en GAME OVER.
        dt = gs.get("detectors")
        if dt:
            try:
                left_det, right_det = dt
                vis = (not is_paused and not is_over) and not admin_state.get("mouse_control")
                # Actualizar sólo cuando cambie la visibilidad para evitar updates constantes
                if gs.get("detectors_visible") != vis:
                    left_det.visible = vis
                    right_det.visible = vis
                    gs["detectors_visible"] = vis
                    try:
                        page.update()
                    except Exception:
                        pass
            except Exception:
                pass

        # Fondo
        items.append(ft.Container(width=W, height=H,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                colors=["#0d0d2b", "#141450"])))

        # Plataformas
        for p in gs["platforms"]:
            sy = p["wy"] - gs["cam"]
            if -PLATH - 4 < sy < H + PLATH:
                if p["type"] == "bouncy":
                    col  = "#ff6b35"
                    gcol = "#22ff6b35"
                elif p["type"] == "rescue":
                    col  = "#58ff99"
                    gcol = "#2200ff99"
                else:
                    col  = "#00e5ff"
                    gcol = "#2200e5ff"
                items.append(ft.Container(left=p["wx"]-3, top=sy-3,
                    width=p["w"]+6, height=PLATH+6, bgcolor=gcol, border_radius=5))
                if p["type"] == "rescue":
                    items.append(ft.Container(left=p["wx"], top=sy,
                        width=p["w"], height=PLATH, bgcolor=col, border_radius=3,
                        content=ft.Container(alignment=ft.alignment.center,
                            content=ft.Text("SEGURA", size=9, color="#003300",
                                weight=ft.FontWeight.BOLD))))
                else:
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
                    # Jetpack: halo naranja más pequeño y circular
                    items.append(ft.Container(       # halo exterior  70×70
                        left=pu["wx"] - 35, top=psy - 35,
                        width=70, height=70,
                        bgcolor="#44ff7700", border_radius=35))
                    items.append(ft.Container(       # halo interior  50×50
                        left=pu["wx"] - 25, top=psy - 25,
                        width=50, height=50,
                        bgcolor="#99ff8800", border_radius=25,
                        border=ft.border.all(2, "#ffaa00")))
                    items.append(ft.Container(       # imagen: tamaño mayor dentro del halo
                        left=pu["wx"] - 39, top=psy - 39,
                        width=78, height=78,
                        alignment=ft.alignment.center,
                        content=ft.Image(src=img_src, width=76, height=76,
                                         fit=ft.ImageFit.CONTAIN)))

        # Letras
        for l in gs["letters"]:
            sy = l["wy"] - gs["cam"]
            if -30 < sy < H + 30:
                fill = "#55ffd700"
                border = "#ffd700"
                text_color = "#ffd700"

                items.append(ft.Container(left=l["wx"]-5, top=sy-5,
                    width=30, height=30, bgcolor=fill,
                    border_radius=15, border=ft.border.all(1, border)))
                items.append(ft.Container(left=l["wx"]+1, top=sy-1,
                    content=ft.Text(l["char"], size=17, color=text_color,
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

        if admin_state.get("ghost"):
            # Cuando el admin está invisible, no cortamos el render completo; solo
            # añadimos un contorno tenue del robot y saltamos detalles.
            items.append(ft.Container(
                left=px + 4, top=py + 4,
                width=24, height=24,
                border=ft.border.all(1, "#88ffffff"),
                border_radius=12,
                opacity=0.12))
        else:
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

        hud_left = ft.Container(
            width=144,
            content=ft.Column([
                ft.Text("ALTURA", size=9, color="#88d8ff",
                        weight=ft.FontWeight.BOLD),
                ft.Text(f"{gs['score']}", size=19, color="#ffffff",
                        weight=ft.FontWeight.BOLD),
                ft.Text("RÉCORD", size=9, color="#ffd166",
                        weight=ft.FontWeight.BOLD),
                ft.Text(f"{record['best_height']}", size=16, color="#ffe08a",
                        weight=ft.FontWeight.BOLD),
            ], spacing=1))

        hud_center = ft.Container(expand=False, width=0)
        if gs.get("shield_ttl", 0) > 0:
            ttl = gs["shield_ttl"]
            segundos = int(ttl * 0.032)  # Convertir ticks a segundos
            hud_center = ft.Container(
                bgcolor="#220099ff", border_radius=8,
                border=ft.border.all(1, "#00aaff"),
                padding=ft.padding.symmetric(horizontal=8, vertical=2),
                content=ft.Row([
                    ft.Text("🛡️", size=14),
                    ft.Text(f"{segundos}s", size=12, color="#00aaff", weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6))

        hud_right = ft.Container(expand=True, alignment=ft.alignment.center_right)
        if gs["target"]:
            tw = gs["target"]
            # Mostrar la traducción si existe; si no, mostrar la palabra en inglés
            display_translation = TRANSLATIONS.get(tw, tw)
            hud_right = ft.Container(
            expand=True,
            alignment=ft.alignment.center_right,
            content=ft.Column([
                ft.Text(f"Encuentra la palabra: {display_translation}", size=13,
                    color="#ffee55", weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.RIGHT),
                ft.Text(f"✓ {len(gs['found'])}" if gs["found"] else "",
                    size=12, color="#00ff88",
                    text_align=ft.TextAlign.RIGHT),
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END))

        items.append(ft.Container(
            left=4, top=2, right=4, height=84,
            bgcolor="#cc000000",
            border_radius=12,
            padding=ft.padding.only(left=8, right=8, top=8, bottom=8),
            content=ft.Row([
                hud_left,
                hud_center,
                hud_right,
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ))

        # Abajo: palabra en INGLÉS completa con guiones (todas las letras)
        if gs["target"]:
            tw = gs["target"]
            word_spans = [
                ft.TextSpan(
                    text=c + " ",
                    style=ft.TextStyle(color="#ffd700" if i in gs["collected_positions"] else "#888888")
                )
                for i, c in enumerate(tw)
            ]
            items.append(ft.Container(left=6, top=94, right=6,
                padding=ft.padding.all(8),
                bgcolor="#22000000", border_radius=10,
                content=ft.Column([
                    ft.Text("En inglés es:", size=16, color="#ffd700",
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Text(spans=word_spans, size=16, text_align=ft.TextAlign.CENTER),
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
        except (OSError, BrokenPipeError, ConnectionResetError, Exception):
            pass

    # ── LOOP ─────────────────────────────────────────────────────────────────
    running = {"v": True}

    eyes_img  = ft.Image(src=SECUENCIA_OJOS[0], width=160, height=160,
                         opacity=1, animate_opacity=800)
    text_home = ft.Text("HOME", size=54, weight=ft.FontWeight.BOLD,
                        color="#00e5ff", opacity=0, animate_opacity=800)
    text_jump = ft.Text("JUMP", size=54, weight=ft.FontWeight.BOLD,
                        color="#ffd700", opacity=0, animate_opacity=800)

    nueva_anim_img = ft.Image(src="Animacion_nueva/frame1.png", width=255, height=150,
                              fit=ft.ImageFit.CONTAIN, visible=False)
    infinita_anim_img = ft.Image(src="Animacion_Infinita/frame32.png", width=280, height=190,
                                 fit=ft.ImageFit.CONTAIN, visible=False)

    def _restart_anim():
        """Reinicia la animación de ojos del menú."""
        gs["anim"].update({"index": 0, "last_time": 0, "complete": False})
        gs["anim_nueva"].update({"index": 0, "last_time": 0, "mode": "normal"})
        eyes_img.opacity  = 1
        eyes_img.src      = SECUENCIA_OJOS[0]
        text_home.opacity = 0
        text_jump.opacity = 0
        nueva_anim_img.visible = False
        infinita_anim_img.visible = False
        nueva_anim_img.src = "Animacion_nueva/frame1.png"
        infinita_anim_img.src = "Animacion_Infinita/frame32.png"
        try:
            safe_update(eyes_img)
            safe_update(text_home)
            safe_update(text_jump)
            safe_update(nueva_anim_img)
            safe_update(infinita_anim_img)
        except Exception:
            pass

    def safe_render():
        """Renderizar sin causar errores de socket."""
        try:
            render()
        except (OSError, BrokenPipeError, ConnectionResetError, Exception):
            # Capturar errores de socket y otras excepciones silenciosamente
            pass

    def on_window_close(e):
        """Manejador de cierre de ventana."""
        running["v"] = False
        time.sleep(0.2)  # Dar tiempo al thread para detenerse

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
                    safe_render(); time.sleep(0.1)
                else:
                    step(); safe_render(); time.sleep(TICK)
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
                            safe_update(eyes_img)
                            safe_update(text_home)
                            safe_update(text_jump)
                            nueva_anim_img.visible = True
                            safe_update(nueva_anim_img)

                # ── Animación nueva e infinita (después de ojos)
                elif menu_idle["in_menu"] and (nueva_anim_img.visible or infinita_anim_img.visible):
                    now = time.time()
                    a_state = gs["anim_nueva"]
                    idx = a_state["index"]
                    mode = a_state["mode"]
                    
                    if mode == "normal":
                        if idx < len(SECUENCIA_NUEVA):
                            img_path, frame_duration = SECUENCIA_NUEVA[idx]
                            if a_state["last_time"] == 0:
                                a_state["last_time"] = now
                                
                            if now - a_state["last_time"] >= frame_duration:
                                nueva_anim_img.src = img_path
                                a_state["index"] += 1
                                a_state["last_time"] = now
                                try: nueva_anim_img.update()
                                except Exception: pass
                        else:
                            # Cambio de fase: Acaba la animación nueva y empieza la infinita
                            a_state.update({"index": 0, "last_time": now, "mode": "infinite"})
                            nueva_anim_img.visible = False
                            infinita_anim_img.src = SECUENCIA_INFINITA[0][0]
                            infinita_anim_img.visible = True
                            try: 
                                safe_update(nueva_anim_img)
                                safe_update(infinita_anim_img)
                            except Exception: pass
                            
                    elif mode == "infinite":
                        if len(SECUENCIA_INFINITA) > 0:
                            img_path, frame_duration = SECUENCIA_INFINITA[idx]
                            if a_state["last_time"] == 0:
                                a_state["last_time"] = now
                            
                            if now - a_state["last_time"] >= frame_duration:
                                a_state["index"] = (a_state["index"] + 1) % len(SECUENCIA_INFINITA)
                                a_state["last_time"] = now
                                infinita_anim_img.src = img_path
                                try: safe_update(infinita_anim_img)
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
            # Si los detectores de pantalla existen, ocultarlos mientras está en pausa
            dt = gs.get("detectors")
            if dt:
                try:
                    left_det, right_det = dt
                    vis = (not gs.get("paused", False)) and not admin_state.get("mouse_control")
                    left_det.visible = vis
                    right_det.visible = vis
                except Exception:
                    pass

            # Actualizar texto/estado del botón de pausa si existe
            try:
                pb = gs.get("pause_btn_inner")
                if pb is not None:
                    if gs.get("paused"):
                        pb.content = ft.Icon(ft.Icons.PLAY_ARROW, color="#00e5ff", size=20)
                    else:
                        pb.content = ft.Icon(ft.Icons.PAUSE, color="#00e5ff", size=20)
                    try:
                        pb.update()
                    except Exception:
                        pass
            except Exception:
                pass

            # Ocultar el botón de pausa mientras el menú de pausa está activo
            try:
                pc = gs.get("pause_btn_container")
                if pc is not None:
                    pc.visible = not gs.get("paused", False)
                    try:
                        pc.update()
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                mo = gs.get("mouse_overlay")
                if mo is not None:
                    mo.visible = bool(admin_state.get("mouse_control") and not gs.get("paused") and not gs.get("over"))
                    try:
                        mo.update()
                    except Exception:
                        pass
            except Exception:
                pass

    def btn_restart():
        reset_gs(); gen_platforms(); pick_target()
        cmd["v"] = "start"
        # Restaurar visibilidad del overlay de ratón si el modo admin está activo
        try:
            mo = gs.get("mouse_overlay")
            if mo is not None:
                mo.visible = bool(admin_state.get("mouse_control") and not gs.get("paused") and not gs.get("over"))
                try:
                    mo.update()
                except Exception:
                    pass
        except Exception:
            pass

    def on_key(e: ft.KeyboardEvent):
        menu_idle["last_action"] = time.time()   # reset idle
        if gs.get("over"):
            if e.key == " ": btn_restart()
        elif e.key in ("Escape", "P", "p"):
            toggle_pause()
        elif getattr(e, "control", False) and getattr(e, "shift", False) and e.key == "A":
            open_admin_modal()
        elif not gs.get("paused"):
            if e.key == "Arrow Left":
                gs["left"] = True;  gs["right"] = False
            elif e.key == "Arrow Right":
                gs["right"] = True; gs["left"]  = False

    page.on_keyboard_event = on_key
    page.on_window_close = on_window_close

    # ── show_game ─────────────────────────────────────────────────────────────
    # Construye la pantalla de juego en vivo con detectores de toque y el botón de pausa.
    def show_game():
        menu_idle["in_menu"] = False
        page.controls.clear()

        # Overlay detectors: left/right half-screen touch to move
        left_detector = ft.Container(
            left=0, top=0, width=W//2, height=H,
            content=ft.GestureDetector(
                expand=True,
                content=ft.Container(bgcolor=None),
                on_tap_down=lambda e: gs.update({"left": True, "right": False}),
                on_tap_up=lambda e: gs.update({"left": False}),
                on_pan_update=lambda e: gs.update({"left": True, "right": False}),
                on_pan_end=lambda e: gs.update({"left": False}),
            )
        )

        right_detector = ft.Container(
            left=W//2, top=0, width=W - W//2, height=H,
            content=ft.GestureDetector(
                expand=True,
                content=ft.Container(bgcolor=None),
                on_tap_down=lambda e: gs.update({"right": True, "left": False}),
                on_tap_up=lambda e: gs.update({"right": False}),
                on_pan_update=lambda e: gs.update({"right": True, "left": False}),
                on_pan_end=lambda e: gs.update({"right": False}),
            )
        )

        # Use a Stack so the detectors sit above the game canvas
        # Registrar detectores para poder ocultarlos cuando esté en pausa.
        gs["detectors"] = (left_detector, right_detector)
        left_detector.visible = not gs.get("paused", False) and not admin_state.get("mouse_control")
        right_detector.visible = not gs.get("paused", False) and not admin_state.get("mouse_control")

        # Crear botón de pausa como icono circular (sin texto)
        pause_inner = ft.Container(
            width=44, height=44, border_radius=22,
            bgcolor=None,
            border=ft.border.all(2, "#00e5ff"),
            alignment=ft.alignment.center,
            content=ft.Icon(ft.Icons.PAUSE, color="#00e5ff", size=20)
        )
        pause_gd = ft.GestureDetector(on_tap_down=lambda e: toggle_pause(), content=pause_inner)
        # Colocar junto al HUD: a la derecha de la sección 'En inglés es:'
        pause_container = ft.Container(left=W - 72, top=90, width=44, height=44, content=pause_gd)
        gs["pause_btn_inner"] = pause_inner
        gs["pause_btn_container"] = pause_container

        mouse_overlay = ft.Container(
            left=0, top=0, width=W, height=H,
            visible=bool(admin_state.get("mouse_control") and not gs.get("paused") and not gs.get("over")),
            content=ft.GestureDetector(
                expand=True,
                content=ft.Container(bgcolor=None),
                on_hover=_mouse_control_hover,
                on_tap_down=_mouse_control_start,
                on_tap_up=_mouse_control_end,
                on_pan_start=_mouse_control_start,
                on_pan_update=_mouse_control_pan,
                on_pan_end=_mouse_control_end,
            )
        )
        gs["mouse_overlay"] = mouse_overlay

        page.add(ft.Stack(width=W, height=H, controls=[
            game_stack,
            mouse_overlay,
            left_detector,
            right_detector,
            pause_container,
        ]))

        safe_page_update()

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
                ft.Container(height=18), # separación antes de botones
                ft.GestureDetector(on_tap_down=lambda _: start_game(), # start_review_session() para repaso previo
                    content=ft.Container(width=230, height=52, border_radius=12, # 
                        bgcolor="#00e5ff", alignment=ft.alignment.center, # 
                        content=ft.Text("▶  JUGAR", size=18, color="#000000", #  
                                        weight=ft.FontWeight.BOLD))), # botón grande
                ft.Container(height=8),
                ft.GestureDetector(on_tap_down=lambda _: show_menu(),
                    content=ft.Container(width=200, height=44, border_radius=10,
                        border=ft.border.all(1, "#44ffffff"),
                        alignment=ft.alignment.center,
                        content=ft.Text("← Volver al menú", size=14, color="#88ffffff"))),
                ft.Container(height=16),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=8, scroll=ft.ScrollMode.AUTO)))
        safe_page_update()

    # ── Menú principal ────────────────────────────────────────────────────────
    # Dibuja la pantalla principal con botones de juego, repaso y ayuda.
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
            ft.Container(content=nueva_anim_img,
                         alignment=ft.alignment.bottom_center, width=W, height=180, bottom=-85),
            ft.Container(content=infinita_anim_img,
                         alignment=ft.alignment.bottom_center, width=W, height=280, bottom=-120, padding=ft.padding.only(top=35))
        ], width=W, height=180, clip_behavior=ft.ClipBehavior.NONE)

        total_words = sum(len(v) for v in VOCABULARY.values())

        base_menu = ft.Container(
            width=W,
            height=page.window.height,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                colors=["#0d0d2b", "#1a1a4e"]),
            content=ft.Column([
                ft.Container(height=36),
                title_stack,
                ft.Container(height=40),
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
                        start_review_session()
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
                ft.Container(height=10),
                ft.GestureDetector(
                    on_tap_down=lambda _: open_help_modal(),
                    content=ft.Container(width=260, height=44, border_radius=12,
                        bgcolor="#1a1a4e",
                        border=ft.border.all(2, "#00e5ff"),
                        alignment=ft.alignment.center,
                        content=ft.Text("Cómo jugar", size=15, color="#00e5ff",
                                        weight=ft.FontWeight.BOLD))),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=6, scroll=ft.ScrollMode.AUTO))

        review_overlay = ft.Container(
            width=page.window.width, height=page.window.height,
            bgcolor="#aa000000",
            alignment=ft.alignment.center,
            visible=review_state["open"],
            content=ft.Container(
                width=330, padding=18,
                bgcolor="#0d0d2b",
                border_radius=16,
                border=ft.border.all(2, "#00e5ff"),
                content=ft.Column([
                    ft.Text("📝  Repaso antes de jugar", size=20, color="#ffd700",
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Text("Escribe la traducción de cada palabra para continuar.",
                            size=12, color="#88ffffff", text_align=ft.TextAlign.CENTER),
                    ft.Container(height=10),
                    *[
                        ft.Container(
                            width=290, padding=12, bgcolor="#111133", border_radius=12,
                            content=ft.Column([
                                ft.Text(f"¿Qué significa {word}?", size=14,
                                        color="#ffffff", weight=ft.FontWeight.BOLD),
                                ft.TextField(
                                    value=review_state["answers"].get(word, ""),
                                    label="Traducción",
                                    text_style=ft.TextStyle(color="#ffffff"),
                                    border_color="#00e5ff",
                                    focused_border_color="#ffd700",
                                    on_change=lambda e, current_word=word: (
                                        review_state["answers"].update({current_word: e.data}),
                                        page.update()
                                    )),
                            ], spacing=4, tight=True))
                        for word in review_state["cards"]
                    ],
                    ft.Container(height=8),
                    ft.Text(
                        review_state["error"],
                        size=12,
                        color="#ff7777",
                        visible=bool(review_state["error"]),
                        text_align=ft.TextAlign.CENTER),
                    ft.Container(height=10),
                    ft.Column([
                        ft.Container(
                            width=290,
                            alignment=ft.alignment.center,
                            content=ft.GestureDetector(
                                on_tap_down=lambda _: show_words_inline(),
                                content=ft.Container(width=250, height=44, border_radius=10,
                                    bgcolor="#00e5ff", alignment=ft.alignment.center,
                                    content=ft.Text("Ir a palabras encontradas", size=14,
                                                    color="#000000", weight=ft.FontWeight.BOLD)))),
                        ft.Container(height=8),
                        ft.Container(
                            width=290,
                            alignment=ft.alignment.center,
                            content=ft.GestureDetector(
                                on_tap_down=lambda _: confirm_review_answers(),
                                content=ft.Container(width=140, height=44, border_radius=10,
                                    bgcolor="#00e5ff", alignment=ft.alignment.center,
                                    content=ft.Text("Continuar", size=14, color="#000000",
                                                    weight=ft.FontWeight.BOLD)))),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, tight=True))
        )

        help_overlay = ft.Container(
            width=page.window.width, height=page.window.height,
            bgcolor="#aa000000",
            alignment=ft.alignment.center,
            visible=help_state["open"],
            content=ft.Container(
                width=330, padding=18,
                bgcolor="#0d0d2b",
                border_radius=16,
                border=ft.border.all(2, "#00e5ff"),
                content=ft.Column([
                    ft.Text("Cómo jugar", size=20, color="#ffd700",
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                    ft.Text("Recoge las letras doradas que estan sobre las plataformas. ",
                            size=12, color="#88ffffff", text_align=ft.TextAlign.CENTER),
                    ft.Container(height=6),
                    ft.Text("Evita las letras incorrectas: Debes esquivarlas para no perder.",
                            size=12, color="#88ffffff", text_align=ft.TextAlign.CENTER),
                    ft.Container(height=10),
                    ft.Row([
                        ft.Container(width=18, height=18, bgcolor="#00e5ff", border_radius=4),
                        ft.Text("  Normal = Plataforma estándar", size=12, color="#ccffffff"),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                    ft.Container(height=6),
                    ft.Row([
                        ft.Container(width=18, height=18, bgcolor="#ff6b35", border_radius=4),
                        ft.Text("  Bouncy = Plataforma naranja para salto extra", size=12, color="#ccffffff"),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                    ft.Container(height=10),
                    ft.Row([
                        ft.Image(src="ESCUDO.png", width=46, height=46,
                                 fit=ft.ImageFit.CONTAIN),
                        ft.Container(width=8),
                        ft.Text("Escudo\nTe protege de un impacto", size=13,
                                color="#ccffffff", text_align=ft.TextAlign.LEFT),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=0),
                    ft.Container(height=8),
                    ft.Row([
                        ft.Image(src="JETPACK.png", width=68, height=68,
                                 fit=ft.ImageFit.CONTAIN),
                        ft.Container(width=8),
                        ft.Text("Jetpack\nSube rápido para llegar más alto", size=13,
                                color="#ccffffff", text_align=ft.TextAlign.LEFT),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=0),
                    ft.Container(height=8),
                    ft.Row([
                        ft.Container(width=22, height=22, bgcolor="#ff2222",
                                     border_radius=11,
                                     border=ft.border.all(2, "#ff7777")),
                        ft.Container(width=8),
                        ft.Text("Bolita roja = ¡PELIGRO! Evita tocarla.", size=13,
                                color="#ccffffff"),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=0),
                    ft.Container(height=12),
                    ft.GestureDetector(
                        on_tap_down=lambda _: close_help_modal(),
                        content=ft.Container(width=180, height=44, border_radius=10,
                            bgcolor="#00e5ff", alignment=ft.alignment.center,
                            content=ft.Text("Cerrar", size=15, color="#000000",
                                            weight=ft.FontWeight.BOLD))),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, tight=True))
        )

        admin_controls["info"] = ft.Text(get_admin_info(), size=12, color="#ccffffff",
                                         text_align=ft.TextAlign.LEFT)
        admin_controls["skip_text"] = ft.Text(
            f"Saltar repaso: {'ON' if admin_state['skip_review'] else 'OFF'}",
            size=14, color="#ffffff", weight=ft.FontWeight.BOLD)
        admin_controls["ghost_text"] = ft.Text(
            f"Modo invisible: {'ON' if admin_state['ghost'] else 'OFF'}",
            size=14, color="#ffffff", weight=ft.FontWeight.BOLD)
        admin_controls["mouse_text"] = ft.Text(
            f"Mover con ratón: {'ON' if admin_state['mouse_control'] else 'OFF'}",
            size=14, color="#ffffff", weight=ft.FontWeight.BOLD)

        admin_overlay = ft.Container(
            width=page.window.width, height=page.window.height,
            bgcolor="#bb000000",
            alignment=ft.alignment.center,
            visible=admin_state["open"],
            content=ft.Container(
                width=340, height=page.window.height - 120, padding=18,
                bgcolor="#0a0a23",
                border_radius=16,
                border=ft.border.all(2, "#00e5ff"),
                content=ft.Column([
                    ft.Text("ADMINISTRADOR", size=20, color="#ffd700",
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=10),
                    admin_controls["info"],
                    ft.Container(height=12),
                    ft.GestureDetector(
                        on_tap_down=lambda _: (close_admin_modal(), btn_restart()),
                        content=ft.Container(width=240, height=44, border_radius=10,
                            bgcolor="#00e5ff", alignment=ft.alignment.center,
                            content=ft.Text("Reiniciar juego", size=14, color="#000000",
                                            weight=ft.FontWeight.BOLD))),
                    ft.Container(height=8),
                    ft.GestureDetector(
                        on_tap_down=lambda _: (close_admin_modal(), safe_render()),
                        content=ft.Container(width=240, height=44, border_radius=10,
                            bgcolor="#22ffffff", alignment=ft.alignment.center,
                            content=ft.Text("Actualizar vista", size=14, color="#ffffff",
                                            weight=ft.FontWeight.BOLD))),
                    ft.Container(height=8),
                    ft.GestureDetector(
                        on_tap_down=lambda _: (close_admin_modal(), start_game()),
                        content=ft.Container(width=240, height=44, border_radius=10,
                            bgcolor="#00cc88", alignment=ft.alignment.center,
                            content=ft.Text("Aplicar y Jugar", size=14, color="#000000",
                                            weight=ft.FontWeight.BOLD))),
                    ft.Container(height=8),
                    ft.GestureDetector(
                        on_tap_down=lambda _: toggle_admin_skip_review(),
                        content=ft.Container(width=240, height=44, border_radius=10,
                            bgcolor="#22ffffff", alignment=ft.alignment.center,
                            content=admin_controls["skip_text"])),
                    ft.Container(height=8),
                    ft.GestureDetector(
                        on_tap_down=lambda _: toggle_admin_ghost(),
                        content=ft.Container(width=240, height=44, border_radius=10,
                            bgcolor="#22ffffff", alignment=ft.alignment.center,
                            content=admin_controls["ghost_text"])),
                    ft.Container(height=8),
                    ft.GestureDetector(
                        on_tap_down=lambda _: admin_apply_powerup("shield"),
                        content=ft.Container(width=240, height=44, border_radius=10,
                            bgcolor="#22ffffff", alignment=ft.alignment.center,
                            content=ft.Text("Dar ESCUDO", size=14, color="#ffffff",
                                            weight=ft.FontWeight.BOLD))),
                    ft.Container(height=8),
                    ft.GestureDetector(
                        on_tap_down=lambda _: admin_apply_powerup("jetpack"),
                        content=ft.Container(width=240, height=44, border_radius=10,
                            bgcolor="#22ffffff", alignment=ft.alignment.center,
                            content=ft.Text("Dar JETPACK", size=14, color="#ffffff",
                                            weight=ft.FontWeight.BOLD))),
                    ft.Container(height=8),
                    ft.GestureDetector(
                        on_tap_down=lambda _: toggle_admin_mouse_control(),
                        content=ft.Container(width=240, height=44, border_radius=10,
                            bgcolor="#22ffffff", alignment=ft.alignment.center,
                            content=admin_controls["mouse_text"])),
                    ft.Container(height=8),
                    ft.GestureDetector(
                        on_tap_down=lambda _: (close_admin_modal(), clear_progress()),
                        content=ft.Container(width=240, height=44, border_radius=10,
                            bgcolor="#ff5555", alignment=ft.alignment.center,
                            content=ft.Text("Borrar progreso", size=14, color="#000000",
                                            weight=ft.FontWeight.BOLD))),
                    ft.Container(height=8),
                    ft.GestureDetector(
                        on_tap_down=lambda _: close_admin_modal(),
                        content=ft.Container(width=240, height=44, border_radius=10,
                            bgcolor="#ff4444", alignment=ft.alignment.center,
                            content=ft.Text("Cerrar admin", size=14, color="#ffffff",
                                            weight=ft.FontWeight.BOLD))),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, tight=True,
                   scroll=ft.ScrollMode.AUTO))
        )

        page.controls.clear()
        page.add(ft.Stack([base_menu, review_overlay, help_overlay, admin_overlay], width=W, height=page.window.height))
        # Limpiar referencias a detectores si existían (salimos del juego)
        gs["detectors"] = None
        safe_page_update()

    # ── Palabras encontradas ─────────────────────────────────────────────────
    # Muestra una lista de palabras ya completadas por el jugador.
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
        page.add(ft.Container(
            width=page.window.width,
            height=page.window.height,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                colors=["#0d0d2b", "#141450"]),
            content=ft.Column([
                ft.Container(height=24),
                ft.Text("📚 Palabras Encontradas", size=22, color="#00e5ff",
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text(f"{len(found_set)} de {total_words} totales",
                        size=13, color="#88ffffff", text_align=ft.TextAlign.CENTER),
                ft.Container(height=14),
                ft.Container(
                    width=340,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    bgcolor="#120f2f",
                    border_radius=18,
                    border=ft.border.all(1, "#22ffffff"),
                    content=ft.Column(sections, scroll=ft.ScrollMode.AUTO, spacing=0)),
                ft.Container(height=12),
                ft.GestureDetector(on_tap_down=lambda _: show_menu(),
                    content=ft.Container(width=220, height=44, border_radius=10,
                        bgcolor="#22ffffff", alignment=ft.alignment.center,
                        content=ft.Text("← Volver al menú", size=14, color="#ffffff"))),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=0, alignment=ft.MainAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO)))
        safe_page_update()

    show_menu()


ft.app(main, assets_dir="assets")