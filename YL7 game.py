import pygame
import math
import sys
import random

# Peamised setingud
WIDTH, HEIGHT = 1920, 1080
FPS = 60
TILE_SIZE = 60
FOV = math.radians(60)
HALF_FOV = FOV / 2 #pool FOV
NUM_RAYS = 240
MAX_DEPTH = 1000
DELTA_ANGLE = (math.pi / 3) / NUM_RAYS  # alg nurk
DIST = NUM_RAYS / (2 * math.tan(HALF_FOV))
PROJ_COEFF = 4 * DIST * TILE_SIZE
SCALE = WIDTH // NUM_RAYS  # iga ray slici laius

# Kaart 1 - sein , . - floor
MAP = [
    '11111111111111111111',
    '1............1.....1',
    '1...11...11........1',
    '1...1..1......11...1',
    '1...1..1..111.1....1',
    '1.....1.......11...1',
    '1...1.....11.......1',
    '11111111111111111111',
]

#Mängija setingud
player_x = 100
player_y = 100
player_angle = 0
player_angle %= 2 * math.pi

#skoor ja lasu algandmed
score = 0
last_shot_time = 0
SHOT_COOLDOWN = 300

#Start pygame
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
fps = int(clock.get_fps())

#FONT
font = pygame.font.Font("P2S.ttf", 35)

#muusika importimine
pygame.mixer.init()
pygame.mixer.music.load("MUUSIKA.mp3")
pygame.mixer.music.set_volume(0.5)
pygame.mixer.music.play(-1)  # Loop forever
gunshot_sound = pygame.mixer.Sound("Lask.mp3")
gunshot_sound.set_volume(0.7)

# Laadib Textuurid
wall_texture = pygame.image.load('wall.jpeg').convert()
gun_image = pygame.image.load("gun.png").convert_alpha()
muzzle_flash = pygame.image.load("Flash.png").convert_alpha()
wall_texture = pygame.transform.scale(wall_texture, (64, 64))
gun_image = pygame.transform.scale(gun_image, (400, 400))
muzzle_flash = pygame.transform.scale(muzzle_flash, (100, 100))
TEXTURE_WIDTH, TEXTURE_HEIGHT = wall_texture.get_size()

