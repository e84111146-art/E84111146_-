import pygame
import sys
import random
import math
import os
import json

pygame.init()
WIDTH, HEIGHT = 800, 400
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("橫向射擊遊戲：闖關版")
clock = pygame.time.Clock()

# ---------- Assets ----------
ASSET_DIR = "."
def load_image_try(*names, size=None, fallback_color=(200, 0, 0)):
    for n in names:
        try:
            img = pygame.image.load(n).convert_alpha()
            if size: img = pygame.transform.scale(img, size)
            return img
        except Exception:
            continue
    surf = pygame.Surface(size if size else (40, 40), pygame.SRCALPHA)
    surf.fill(fallback_color)
    return surf

class _Silent:
    def play(self): pass
    def set_volume(self, v): pass

def load_sound_try(*names):
    for n in names:
        try: return pygame.mixer.Sound(n)
        except Exception: continue
    return _Silent()

# Sounds (silent fallbacks if missing)
shoot_sound = load_sound_try("Sound/shoot4.mp3", os.path.join(ASSET_DIR, "shoot4.mp3")); shoot_sound.set_volume(0.4)
enemy_dead_sound = load_sound_try("Sound/enemy die.mp3", os.path.join(ASSET_DIR, "enemy die.mp3")); enemy_dead_sound.set_volume(0.5)

# Fonts & colors
WHITE=(255,255,255); BLACK=(0,0,0); RED=(255,0,0); GREEN=(0,255,0); YELLOW=(255,255,0)
font = pygame.font.SysFont(None, 24); big_font = pygame.font.SysFont(None, 56); title_font = pygame.font.SysFont(None, 72)

# Game states
STATE_MENU="menu"; STATE_LEVEL_SELECT="level_select"
STATE_LEVEL_INTRO="level_intro"; STATE_PLAYING="playing"; STATE_SHOP="shop"
STATE_GAME_OVER="game_over"; STATE_VICTORY="victory"

# Player
player = pygame.Rect(50, HEIGHT-60, 40, 40)
PLAYER_MAX_HP = 10
player_speed_base = 5
player_hp = PLAYER_MAX_HP
player_exp = 0
player_gold = 0
bullet_speed_base = 7
bullet_double = False; bullet_double_timer = 0
bullet_fast = False; bullet_fast_timer = 0

# Entities
bullets = []; enemy_bullets = []; enemies = []; items = []
enemy_spawn_timer = 0

# Era & progression
ERA_NAMES = {1:"Prehistoric Era", 2:"Dutch Rule", 3:"Japanese Rule"}
level = 1; MAX_LEVEL = 3; level_intro_timer = 0

def level_params(lv):
    return {
        1: {"enemy_hp":30, "spawn_cd":60, "enemy_speed":2.0, "enemy_bullet_chance":0.010, "boss_hp":220},
        2: {"enemy_hp":42, "spawn_cd":50, "enemy_speed":2.4, "enemy_bullet_chance":0.014, "boss_hp":280},
        3: {"enemy_hp":56, "spawn_cd":40, "enemy_speed":2.8, "enemy_bullet_chance":0.018, "boss_hp":340},
    }[min(max(lv,1),3)]

# Images
player_img = load_image_try("hero.png", os.path.join(ASSET_DIR, "hero.png"), size=(70, 70))
ENEMY_IMAGES = {
    1: load_image_try("原始人.png", os.path.join(ASSET_DIR, "原始人.png"), size=(70,70)),
    2: load_image_try("荷蘭人.png", os.path.join(ASSET_DIR, "荷蘭人.png"), size=(70,70)),
    3: load_image_try("日本人.png", os.path.join(ASSET_DIR, "日本人.png"), size=(70,70)),
}
BOSS_IMAGES = {
    1: load_image_try("原始人.png", os.path.join(ASSET_DIR, "原始人.png"), size=(170,170)),
    2: load_image_try("荷蘭人.png", os.path.join(ASSET_DIR, "荷蘭人.png"), size=(180,180)),
    3: load_image_try("日本人.png", os.path.join(ASSET_DIR, "日本人.png"), size=(190,190)),
}
BG_IMAGES = {
    1: load_image_try("bg_level1.png", os.path.join(ASSET_DIR, "bg_level1.png"), size=(WIDTH, HEIGHT), fallback_color=(120,90,60)),
    2: load_image_try("bg_level2.png", os.path.join(ASSET_DIR, "bg_level2.png"), size=(WIDTH, HEIGHT), fallback_color=(120,170,210)),
    3: load_image_try("bg_level3.png", os.path.join(ASSET_DIR, "bg_level3.png"), size=(WIDTH, HEIGHT), fallback_color=(230,200,200)),
}
MENU_BG = load_image_try("menu_bg.png", os.path.join(ASSET_DIR, "menu_bg.png"), size=(WIDTH, HEIGHT), fallback_color=(20,20,40))

