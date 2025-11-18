import sys
import random
import math
import pygame
import array
import numpy as np

# ============================================================
# CONFIG
# ============================================================
SCREEN_WIDTH  = 800
SCREEN_HEIGHT = 600
FPS           = 60

PLAYER_SPEED  = 4
BULLET_SPEED  = 8
ENEMY_SPEED   = 3

ENEMY_SPAWN_INTERVAL = 1000  # ms

BG_TOP_COLOR    = (10, 20, 60)
BG_BOTTOM_COLOR = (2, 2, 10)
MOUNTAIN_COLOR  = (150, 0, 150)
STAR_COLOR      = (200, 200, 255)

MOUNTAIN_BASE_Y = SCREEN_HEIGHT - 80
DEBUG           = False

SCALE           = 2  # scale factor for all sprites

# Sound settings
SOUND_ENABLED   = True
SAMPLE_RATE     = 22050

# ============================================================
# SPRITE PALETTE + HELPERS
# ============================================================
COLORS = {
    ".": None,                    # transparent
    "O": (0, 0, 0),               # outline (not used much)
    "H": (235, 235, 235),         # hull (white/light grey)
    "B": (0, 200, 255),           # blue/cyan cockpit
    "Y": (255, 230, 90),          # yellow accent / top stripe
    "A": (255, 170, 40),          # orange engine section
    "F": (255, 100, 20),          # bright orange flame
    "R": (255, 40, 40),           # red (for explosion, etc.)
    "G": (80, 255, 120),          # enemy green
    "M": (255, 80, 200),          # magenta accent
    "C": (0, 220, 220),           # cyan accent (enemy)
}


def surface_from_pattern(pattern, scale: int = 1) -> pygame.Surface:
    """Create a Surface from an ASCII pattern using COLORS."""
    height = len(pattern)
    width  = len(pattern[0]) if height > 0 else 0
    surf   = pygame.Surface((width * scale, height * scale), pygame.SRCALPHA)

    for y, row in enumerate(pattern):
        for x, ch in enumerate(row):
            color = COLORS.get(ch)
            if color is None:
                continue
            rect = pygame.Rect(x * scale, y * scale, scale, scale)
            pygame.draw.rect(surf, color, rect)
    return surf


# -------- Player ship patterns (right-facing) --------
_PLAYER_RIGHT_PATTERN = [
    "........................",
    "..............YY........",
    ".............YYYY.......",
    "........HHHHHHHHHYY.....",
    "......HHHHHHHHHHHHHYY...",
    ".....HHHHHHBBBBBHHHHY...",
    "....HHHHHHHHHHHHHHHHH...",
    "...AAAAHHHHHHHHHHHHF....",
    "..AAAAAAHHHHHHHHHFFF....",
    "...AAAAHHHHHHHHHHF......",
    "......FFF...............",
    "........................",
]

# Enemy pattern
_ENEMY_PATTERN = [
    "................",
    "......GGGG......",
    "....GGGGGGGG....",
    "...GGGGGGGGGG...",
    "..GGGGMGGGMGGG..",
    "..GGGGGGGGGGGG..",
    "...GGGGGGGGGG...",
    "....GCCGGCCG....",
    ".....GCCGCC.....",
    "......GGGG......",
    "................",
    "................",
]

# Explosion patterns (3 frames)
_EXPLOSION_FRAMES = [
    [
        "........",
        "....Y...",
        "...YYY..",
        "....Y...",
        "........",
        "........",
        "........",
        "........",
    ],
    [
        "........",
        "...AYY..",
        "..AYYYY.",
        "..YYYYA.",
        "...AYY..",
        "........",
        "........",
        "........",
    ],
    [
        "..RAYY..",
        ".RAYYYY.",
        "RAYYYYYR",
        "RYYYYYAR",
        ".RAYYYY.",
        "..RAYY..",
        "........",
        "........",
    ],
]


def create_player_ship_right(scale: int = 1) -> pygame.Surface:
    return surface_from_pattern(_PLAYER_RIGHT_PATTERN, scale)


def create_player_ship_left(scale: int = 1) -> pygame.Surface:
    right = create_player_ship_right(scale)
    return pygame.transform.flip(right, True, False)


