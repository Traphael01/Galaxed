import os
import time
import math
import random
import json
import tkinter as tk
from PIL import Image, ImageTk
import pygame 


#sound apply
pygame.mixer.init()


# =========================================
#  CONFIG
# =========================================
WIN_W, WIN_H = 1280, 720
ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
FRAME_DELAY_MS = 16  # ~60 FPS
BULLET_SPEED = -14
BULLET_WIDTH = 3
PLAYER_RADIUS = 24

# =========================================
#  UTILS
# =========================================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def load_image(path, size=None):
    if not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("RGBA")
        if size:
            img = img.resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


def load_image_raw(path):
    if not os.path.exists(path):
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def slice_spritesheet_horiz(pil_image, frame_w=None, frame_h=None):
    """Slice a horizontal spritesheet into PhotoImage frames.
    If frame_w/frame_h not provided, assume square frames with side = image height.
    """
    if pil_image is None:
        return []
    W, H = pil_image.size
    if frame_h is None:
        frame_h = H
    if frame_w is None:
        frame_w = frame_h
    n = max(1, W // frame_w)
    frames = []
    for i in range(n):
        box = (i * frame_w, 0, (i + 1) * frame_w, frame_h)
        if box[2] <= W:
            crop = pil_image.crop(box)
            frames.append(ImageTk.PhotoImage(crop))
    return frames


# =========================================
#  ENTITA'
# =========================================
class Enemy:
    def __init__(self, app, typ, x, y=-48, hp=None):
        self.app = app
        self.type = typ
        self.x = x
        self.y = y
        if typ == "blue":
            self.max_hp = 1 if hp is None else hp
            self.speed = 1.4
            self.radius = 20
            self.sprite_img = app.enemy_images.get("blue")
        elif typ == "gray":
            self.max_hp = 3 if hp is None else hp
            self.speed = 1.0
            self.radius = 26
            self.sprite_img = app.enemy_images.get("gray")
        elif typ == "red":
            self.max_hp = 5 if hp is None else hp
            self.speed = 0.8
            self.radius = 30
            self.sprite_img = app.enemy_images.get("red")
        else:
            self.max_hp = 1
            self.speed = 1.0
            self.radius = 22
            self.sprite_img = None
        self.hp = self.max_hp

        if self.sprite_img:
            self.id = self.app.canvas.create_image(self.x, self.y, image=self.sprite_img, anchor="center")
        else:
            self.id = self.app.canvas.create_oval(self.x - self.radius, self.y - self.radius,
                                                  self.x + self.radius, self.y + self.radius,
                                                  fill="#ffffff", outline="")
        self.hp_img_id = None

    def update(self, dt):
        # lieve inseguimento orizzontale
        px = self.app.player.get("x", WIN_W // 2)
        self.x += (px - self.x) * 0.0022 * dt * 60
        self.y += self.speed * dt * 60
        try:
            if self.sprite_img:
                self.app.canvas.coords(self.id, self.x, self.y)
            else:
                self.app.canvas.coords(self.id, self.x - self.radius, self.y - self.radius,
                                             self.x + self.radius, self.y + self.radius)
        except Exception:
            pass

    def hit(self, dmg):
        self.hp -= max(1, int(dmg))
        if self.hp <= 0:
            self.destroy()
            return True
        return False

    def destroy(self):
        # piccole particelle
        for i in range(6):
            r = random.randint(3, 8)
            px = self.x + random.uniform(-8, 8)
            py = self.y + random.uniform(-8, 8)
            tid = self.app.canvas.create_oval(px - r, py - r, px + r, py + r, fill="#ffd27a", outline="")
            self.app.after(180 + i * 40, lambda _id=tid: self.app.canvas.delete(_id))
        try:
            self.app.canvas.delete(self.id)
        except Exception:
            pass
        # DROP POWERUP con probabilità totale ~29.99999%
        if random.random() < 0.2999999:
            # ripartizione: energy 50%, rapid 35%, hyper 15%
            r = random.random()
            if r < 0.50:
                self.app.spawn_powerup("energy", self.x, self.y)
            elif r < 0.85:
                self.app.spawn_powerup("rapid", self.x, self.y)
            else:
                self.app.spawn_powerup("hyper", self.x, self.y)

import os, time, math, random

class Boss:
    def __init__(self, app, name, sheet_path, behavior):
        self.app = app
        self.name = name
        self.x = WIN_W // 2
        self.y = 140
        self.vx = 2.0
        self.vy = 0.0
        self.hp = behavior.get("hp", 200)
        self.max_hp = self.hp
        self.phase = 0
        self.t = 0.0
        self.behavior = behavior
        self.bullets = []  # lista proiettili del boss

        self.invulnerable = False
        self.visible = True
        self.last_switch = time.time()
        self.last_shot = 0.0

        self.frames = []
        self.anim_sequence = []
        self.frame_i = 0
        self.frame_timer = 0.0

        # --- BOTWOON ---
        if self.name.lower() == "botwoon":
            bot_dir = os.path.join(ASSET_DIR, "botwoon")
            for i in range(1, 6):
                p = os.path.join(bot_dir, f"botwoon{i}.png")
                img = load_image(p)
                if img:
                    self.frames.append(img)
            # sequenza 1→2→3→4→5→4→3→2→1
            self.anim_sequence = list(range(5)) + list(range(3, 0, -1))
            self.anim_index = 0
            self.anim_speed = 0.08  # secondi per frame

        elif self.name.lower() in ("phantom", "phantoon"):
            phantom_dir = os.path.join(ASSET_DIR, "phantom")
            eye_path = os.path.join(phantom_dir, "eye.png")
            close_path = os.path.join(phantom_dir, "close.png")

            img_eye = load_image(eye_path)
            img_close = load_image(close_path)

            self.frames = []
            if img_eye:
                self.frames.append(img_eye)
            if img_close:
                self.frames.append(img_close)

            self.visible = True
            self.invulnerable = False
            self.last_switch = time.time()
            self.last_shot = 0.0

            # --- nuovi parametri di tiro ---
            self.shoot_delay = 0.2   # 1 proiettile per lato al secondo
            self.shot_speed = 9
            self.shot_radius = 6
            self.bullet_delay = 1.0  # attesa di 1s prima di partire


        # --- RIDLEY ---
        elif self.name.lower() == "ridley":
            rid_dir = os.path.join(ASSET_DIR, "ridley")
            self.ridley_imgs = {
                "right": load_image(os.path.join(rid_dir, "r_right.png")),
                "right2": load_image(os.path.join(rid_dir, "r_right2.png")),
                "left": load_image(os.path.join(rid_dir, "r_left.png")),
                "left2": load_image(os.path.join(rid_dir, "r_left2.png")),
                "att": load_image(os.path.join(rid_dir, "r_att.png")),
                "att2": load_image(os.path.join(rid_dir, "r_att2.png")),
                "fire": load_image(os.path.join(rid_dir, "bull.png")),
            }
            self.facing_right = True
            self.last_fire = 0.0
            self.last_pongo = 0.0
            self.is_attacking = False
            self.attack_stage = 0
            self.anim_timer = 0.0
            self.walk_toggle = False

        # --- Default fallback ---
        else:
            pil = load_image_raw(sheet_path)
            self.frames = slice_spritesheet_horiz(pil) if pil else []
            if self.frames:
                self.anim_sequence = list(range(len(self.frames)))

        # --- Crea sprite su canvas ---
        if self.name.lower() == "ridley":
            img0 = self.ridley_imgs.get("right")
        elif self.frames:
            img0 = self.frames[0]
        else:
            img0 = None

        if img0:
            self.id = self.app.canvas.create_image(self.x, self.y, image=img0, anchor="center")
            if not hasattr(self.app, "image_refs"):
                self.app.image_refs = []
            self.app.image_refs.append(img0)
        else:
            self.id = self.app.canvas.create_rectangle(self.x - 80, self.y - 80,
                                                       self.x + 80, self.y + 80,
                                                       outline="red")

    # ----------------------------------------------------
    def update(self, dt):
        self.t += dt
        self.frame_timer += dt
        now = time.time()

        if self.name.lower() == "botwoon":
            # Movimento serpentino
            self.x += math.cos(self.t * 2.0) * 3.0
            self.y = 180 + math.sin(self.t * 1.3) * 60

            # --- Animazione sprite ---
            if self.frame_timer >= self.anim_speed:
                self.frame_timer = 0.0
                self.anim_index = (self.anim_index + 1) % len(self.anim_sequence)
                frame = self.frames[self.anim_sequence[self.anim_index]]
                self.app.canvas.itemconfig(self.id, image=frame)
                if not hasattr(self.app, "image_refs"):
                    self.app.image_refs = []
                self.app.image_refs.append(frame)

            # --- Spara verso il basso con spread ---
            if random.random() < 0.03:
                self.shoot_spread(3, speed=5.5, upwards=False)

            self.app.canvas.coords(self.id, self.x, self.y)

        # --- PHANTOM ---
        elif self.name.lower() in ("phantom", "phantoon"):
            if now - self.last_switch >= 5.0:
                self.visible = not self.visible
                self.invulnerable = not self.visible
                self.last_switch = now
                if len(self.frames) >= 2:
                    img = self.frames[0] if self.visible else self.frames[1]
                    try:
                        self.app.canvas.itemconfig(self.id, image=img)
                        if not hasattr(self.app, "image_refs"):
                            self.app.image_refs = []
                        self.app.image_refs.append(img)
                    except Exception:
                        pass

            self.x += math.cos(self.t * 1.5) * 2.5
            self.y = 180 + math.sin(self.t * 1.2) * 20

            if self.visible and now - self.last_shot >= self.shoot_delay:
                self.last_shot = now
                self._phantom_shoot_pair()

        # --- RIDLEY ---
        elif self.name.lower() == "ridley":
            player_x = self.app.player["x"]
            player_y = self.app.player["y"]

            if self.is_attacking:
                self._update_pongo_attack(now, dt)
            else:
                # --- Suono di ruggito casuale ---
                if not hasattr(self, "last_roar_time"):
                    self.last_roar_time = 0
                if now - self.last_roar_time >= 2.0:
                    if random.random() < 0.0333:
                        try:
                            roar_path = os.path.join(ASSET_DIR, "ridley", "rugh.mp3")
                            roar_sound = pygame.mixer.Sound(roar_path)
                            roar_sound.play()
                        except Exception as e:
                            print(f"Errore suono ruggito: {e}")

                        self.last_roar_time = now

                # --- Movimento e attacchi ---
                dx = player_x - self.x
                if abs(dx) > 5:
                    direction = 1 if dx > 0 else -1
                    self.x += direction * 3.0
                    self.facing_right = direction > 0
                    self._animate_ridley_walk(dt)

                if now - self.last_fire >= 1.0:
                    self.last_fire = now
                    self._ridley_fireball(player_x, player_y)

                if self.facing_right and now - self.last_pongo >= 7.0:
                    self.last_pongo = now
                    self._start_pongo_attack(player_x, player_y)


       # --- Aggiorna posizione ---
        try:
            self.app.canvas.coords(self.id, self.x, self.y)
        except Exception:
            pass

        # --- Aggiorna proiettili ---
        for pb in list(self.bullets):

            # ⏳ attesa solo per i proiettili di PHANTOM / PHANTOON
            if self.name.lower() in ("phantom", "phantoon"):
                if not pb.get("active", True):
                    if time.time() - pb.get("spawn_time", 0) >= pb.get("delay", 0):
                        pb["active"] = True
                    else:
                        continue  # aspetta ancora, non si muove

            # --- movimento proiettile ---
            pb["x"] += pb.get("dx", 0)
            pb["y"] += pb.get("dy", 0)

            try:
                if pb.get("img", False):
                    # immagine: aggiorna la posizione semplice
                    self.app.canvas.coords(pb["id"], pb["x"], pb["y"])

                elif pb.get("type", "") == "line":
                    # linea: mantienila dritta orizzontale
                    length = pb.get("length", 14)
                    self.app.canvas.coords(
                        pb["id"],
                        pb["x"] - length / 2, pb["y"],
                        pb["x"] + length / 2, pb["y"]
                    )

                else:
                    # ovale (pallina classica)
                    r = pb.get("r", 6)
                    self.app.canvas.coords(
                        pb["id"],
                        pb["x"] - r, pb["y"] - r,
                        pb["x"] + r, pb["y"] + r
                    )

            except Exception:
                continue

            # --- collisione con il player ---
            player_x = self.app.player["x"]
            player_y = self.app.player["y"]
            pr = pb.get("r", 6)
            hit_dist = 26 + pr
            if math.hypot(pb["x"] - player_x, pb["y"] - player_y) < hit_dist:
                self.app.damage_player(1)
                self._delete_bullet(pb)
                continue

            # --- rimozione se fuori dallo schermo ---
            if (pb["y"] < -60 or pb["y"] > WIN_H + 60 or
                    pb["x"] < -60 or pb["x"] > WIN_W + 60):
                self._delete_bullet(pb)


    # ----------------------------------------------------
    def _phantom_shoot_pair(self):
        """Spara due proiettili (uno per lato) che attendono 1s prima di partire."""
        offsets = [-70, 70]
        player_x = self.app.player["x"]
        player_y = self.app.player["y"]

        for ox in offsets:
            bx = self.x + ox
            by = self.y
            r = self.shot_radius

            # disegna un proiettile come una linea rossa ferma
            length = 14
            bid = self.app.canvas.create_line(
                bx - length / 2, by, bx + length / 2, by,
                fill="red", width=3
            )

            # calcola direzione verso il player (ma NON muovere subito)
            ang = math.atan2(player_y - by, player_x - bx)
            speed = self.shot_speed
            dx = math.cos(ang) * speed
            dy = math.sin(ang) * speed

            # il proiettile inizialmente è fermo
            pb = {
                "id": bid, "x": bx, "y": by,
                "dx": dx, "dy": dy,
                "r": r, "img": False,
                "spawn_time": time.time(),
                "delay": self.bullet_delay,  # aspetta 1 secondo prima di muoversi
                "active": False
            }
            self.bullets.append(pb)


    # ----------------------------------------------------
    def _ridley_fireball(self, player_x, player_y):
        if self.is_attacking:
            return

        # --- Suono fireball ---
        try:
            fire_path = os.path.join(ASSET_DIR, "ridley", "Fireball.mp3")
            fire_sound = pygame.mixer.Sound(fire_path)
            fire_sound.play()
        except Exception as e:
            print(f"Errore suono Fireball: {e}")

        fire_img = self.ridley_imgs.get("fire")
        if not fire_img:
            return

        bid = self.app.canvas.create_image(self.x, self.y, image=fire_img)
        if not hasattr(self.app, "image_refs"):
            self.app.image_refs = []
        self.app.image_refs.append(fire_img)

        ang = math.atan2(player_y - self.y, player_x - self.x)
        speed = 6
        dx, dy = math.cos(ang) * speed, math.sin(ang) * speed
        self.bullets.append({
            "id": bid,
            "x": self.x,
            "y": self.y,
            "dx": dx,
            "dy": dy,
            "img": True
        })


    # ----------------------------------------------------
    def _start_pongo_attack(self, player_x, player_y):
        self.is_attacking = True
        self.attack_stage = 0
        self.attack_start_time = time.time()
        self.attack_origin_y = self.y
        self.attack_target_x = player_x
        self.attack_target_y = player_y - 20

    def _update_pongo_attack(self, now, dt):
        self.x += (self.attack_target_x - self.x) * 0.15

        if self.attack_stage == 0:
            self.y += 25 * dt * 60
            if self.y >= self.attack_target_y:
                self.attack_stage = 1
                self.attack_stage_start = now
                img = self.ridley_imgs.get("att")
                if img:
                    self.app.canvas.itemconfig(self.id, image=img)

        elif self.attack_stage == 1:
            if now - self.attack_stage_start >= 1.0:
                self.attack_stage = 2
                self.attack_stage_start = now
                img = self.ridley_imgs.get("att2")
                if img:
                    self.app.canvas.itemconfig(self.id, image=img)

        elif self.attack_stage == 2:
            self.y -= 15 * dt * 60
            if self.y <= self.attack_origin_y:
                self.y = self.attack_origin_y
                self.is_attacking = False
                self.attack_stage = 0
                img = self.ridley_imgs.get("right") if self.facing_right else self.ridley_imgs.get("left")
                if img:
                    self.app.canvas.itemconfig(self.id, image=img)

        # --- Collisione con cooldown ---
        player_x = self.app.player["x"]
        player_y = self.app.player["y"]
        if math.hypot(self.x - player_x, self.y - player_y) < 70:
            # Usa un timestamp per evitare danni troppo frequenti
            if not hasattr(self, "last_pongo_damage"):
                self.last_pongo_damage = 0
            if now - self.last_pongo_damage >= 0.2:  # cooldown di 0.2 secondi
                self.app.damage_player(1)
                self.last_pongo_damage = now

        # --- Aggiorna posizione su canvas ---
        try:
            self.app.canvas.coords(self.id, self.x, self.y)
        except Exception:
            pass


    # ----------------------------------------------------
    def _animate_ridley_walk(self, dt):
        self.anim_timer += dt
        if self.anim_timer >= 0.2:
            self.anim_timer = 0.0
            self.walk_toggle = not self.walk_toggle
            if self.facing_right:
                img = self.ridley_imgs.get("right2") if self.walk_toggle else self.ridley_imgs.get("right")
            else:
                img = self.ridley_imgs.get("left2") if self.walk_toggle else self.ridley_imgs.get("left")
            if img:
                self.app.canvas.itemconfig(self.id, image=img)

    # ----------------------------------------------------
    def hit(self, dmg):
        if getattr(self, "invulnerable", False):
            return False
        self.hp -= max(1, int(dmg))
        if self.hp <= 0:
            self.destroy()
            return True
        return False

    def destroy(self):
        try:
            self.app.canvas.delete(self.id)
        except Exception:
            pass
        for pb in list(self.bullets):
            self._delete_bullet(pb)
        # notifica l'app indicando quale boss è stato sconfitto
        try:
            # preferibile: passa il nome del boss
            self.app.on_boss_defeated(self.name)
        except TypeError:
            # fallback: se l'app ha vecchia firma, chiamala senza argomenti
            try:
                self.app.on_boss_defeated()
            except Exception:
                pass


    def _delete_bullet(self, pb):
        try:
            self.app.canvas.delete(pb["id"])
        except Exception:
            pass
        if pb in self.bullets:
            self.bullets.remove(pb)

    def shoot_spread(self, count, speed=5.0, upwards=False):
        """Tiro a ventaglio verso il basso (corretto)"""
        if count <= 0:
            return
        base_angle = 90 if not upwards else 270  # 270° = su
        spread = 40
        angles = [
            math.radians(base_angle + spread * (i / (count - 1) - 0.5))
            for i in range(count)
        ]
        for a in angles:
            dx, dy = math.cos(a) * speed, math.sin(a) * speed
            bid = self.app.canvas.create_line(
            self.x, self.y, self.x, self.y + 12,  # linea verticale
            fill="orange", width=3
            )
            self.bullets.append({"id": bid, "x": self.x, "y": self.y,
                                 "dx": dx, "dy": dy})

# =========================================
#  APP
# =========================================
class GalaxedApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Galaxed")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)

        self.canvas = tk.Canvas(self, width=WIN_W, height=WIN_H, highlightthickness=0)
        self.canvas.pack()

        self._load_assets()

        self.images = []  # mantiene riferimenti alle immagini tkinter (boss, proiettili, ecc.)


        self.pressed = set()
        self.bullets = []
        self.last_shot = 0.0
        self.default_shot_cooldown = 0.11  # assault-ish
        self.shot_cooldown = self.default_shot_cooldown

        self.enemy_bullets = []

        self.enemies = []
        self.powerups = []
        self.waves = []
        self.wave_index = 0
        self.wave_timer = 0.0
        self.wave_active = False

        self.boss = None

        
        self.player = {}
        self._bind_keys()

        self.level = 1
        self.state = "menu"
        self._show_menu()

        self._last_time = time.time()
        self.after(FRAME_DELAY_MS, self._update_loop)

        self.paused = False

        
    # --------------- ASSETS ----------------
    def _load_assets(self):
        self.bg = load_image(os.path.join(ASSET_DIR, "background.png"), (WIN_W, WIN_H))
        # ship
        samus_dir = os.path.join(ASSET_DIR, "samus")
        self.ship_center = load_image(os.path.join(samus_dir, "gunship.png")) 
        self.ship_left   = load_image(os.path.join(samus_dir, "gunship_left.png")) 
        self.ship_right  = load_image(os.path.join(samus_dir, "gunship_right.png")) 
        self.ship_rainbow = load_image(os.path.join(samus_dir, "R_gunship.png")) 
        self.ship_r_left = load_image(os.path.join(samus_dir, "R_gunship_left.png"))
        self.ship_r_right = load_image(os.path.join(samus_dir, "R_gunship_right.png"))
        if not self.ship_left: self.ship_left = self.ship_center
        if not self.ship_right: self.ship_right = self.ship_center

        # stamina (dash anim while sprinting)
        self.stamina_frames = []
        stamina_dir = os.path.join(ASSET_DIR, "stamina")
        if os.path.isdir(stamina_dir):
            files = sorted([f for f in os.listdir(stamina_dir) if f.lower().endswith(".png")])
            for fn in files:
                img = load_image(os.path.join(stamina_dir, fn))
                if img:
                    self.stamina_frames.append(img)

        dash_dir = os.path.join(ASSET_DIR, "dash")
        self.dash_center = load_image(os.path.join(dash_dir, "dash.png"))
        self.dash_left   = load_image(os.path.join(dash_dir, "dash_left.png"))
        self.dash_right  = load_image(os.path.join(dash_dir, "dash_right.png"))

        # life: 7 barrette life-0 .. life-6 (0=full)
        self.life_frames = []
        life_dir = os.path.join(ASSET_DIR, "life")
        if os.path.isdir(life_dir):
            # ensure 7 frames in correct order index 0=full,6=empty-most
            for i in range(7):
                p = os.path.join(life_dir, f"life-{i}.png")
                img = load_image(p)
                if img:
                    self.life_frames.append(img)
            if len(self.life_frames) == 7:
                pass
            elif self.life_frames:
                # fallback keep what we found
                self.life_frames = self.life_frames[:7]

        # powerups
        self.pu_images = {}
        pu_dir = os.path.join(ASSET_DIR, "powerups")
        if os.path.isdir(pu_dir):
            self.pu_images["energy"] = load_image(os.path.join(pu_dir, "energy.png"))
            self.pu_images["hyper"]  = load_image(os.path.join(pu_dir, "Hyper.png"))
            self.pu_images["rapid"]  = load_image(os.path.join(pu_dir, "speed_B.png"))

        # enemies
        self.enemy_images = {"blue": None, "gray": None, "red": None}
        blu_dir = os.path.join(ASSET_DIR, "blu")
        gray_dir = os.path.join(ASSET_DIR, "gray")
        red_dir = os.path.join(ASSET_DIR, "red")
        self.enemy_images["blue"] = load_image(os.path.join(blu_dir, "blu.png")) if os.path.isdir(blu_dir) else None
        self.enemy_images["gray"] = load_image(os.path.join(gray_dir, "gray.png")) if os.path.isdir(gray_dir) else None
        self.enemy_images["red"]  = load_image(os.path.join(red_dir, "red.png")) if os.path.isdir(red_dir) else None

        # bosses sheets (use provided filenames)
        self.sheet_botwoon = os.path.join(ASSET_DIR, "botwoon.png")
        # they wrote phantom.png in tree (also spelled phandom earlier)
        self.sheet_phantom = os.path.join(ASSET_DIR, "phantom.png")
        # they wrote ridlay.png in tree
        self.sheet_ridley  = os.path.join(ASSET_DIR, "ridlay.png")

    def play_music(self, path):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.6)  # volume 0.0–1.0 (modificalo a piacere)
            pygame.mixer.music.play(-1)  # -1 = loop infinito
        except Exception as e:
            print("Errore caricando musica:", e)

    def stop_music(self):
        pygame.mixer.music.stop()

    # --------------- UI SCREENS ----------------
    def _bind_keys(self):
        self.bind("<KeyPress>", self._on_key_down)
        self.bind("<KeyRelease>", self._on_key_up)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.bind("<Escape>", self._handle_escape)

    def _show_menu(self):
        self.state = "menu"
        self.canvas.delete("all")

        if self.bg:
            self.canvas.create_image(0, 0, image=self.bg, anchor="nw")

        # Titolo del gioco
        self.canvas.create_text(WIN_W // 2, 110, text="GALAXED", font=("Arial", 56, "bold"), fill="white")

        bw, bh = 340, 88
        bx0 = WIN_W // 2 - bw // 2

        # --- Bottone "GIOCA" ---
        by0 = WIN_H // 2 - bh // 2
        self.play_rect = self.canvas.create_rectangle(bx0, by0, bx0 + bw, by0 + bh,
                                                    fill="#223344", outline="white", width=3, tags="play")
        self.play_text = self.canvas.create_text(WIN_W // 2, WIN_H // 2, text="PLAY",
                                                font=("Arial", 32), fill="white", tags="play")
        self.canvas.tag_bind("play", "<Button-1>", lambda e: self._show_level_select())

        # --- Bottone "OPTIONS" (sotto Play) ---
        by_opt = by0 + bh + 40
        self.options_rect = self.canvas.create_rectangle(bx0, by_opt, bx0 + bw, by_opt + bh,
                                                        fill="#223344", outline="white", width=3, tags="options")
        self.options_text = self.canvas.create_text(WIN_W // 2, by_opt + bh // 2, text="OPTIONS",
                                                    font=("Arial", 32), fill="white", tags="options")
        self.canvas.tag_bind("options", "<Button-1>", lambda e: self._show_options())

        # --- Bottone "CREDITS" (sotto OPTIONS) ---
        by1 = by_opt + bh + 40
        self.credits_rect = self.canvas.create_rectangle(bx0, by1, bx0 + bw, by1 + bh,
                                                        fill="#223344", outline="white", width=3, tags="credits")
        self.credits_text = self.canvas.create_text(WIN_W // 2, by1 + bh // 2, text="CREDITS",
                                                    font=("Arial", 32), fill="white", tags="credits")
        self.canvas.tag_bind("credits", "<Button-1>", lambda e: self._show_credits())

        # --- Bottone "EXIT" in basso a sinistra ---
        bw, bh = 160, 50
        bx0, by0 = 40, WIN_H - 80

        self.canvas.create_rectangle(
            bx0, by0, bx0 + bw, by0 + bh,
            fill="#223344", outline="white", width=2, tags="exit"
        )
        self.canvas.create_text(
            bx0 + bw // 2, by0 + bh // 2,
            text="EXIT",
            font=("Arial", 18),
            fill="white",
            tags="exit"
        )

        self.canvas.tag_bind("exit", "<Button-1>", lambda e: self._exit_game())


    def _exit_game(self):
        """Chiude il gioco in modo sicuro e previene errori 'alloc invalid block'."""
        import sys
        try:
            # Ferma la musica e disattiva il mixer
            pygame.mixer.music.stop()
            pygame.mixer.quit()   # <-- questa è la riga chiave
        except Exception as e:
            print("Errore nel chiudere l’audio:", e)

        # Distrugge la finestra Tkinter
        self.destroy()

        # Uscita pulita del programma
        sys.exit(0)
    
    def _show_credits(self):
        import tkinter as tk
        self.state = "credits"
        self.canvas.delete("all")

        # Sfondo
        if self.bg:
            self.canvas.create_image(WIN_W // 2, WIN_H // 2, image=self.bg, anchor="center")

        # Testo dei crediti
        credits_text = (
            "Created by\n\nTraphael\n\n\n"
            "Sound and images by\n\nTraphael\n\nInternet\n\n\n"
            "Inspired by\n\nSuper Metroid\nby Nintendo®"
        )

        # Crea il testo partendo da sotto la finestra
        text_id = self.canvas.create_text(
            WIN_W // 2,
            WIN_H + 400,  # parte da fuori schermo
            text=credits_text,
            font=("Arial", 28),
            fill="white",
            justify="center"
        )

        # --- Animazione verso l'alto ---
        def animate():
            coords = self.canvas.coords(text_id)
            if not coords:
                return  # il testo è stato eliminato, interrompi animazione
            if coords[1] > WIN_H // 2:
                self.canvas.move(text_id, 0, -5)  # velocità salita
                self.after(30, animate)

        # ✅ Avvia davvero l'animazione
        animate()

        # --- Bottone "INDIETRO" ---
        bw, bh = 160, 50
        bx0, by0 = 40, WIN_H - 80
        self.canvas.create_rectangle(
            bx0, by0, bx0 + bw, by0 + bh,
            fill="#223344", outline="white", width=2, tags="back"
        )
        self.canvas.create_text(
            bx0 + bw // 2, by0 + bh // 2,
            text="INDIETRO", font=("Arial", 18), fill="white", tags="back"
        )
        self.canvas.tag_bind("back", "<Button-1>", lambda e: self._show_menu())


    def _show_level_select(self):
        self.state = "levels"
        self.canvas.delete("all")

        if self.bg:
            self.canvas.create_image(0, 0, image=self.bg, anchor="nw")

        self.canvas.create_text(WIN_W // 2, 80, text="Seleziona livello", font=("Arial", 36), fill="white")
        labels = [" Level 1\nBotwoon", " Level 2\nPhantom", "Level 3\nRidley"]

        for i, lbl in enumerate(labels):
            y = 200 + i * 120
            tag = f"lvl{i+1}"
            self.canvas.create_rectangle(WIN_W // 2 - 260, y - 36, WIN_W // 2 + 260, y + 36,
                                        fill="#123344", outline="white", width=3, tags=(tag,))
            self.canvas.create_text(WIN_W // 2, y, text=lbl, font=("Arial", 20),
                                    fill="white", tags=(tag,))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, lvl=i + 1: self._start_level(lvl))

        # --- Bottone "INDIETRO" in basso a sinistra ---
        bw, bh = 160, 50
        bx0, by0 = 40, WIN_H - 80
        back_rect = self.canvas.create_rectangle(bx0, by0, bx0 + bw, by0 + bh,
                                                fill="#223344", outline="white", width=2, tags="back")
        back_text = self.canvas.create_text(bx0 + bw // 2, by0 + bh // 2,
                                            text="INDIETRO", font=("Arial", 18), fill="white", tags="back")
        self.canvas.tag_bind("back", "<Button-1>", lambda e: self._show_menu())

    def _show_options(self):
        self.state = "options"
        self._clear_widgets()  
        self.canvas.delete("all")

        # Sfondo
        self.canvas.create_image(WIN_W // 2, WIN_H // 2, image=self.bg, anchor="center")

        # Titolo
        self.canvas.create_text(
            WIN_W // 2, 120,
            text="OPTIONS",
            font=("Orbitron", 48, "bold"),
            fill="white"
        )

        # --- Volume ---
        self.canvas.create_text(
            WIN_W // 2, WIN_H // 2 - 150,
            text="Volume",
            font=("Orbitron", 20),
            fill="white"
        )

        self.volume_slider = tk.Scale(
            self, from_=0, to=100, orient="horizontal",
            troughcolor="#1a2a3a", bg="#0f1b2b", fg="white",
            highlightthickness=0, showvalue=True, length=300,
            font=("Orbitron", 12), relief="flat", bd=0,
            command=lambda v: pygame.mixer.music.set_volume(int(v)/100)
        )
        self.volume_slider.set(50)
        self.canvas.create_window(WIN_W // 2, WIN_H // 2 - 100, window=self.volume_slider)

        # --- Risoluzione ---
        self.canvas.create_text(
            WIN_W // 2, WIN_H // 2 - 20,
            text="Risoluzione",
            font=("Orbitron", 20),
            fill="white"
        )

        self.resolution_var = tk.StringVar(value="1280x720 (Default)")
        self.resolution_menu = tk.OptionMenu(
            self, self.resolution_var,
            "1280x720 (Default)", "Fullscreen",
            command=lambda choice: self._apply_resolution(
                "fullscreen" if "Full" in choice else "windowed"
            )
        )
        self.resolution_menu.config(
            font=("Orbitron", 14), bg="#1a2a3a", fg="white",
            activebackground="#1a2a3a", activeforeground="white",
            relief="flat", highlightthickness=2, highlightbackground="white",
            width=20
        )
        self.canvas.create_window(WIN_W // 2, WIN_H // 2 + 40, window=self.resolution_menu)

        # ===== BACK BUTTON =====
        bw, bh = 160, 50
        bx0, by0 = 40, WIN_H - 80
        self.canvas.create_rectangle(bx0, by0, bx0 + bw, by0 + bh,
                                    fill="#223344", outline="white", width=2, tags="back_opt")
        self.canvas.create_text(bx0 + bw // 2, by0 + bh // 2,
                                text="BACK", font=("Arial", 18), fill="white", tags="back_opt")
        self.canvas.tag_bind("back_opt", "<Button-1>", lambda e: self._close_options())

    def _toggle_res_menu(self):
        """Mostra o nasconde la mini tendina delle risoluzioni."""
        if self.res_options_visible:
            self.canvas.delete("res_option")
            self.res_options_visible = False
            return

        bw, bh = 260, 50
        bx = WIN_W // 2 - bw // 2
        by = WIN_H // 2 + 100

        options = [("1280x720 (Default)", "windowed"),
                ("Fullscreen", "fullscreen")]

        for i, (label, mode) in enumerate(options):
            y = by + i * (bh + 10)
            self.canvas.create_rectangle(bx, y, bx + bw, y + bh,
                                        fill="#223344", outline="white", width=2,
                                        tags=("res_option", f"opt{i}"))
            self.canvas.create_text(WIN_W // 2, y + bh // 2, text=label,
                                    font=("Arial", 18), fill="white", tags=("res_option", f"opt{i}"))
            self.canvas.tag_bind(f"opt{i}", "<Button-1>", lambda e, m=mode, l=label: self._apply_resolution(m, l))

        self.res_options_visible = True

    def _apply_resolution(self, mode):
        """Gestisce il passaggio tra fullscreen e finestra 1280x720."""
        if mode == "fullscreen":
            self.attributes("-fullscreen", True)
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
        else:
            self.attributes("-fullscreen", False)
            screen_w, screen_h = 1280, 720
            # centra la finestra
            x = (self.winfo_screenwidth() - screen_w) // 2
            y = (self.winfo_screenheight() - screen_h) // 2
            self.geometry(f"{screen_w}x{screen_h}+{x}+{y}")

        # aggiorna dimensioni globali
        global WIN_W, WIN_H
        WIN_W, WIN_H = screen_w, screen_h

        # ridimensiona canvas
        self.canvas.config(width=WIN_W, height=WIN_H)

        # --- Adatta lo sfondo ---
        bg_path = os.path.join(ASSET_DIR, "background.png")
        bg_img = Image.open(bg_path)
        bg_ratio = bg_img.width / bg_img.height
        screen_ratio = WIN_W / WIN_H

        if bg_ratio > screen_ratio:
            new_height = WIN_H
            new_width = int(WIN_H * bg_ratio)
        else:
            new_width = WIN_W
            new_height = int(WIN_W / bg_ratio)

        bg_img = bg_img.resize((new_width, new_height), Image.LANCZOS)
        self.bg = ImageTk.PhotoImage(bg_img)
        self.canvas.create_image(WIN_W // 2, WIN_H // 2, image=self.bg, anchor="center")

        # ✅ Aggiorna tutti i layout in base allo stato corrente
        self._refresh_ui_after_resize()

        # Dentro _apply_resolution(), dopo self._refresh_ui_after_resize()
        if mode == "fullscreen":
            self.resolution_var.set("Fullscreen")
        else:
            self.resolution_var.set("1280x720 (Default)")

    def _refresh_ui_after_resize(self):
        """Aggiorna interfaccia e widget dopo cambio risoluzione."""
        self.canvas.delete("all")
        self._clear_widgets() 

        # Mantiene la schermata corrente
        if self.state == "menu":
            self._show_menu()
        elif self.state == "options":
            self._show_options()
        elif self.state == "credits":
            self._show_credits()
        elif self.state == "levels":
            self._show_level_select()
        else:
            # Se sei in gioco, aggiorna solo lo sfondo
            if self.bg:
                self.canvas.create_image(WIN_W // 2, WIN_H // 2, image=self.bg, anchor="center")

    def _set_windowed(self, label):
        """Torna alla finestra 1280x720 centrata"""
        self.attributes("-fullscreen", False)
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)

        # Ripristina sfondo originale
        self.bg = load_image(os.path.join(ASSET_DIR, "background.png"), (WIN_W, WIN_H))
        self._show_options()  # ricarica schermata
        self.canvas.itemconfig(self.res_text, text=label)


    def _set_fullscreen(self, label):
        """Attiva fullscreen e adatta lo sfondo"""
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        self.attributes("-fullscreen", True)

        # Allarga solo lo sfondo
        bg_path = os.path.join(ASSET_DIR, "background.png")
        self.bg = load_image(bg_path, (screen_w, screen_h))
        self._show_options()
        self.canvas.itemconfig(self.res_text, text=label)

    def _close_options(self):
        if hasattr(self, "volume_slider"):
            self.volume_slider.destroy()
        self._show_menu()

    def _clear_widgets(self):
        """Rimuove tutti i widget Tk attivi (bottoni, slider, menu, ecc.)."""
        for widget in self.winfo_children():
            # non eliminare il canvas principale!
            if widget != self.canvas:
                widget.destroy()

    # --------------- GAME SETUP ----------------
    def _start_level(self, level):
        self.level = level
        self.state = "playing"
        self.canvas.delete("all")
        if self.bg:
            self.canvas.create_image(0, 0, image=self.bg, anchor="nw")

        self.play_music(os.path.join(ASSET_DIR, "background.mp3"))

        self.player = {
            "x": WIN_W // 2,
            "y": WIN_H - 140,
            "base_speed": 4.0,
            "speed": 4.0,
            "vx": 0.0,
            "vy": 0.0,
            "stamina": 3,
            "max_stamina": 3,
            "stamina_recharge_time": 3,
            "health": 6,
            "max_health": 6,
            "rapid_until": 0.0,
            "hyper_until": 0.0,
            "sprinting": False,
        }


        img = self.ship_center or self.ship_left or self.ship_right
        self.ship_item = self.canvas.create_image(self.player["x"], self.player["y"], image=img, anchor="center")
        self.current_ship_img = img

        self.stamina_img_id = None
        self.current_stamina_frame = None
        if self.stamina_frames:
            self.stamina_img_id = self.canvas.create_image(42, WIN_H - 46, image=self.stamina_frames[-1], anchor="nw")
            self.current_stamina_frame = self.stamina_frames[-1]

        # life icon
        self.life_img_id = None
        if self.life_frames:
            frame = self.life_frames[0] if self.player["health"] >= self.player["max_health"] else self.life_frames[self.player["max_health"] - self.player["health"]]
            self.life_img_id = self.canvas.create_image(WIN_W - 180, 16, image=frame, anchor="nw")

        self.enemies.clear()
        self.powerups.clear()
        self.bullets.clear()
        self.boss = None
        
        LEVEL_DIR = os.path.join(os.path.dirname(__file__))
        json_file = os.path.join(LEVEL_DIR, f"level{level}.json")

        try:
            with open(json_file, "r") as f:
                self.waves = json.load(f)
        except Exception as e:
            print("Errore caricando le ondate:", e)
            self.waves = []
        self.wave_index = 0
        self.wave_timer = 0.0
        self.wave_active = True
        self.wave_gap = 1.4
        self._wave_finish_timer = None
   

    def _make_wave_line(self, n, typ="blue", y_delay=0.18):
        wave = []
        for j in range(n):
            x = 120 + (j % 10) * 100
            wave.append({"type": typ, "x": x, "delay": j * y_delay})
        return wave

    def _make_wave_vmix(self, n, gray_every=4, red_every=7):
        wave = []
        for j in range(n):
            typ = "blue"
            if (j + 1) % red_every == 0:
                typ = "red"
            elif (j + 1) % gray_every == 0:
                typ = "gray"
            x = 80 + (j % 12) * 96
            wave.append({"type": typ, "x": x, "delay": j * 0.16})
        return wave

    def _make_wave_sine(self, n):
        wave = []
        for j in range(n):
            typ = random.choice(["blue", "gray", "blue", "red"])  # più blu
            x = 100 + (j % 11) * 100
            wave.append({"type": typ, "x": x, "delay": j * 0.14})
        return wave

    def _make_wave_swarm(self, n):
        wave = []
        for j in range(n):
            typ = random.choice(["blue", "gray", "red"])
            x = random.randint(80, WIN_W - 80)
            wave.append({"type": typ, "x": x, "delay": j * 0.10})
        return wave
    
    
    # --------------- INPUT ----------------
    def _on_canvas_click(self, event):
        if self.state != "playing":
            return
        self._shoot()

    def _on_key_down(self, event):
        k = event.keysym.lower()
        self.pressed.add(k)

    def _on_key_up(self, event):
        k = event.keysym.lower()
        if k in self.pressed:
            self.pressed.remove(k)

    def _handle_escape(self, event):
        """Gestisce il tasto ESC a seconda dello stato del gioco"""
        if getattr(self, "state", None) == "playing":
            self._toggle_pause()
        elif getattr(self, "state", None) in ("menu", "levels"):
            # In futuro potresti aggiungere un suono o azione qui
            pass
    # --------------- GAME LOOP ----------------
    def _update_loop(self):
        now = time.time()
        dt = now - getattr(self, "_last_time", now)
        self._last_time = now

        if self.state == "playing":
            self._update_player(dt)
            self._update_enemies(dt)
            self._update_bullets(dt)
            self._update_enemy_bullets(dt)
            self._update_powerups(dt)
            self._update_hud()
            self._update_waves(dt)
            if self.boss:
                self.boss.update(dt)

        self.after(FRAME_DELAY_MS, self._update_loop)
        if getattr(self, "paused", False):
            return  # ⛔ Blocca tutto se in pausa

    # --------------- PLAYER ----------------
    def _shoot(self):
        import pygame
        now = time.time()
        if now - self.last_shot < self.shot_cooldown:
            return
        self.last_shot = now

        dmg = 1
        is_hyper = self.player["hyper_until"] > now
        if is_hyper:
            dmg = 6

        # --- Riproduzione suono in base alla modalità ---
        try:
            if is_hyper:
                sound_path = os.path.join(ASSET_DIR, "samus", "R_shoot.mp3")
            else:
                sound_path = os.path.join(ASSET_DIR, "samus", "shoot.mp3")

            sound = pygame.mixer.Sound(sound_path)
            sound.play()
        except Exception as e:
            print(f"Errore suono sparo: {e}")


        # --- Creazione proiettile ---
        sx, sy = self.player["x"], self.player["y"] - 28
        bid = self.canvas.create_line(
            sx, sy, sx, sy + (BULLET_SPEED * 2),
            fill="yellow", width=BULLET_WIDTH
        )

        self.bullets.append({
            "id": bid,
            "x": sx,
            "y": sy,
            "dx": 0,
            "dy": BULLET_SPEED,
            "damage": dmg
        })


    def _update_player(self, dt):
        # movement
        ax = 0; ay = 0
        if "a" in self.pressed or "left" in self.pressed: ax -= 1
        if "d" in self.pressed or "right" in self.pressed: ax += 1
        if "w" in self.pressed or "up" in self.pressed: ay -= 1
        if "s" in self.pressed or "down" in self.pressed: ay += 1

        mag = math.hypot(ax, ay)
        if mag > 0: ax /= mag; ay /= mag

        sprinting = ("shift_l" in self.pressed) or ("shift_r" in self.pressed)
        self.player["sprinting"] = False
        speed = self.player["base_speed"]

        now = time.time()

        # --- DASH ---
        if sprinting and self.player["stamina"] >= 1 and (ax != 0 or ay != 0):
            last_dash = self.player.get("last_dash", 0)
            if now - last_dash >= 0.5:  # cooldown dash
                self.player["sprinting"] = True
                self.player["stamina"] -= 1
                self.player["last_dash"] = now
                self.player["stamina_recharge_time"] = now + 3.0  # inizio ricarica

                # --- Suono dash ---
                try:
                    dash_path = os.path.join(ASSET_DIR, "dash", "dash.mp3")
                    dash_sound = pygame.mixer.Sound(dash_path)
                    dash_sound.play()
                except Exception as e:
                    print(f"Errore suono dash: {e}")


                # --- Movimento dash ---
                dash_distance = 80
                self.player["x"] += ax * dash_distance
                self.player["y"] += ay * dash_distance

                # --- Sprite dash ---
                if ax < 0: 
                    dash_sprite_img = self.dash_left
                elif ax > 0: 
                    dash_sprite_img = self.dash_right
                else: 
                    dash_sprite_img = self.dash_center

                dash_sprite = self.canvas.create_image(self.player["x"], self.player["y"], image=dash_sprite_img)
                self.after(200, lambda _id=dash_sprite: self.canvas.delete(_id))

                # --- Scia blu ---
                if random.random() < 0.25:
                    r = random.randint(3, 7)
                    tid = self.canvas.create_oval(
                        self.player["x"] - r, self.player["y"] - r,
                        self.player["x"] + r, self.player["y"] + r,
                        fill="#4fd2ff", outline=""
                    )
                    self.after(160, lambda _id=tid: self.canvas.delete(_id))
        else:
            self.player["sprinting"] = False


        # --- RIGENERAZIONE STAMINA ---
        if self.player["stamina"] < self.player["max_stamina"]:
            if now >= self.player["stamina_recharge_time"]:
                self.player["stamina"] += 1
                self.player["stamina_recharge_time"] = now + 3.0  # prossimo punto tra 3 sec
                self.player["stamina"] = min(self.player["stamina"], self.player["max_stamina"])

        
        # power-ups effetti
        if self.player["rapid_until"] > now:
            self.shot_cooldown = max(0.02, self.default_shot_cooldown * 0.45)
        else:
            self.shot_cooldown = self.default_shot_cooldown

        self.player["vx"] = ax * speed
        self.player["vy"] = ay * speed
        self.player["x"] = clamp(self.player["x"] + self.player["vx"], 40, WIN_W - 40)
        self.player["y"] = clamp(self.player["y"] + self.player["vy"], 60, WIN_H - 60)

        # ship orientation + rainbow while hyper
        if self.player["hyper_until"] > now:
            # modalità rainbow: usa le versioni arcobaleno
            if self.player["vx"] < -0.4:
                new_img = self.ship_r_left
            elif self.player["vx"] > 0.4:
                new_img = self.ship_r_right
            else:
                new_img = self.ship_rainbow
        else:
            # modalità normale
            if self.player["vx"] < -0.4:
                new_img = self.ship_left
            elif self.player["vx"] > 0.4:
                new_img = self.ship_right
            else:
                new_img = self.ship_center

        # aggiorna immagine se è cambiata
        if new_img is not self.current_ship_img:
            self.current_ship_img = new_img
            self.canvas.itemconfigure(self.ship_item, image=new_img)

        # aggiorna posizione
        self.canvas.coords(self.ship_item, self.player["x"], self.player["y"])

        if getattr(self, "paused", False):
            return

    # --------------- ENEMIES/BULLETS/POWERUPS ----------------
    def spawn_enemy(self, typ, x):
        self.enemies.append(Enemy(self, typ, x, y=-40))

    def spawn_powerup(self, typ, x, y):
        img = self.pu_images.get(typ)
        if img:
            pid = self.canvas.create_image(x - 12, y - 12, image=img, anchor="nw")
        else:
            color = {"energy": "#7aff9a", "rapid": "#7ad1ff", "hyper": "#ff7ae1"}.get(typ, "white")
            pid = self.canvas.create_oval(x - 12, y - 12, x + 12, y + 12, fill=color, outline="")
        self.powerups.append({"id": pid, "type": typ, "x": x, "y": y})

    def _update_enemies(self, dt):
        for e in list(self.enemies):
            e.update(dt)

            # probabilità di sparo diversa per tipo
            if e.type == "red" and random.random() < 0.020:
                self.E_shoot(e)
            elif e.type == "gray" and random.random() < 0.010:
                self.E_shoot(e)
            elif e.type == "blue" and random.random() < 0.005:
                self.E_shoot(e)

            # se esce dallo schermo
            if e.y > WIN_H + 60:
                try:
                    self.canvas.delete(e.id)
                except Exception:
                    pass
                if e in self.enemies:
                    self.enemies.remove(e)
                continue

            # collisione con il player
            if math.hypot(e.x - self.player["x"], e.y - self.player["y"]) < (e.radius + PLAYER_RADIUS):
                self.damage_player(1)
                e.destroy()
                if e in self.enemies:
                    self.enemies.remove(e)

    def damage_player(self, dmg):
        """Riduce la vita del giocatore e riproduce il suono di danno se sopravvive."""
        new_health = self.player["health"] - max(1, int(dmg))
        new_health = max(0, new_health)
        
        # --- Riproduci suono solo se il player SOPRAVVIVE ---
        if new_health > 0:
            try:
                hit_path = os.path.join(ASSET_DIR, "life", "damage.mp3")
                hit_sound = pygame.mixer.Sound(hit_path)
                hit_sound.play()
            except Exception as e:
                print(f"Errore suono danno: {e}")

        self.player["health"] = new_health

        # --- Applica il danno effettivo ---
        self.player["health"] = new_health
        
        # --- Effetto visivo di impatto ---
        pid = self.canvas.create_oval(
            self.player["x"] - 28, self.player["y"] - 28,
            self.player["x"] + 28, self.player["y"] + 28,
            outline="white"
        )
        self.after(220, lambda _id=pid: self.canvas.delete(_id))

        # --- Se la vita scende a 0 o meno → morte ---
        if self.player["health"] <= 0:
            self._on_player_dead()

    def _on_player_dead(self):
        import tkinter as tk
        from PIL import Image, ImageTk, ImageSequence
        import pygame

         # --- Previene doppi trigger di morte ---
        if getattr(self, "_player_dead", False):
            return
        self._player_dead = True
        # --- Stop musica di background ---
        try:
            pygame.mixer.music.stop()
        except Exception as e:
            print(f"Errore stop musica: {e}")

       # --- Suono di morte ---
        try:
            death_path = os.path.join(ASSET_DIR, "samus", "end.mp3")
            death_sound = pygame.mixer.Sound(death_path)
            death_sound.play()
        except Exception as e:
            print(f"Errore suono morte: {e}")

        # --- Blocca logica di gioco ---
        self.wave_active = False
        self.enemies.clear()
        self.powerups.clear()
        self.bullets.clear()

        # --- Mostra GIF di sconfitta direttamente nella finestra principale ---
        try:
            try:
                gif_path = os.path.join(ASSET_DIR, "DV", "endi.gif")
                im = Image.open(gif_path)
            except Exception as e:
                print(f"Errore caricamento GIF di sconfitta: {e}")


            # Carica subito il primo frame (per evitare ritardo visivo)
            first_frame = ImageTk.PhotoImage(im.copy().convert("RGBA").resize((WIN_W, WIN_H), Image.LANCZOS))
            self.gif_label = tk.Label(self, bg="black", image=first_frame)
            self.gif_label.image = first_frame
            self.gif_label.place(x=0, y=0, width=WIN_W, height=WIN_H)
            self.update_idletasks()

            # Carica tutti i frame
            frames = []
            for frame in ImageSequence.Iterator(im):
                frame = frame.copy().convert("RGBA").resize((WIN_W, WIN_H), Image.LANCZOS)
                frames.append(ImageTk.PhotoImage(frame))
            self.frames_defeat = frames

            # --- Animazione fluida (10 fps) ---
            def update_frame(i=0):
                if not hasattr(self, "gif_label") or not self.gif_label.winfo_exists():
                    return
                self.gif_label.config(image=self.frames_defeat[i])
                self.after(100, update_frame, (i + 1) % len(self.frames_defeat))  # 10fps

            update_frame(0)

            # --- Testo "GAME OVER" sopra la GIF ---
            txt = tk.Label(
                self,
                text="GAME OVER",
                font=("Arial", 36, "bold"),
                fg="red",
                bg="black"
            )
            txt.place(relx=0.5, rely=0.9, anchor="center")

            # --- Dopo 5 secondi: rimuove la GIF e torna al menu ---
            def close_defeat():
                if hasattr(self, "gif_label") and self.gif_label.winfo_exists():
                    self.gif_label.destroy()
                txt.destroy()
                self._show_menu()

            self.after(4500, close_defeat)

        except Exception as e:
            print(f"Errore caricamento o animazione GIF: {e}")

    def E_shoot(self, enemy):
        """Crea un proiettile nemico inclinato verso il giocatore e riproduce il suono di sparo."""
        if not self.player:
            return

        try:
            sound_path = os.path.join(ASSET_DIR, "E_shoot.mp3")
            pygame.mixer.Sound(sound_path).play()
        except Exception as e:
            print(f"Errore suono E_shoot: {e}")


        # Posizione iniziale
        ex, ey = enemy.x, enemy.y
        px, py = self.player["x"], self.player["y"]

        # Calcolo direzione verso il player
        dx = px - ex
        dy = py - ey
        dist = math.hypot(dx, dy)
        if dist == 0:
            dist = 1
        dx /= dist
        dy /= dist

        # Velocità proiettile
        speed = 6.0  # puoi aumentare o diminuire

        # Crea proiettile sul canvas (più allungato)
        length = 24  # più grande del player bullet
        bid = self.canvas.create_line(
            ex, ey, ex + dx * length, ey + dy * length, fill="#ff6b6b", width=3
        )

        # Aggiunge proiettile alla lista
        self.enemy_bullets.append({
            "id": bid,
            "x": ex,
            "y": ey,
            "dx": dx * speed,
            "dy": dy * speed,
            "damage": 1
        })


    def _update_enemy_bullets(self, dt):
        for b in list(self.enemy_bullets):
            b["x"] += b["dx"]
            b["y"] += b["dy"]

            # Aggiorna posizione della linea
            try:
                self.canvas.coords(
                    b["id"],
                    b["x"], b["y"],
                    b["x"] + (b["dx"] * 4),
                    b["y"] + (b["dy"] * 4)
                )
            except Exception:
                continue

            # Collisione con il giocatore
            if math.hypot(b["x"] - self.player["x"], b["y"] - self.player["y"]) < 24:
                self.damage_player(b["damage"])
                try:
                    self.canvas.delete(b["id"])
                except Exception:
                    pass
                self.enemy_bullets.remove(b)
                continue

            # Se esce dallo schermo
            if (b["x"] < -50 or b["x"] > WIN_W + 50 or
                    b["y"] < -50 or b["y"] > WIN_H + 50):
                try:
                    self.canvas.delete(b["id"])
                except Exception:
                    pass
                self.enemy_bullets.remove(b)

    def _update_bullets(self, dt):
        for b in list(self.bullets):
            b["x"] += b["dx"]
            b["y"] += b["dy"]
            try:
                self.canvas.coords(b["id"], b["x"], b["y"], b["x"], b["y"] + (b["dy"] * 2))
            except Exception:
                pass
            hit_any = False
            # vs enemies
            for e in list(self.enemies):
                if math.hypot(e.x - b["x"], e.y - b["y"]) < (e.radius + 6):
                    dead = e.hit(b.get("damage", 1))
                    try: self.canvas.delete(b["id"])
                    except Exception: pass
                    if b in self.bullets: self.bullets.remove(b)
                    if dead and e in self.enemies: self.enemies.remove(e)
                    hit_any = True
                    break
            if hit_any:
                continue
            # vs boss
            if self.boss:
                if math.hypot(self.boss.x - b["x"], self.boss.y - b["y"]) < 90:
                    dead = self.boss.hit(b.get("damage", 1))
                    try: self.canvas.delete(b["id"])
                    except Exception: pass
                    if b in self.bullets: self.bullets.remove(b)
                    if dead:
                        self.boss = None
                else:
                    # cull offscreen
                    if b["y"] < -60 or b["y"] > WIN_H + 60 or b["x"] < -60 or b["x"] > WIN_W + 60:
                        try: self.canvas.delete(b["id"])
                        except Exception: pass
                        if b in self.bullets: self.bullets.remove(b)
            else:
                if b["y"] < -60 or b["y"] > WIN_H + 60 or b["x"] < -60 or b["x"] > WIN_W + 60:
                    try: self.canvas.delete(b["id"])
                    except Exception: pass
                    if b in self.bullets: self.bullets.remove(b)

    def _update_powerups(self, dt):
        for pu in list(self.powerups):
            pu["y"] += 0.9
            try:
                self.canvas.coords(pu["id"], pu["x"] - 12, pu["y"] - 12)
            except Exception:
                pass
            if math.hypot(pu["x"] - self.player["x"], pu["y"] - self.player["y"]) < 36:
                typ = pu["type"]
                now = time.time()
                if typ == "energy":
                    if self.player["health"] < self.player["max_health"]:
                        self.player["health"] = min(self.player["max_health"], self.player["health"] + 1)
                    # se vita piena: nullo (non fa nulla)
                elif typ == "rapid":
                    self.player["rapid_until"] = now + 10.0
                elif typ == "hyper":
                    self.player["hyper_until"] = now + 20.0
                try: self.canvas.delete(pu["id"])
                except Exception: pass
                if pu in self.powerups: self.powerups.remove(pu)
            elif pu["y"] > WIN_H + 40:
                try: self.canvas.delete(pu["id"])
                except Exception: pass
                if pu in self.powerups: self.powerups.remove(pu)

    # --------------- HUD & WAVES ----------------
    def _update_hud(self):
        # stamina (icone fisse per dash)
        if self.stamina_frames and self.stamina_img_id:
            st = clamp(int(self.player["stamina"]), 0, 3)  # 0-3
            # st = 3 → dash_4.png, 2 → dash_3.png, 1 → dash_2.png, 0 → dash_1.png
            frame_idx = st  # se le immagini sono in ordine dash_1→0, dash_2→1, dash_3→2, dash_4→3
            frame = self.stamina_frames[frame_idx]
            if frame is not self.current_stamina_frame:
                self.current_stamina_frame = frame
                self.canvas.itemconfigure(self.stamina_img_id, image=frame)


        # life (7 barrette)
        if self.life_frames and self.life_img_id:
            missing = clamp(self.player["max_health"] - self.player["health"], 0, 6)
            frame = self.life_frames[missing]
            try:
                self.canvas.itemconfigure(self.life_img_id, image=frame)
            except Exception:
                pass

        # wave label
        if self.wave_active:
            self.canvas.delete("wave_text")
            self.canvas.create_text(86, 40, text=f"WAVE {min(self.wave_index + 1, len(self.waves))}/{len(self.waves)}",
                                    font=("Arial", 16), fill="white", tags="wave_text")
        elif self.boss:
            # boss HP bar
            self.canvas.delete("wave_text")
            pct = self.boss.hp / max(1, self.boss.max_hp)
            w = int(300 * pct)
            x0, y0 = WIN_W // 2 - 150, 20
            self.canvas.delete("boss_hp")
            self.canvas.create_rectangle(x0, y0, x0 + 300, y0 + 16, outline="white", tags="boss_hp")
            self.canvas.create_rectangle(x0, y0, x0 + w, y0 + 16, fill="#ff6b6b", outline="", tags="boss_hp")

    def _update_waves(self, dt):
        if not self.wave_active or self.wave_index >= len(self.waves):
            return
        current = self.waves[self.wave_index]
        self.wave_timer += dt

        for spawn in current:
            if spawn.get("type") == "_BOSS_":
                if not self.enemies and self.boss is None:
                    self._spawn_boss(spawn.get("name", "Boss"))
                    spawn["spawned"] = True
                continue
            if not spawn.get("spawned") and self.wave_timer >= spawn.get("delay", 0.0):
                self.spawn_enemy(spawn.get("type", "blue"), spawn.get("x", WIN_W // 2))
                spawn["spawned"] = True

        # advance
        all_spawned = all(sp.get("spawned", False) for sp in current)
        if all_spawned:
            if (not self.enemies) and (self.boss is None):
                if self._wave_finish_timer is None:
                    self._wave_finish_timer = 0.0
                self._wave_finish_timer += dt
                if self._wave_finish_timer >= self.wave_gap:
                    self.wave_index += 1
                    self.wave_timer = 0.0
                    self._wave_finish_timer = None
                    if self.wave_index >= len(self.waves):
                        self.wave_active = False
            else:
                self._wave_finish_timer = 0.0

    #----------------pause-----------------

    def _toggle_pause(self):
        """Attiva o disattiva la pausa."""
        # Se non stai giocando → ignora
        if getattr(self, "state", None) != "playing":
            return

        # Se già in pausa → riprendi
        if getattr(self, "paused", False):
            self._resume_game()
        else:
            self._pause_game()
    def _pause_game(self):
        """Mostra menu di pausa e blocca il gioco"""
        self.paused = True
        self.wave_active = False  # blocca nemici / spawn

        # --- Filtro grigio trasparente ---
        self.pause_overlay = self.canvas.create_rectangle(
            0, 0, WIN_W, WIN_H,
            fill="black", stipple="gray50", outline="",
            tags="pause_menu"
        )

        # --- Titolo ---
        self.canvas.create_text(
            WIN_W // 2, 150,
            text="PAUSE",
            font=("Arial", 48, "bold"),
            fill="white",
            tags="pause_menu"
        )

        # --- Pulsanti ---
        bw, bh = 260, 70
        spacing = 100
        start_y = 250
        buttons = [
            ("Resume", self._resume_game),
            ("Options", self._open_options_menu),
            ("Menu", self._back_to_main_menu)
        ]

        for i, (label, action) in enumerate(buttons):
            y = start_y + i * spacing
            tag = f"pause_btn_{i}"
            self.canvas.create_rectangle(
                WIN_W // 2 - bw // 2, y - bh // 2,
                WIN_W // 2 + bw // 2, y + bh // 2,
                fill="#223344", outline="white", width=3, tags=(tag, "pause_menu")
            )
            self.canvas.create_text(
                WIN_W // 2, y,
                text=label,
                font=("Arial", 28),
                fill="white",
                tags=(tag, "pause_menu")
            )
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, f=action: f())

    def _resume_game(self):
        """Chiude il menu di pausa e riprende il gioco"""
        if not getattr(self, "paused", False):
            return

        self.paused = False
        self.wave_active = True
        self.canvas.delete("pause_menu")
        if hasattr(self, "pause_overlay"):
            self.canvas.delete(self.pause_overlay)
            self.pause_overlay = None

    def _open_options_menu(self):
        """Mostra menu opzioni con slider volume"""
        self.canvas.delete("pause_menu")

        self.canvas.create_text(
            WIN_W // 2, 150,
            text="OPtions",
            font=("Arial", 40, "bold"),
            fill="white",
            tags="options_menu"
        )

        self.canvas.create_text(
            WIN_W // 2 - 100, WIN_H // 2,
            text="Volume:",
            font=("Arial", 24),
            fill="white",
            tags="options_menu"
        )

        import tkinter as tk
        self.volume_var = tk.DoubleVar(value=pygame.mixer.music.get_volume() * 100)
        self.volume_slider = tk.Scale(
            self,
            from_=0, to=100,
            orient="horizontal",
            variable=self.volume_var,
            command=lambda v: pygame.mixer.music.set_volume(float(v) / 100),
            length=200,
            bg="#223344", fg="white",
            troughcolor="#112233", highlightthickness=0
        )
        self.volume_slider.place(x=WIN_W // 2, y=WIN_H // 2 - 20, anchor="w")

        self.canvas.create_rectangle(
            WIN_W // 2 - 120, WIN_H - 120,
            WIN_W // 2 + 120, WIN_H - 60,
            fill="#223344", outline="white", width=3, tags=("back_from_options", "options_menu")
        )
        self.canvas.create_text(
            WIN_W // 2, WIN_H - 90,
            text="Back",
            font=("Arial", 24),
            fill="white",
            tags=("back_from_options", "options_menu")
        )
        self.canvas.tag_bind("back_from_options", "<Button-1>", lambda e: self._close_options_menu())

    def _close_options_menu(self):
        """Ritorna al menu pausa"""
        self.canvas.delete("options_menu")
        if hasattr(self, "volume_slider"):
            self.volume_slider.destroy()
        self._pause_game()
    
    def _back_to_main_menu(self):
        """Ferma musica e torna al menu principale"""
        try:
            pygame.mixer.music.stop()
        except Exception as e:
            print(f"Errore stop musica: {e}")

        self.paused = False
        self.wave_active = False
        self.state = "menu"

        self.canvas.delete("pause_menu")
        if hasattr(self, "pause_overlay"):
            self.canvas.delete(self.pause_overlay)
            self.pause_overlay = None

        self._show_menu()

   # --------------- BOSS ----------------
    def _spawn_boss(self, name):
        self.stop_music()
        nm = name.lower()

        try:
            # --- Percorsi dinamici ---
            botwoon_dir = os.path.join(ASSET_DIR, "botwoon")
            phantom_dir = os.path.join(ASSET_DIR, "phantom")
            ridley_dir = os.path.join(ASSET_DIR, "ridley")

            # --- Botwoon ---
            if nm == "botwoon":
                self.boss = Boss(self, "Botwoon", self.sheet_botwoon, {"hp": 160})
                music_path = os.path.join(botwoon_dir, "boot.mp3")

            # --- Phantom ---
            elif nm == "phantom":
                self.boss = Boss(self, "Phantom", self.sheet_phantom, {"hp": 220})
                music_path = os.path.join(phantom_dir, "phantom.mp3")

            # --- Ridley ---
            else:
                self.boss = Boss(self, "Ridley", self.sheet_ridley, {"hp": 300})
                music_path = os.path.join(ridley_dir, "bossfight_R.mp3")

            # --- Carica e avvia musica ---
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.play(-1)

        except Exception as e:
            print(f"Errore caricamento musica boss {name}: {e}")

        self.wave_active = False


    def on_boss_defeated(self, boss_name=None):
        from PIL import Image, ImageTk, ImageSequence
        import pygame
        import os

        # --- Ferma musica ---
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

        boss_name = (boss_name or "").lower()

       # --- Seleziona GIF, durata e suono ---
        dv_dir = os.path.join(ASSET_DIR, "DV")
        cop_dir = os.path.join(ASSET_DIR, "cop")

        if boss_name.lower() in ("botwoon", "phantom", "phanthoon"):
            gif_path = os.path.join(dv_dir, "win.gif")
            total_ms = 4150
            show_victory_text = True
            sound_path = os.path.join(dv_dir, "wini.mp3")

        elif boss_name.lower() == "ridley":
            gif_path = os.path.join(cop_dir, "cop.gif")
            total_ms = 35000
            show_victory_text = False
            sound_path = os.path.join(cop_dir, "COP.mp3")

        else:
            # Default: testo semplice
            gif_path = None
            total_ms = 0
            show_victory_text = True
            sound_path = None

            self.canvas.create_text(
                WIN_W // 2, WIN_H // 2,
                text="LIVELLO COMPLETATO!",
                font=("Arial", 36, "bold"),
                fill="#7aff9a"
            )

            self.after(1200, lambda: self._show_level_select())
            return

        # --- Verifica esistenza file GIF ---
        if not os.path.exists(gif_path):
            print(f"GIF non trovata: {gif_path}")
            self.canvas.create_text(
                WIN_W // 2, WIN_H // 2,
                text="LIVELLO COMPLETATO!",
                font=("Arial", 36, "bold"),
                fill="#7aff9a"
            )
            self.after(1200, lambda: self._show_level_select())
            return

        # --- Carica e ridimensiona GIF a tutto schermo ---
        try:
            gif = Image.open(gif_path)
            frames = []
            durations = []
            for frame in ImageSequence.Iterator(gif):
                resized = frame.convert("RGBA").resize((WIN_W, WIN_H), Image.Resampling.LANCZOS)
                frames.append(ImageTk.PhotoImage(resized))
                durations.append(gif.info.get("duration", 100))
        except Exception as e:
            print(f"Errore caricamento GIF {gif_path}: {e}")
            self.canvas.create_text(
                WIN_W // 2, WIN_H // 2,
                text="LIVELLO COMPLETATO!",
                font=("Arial", 36, "bold"),
                fill="#7aff9a"
            )
            self.after(1200, lambda: self._show_level_select())
            return

        # --- Testo "VICTORY!" per botwoon/phantom ---
        text_id = None
        if show_victory_text:
            text_id = self.canvas.create_text(
                WIN_W // 2, 60,
                text="VICTORY!",
                font=("Arial", 40, "bold"),
                fill="#7aff9a"
            )

        # --- Mostra la GIF a schermo intero ---
        gif_id = self.canvas.create_image(WIN_W // 2, WIN_H // 2, image=frames[0])
        if not hasattr(self, "_gif_refs"):
            self._gif_refs = []
        self._gif_refs.append({"frames": frames, "gif_id": gif_id, "text_id": text_id})

        # --- Suono: parte solo quando la GIF è mostrata (cioè adesso) ---
        if sound_path and os.path.exists(sound_path):
            try:
                sound = pygame.mixer.Sound(sound_path)
                sound.play()
            except Exception as e:
                print(f"Errore suono vittoria: {e}")

        # --- Animazione GIF ---
        def animate(idx=0):
            try:
                self.canvas.itemconfig(gif_id, image=frames[idx])
            except Exception:
                return
            dur = durations[idx] if idx < len(durations) else 100
            self.after(dur, lambda: animate((idx + 1) % len(frames)))

        animate(0)

        # --- Dopo la durata, torna al menu ---
        self.after(total_ms, lambda: self._show_level_select())


if __name__ == "__main__":
    app = GalaxedApp()
    app.mainloop()