# Boss
boss = None; boss_alive = False

# Items (shop images are optional; if missing, simple squares are used)
item_images = {
    "heal": pygame.image.load("Image/power/heal.png"),
    "speed": pygame.image.load("Image/power/speed.png"),
    "double": pygame.image.load("Image/power/double.png"),
    "exp": pygame.image.load("Image/power/exp.png"),
}
for k in item_images:
    item_images[k] = pygame.transform.scale(item_images[k], (20, 20))

# 商店圖片
shop_images = {
    "speed": pygame.image.load("Image/power/speed.png"),
    "double": pygame.image.load("Image/power/double.png"),
    "heal": pygame.image.load("Image/power/heal.png"),
}

# Save/Load
SAVE_PATH = "savegame.json"
def save_game(max_unlocked, gold=0):
    data = {"max_unlocked": int(max_unlocked), "gold": int(gold)}
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f: json.dump(data, f)
        return True
    except Exception as e:
        print("Save failed:", e); return False

def load_game():
    if not os.path.exists(SAVE_PATH): return {"max_unlocked": 1, "gold": 0}
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f: data = json.load(f)
        if not isinstance(data, dict): raise ValueError("Bad format")
        return {"max_unlocked": int(data.get("max_unlocked", 1)), "gold": int(data.get("gold", 0))}
    except Exception as e:
        print("Load failed:", e); return {"max_unlocked": 1, "gold": 0}

save_data = load_game()

# Helpers
def reset_player():
    global player, player_hp, player_exp
    player.x, player.y = 50, HEIGHT-60
    player_hp = PLAYER_MAX_HP
    player_exp = 0

def clear_entities():
    bullets.clear(); enemy_bullets.clear(); enemies.clear(); items.clear()

def start_level(lv):
    global level, level_intro_timer, boss, boss_alive, game_state
    level = lv; clear_entities(); reset_player()
    boss = None; boss_alive = False
    level_intro_timer = 90; game_state = STATE_LEVEL_INTRO

def spawn_enemy():
    y = random.choice([HEIGHT-60, HEIGHT-160, HEIGHT-260])
    vy = random.choice([-1, 0, 1])
    return {"rect": pygame.Rect(WIDTH, y, 40, 40), "hp": level_params(level)["enemy_hp"], "vy": vy}