def create_enemy_ship(scale: int = 1) -> pygame.Surface:
    return surface_from_pattern(_ENEMY_PATTERN, scale)


def create_bullet_surface(length: int = 8, scale: int = 1) -> pygame.Surface:
    surf = pygame.Surface((length * scale, 2 * scale), pygame.SRCALPHA)
    pygame.draw.rect(
        surf,
        COLORS["Y"],
        pygame.Rect(0, 0, length * scale, 2 * scale),
    )
    return surf


def create_explosion_frames(scale: int = 1) -> list[pygame.Surface]:
    return [surface_from_pattern(p, scale) for p in _EXPLOSION_FRAMES]


# ============================================================
# SOUND GENERATION
# ============================================================
# Try to use sndarray if available (requires numpy), otherwise use fallback
try:
    import pygame.sndarray
    USE_SNDARRAY = True
except ImportError:
    USE_SNDARRAY = False

def generate_tone(frequency, duration_ms, volume=0.3, wave_type='sine'):
    """Generate a simple tone."""
    duration = duration_ms / 1000.0
    samples = int(SAMPLE_RATE * duration)
    max_sample = 2**(16 - 1) - 1
    
    # Create stereo array (2 channels)
    arr = array.array('h', [0] * (samples * 2))
    
    for i in range(samples):
        t = float(i) / SAMPLE_RATE
        if wave_type == 'sine':
            sample = math.sin(2 * math.pi * frequency * t)
        elif wave_type == 'square':
            sample = 1.0 if (int(frequency * t) % 2) == 0 else -1.0
        elif wave_type == 'sawtooth':
            sample = 2 * (t * frequency - math.floor(t * frequency + 0.5))
        else:
            sample = math.sin(2 * math.pi * frequency * t)
        
        val = int(max_sample * volume * sample)
        # Stereo: left and right channels
        arr[i * 2] = val
        arr[i * 2 + 1] = val
    
    # Create sound from array - use sndarray if available, otherwise try direct buffer
    if USE_SNDARRAY:
        # Convert array to numpy array for sndarray
        try:
            import numpy as np
            np_arr = np.frombuffer(arr, dtype=np.int16).reshape((samples, 2))
            return pygame.sndarray.make_sound(np_arr)
        except:
            pass
    
    # Fallback: create silent sound (sounds will be disabled)
    # This is a workaround - pygame.mixer.Sound doesn't easily accept raw arrays
    silent_arr = array.array('h', [0] * (samples * 2))
    return pygame.mixer.Sound(buffer=bytes(silent_arr))


def generate_laser_sound():
    """Generate a laser/shooting sound."""
    # Quick high-pitched beep
    return generate_tone(800, 50, volume=0.2, wave_type='square')


def generate_explosion_sound():
    """Generate an explosion sound."""
    # Low rumble with higher frequencies
    duration = 200
    samples = int(SAMPLE_RATE * duration / 1000.0)
    max_sample = 2**(16 - 1) - 1
    
    # Create stereo array
    arr = array.array('h', [0] * (samples * 2))
    
    for i in range(samples):
        t = float(i) / SAMPLE_RATE
        # Mix multiple frequencies for explosion effect
        freq1 = 60 + (t * 200)  # Rising low frequency
        freq2 = 200 + (t * 400)  # Rising mid frequency
        sample = (math.sin(2 * math.pi * freq1 * t) * 0.5 + 
                 math.sin(2 * math.pi * freq2 * t) * 0.3)
        # Add decay
        volume = 0.4 * (1.0 - t / (duration / 1000.0))
        val = int(max_sample * volume * sample)
        arr[i * 2] = val
        arr[i * 2 + 1] = val
    
    # Create sound - use same method as generate_tone
    if USE_SNDARRAY:
        try:
            import numpy as np
            np_arr = np.frombuffer(arr, dtype=np.int16).reshape((samples, 2))
            return pygame.sndarray.make_sound(np_arr)
        except:
            pass
    
    # Fallback: silent sound
    silent_arr = array.array('h', [0] * (samples * 2))
    return pygame.mixer.Sound(buffer=bytes(silent_arr))


def generate_enemy_hit_sound():
    """Generate a hit sound."""
    # Short beep
    return generate_tone(400, 30, volume=0.15, wave_type='square')