# vastaste spritid ja suvaline spawn punkt
walkable_tiles = [(x, y) for y, row in enumerate(MAP) for x, val in enumerate(row) if val == '.']
def get_random_position():
    x, y = random.choice(walkable_tiles)
    return (x * TILE_SIZE + TILE_SIZE // 2, y * TILE_SIZE + TILE_SIZE // 2)

enemy_texture = pygame.image.load("vastane.png").convert_alpha()
sprites = [{
    "x": 75, "y": 175,
    "vastane": enemy_texture,
    "health": 3,
}]
sprites[0]["x"], sprites[0]["y"] = get_random_position()

 #lasu raycastimine
def shoot_ray(px, py, pa):
    global sprites, score
    ray_len = 0
    step_size = 1
    max_range = 1000
    ray_x = px
    ray_y = py
    hit_enemy = False
    while ray_len < max_range:
        ray_x += math.cos(pa) * step_size
        ray_y += math.sin(pa) * step_size
        ray_len += step_size
        for sprite in sprites:
            sx, sy = sprite["x"], sprite["y"]
            dist = math.hypot(ray_x - sx, ray_y - sy)
            if dist < 30 and sprite["health"] > 0:
                sprite["health"] -= 1
                if sprite["health"] <= 0:
                    score += 1
                    sprite["x"], sprite["y"] = get_random_position()
                    sprite["health"] = 3
                hit_enemy = True
                break
        if hit_enemy:
            return

    #seinte leidmine raycasteriga
def raycasting(sc, px, py, angle):
    z_buffer = []  # alsutab bufferi

    start_angle = angle - HALF_FOV
    for ray in range(NUM_RAYS):
        cur_angle = start_angle + ray * DELTA_ANGLE
        sin_a = math.sin(cur_angle)
        cos_a = math.cos(cur_angle)

        map_x = int(px // TILE_SIZE)
        map_y = int(py // TILE_SIZE)

        delta_dist_x = abs(1 / cos_a) if cos_a != 0 else float('inf')
        delta_dist_y = abs(1 / sin_a) if sin_a != 0 else float('inf')

        if cos_a < 0:
            step_x = -1
            side_dist_x = (px - map_x * TILE_SIZE) / TILE_SIZE * delta_dist_x
        else:
            step_x = 1
            side_dist_x = ((map_x + 1) * TILE_SIZE - px) / TILE_SIZE * delta_dist_x

        if sin_a < 0:
            step_y = -1
            side_dist_y = (py - map_y * TILE_SIZE) / TILE_SIZE * delta_dist_y
        else:
            step_y = 1
            side_dist_y = ((map_y + 1) * TILE_SIZE - py) / TILE_SIZE * delta_dist_y

        hit = False
        side = 0
        while not hit:
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1
            if 0 <= map_y < len(MAP) and 0 <= map_x < len(MAP[0]):
                if MAP[map_y][map_x] == '1':
                    hit = True

        # Fisheye parandus
        if side == 0:
            depth = (map_x - px / TILE_SIZE + (1 - step_x) / 2) / (cos_a / TILE_SIZE)
        else:
            depth = (map_y - py / TILE_SIZE + (1 - step_y) / 2) / (sin_a / TILE_SIZE)

        depth *= math.cos(angle - cur_angle)
        z_buffer.append(depth) #Zbuffer et teaks millal vastane on vaateväljas

        wall_height = PROJ_COEFF / (depth + 0.0001) #seina kõrguse arvutamine

        if side == 0:
            wall_x = py + depth * sin_a
        else:
            wall_x = px + depth * cos_a
        #seina textuuride arvutamine
        wall_x %= TILE_SIZE
        tex_x = int((wall_x / TILE_SIZE) * TEXTURE_WIDTH)
        tex_x = max(0, min(TEXTURE_WIDTH - 1, tex_x))

        tex_column = wall_texture.subsurface((tex_x, 0, 1, TEXTURE_HEIGHT))
        tex_column = pygame.transform.scale(tex_column, (SCALE, int(wall_height)))

        shade = 1 if side == 1 else 0.5
        tex_column.fill((shade * 255, shade * 255, shade * 255), special_flags=pygame.BLEND_MULT)

        screen.blit(tex_column, (ray * SCALE, HEIGHT // 2 - wall_height // 2))

    return z_buffer  #returnib Zbufferi


def draw_minimap():
    mini_scale = min(WIDTH / (len(MAP[0]) * TILE_SIZE * 5), HEIGHT / (len(MAP) * TILE_SIZE * 5))

    # joonistab kaardi seinte ja põrandaga
    for y, row in enumerate(MAP):
        for x, cell in enumerate(row):
            color = (155, 155, 255) if cell == '1' else (60, 50, 50)
            pygame.draw.rect(screen, color, (x * TILE_SIZE * mini_scale, y * TILE_SIZE * mini_scale,
                                             TILE_SIZE * mini_scale, TILE_SIZE * mini_scale))

    # joonistab mängija positsiooni kaardile
    pygame.draw.circle(screen, (255, 0, 0), (int(player_x * mini_scale), int(player_y * mini_scale)), 3)

    # joonistab raycasteri "ray'd" kaardile
    start_angle = player_angle - HALF_FOV
    for ray in range(NUM_RAYS):
        cur_angle = start_angle + ray * DELTA_ANGLE
        ray_x = player_x
        ray_y = player_y
        ray_len = 0
        step_size = 5
        max_range = 1000

        while ray_len < max_range:
            ray_x += math.cos(cur_angle) * step_size
            ray_y += math.sin(cur_angle) * step_size
            ray_len += step_size

            map_x, map_y = int(ray_x // TILE_SIZE), int(ray_y // TILE_SIZE)
            if 0 <= map_y < len(MAP) and 0 <= map_x < len(MAP[0]) and MAP[map_y][map_x] == '1':

                pygame.draw.line(screen, (255, 255, 0),
                                 (int(player_x * mini_scale), int(player_y * mini_scale)),
                                 (int(ray_x * mini_scale), int(ray_y * mini_scale)), 1)
                break

    # joonistab vastase mini kaardile
    for sprite in sprites:
        enemy_x, enemy_y = sprite["x"], sprite["y"]

        mini_enemy_x = int(enemy_x * mini_scale)
        mini_enemy_y = int(enemy_y * mini_scale)
        pygame.draw.circle(screen, (0, 255, 0), (mini_enemy_x, mini_enemy_y), 4)


    #Inputide käsitleja
def handle_input():
    global player_x, player_y, player_angle
    keys = pygame.key.get_pressed()
    speed = 3
    rot_speed = 0.03
    if keys[pygame.K_a]:
        player_angle -= rot_speed
    if keys[pygame.K_d]:
        player_angle += rot_speed
    if keys[pygame.K_w]:
        new_x = player_x + speed * math.cos(player_angle)
        new_y = player_y + speed * math.sin(player_angle)
        if MAP[int(new_y // TILE_SIZE)][int(new_x // TILE_SIZE)] == '.':
            player_x, player_y = new_x, new_y
    if keys[pygame.K_s]:
        new_x = player_x - speed * math.cos(player_angle)
        new_y = player_y - speed * math.sin(player_angle)
        if MAP[int(new_y // TILE_SIZE)][int(new_x // TILE_SIZE)] == '.':
            player_x, player_y = new_x, new_y
    #ESC nuppu vajutades saab mängu kinni panna
    if keys[pygame.K_ESCAPE]:
        pygame.quit()


    #vastase tuvastamine, kas vastane on mängijale nähtav
def is_enemy_visible(px, py, enemy_x, enemy_y, pa):
    dx = enemy_x - px
    dy = enemy_y - py
    distance = math.hypot(dx, dy)

    # vastase nurga leidmine mängijaga nende relatiivsuse leidmine
    sprite_angle = math.atan2(dy, dx)
    diff_angle = sprite_angle - pa

    # nurga ühtlustamine
    while diff_angle > math.pi:
        diff_angle -= 2 * math.pi
    while diff_angle < -math.pi:
        diff_angle += 2 * math.pi

    # Kui vastane ei ole nähtaval siis teda ei renderita
    if not (-HALF_FOV < diff_angle < HALF_FOV):
        return False

    # tuvastab kas Raycasteri ray läheb vastu seina
    ray_angle = pa + diff_angle
    ray_len = 0
    step_size = 5
    max_range = MAX_DEPTH
    ray_x = px
    ray_y = py
    x, y = random.choice(walkable_tiles)

    while ray_len < max_range:
        ray_x += math.cos(ray_angle) * step_size
        ray_y += math.sin(ray_angle) * step_size
        ray_len += step_size
        map_x, map_y = int(ray_x // TILE_SIZE), int(ray_y // TILE_SIZE)

        if math.hypot(ray_x - enemy_x, ray_y - enemy_y) < 10:
            return True    #kui vastane on nähtav ja seina vahel pole siis returnitakse True

        if 0 <= map_y < len(MAP) and 0 <= map_x < len(MAP[0]) and MAP[map_y][map_x] == '1':
            return False  # Kui vastase ja mängija vahele jääb sein siis antakse False väljund

    return True

    #joonistame vastase
def draw_enemy_sprite(sprite, px, py, pa, z_buffer, FOV):
    dx = sprite["x"] - px
    dy = sprite["y"] - py
    distance = math.hypot(dx, dy)

    sprite_angle = math.atan2(dy, dx)
    diff_angle = sprite_angle - pa

    while diff_angle > math.pi:
        diff_angle -= 2 * math.pi
    while diff_angle < -math.pi:
        diff_angle += 2 * math.pi

    if not (-HALF_FOV < diff_angle < HALF_FOV):
        return

    # Paneb vastase nurga mängu aknaga vastavusse, ei teki FOV ja ekraani suuruse vigu. ei anna enam errorit
    ray_offset = diff_angle / FOV
    screen_x = int((0.5 + ray_offset) * WIDTH)

    if screen_x < 0 or screen_x >= WIDTH:
        return

    ray_index = screen_x // SCALE
    if 0 <= ray_index < len(z_buffer) and z_buffer[ray_index] < distance:
        return

    sprite_size = int(5000 / (distance + 0.0001)) * 6 #Lisades multiplierile suuremat numbrit saab muuta vastase suurust
    sprite_size = max(10, min(sprite_size, HEIGHT)) #maarab vastase maximaalse ja minimaalse suuruse

    # muudab spritide suurusi ja joonistab nad ekraanile
    sprite_image = pygame.transform.scale(sprite["vastane"], (sprite_size, sprite_size))
    print(f"[DEBUG] Sprite @ {sprite['x']:.1f},{sprite['y']:.1f} | screen_x: {screen_x} | dist: {distance:.1f}")
    screen.blit(sprite_image, (screen_x - sprite_size // 2, HEIGHT // 2 - sprite_size // 2))


#peamine tsykkel
def main():
    global last_shot_time
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        #Ekraani algvärv
        screen.fill((100, 100, 100))

        # inputide handler
        handle_input()

        # laskmise handler
        mouse_buttons = pygame.mouse.get_pressed()
        if mouse_buttons[0]:
            current_time = pygame.time.get_ticks()
            if current_time - last_shot_time > SHOT_COOLDOWN:
                last_shot_time = current_time
                shoot_ray(player_x, player_y, player_angle)
                gunshot_sound.play()

        #joonistame laeks ja põrandaks ristkülikud
        pygame.draw.rect(screen, (25, 15, 15), (0, 1 , WIDTH, 1080))
        pygame.draw.rect(screen, (40, 40, 50), (0, HEIGHT // 2, WIDTH, HEIGHT // 2))

        # raycastib seinad
        z_buffer = raycasting(screen, player_x, player_y, player_angle)

        # joonistab mini kaardi
        draw_minimap()

        # kutsub vastase tsükli
        for sprite in sprites:
            draw_enemy_sprite(sprite, player_x, player_y, player_angle, z_buffer, FOV)

        # joonistab mangija relva ja tulistades relva tulepalli
        if pygame.time.get_ticks() - last_shot_time < 100:  # Flash lasts 100ms
            screen.blit(muzzle_flash, (WIDTH // 2 - 30, HEIGHT - 420))
        screen.blit(gun_image, (WIDTH // 2 - 100 , HEIGHT - 350))

        # joonistab skoori
        score_text = font.render(f"Score: {score}", True, (255, 255, 0))
        screen.blit(score_text, (100, 1000))

        pygame.display.flip() # refreshib akna
        clock.tick(FPS) #viib mängu akna refreshi vastavusse ülal toodud FPSi valuega


main()