def spawn_boss():
    hp = level_params(level)["boss_hp"]; vy = random.choice([-2,-1,1,2])
    return {"rect": pygame.Rect(WIDTH-220, HEIGHT//2-80, 160, 160), "hp": hp, "timer": 0, "vy": vy}

def draw_hp_bar(x, y, current, max_value, width=120, height=12):
    pygame.draw.rect(screen, RED, (x, y, width, height))
    ratio = max(0, current/max_value)
    pygame.draw.rect(screen, GREEN, (x, y, int(width*ratio), height))

def spawn_enemy_bullet(x, y, vx, vy, size=8):
    enemy_bullets.append({"rect": pygame.Rect(x, y, size, size), "vx": vx, "vy": vy})

def boss_attack_pattern(b):
    t = b["timer"]; bx, by = b["rect"].centerx, b["rect"].centery
    if level == 1:
        if t % 18 == 0: spawn_enemy_bullet(bx-20, by, -6, 0, size=12)
    elif level == 2:
        if t % 36 == 0:
            for vy in (-2,0,2): spawn_enemy_bullet(bx-20, by, -6.5, vy, size=10)
    elif level == 3:
        if t % 30 == 0:
            for ang_deg in (-30,-15,0,15,30):
                ang = math.radians(ang_deg)
                vx = -7 * math.cos(ang); vy = 7 * math.sin(ang)
                spawn_enemy_bullet(bx-20, by, vx, vy, size=10)

def handle_shop_keydown(key):
    global bullet_fast, bullet_fast_timer, bullet_double, bullet_double_timer, player_hp, player_gold, game_state
    if key == pygame.K_1 and player_gold >= 200: bullet_fast=True; bullet_fast_timer=300; player_gold-=200; save_game(save_data.get("max_unlocked",1), player_gold)
    elif key == pygame.K_2 and player_gold >= 300: bullet_double=True; bullet_double_timer=300; player_gold-=300; save_game(save_data.get("max_unlocked",1), player_gold)
    elif key == pygame.K_3 and player_gold >= 150: player_hp=min(PLAYER_MAX_HP, player_hp+3); player_gold-=150; save_game(save_data.get("max_unlocked",1), player_gold)
    elif key == pygame.K_ESCAPE: game_state = STATE_PLAYING

def next_level_or_victory():
    global level, game_state, save_data
    if level >= MAX_LEVEL:
        game_state = STATE_VICTORY
    else:
        level += 1
        if save_data.get("max_unlocked", 1) < level:
            save_data["max_unlocked"] = level
            save_data["gold"] = player_gold
            save_game(save_data["max_unlocked"], save_data["gold"])
        start_level(level)

def reset_full_game():
    global level, player_gold, bullet_double, bullet_double_timer, bullet_fast, bullet_fast_timer, game_state
    level = 1; player_gold = 0
    bullet_double = False; bullet_double_timer = 0
    bullet_fast = False; bullet_fast_timer = 0
    start_level(level)

# ---------- Menu / UI helpers ----------
def draw_menu_bg():
    screen.blit(MENU_BG, (0,0))

def button(rect, text, enabled=True, subtext=None):
    # Card-style button with shadow
    shadow = rect.move(0, 4)
    pygame.draw.rect(screen, (0,0,0,80), shadow, border_radius=14)
    pygame.draw.rect(screen, (245, 245, 245) if enabled else (210,210,210), rect, border_radius=14)
    pygame.draw.rect(screen, (40,40,40), rect, 2, border_radius=14)
    label = big_font.render(text, True, (30,30,35) if enabled else (120,120,120))
    screen.blit(label, (rect.centerx - label.get_width()//2, rect.centery - label.get_height()//2))
    if subtext:
        s = font.render(subtext, True, (90,90,100))
        screen.blit(s, (rect.centerx - s.get_width()//2, rect.bottom + 8))
    return rect

def label_center(text, y, font_obj=None, color=WHITE):
    f = font_obj or title_font
    surf = f.render(text, True, color)
    screen.blit(surf, (WIDTH//2 - surf.get_width()//2, y))

# ---------- Autosave timer ----------
autosave_counter = 0

# ---------- Boot to main menu ----------
game_state = STATE_MENU
selected_from_menu = False  # flag to prevent double triggers

# ---------- Main loop ----------
# ---------- Main loop ----------
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            # autosave on quit
            save_game(max(save_data.get("max_unlocked",1), level), player_gold)
            pygame.quit(); sys.exit()

        if event.type == pygame.KEYDOWN:
            if game_state == STATE_MENU:
                if event.key in (pygame.K_RETURN, pygame.K_c):
                    # Continue from highest unlocked
                    target = max(1, min(save_data.get("max_unlocked",1), MAX_LEVEL))
                    start_level(target)
                elif event.key in (pygame.K_n,):
                    # New game from level 1
                    save_data["max_unlocked"] = 1; save_data["gold"] = 0; save_game(1,0)
                    start_level(1)
                elif event.key in (pygame.K_l,):
                    game_state = STATE_LEVEL_SELECT
                elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                    save_game(max(save_data.get("max_unlocked",1), level), player_gold)
                    pygame.quit(); sys.exit()

            elif game_state == STATE_LEVEL_SELECT:
                if event.key == pygame.K_ESCAPE:
                    game_state = STATE_MENU
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    lv = int(event.unicode)
                    if lv <= save_data.get("max_unlocked",1):
                        start_level(lv)

            elif game_state == STATE_LEVEL_INTRO:
                # allow S to visit shop before start
                if event.key == pygame.K_s:
                    game_state = STATE_SHOP
                else:
                    # any key starts
                    game_state = STATE_PLAYING

            elif game_state == STATE_PLAYING:
                if event.key == pygame.K_SPACE:
                    shoot_sound.play()
                    b = pygame.Rect(player.right, player.centery-5, 10, 10)
                    bullets.append(b)
                    if bullet_double:
                        b2 = pygame.Rect(player.right, player.centery+10, 10, 10)
                        bullets.append(b2)
                elif event.key == pygame.K_s:
                    game_state = STATE_SHOP
                elif event.key == pygame.K_F5:
                    max_unlocked = max(save_data.get("max_unlocked", 1), level)
                    if save_game(max_unlocked, player_gold):
                        save_data["max_unlocked"] = max_unlocked
                        save_data["gold"] = player_gold
                elif event.key == pygame.K_F9:
                    save_data = load_game()

            elif game_state == STATE_SHOP:
                if event.key == pygame.K_1 and player_gold >= 300:
                    bullet_double = True
                    bullet_double_timer = 300
                    player_gold -= 300
                elif event.key == pygame.K_2 and player_gold >= 200:
                    bullet_fast = True
                    bullet_fast_timer = 300
                    player_gold -= 200
                elif event.key == pygame.K_3 and player_gold >= 150:
                    player_hp = min(PLAYER_MAX_HP, player_hp + 3)
                    player_gold -= 150
                elif event.key == pygame.K_ESCAPE:
                    game_state = STATE_PLAYING

            elif game_state in (STATE_GAME_OVER, STATE_VICTORY):
                if event.key == pygame.K_r: reset_full_game()
                elif event.key in (pygame.K_q, pygame.K_ESCAPE): 
                    save_game(max(save_data.get("max_unlocked",1), level), player_gold)
                    pygame.quit(); sys.exit()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if game_state == STATE_MENU:
                # click buttons
                bw, bh = 360, 64
                gap = 26
                start_y = HEIGHT//2 - (bh*3 + gap*2)//2
                rects = [
                    pygame.Rect(WIDTH//2 - bw//2, start_y + (bh+gap)*0, bw, bh),  # Continue
                    pygame.Rect(WIDTH//2 - bw//2, start_y + (bh+gap)*1, bw, bh),  # Level Select
                    pygame.Rect(WIDTH//2 - bw//2, start_y + (bh+gap)*2, bw, bh),  # New Game
                ]
                labels = ["Continue", "Level Select", "New Game"]
                for i, r in enumerate(rects):
                    if r.collidepoint(mx, my):
                        if i == 0:
                            target = max(1, min(save_data.get("max_unlocked",1), MAX_LEVEL))
                            start_level(target)
                        elif i == 1:
                            game_state = STATE_LEVEL_SELECT
                        elif i == 2:
                            save_data["max_unlocked"] = 1; save_data["gold"] = 0; save_game(1,0)
                            start_level(1)
                # Quit text zone
                q_rect = pygame.Rect(WIDTH//2-120, HEIGHT-56, 240, 40)
                if q_rect.collidepoint(mx,my):
                    save_game(max(save_data.get("max_unlocked",1), level), player_gold)
                    pygame.quit(); sys.exit()

            elif game_state == STATE_LEVEL_SELECT:
                # Level cards
                bw, bh = 200, 120
                spacing = 40
                total_w = bw*3 + spacing*2
                start_x = WIDTH//2 - total_w//2
                y = HEIGHT//2 - bh//2
                unlocked = save_data.get("max_unlocked", 1)
                for i in range(3):
                    rect = pygame.Rect(start_x + i*(bw+spacing), y, bw, bh)
                    if i+1 <= unlocked and rect.collidepoint(mx, my):
                        start_level(i+1)

    # --- 畫面更新 ---
    if game_state == STATE_SHOP:
        shop_items = [
            {"img": shop_images["double"], "name": "Double", "price": 300, "key": "1"},
            {"img": shop_images["speed"], "name": "Speed", "price": 200, "key": "2"},
            {"img": shop_images["heal"], "name": "Heal +3", "price": 150, "key": "3"},
        ]
        shop_text = big_font.render("[SHOP]", True, WHITE)
        screen.blit(shop_text, (WIDTH // 2 - shop_text.get_width() // 2, 20))
        y_base = 90
        for i, item in enumerate(shop_items):
            card_rect = pygame.Rect(WIDTH // 2 - 180, y_base + i * 100, 360, 90)
            pygame.draw.rect(screen, (230, 230, 230), card_rect, border_radius=12)
            pygame.draw.rect(screen, BLACK, card_rect, 2, border_radius=12)

            img = pygame.transform.scale(item["img"], (60, 60))
            screen.blit(img, (card_rect.x + 15, card_rect.y + 15))

            name_text = font.render(f"{item['key']}. {item['name']}", True, BLACK)
            price_text = font.render(f"{item['price']} $$", True, (120, 70, 0))
            screen.blit(name_text, (card_rect.x + 90, card_rect.y + 25))
            screen.blit(price_text, (card_rect.x + 90, card_rect.y + 50))

        exit_text = font.render("(ESC 離開)", True, BLACK)
        screen.blit(exit_text, (WIDTH // 2 - exit_text.get_width() // 2, y_base + len(shop_items) * 100 + 20))

 
    elif game_state in (STATE_GAME_OVER, STATE_VICTORY):
                if event.key == pygame.K_r: reset_full_game()
                elif event.key in (pygame.K_q, pygame.K_ESCAPE): save_game(max(save_data.get("max_unlocked",1), level), player_gold); pygame.quit(); sys.exit()

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if game_state == STATE_MENU:
                # click buttons
                bw, bh = 360, 64
                gap = 26
                start_y = HEIGHT//2 - (bh*3 + gap*2)//2
                rects = [
                    pygame.Rect(WIDTH//2 - bw//2, start_y + (bh+gap)*0, bw, bh),  # Continue
                    pygame.Rect(WIDTH//2 - bw//2, start_y + (bh+gap)*1, bw, bh),  # Level Select
                    pygame.Rect(WIDTH//2 - bw//2, start_y + (bh+gap)*2, bw, bh),  # New Game
                ]
                labels = ["Continue", "Level Select", "New Game"]
                for i, r in enumerate(rects):
                    if r.collidepoint(mx, my):
                        if i == 0:
                            target = max(1, min(save_data.get("max_unlocked",1), MAX_LEVEL))
                            start_level(target)
                        elif i == 1:
                            game_state = STATE_LEVEL_SELECT
                        elif i == 2:
                            save_data["max_unlocked"] = 1; save_data["gold"] = 0; save_game(1,0)
                            start_level(1)
                # Quit text zone
                q_rect = pygame.Rect(WIDTH//2-120, HEIGHT-56, 240, 40)
                if q_rect.collidepoint(mx,my):
                    save_game(max(save_data.get("max_unlocked",1), level), player_gold)
                    pygame.quit(); sys.exit()

            elif game_state == STATE_LEVEL_SELECT:
                # Level cards
                bw, bh = 200, 120
                spacing = 40
                total_w = bw*3 + spacing*2
                start_x = WIDTH//2 - total_w//2
                y = HEIGHT//2 - bh//2
                unlocked = save_data.get("max_unlocked", 1)
                for i in range(3):
                    rect = pygame.Rect(start_x + i*(bw+spacing), y, bw, bh)
                    if i+1 <= unlocked and rect.collidepoint(mx, my):
                        start_level(i+1)

    # ---------- Updates ----------
    if game_state == STATE_LEVEL_INTRO:
        level_intro_timer -= 1
        if level_intro_timer <= 0:
            game_state = STATE_PLAYING

    if game_state == STATE_PLAYING:
        keys = pygame.key.get_pressed(); spd = player_speed_base
        if keys[pygame.K_LEFT]  and player.left  > 0:     player.x -= spd
        if keys[pygame.K_RIGHT] and player.right < WIDTH: player.x += spd
        if keys[pygame.K_UP]    and player.top   > 0:     player.y -= spd
        if keys[pygame.K_DOWN]  and player.bottom< HEIGHT:player.y += spd

        # Player bullets
        speed = bullet_speed_base*(2 if bullet_fast else 1)
        for b in bullets[:]:
            b.x += speed
            if b.right > WIDTH: bullets.remove(b)

        # Spawn enemies
        enemy_spawn_timer += 1
        if not boss_alive:
            if enemy_spawn_timer > level_params(level)["spawn_cd"] and boss is None:
                enemies.append(spawn_enemy()); enemy_spawn_timer = 0

        # Enemy move & shoot
        for e in enemies[:]:
            e["rect"].x -= int(level_params(level)["enemy_speed"])
            e["rect"].y += e["vy"]
            if e["rect"].top <= 0 or e["rect"].bottom >= HEIGHT: e["vy"] *= -1
            if random.random() < level_params(level)["enemy_bullet_chance"]:
                spawn_enemy_bullet(e["rect"].x, e["rect"].centery, -5, 0, size=8)
            if e["rect"].right < 0: enemies.remove(e)

        # Enemy bullets
        for eb in enemy_bullets[:]:
            eb["rect"].x += eb["vx"]; eb["rect"].y += eb["vy"]
            if eb["rect"].colliderect(player):
                player_hp -= 1; enemy_bullets.remove(eb)
                if player_hp <= 0: game_state = STATE_GAME_OVER
            elif eb["rect"].right < 0 or eb["rect"].left > WIDTH or eb["rect"].bottom < 0 or eb["rect"].top > HEIGHT:
                enemy_bullets.remove(eb)

        # Collide: player vs enemies
        for e in enemies[:]:
            if player.colliderect(e["rect"]):
                player_hp -= 1; enemies.remove(e)
                if player_hp <= 0: game_state = STATE_GAME_OVER

        # Bullet vs enemies
        for b in bullets[:]:
            for e in enemies[:]:
                if b.colliderect(e["rect"]):
                    bullets.remove(b); e["hp"] -= 10
                    if e["hp"] <= 0:
                        enemy_dead_sound.play(); enemies.remove(e); player_gold += 100
                        save_game(max(save_data.get("max_unlocked",1), level), player_gold)  # autosave gold
                        if random.random() < 0.8:
                            drop = random.choice(["heal","exp","speed","double"])
                            items.append({"rect": pygame.Rect(e["rect"].x, e["rect"].y, 20, 20), "type": drop})
                    break

        # Items
        for it in items[:]:
            if player.colliderect(it["rect"]):
                if it["type"] == "heal": player_hp = min(PLAYER_MAX_HP, player_hp+2)
                elif it["type"] == "exp": player_exp += 10
                elif it["type"] == "speed": bullet_fast=True; bullet_fast_timer=300
                elif it["type"] == "double": bullet_double=True; bullet_double_timer=300
                items.remove(it)
        for it in items[:]:
            it["rect"].y += 1
            if it["rect"].top > HEIGHT: items.remove(it)

        # Buff timers
        if bullet_fast:
            bullet_fast_timer -= 1
            if bullet_fast_timer <= 0: bullet_fast = False
        if bullet_double:
            bullet_double_timer -= 1
            if bullet_double_timer <= 0: bullet_double = False

        # Boss spawn when EXP threshold reached
        if player_exp >= 20 and boss is None:
            boss = spawn_boss(); boss_alive = True

        # Boss behavior
        if boss:
            boss["timer"] += 1
            if boss["rect"].x > WIDTH - 240: boss["rect"].x -= 1
            boss["rect"].y += boss["vy"]
            if boss["rect"].top <= 0 or boss["rect"].bottom >= HEIGHT: boss["vy"] *= -1
            boss_attack_pattern(boss)

            for b in bullets[:]:
                if b.colliderect(boss["rect"]):
                    bullets.remove(b); boss["hp"] -= 5
                    if boss["hp"] <= 0:
                        boss = None; boss_alive = False
                        player_gold += 1000; player_exp += 50
                        current_unlocked = save_data.get("max_unlocked", 1)
                        if current_unlocked < min(level + 1, MAX_LEVEL):
                            save_data["max_unlocked"] = min(level + 1, MAX_LEVEL)
                            save_data["gold"] = player_gold
                            save_game(save_data["max_unlocked"], save_data["gold"])
                        next_level_or_victory()
                        break

        # Autosave every ~10 seconds
        autosave_interval_frames = 600  # 60fps * 10s
        globals().setdefault("autosave_counter", 0)
        autosave_counter = globals()["autosave_counter"] + 1
        if autosave_counter >= autosave_interval_frames:
            save_game(max(save_data.get("max_unlocked",1), level), player_gold)
            autosave_counter = 0
        globals()["autosave_counter"] = autosave_counter

    # ---------- Draw ----------
    if game_state in (STATE_MENU, STATE_LEVEL_SELECT):
        draw_menu_bg()

    if game_state == STATE_MENU:
        label_center("", 40, title_font, WHITE)
        # Buttons layout
        bw, bh = 360, 64
        gap = 26
        start_y = HEIGHT//2 - (bh*3 + gap*2)//2
        rects = [
            pygame.Rect(WIDTH//2 - bw//2, start_y + (bh+gap)*0, bw, bh),
            pygame.Rect(WIDTH//2 - bw//2, start_y + (bh+gap)*1, bw, bh),
            pygame.Rect(WIDTH//2 - bw//2, start_y + (bh+gap)*2, bw, bh),
        ]
        button(rects[0], "Continue (Enter)")
        button(rects[1], "Level Select (L)")
        button(rects[2], "New Game (N)")
        tip = font.render("", True, (210,210,220))
        screen.blit(tip, (WIDTH//2 - tip.get_width()//2, HEIGHT - 78))
        # Quit area
        q_rect = pygame.Rect(WIDTH//2-120, HEIGHT-56, 240, 40)
        pygame.draw.rect(screen, (245,245,245), q_rect, border_radius=12)
        pygame.draw.rect(screen, (40,40,40), q_rect, 2, border_radius=12)
        q_lbl = font.render("Quit (Q)", True, (30,30,35)); screen.blit(q_lbl, (q_rect.centerx - q_lbl.get_width()//2, q_rect.centery - q_lbl.get_height()//2))
 
    elif game_state == STATE_LEVEL_SELECT:
        label_center("Select Level", 36, title_font, WHITE)
        bw, bh = 200, 120
        spacing = 40
        total_w = bw*3 + spacing*2
        start_x = WIDTH//2 - total_w//2
        y = HEIGHT//2 - bh//2
        unlocked = save_data.get("max_unlocked", 1)
        for i in range(3):
            rect = pygame.Rect(start_x + i*(bw+spacing), y, bw, bh)
            enabled = (i+1) <= unlocked
            # draw card
            shadow = rect.move(0,4); pygame.draw.rect(screen, (0,0,0,80), shadow, border_radius=14)
            color = (245,245,245) if enabled else (210,210,210)
            pygame.draw.rect(screen, color, rect, border_radius=14)
            pygame.draw.rect(screen, (40,40,40), rect, 2, border_radius=14)
            text = f"Level {i+1}\n{ERA_NAMES.get(i+1,'')}"
            title = big_font.render(f"Level {i+1}", True, (30,30,35) if enabled else (120,120,120))
            era = font.render(ERA_NAMES.get(i+1,""), True, (50,50,60) if enabled else (130,130,130))
            screen.blit(title, (rect.centerx - title.get_width()//2, rect.y + 22))
            screen.blit(era, (rect.centerx - era.get_width()//2, rect.y + 22 + title.get_height() + 6))
            if not enabled:
                # lock overlay
                overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA); overlay.fill((100,100,100,90))
                screen.blit(overlay, rect.topleft)
        tip = font.render("Click a level (or press 1-3). ESC to menu.", True, (210,210,220))
        screen.blit(tip, (WIDTH//2 - tip.get_width()//2, HEIGHT - 60)) 

    elif game_state in (STATE_PLAYING, STATE_SHOP, STATE_LEVEL_INTRO):
        # Background
        screen.blit(BG_IMAGES.get(level, list(BG_IMAGES.values())[0]), (0,0))
        # Player
        screen.blit(player_img, player)

        # Enemies
        for e in enemies:
            screen.blit(ENEMY_IMAGES.get(level, list(ENEMY_IMAGES.values())[0]), e["rect"].topleft)
            # small HP bar for enemies
            pygame.draw.rect(screen, RED,   (e["rect"].x, e["rect"].y - 8, 40, 5))
            pygame.draw.rect(screen, GREEN, (e["rect"].x, e["rect"].y - 8, int(40 * e["hp"]/level_params(level)["enemy_hp"]), 5))

        # Bullets
        for b in bullets:
            pygame.draw.rect(screen, WHITE, b)
        for eb in enemy_bullets:
            pygame.draw.rect(screen, YELLOW, eb["rect"])

        # Items
        for it in items:
            img = item_images.get(it["type"])
            if img: screen.blit(img, it["rect"])

        # Boss
        if boss:
            screen.blit(BOSS_IMAGES.get(level, list(BOSS_IMAGES.values())[0]), boss["rect"].topleft)
            # boss HP bar
            pygame.draw.rect(screen, RED, (300, 20, 220, 15))
            # need boss hp; approximate if missing
            # In this script we hold hp in boss["hp"]
            pygame.draw.rect(screen, GREEN, (300, 20, int(220 * boss["hp"]/level_params(level)["boss_hp"]), 15))
            screen.blit(font.render(f"BOSS - {ERA_NAMES.get(level,'')}", True, BLACK), (300, 0))

        # HUD (HP bar + texts)
        draw_hp_bar(10, 10, player_hp, PLAYER_MAX_HP, width=120, height=12)
        screen.blit(font.render(f"EXP: {player_exp}", True, WHITE), (10, 30))
        screen.blit(font.render(f"Gold: {player_gold}", True, WHITE), (10, 50))
        screen.blit(font.render(f"Level: {level}/{MAX_LEVEL} - {ERA_NAMES.get(level,'')}", True, WHITE), (10, 70))

        if game_state == STATE_LEVEL_INTRO:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill((255,255,255,170))
            screen.blit(overlay, (0,0))
            intro = big_font.render(f"Level {level} - {ERA_NAMES.get(level,'')}", True, BLACK)
            tip = font.render("Press any key to start (S = Shop)", True, BLACK)
            screen.blit(intro, (WIDTH//2 - intro.get_width()//2, HEIGHT//2 - 40))
            screen.blit(tip, (WIDTH//2 - tip.get_width()//2, HEIGHT//2 + 10))

        # ===== Shop (KEEP original panel style) =====

        # ===== Shop (card-style from new.py) =====
        if game_state == STATE_SHOP:
            # Title
            shop_text = big_font.render("[SHOP]", True, WHITE)
            screen.blit(shop_text, (WIDTH // 2 - shop_text.get_width() // 2, 20))

            shop_items = [
                {"img": shop_images["double"], "name": "Double", "price": 300, "key": "1"},
                {"img": shop_images["speed"],  "name": "Speed",  "price": 200, "key": "2"},
                {"img": shop_images["heal"],   "name": "Heal +3","price": 150, "key": "3"},
            ]

            y_base = 90
            for i, item in enumerate(shop_items):
                card_rect = pygame.Rect(WIDTH // 2 - 180, y_base + i * 100, 360, 90)
                pygame.draw.rect(screen, (230, 230, 230), card_rect, border_radius=12)
                pygame.draw.rect(screen, BLACK, card_rect, 2, border_radius=12)

                if item["img"]:
                    img = pygame.transform.scale(item["img"], (60, 60))
                    screen.blit(img, (card_rect.x + 15, card_rect.y + 15))

                name_text = font.render(f"{item['key']}. {item['name']}", True, BLACK)
                price_text = font.render(f"{item['price']} $$", True, (120, 70, 0))
                screen.blit(name_text, (card_rect.x + 90, card_rect.y + 25))
                screen.blit(price_text, (card_rect.x + 90, card_rect.y + 50))

            exit_text = font.render("(ESC to close)", True, BLACK)
            screen.blit(exit_text, (WIDTH // 2 - exit_text.get_width() // 2, y_base + len(shop_items) * 100 + 20))

    if game_state == STATE_GAME_OVER:
        label_center("Game Over", HEIGHT//2 - 40, big_font, RED)
        tip = font.render("R: Restart   Q/Esc: Quit", True, WHITE)
        screen.blit(tip, (WIDTH//2 - tip.get_width()//2, HEIGHT//2 + 10))

    if game_state == STATE_VICTORY:
        label_center("Victory!", HEIGHT//2 - 60, big_font, GREEN)
        tip = font.render("R: Restart   Q/Esc: Quit", True, WHITE)
        screen.blit(tip, (WIDTH//2 - tip.get_width()//2, HEIGHT//2 - 10))

    pygame.display.flip()
    clock.tick(60)