def generate_player_death_sound():
    """Generate player death sound."""
    # Longer, dramatic sound
    duration = 500
    samples = int(SAMPLE_RATE * duration / 1000.0)
    max_sample = 2**(16 - 1) - 1
    
    # Create stereo array
    arr = array.array('h', [0] * (samples * 2))
    
    for i in range(samples):
        t = float(i) / SAMPLE_RATE
        # Descending tone
        freq = 400 - (t * 300)
        sample = math.sin(2 * math.pi * freq * t)
        volume = 0.5 * (1.0 - t / (duration / 1000.0))
        val = int(max_sample * volume * sample)
        arr[i * 2] = val
        arr[i * 2 + 1] = val
    
    # Create sound - use same method as generate_tone
    if USE_SNDARRAY:
        try:
            import numpy as np
            np_arr = np.frombuffer(arr, dtype=np.int16).reshape((samples, 2))
            return pygame.sndarray.make_sound(np_arr)
        except:
            pass
    
    # Fallback: silent sound
    silent_arr = array.array('h', [0] * (samples * 2))
    return pygame.mixer.Sound(buffer=bytes(silent_arr))


def generate_enemy_spawn_sound():
    """Generate enemy spawn sound."""
    # Quick ascending beep
    duration = 100
    samples = int(SAMPLE_RATE * duration / 1000.0)
    max_sample = 2**(16 - 1) - 1
    
    # Create stereo array
    arr = array.array('h', [0] * (samples * 2))
    
    for i in range(samples):
        t = float(i) / SAMPLE_RATE
        freq = 200 + (t * 300)  # Rising frequency
        sample = math.sin(2 * math.pi * freq * t)
        volume = 0.2
        val = int(max_sample * volume * sample)
        arr[i * 2] = val
        arr[i * 2 + 1] = val
    
    # Create sound - use same method as generate_tone
    if USE_SNDARRAY:
        try:
            import numpy as np
            np_arr = np.frombuffer(arr, dtype=np.int16).reshape((samples, 2))
            return pygame.sndarray.make_sound(np_arr)
        except:
            pass
    
    # Fallback: silent sound
    silent_arr = array.array('h', [0] * (samples * 2))
    return pygame.mixer.Sound(buffer=bytes(silent_arr))


def generate_thrust_sound():
    """Generate continuous thrust/engine sound."""
    # Low rumbling engine sound
    duration = 500  # Longer for looping
    samples = int(SAMPLE_RATE * duration / 1000.0)
    max_sample = 2**(16 - 1) - 1
    
    # Create stereo array
    arr = array.array('h', [0] * (samples * 2))
    
    for i in range(samples):
        t = float(i) / SAMPLE_RATE
        # Mix low frequencies for engine rumble
        freq1 = 80 + math.sin(t * 2) * 10  # Varying low frequency
        freq2 = 120 + math.sin(t * 3) * 15  # Slightly higher
        sample = (math.sin(2 * math.pi * freq1 * t) * 0.4 + 
                 math.sin(2 * math.pi * freq2 * t) * 0.2)
        # Add some noise for realism
        sample += (random.random() - 0.5) * 0.1
        volume = 0.15
        val = int(max_sample * volume * sample)
        arr[i * 2] = val
        arr[i * 2 + 1] = val
    
    # Create sound - use same method as generate_tone
    if USE_SNDARRAY:
        try:
            import numpy as np
            np_arr = np.frombuffer(arr, dtype=np.int16).reshape((samples, 2))
            sound = pygame.sndarray.make_sound(np_arr)
            sound.set_volume(0.3)
            return sound
        except:
            pass
    
    # Fallback: silent sound
    silent_arr = array.array('h', [0] * (samples * 2))
    sound = pygame.mixer.Sound(buffer=bytes(silent_arr))
    sound.set_volume(0.3)
    return sound


# ============================================================
# SPRITE CLASSES
# ============================================================
class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image_right = create_player_ship_right(SCALE)
        self.image_left  = create_player_ship_left(SCALE)
        self.image       = self.image_right
        self.rect        = self.image.get_rect()

        self.rect.centerx = SCREEN_WIDTH // 4
        self.rect.centery = SCREEN_HEIGHT // 2

        self.speed     = PLAYER_SPEED
        self.direction = 1  # 1 = right, -1 = left
        
        # Lives system
        self.lives = 3
        self.invincible = False
        self.invincible_timer = 0
        self.invincible_duration = 2000  # 2 seconds of invincibility
        
        # Thrust tracking
        self.is_thrusting = False
        self.thrust_sound_channel = None

    def handle_input(self, keys):
        dx = dy = 0
        was_thrusting = self.is_thrusting
        self.is_thrusting = False
        
        if keys[pygame.K_LEFT]:
            dx -= self.speed
            self.direction = -1
            self.is_thrusting = True  # Moving forward (left)
        if keys[pygame.K_RIGHT]:
            dx += self.speed
            self.direction = 1
            self.is_thrusting = True  # Moving forward (right)
        if keys[pygame.K_UP]:
            dy -= self.speed
        if keys[pygame.K_DOWN]:
            dy += self.speed

        self.rect.x += dx
        self.rect.y += dy

        # Clamp to screen and above mountains
        top_limit    = 20
        bottom_limit = MOUNTAIN_BASE_Y - 10

        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH:
            self.rect.right = SCREEN_WIDTH
        if self.rect.top < top_limit:
            self.rect.top = top_limit
        if self.rect.bottom > bottom_limit:
            self.rect.bottom = bottom_limit

        # Set sprite based on direction - swap if sprites are backwards
        self.image = self.image_left if self.direction >= 0 else self.image_right

    def update(self, *args, **kwargs):
        # Update invincibility timer
        now = kwargs.get('now', 0)
        if self.invincible:
            if now - self.invincible_timer >= self.invincible_duration:
                self.invincible = False
    
    def take_damage(self, now):
        """Player takes damage - lose a life and become invincible."""
        if self.invincible:
            return False  # Already invincible, no damage
        
        self.lives -= 1
        self.invincible = True
        self.invincible_timer = now
        
        # Reset position to safe area
        self.rect.centerx = SCREEN_WIDTH // 4
        self.rect.centery = SCREEN_HEIGHT // 2
        
        return True  # Damage taken
    
    def is_alive(self):
        """Check if player is still alive."""
        return self.lives > 0


class Enemy(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = create_enemy_ship(SCALE)
        self.rect  = self.image.get_rect()

        self.rect.left = SCREEN_WIDTH + random.randint(0, 50)
        top_limit      = 40
        bottom_limit   = MOUNTAIN_BASE_Y - 20
        self.rect.centery = random.randint(top_limit, bottom_limit)

        self.speed_x          = -ENEMY_SPEED
        self.wobble_offset    = random.uniform(0, math.pi * 2)
        self.wobble_speed     = random.uniform(0.03, 0.06)
        self.wobble_amplitude = random.randint(2, 6)

    def update(self, *args, **kwargs):
        self.rect.x += self.speed_x
        self.wobble_offset += self.wobble_speed
        self.rect.y += int(math.sin(self.wobble_offset) * self.wobble_amplitude)

        if self.rect.right < -50:
            self.kill()


class Bullet(pygame.sprite.Sprite):
    def __init__(self, pos, direction: int = 1):
        super().__init__()
        self.image    = create_bullet_surface(scale=SCALE)
        self.rect     = self.image.get_rect()
        self.speed_x  = BULLET_SPEED * direction

        # If firing right, spawn at left of bullet; if left, align right
        if direction >= 0:
            self.rect.midleft = pos
        else:
            self.rect.midright = pos

    def update(self, *args, **kwargs):
        self.rect.x += self.speed_x
        if self.rect.left > SCREEN_WIDTH or self.rect.right < 0:
            self.kill()


class Explosion(pygame.sprite.Sprite):
    def __init__(self, center):
        super().__init__()
        self.frames       = create_explosion_frames(SCALE)
        self.index        = 0
        self.image        = self.frames[self.index]
        self.rect         = self.image.get_rect()
        self.rect.center  = center
        self.frame_timer  = 0
        self.frame_length = 80  # ms

    def update(self, *args, **kwargs):
        # Get dt from kwargs or use default
        dt = kwargs.get('dt', 16)  # Default to ~60fps if not provided
        self.frame_timer += dt
        if self.frame_timer >= self.frame_length:
            self.frame_timer = 0
            self.index += 1
            if self.index >= len(self.frames):
                self.kill()
            else:
                center = self.rect.center
                self.image = self.frames[self.index]
                self.rect  = self.image.get_rect()
                self.rect.center = center


# ============================================================
# BACKGROUND HELPERS
# ============================================================
def draw_vertical_gradient(surface, top_color, bottom_color):
    width, height = surface.get_size()
    for y in range(height):
        t = y / height
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (width, y))


def draw_mountains(surface):
    w, h   = surface.get_size()
    base_y = MOUNTAIN_BASE_Y
    color  = MOUNTAIN_COLOR

    points = []
    step   = 30
    x      = 0
    current_y = base_y
    while x <= w + step:
        points.append((x, current_y))
        x += step
        current_y = base_y - random.randint(10, 40)

    poly_points = [(0, h)] + points + [(w, h)]
    pygame.draw.polygon(surface, color, poly_points, width=2)


def draw_stars(surface, star_positions):
    for x, y in star_positions:
        surface.set_at((x, y), STAR_COLOR)


# ============================================================
# MAIN GAME LOOP
# ============================================================
def main():
    pygame.init()
    pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Simple Defender-style Game (Single File)")
    clock  = pygame.time.Clock()
    
    # Generate sound effects
    sound_enabled = SOUND_ENABLED
    if sound_enabled:
        try:
            # Test if we can actually create sounds
            test_sound = generate_laser_sound()
            if USE_SNDARRAY or hasattr(test_sound, 'play'):
                sounds = {
                    'laser': generate_laser_sound(),
                    'explosion': generate_explosion_sound(),
                    'hit': generate_enemy_hit_sound(),
                    'death': generate_player_death_sound(),
                    'spawn': generate_enemy_spawn_sound(),
                    'thrust': generate_thrust_sound(),
                }
            else:
                raise Exception("Sound generation not supported")
        except Exception as e:
            print(f"Warning: Could not generate sounds: {e}")
            print("Sounds will be disabled. Install numpy for sound support: pip install numpy")
            sounds = {}
            sound_enabled = False
    else:
        sounds = {}

    # Pre-generate stars
    star_positions = [
        (
            random.randint(0, SCREEN_WIDTH - 1),
            random.randint(0, MOUNTAIN_BASE_Y - 50),
        )
        for _ in range(120)
    ]

    # Sprite groups
    all_sprites = pygame.sprite.Group()
    enemies     = pygame.sprite.Group()
    bullets     = pygame.sprite.Group()
    explosions  = pygame.sprite.Group()

    player = Player()
    all_sprites.add(player)

    score          = 0
    font           = pygame.font.SysFont("Consolas", 24)
    last_enemy_spawn = 0
    fire_cooldown    = 100  # ms
    last_shot_time   = 0

    debug = DEBUG
    state = "playing"

    running = True
    while running:
        dt  = clock.tick(FPS)
        now = pygame.time.get_ticks()

        # ---------- Events ----------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1:
                    debug = not debug
                if state == "game_over" and event.key == pygame.K_RETURN:
                    return main()  # restart

        keys = pygame.key.get_pressed()

        # ---------- Update ----------
        if state == "playing":
            player.handle_input(keys)
            
            # Handle thrust sound
            if sound_enabled and 'thrust' in sounds:
                if player.is_thrusting:
                    if player.thrust_sound_channel is None or not player.thrust_sound_channel.get_busy():
                        player.thrust_sound_channel = sounds['thrust'].play(-1)  # Loop
                else:
                    if player.thrust_sound_channel and player.thrust_sound_channel.get_busy():
                        player.thrust_sound_channel.stop()
                        player.thrust_sound_channel = None

            # Shooting
            if keys[pygame.K_SPACE]:
                if now - last_shot_time >= fire_cooldown:
                    direction = player.direction
                    if direction >= 0:
                        pos = (player.rect.right, player.rect.centery)
                    else:
                        pos = (player.rect.left, player.rect.centery)
                    bullet = Bullet(pos, direction=direction)
                    bullets.add(bullet)
                    all_sprites.add(bullet)
                    last_shot_time = now
                    # Play laser sound
                    if sound_enabled and 'laser' in sounds:
                        sounds['laser'].play()

            # Spawn enemies
            if now - last_enemy_spawn >= ENEMY_SPAWN_INTERVAL:
                enemy = Enemy()
                enemies.add(enemy)
                all_sprites.add(enemy)
                last_enemy_spawn = now
                # Play spawn sound (occasionally, not every spawn)
                if sound_enabled and 'spawn' in sounds and random.random() < 0.3:
                    sounds['spawn'].play()

            # Update entities
            all_sprites.update(dt=dt, now=now)
            explosions.update(dt=dt)

            # Collisions: bullets vs enemies
            hits = pygame.sprite.groupcollide(enemies, bullets, True, True)
            for enemy in hits.keys():
                score += 100
                explosion = Explosion(enemy.rect.center)
                explosions.add(explosion)
                all_sprites.add(explosion)
                # Play explosion sound
                if sound_enabled and 'explosion' in sounds:
                    sounds['explosion'].play()

            # Collisions: player vs enemies (only if not invincible)
            if not player.invincible and pygame.sprite.spritecollideany(player, enemies):
                if player.take_damage(now):
                    explosion = Explosion(player.rect.center)
                    explosions.add(explosion)
                    all_sprites.add(explosion)
                    # Play hit/death sound
                    if sound_enabled and 'hit' in sounds:
                        sounds['hit'].play()
                    
                    # Check if game over
                    if not player.is_alive():
                        # Play death sound
                        if sound_enabled and 'death' in sounds:
                            sounds['death'].play()
                        state = "game_over"

        # ---------- Draw ----------
        draw_vertical_gradient(screen, BG_TOP_COLOR, BG_BOTTOM_COLOR)
        draw_stars(screen, star_positions)
        draw_mountains(screen)

        # Draw all sprites except player (we'll draw player separately for blinking)
        for sprite in all_sprites:
            if sprite != player:
                screen.blit(sprite.image, sprite.rect)
        
        # Draw player with blinking effect when invincible
        if player.invincible:
            # Blink effect - draw every other frame (flashes)
            if (now // 100) % 2 == 0:
                screen.blit(player.image, player.rect)
        else:
            screen.blit(player.image, player.rect)
        
        # Draw thrust effect when moving forward
        if player.is_thrusting:
            # Calculate thrust position (back of ship)
            if player.direction >= 0:  # Facing right
                thrust_x = player.rect.left - 8
                thrust_y = player.rect.centery
            else:  # Facing left
                thrust_x = player.rect.right + 8
                thrust_y = player.rect.centery
            
            # Draw thrust particles (orange/yellow flame)
            for i in range(3):
                offset_x = random.randint(-2, 2)
                offset_y = random.randint(-3, 3)
                particle_x = thrust_x + offset_x
                particle_y = thrust_y + offset_y
                
                # Draw flame particles
                if i == 0:
                    color = COLORS["F"]  # Bright orange
                    size = 3
                elif i == 1:
                    color = COLORS["A"]  # Orange
                    size = 2
                else:
                    color = COLORS["Y"]  # Yellow
                    size = 2
                
                pygame.draw.circle(screen, color, (particle_x, particle_y), size)

        score_surf = font.render(f"SCORE: {score}", True, (0, 255, 0))
        screen.blit(score_surf, (10, 10))
        
        # Draw lives
        lives_surf = font.render(f"LIVES: {player.lives}", True, (255, 255, 0))
        screen.blit(lives_surf, (10, 40))

        if state == "game_over":
            msg      = "GAME OVER - PRESS ENTER TO RESTART"
            msg_surf = font.render(msg, True, (255, 80, 80))
            rect     = msg_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
            screen.blit(msg_surf, rect)
            
            # Show final score
            final_score_msg = f"FINAL SCORE: {score}"
            final_score_surf = font.render(final_score_msg, True, (255, 255, 0))
            final_score_rect = final_score_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
            screen.blit(final_score_surf, final_score_rect)

        if debug:
            for spr in all_sprites:
                pygame.draw.rect(screen, (255, 0, 0), spr.rect, 1)
            dbg_text = f"DEBUG  FPS:{clock.get_fps():5.1f}  ENEMIES:{len(enemies)}"
            dbg_surf = font.render(dbg_text, True, (255, 255, 0))
            screen.blit(dbg_surf, (10, SCREEN_HEIGHT - 30))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()