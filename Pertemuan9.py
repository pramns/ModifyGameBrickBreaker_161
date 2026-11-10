"""
Block Breaker - versi papan (striker) lebih halus.

Yang diubah supaya pergerakan papan terasa halus:
  1. Input dibaca setiap frame dengan pygame.key.get_pressed(), bukan hanya
     lewat event KEYDOWN/KEYUP. KEYDOWN hanya menyala sekali saat tombol
     pertama ditekan (sesudah itu baru menyala lagi setelah repeat delay
     keyboard), jadi papan terasa patah-patah.
  2. Papan pakai kecepatan (velocity) + akselerasi + gesekan (friction),
     bukan langsung loncat sejauh `speed` tiap frame. Papan jadi "meluncur"
     dan berhenti pelan-pelan, bukan berhenti mendadak.
  3. Semua pergerakan dikalikan delta time (dt) sehingga kecepatannya
     konsisten di 30, 60, atau 120 FPS.
  4. FPS dinaikkan 30 -> 60 supaya animasi lebih rapat/halus.
  5. Bonus: sudut pantul bola sekarang tergantung titik tumbukan di papan
     (kiri = melantun ke kiri, kanan = ke kanan), bukan sekadar yFac *= -1.
"""

import math
import random

import pygame

pygame.init()

# Dimensions of the screen
WIDTH, HEIGHT = 600, 500

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
GREY = (120, 120, 120)

font = pygame.font.Font('freesansbold.ttf', 15)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Block Breaker")

clock = pygame.time.Clock()

# --- Pergerakan halus -------------------------------------------------------
FPS = 60                 # frame lebih rapat = animasi lebih halus
DT_CAP = 1.0 / 30.0      # pengaman: jangan pernah menganggap dt sangat besar
                         # (mis. saat window di-drag / tab tidak aktif)

# --- SETEL DI SINI kalau papan masih terasa terlalu cepat / terlalu lambat ---
STRIKER_MAX_SPEED = 390.0   # px/detik  - kecepatan maksimum papan
                            #   (lama: 620. Turunkan lagi bila masih kencang)
STRIKER_ACCEL = 1500.0      # px/detik^2 - makin kecil = makin "berat"/santai
                            #   (lama: 3400)
STRIKER_FRICTION = 1700.0   # px/detik^2 - makin besar = makin cepat berhenti
                            #   (lama: 2400)

BALL_SPEED = 240.0          # px/detik  (lama: 300)
BALL_SPEED_STEP = 6.0       # bertambah setiap blok pecah (lama: 12)
BALL_SPEED_MAX = 400.0      # batas atas kecepatan bola (lama: 560)

# --- Power-up "x3 bola" -----------------------------------------------------
POWERUP_CHANCE = 0.25       # peluang (0-1) sebuah blok menjatuhkan tanda x3
POWERUP_SPEED = 130.0       # px/detik - kecepatan tanda jatuh
POWERUP_SIZE = (26, 26)     # ukuran kotak tanda
POWERUP_MULT = 3            # jumlah bola setelah tanda ditangkap
MAX_BALLS = 9               # batas aman supaya tidak kebanyakan bola
YELLOW = (255, 215, 0)
# ---------------------------------------------------------------------------


# Striker class
class Striker:
    def __init__(self, posx, posy, width, height, speed, color):
        self.posx, self.posy = float(posx), float(posy)
        self.width, self.height = width, height
        self.speed = speed
        self.color = color

        # velocity horizontal papan (px/detik). Diawali 0 = papan diam.
        self.velx = 0.0

        # The rect variable is used to handle the placement
        # and the collisions of the object
        self.strikerRect = pygame.Rect(
            int(self.posx), int(self.posy), self.width, self.height)

    # Used to render the object on the screen
    def display(self):
        pygame.draw.rect(screen, self.color, self.strikerRect)

    # Used to update the state of the object.
    # `direction` : -1 (kiri), 0 (diam), 1 (kanan) - dibaca tiap frame
    # `dt`        : waktu satu frame dalam detik
    def update(self, direction, dt):
        if direction != 0:
            # percepat papan ke arah input
            self.velx += STRIKER_ACCEL * direction * dt
        else:
            # tidak ada input -> perlambat papan sampai berhenti (glide)
            if self.velx > 0:
                self.velx = max(0.0, self.velx - STRIKER_FRICTION * dt)
            elif self.velx < 0:
                self.velx = min(0.0, self.velx + STRIKER_FRICTION * dt)

        # batasi kecepatan maksimum (clamp)
        if self.velx > STRIKER_MAX_SPEED:
            self.velx = STRIKER_MAX_SPEED
        elif self.velx < -STRIKER_MAX_SPEED:
            self.velx = -STRIKER_MAX_SPEED

        # posisi di-update memakai kecepatan x waktu -> gerakan mulus
        self.posx += self.velx * dt

        # Restricting the striker to be in between the
        # left and right edges of the screen
        if self.posx <= 0:
            self.posx = 0.0
            self.velx = 0.0
        elif self.posx + self.width >= WIDTH:
            self.posx = float(WIDTH - self.width)
            self.velx = 0.0

        self.strikerRect = pygame.Rect(
            int(round(self.posx)), int(self.posy), self.width, self.height)

    # Returns the rect of the object
    def getRect(self):
        return self.strikerRect


# Block Class
class Block:
    def __init__(self, posx, posy, width, height, color):
        self.posx, self.posy = posx, posy
        self.width, self.height = width, height
        self.color = color
        self.damage = 100

        # The white blocks have the health of 200. So,
        # the ball must hit it twice to break
        if color == WHITE:
            self.health = 200
        else:
            self.health = 100

        # The rect variable is used to handle the placement
        # and the collisions of the object
        self.blockRect = pygame.Rect(
            self.posx, self.posy, self.width, self.height)

    # Used to render the object on the screen if and only
    # if its health is greater than 0
    def display(self):
        if self.health > 0:
            pygame.draw.rect(screen, self.color, self.blockRect)
            # blok putih yang sudah kena sekali digambar bergaris biar jelas
            if self.health < 200:
                pygame.draw.rect(screen, GREY, self.blockRect, 2)

    # Used to decrease the health of the block
    def hit(self):
        self.health -= self.damage

    # Used to get the rect of the object
    def getRect(self):
        return self.blockRect

    # Used to get the health of the object
    def getHealth(self):
        return self.health


# Ball Class
class Ball:
    def __init__(self, posx, posy, radius, speed, color):
        self.posx, self.posy = float(posx), float(posy)
        self.radius = radius
        self.speed = float(speed)
        self.color = color

        # arah bola disimpan sebagai vektor satuan (x, y)
        self.dirx, self.diry = 0.6, -0.8

    # Used to display the object on the screen
    def display(self):
        pygame.draw.circle(screen, self.color,
                           (int(self.posx), int(self.posy)), self.radius)

    # Used to update the state of the object.
    # Mengembalikan True kalau bola jatuh melewati tepi bawah layar.
    def update(self, dt):
        self.posx += self.dirx * self.speed * dt
        self.posy += self.diry * self.speed * dt

        # Reflecting the ball if it touches
        # either of the vertical edges (pakai radius supaya tidak "nempel")
        if self.posx - self.radius <= 0:
            self.posx = self.radius
            self.dirx = abs(self.dirx)
        elif self.posx + self.radius >= WIDTH:
            self.posx = WIDTH - self.radius
            self.dirx = -abs(self.dirx)

        # Reflection from the top most edge of the screen
        if self.posy - self.radius <= 0:
            self.posy = self.radius
            self.diry = abs(self.diry)

        # If the ball touches the bottom most edge of
        # the screen, True value is returned
        if self.posy - self.radius >= HEIGHT:
            return True

        return False

    # Resets the position of the ball (di atas papan, melaju ke atas)
    def reset(self, striker_rect=None):
        self.posy = HEIGHT - 150.0
        if striker_rect is not None:
            self.posx = striker_rect.centerx
        else:
            self.posx = WIDTH / 2.0
        self.dirx, self.diry = 0.6, -0.8

    # Pantulan dari papan: sudut ditentukan titik tumbukan.
    # Kiri papan -> bola ke kiri, kanan papan -> bola ke kanan.
    def bounceOffStriker(self, striker_rect):
        # -1 di ujung kiri papan, +1 di ujung kanan papan
        offset = (self.posx - striker_rect.centerx) / (striker_rect.width / 2)
        offset = max(-1.0, min(1.0, offset))

        max_angle = math.radians(60)
        angle = offset * max_angle

        self.dirx = math.sin(angle)
        self.diry = -abs(math.cos(angle))   # selalu memantul ke atas

    # Pantulan dari blok: tentukan sumbu mana yang lebih dalam tertembus
    def bounceOffBlock(self, block_rect):
        overlap_x = (block_rect.width / 2 + self.radius) - \
            abs((block_rect.centerx) - self.posx)
        overlap_y = (block_rect.height / 2 + self.radius) - \
            abs((block_rect.centery) - self.posy)

        if overlap_x < overlap_y:
            # tabrakan lebih dalam di sumbu X -> balik arah horizontal
            self.dirx *= -1
        else:
            self.diry *= -1

    # Used to change the direction along Y axis
    def hit(self):
        self.diry *= -1

    # Returns the rect of the ball (dipakai untuk collision)
    def getRect(self):
        return pygame.Rect(int(self.posx) - self.radius,
                           int(self.posy) - self.radius,
                           self.radius * 2, self.radius * 2)


# Helper Functions

# Function used to check collisions between any two entities
def collisionChecker(rect, ball):
    return bool(rect.colliderect(ball))


# PowerUp class - "tanda" yang jatuh dari blok yang pecah.
# Kalau tanda ini kena papan, bola menjadi 3.
class PowerUp:
    def __init__(self, posx, posy, size=POWERUP_SIZE,
                 speed=POWERUP_SPEED, color=YELLOW, label="x3"):
        self.posx, self.posy = float(posx), float(posy)
        self.width, self.height = size
        self.speed = speed
        self.color = color
        self.label = label

        self.rect = pygame.Rect(int(self.posx), int(self.posy),
                                self.width, self.height)

    # Used to display the object on the screen
    def display(self):
        pygame.draw.rect(screen, self.color, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 2)
        text = font.render(self.label, True, BLACK)
        screen.blit(text, text.get_rect(center=self.rect.center))

    # Used to update the state of the object.
    # Mengembalikan True kalau tanda sudah jatuh melewati tepi bawah layar.
    def update(self, dt):
        self.posy += self.speed * dt
        self.rect = pygame.Rect(int(self.posx), int(self.posy),
                                self.width, self.height)
        return self.posy > HEIGHT

    def getRect(self):
        return self.rect


# Membuat bola baru di posisi `posx, posy` dengan arah yang diputar `angle`
# derajat dari arah `base_ball` (dipakai saat bola diperbanyak jadi 3).
def makeBall(base_ball, posx, posy, angle=0.0):
    ball = Ball(posx, posy, base_ball.radius, base_ball.speed, base_ball.color)

    cos_a, sin_a = math.cos(angle), math.sin(angle)
    dx, dy = base_ball.dirx, base_ball.diry
    ball.dirx = dx * cos_a - dy * sin_a
    ball.diry = dx * sin_a + dy * cos_a

    # pastikan tetap vektor satuan & tidak pernah melaju ke bawah saat lahir
    length = math.hypot(ball.dirx, ball.diry) or 1.0
    ball.dirx /= length
    ball.diry = -abs(ball.diry / length)

    return ball


# Perbanyak bola menjadi `POWERUP_MULT` (3): bola lama + 2 bola baru
# yang menyebar ke kiri dan ke kanan.
def multiplyBalls(balls):
    if not balls or len(balls) >= MAX_BALLS:
        return balls

    base = balls[0]
    spread = math.radians(24)

    balls.append(makeBall(base, base.posx, base.posy, -spread))
    balls.append(makeBall(base, base.posx, base.posy, spread))

    return balls[:MAX_BALLS]


# Jatuhkan satu tanda x3 dari posisi blok yang pecah
def spawnPowerUp(block_rect):
    return PowerUp(block_rect.centerx - POWERUP_SIZE[0] / 2,
                   block_rect.centery - POWERUP_SIZE[1] / 2)


# Teks singkat yang melayang di layar (mis. "BOLA x3!")
class FloatingText:
    def __init__(self, text, posx, posy, color=YELLOW, life=1.0):
        self.surface = font.render(text, True, color)
        self.posx, self.posy = float(posx), float(posy)
        self.life = life

    def update(self, dt):
        self.posy -= 30.0 * dt
        self.life -= dt
        return self.life > 0

    def display(self):
        screen.blit(self.surface,
                    self.surface.get_rect(center=(int(self.posx),
                                                  int(self.posy))))


# Function used to populate the blocks
def populateBlocks(blockWidth, blockHeight,
                   horizontalGap, verticalGap):
    listOfBlocks = []

    for i in range(0, WIDTH, blockWidth + horizontalGap):
        for j in range(0, HEIGHT // 2, blockHeight + verticalGap):
            listOfBlocks.append(
                Block(i, j, blockWidth, blockHeight,
                      random.choice([WHITE, GREEN])))

    return listOfBlocks


# Once all the lives are over, this function waits until
# exit or space bar is pressed and does the corresponding action
def gameOver():
    waiting = True

    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    return True

        screen.fill(BLACK)
        msg = font.render("GAME OVER - tekan SPASI untuk main lagi",
                          True, WHITE)
        screen.blit(msg, msg.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        pygame.display.update()
        clock.tick(FPS)


# Ringkasan keadaan game. Diisi setiap frame oleh main() supaya mudah
# dipantau/diuji dari luar (mis. jumlah bola yang sedang aktif).
GAME = {}


# Game Manager
def main():
    running = True
    lives = 3
    score = 0

    scoreText = font.render("score", True, WHITE)
    scoreTextRect = scoreText.get_rect()
    scoreTextRect.center = (20, HEIGHT - 10)

    livesText = font.render("Lives", True, WHITE)
    livesTextRect = livesText.get_rect()
    livesTextRect.center = (120, HEIGHT - 10)

    striker = Striker(0, HEIGHT - 50, 100, 20, STRIKER_MAX_SPEED, WHITE)

    # Bola disimpan di dalam list supaya bisa diperbanyak menjadi 3
    ball = Ball(0, HEIGHT - 150, 7, BALL_SPEED, WHITE)
    ball.reset(striker.getRect())
    balls = [ball]

    # Tanda "x3" yang jatuh, dan teks melayang (mis. "BOLA x3!")
    powerUps = []
    floatingTexts = []

    # anti "nyangkut": setelah memantul dari papan, beri jeda beberapa frame
    hitCooldown = 0

    blockWidth, blockHeight = 40, 15
    horizontalGap, verticalGap = 20, 20

    listOfBlocks = populateBlocks(
        blockWidth, blockHeight, horizontalGap, verticalGap)

    # Game loop
    while running:
        # dt = durasi satu frame (detik). Semua pergerakan dikalikan dt
        # supaya kecepatan sama di FPS berapa pun.
        dt = min(clock.tick(FPS) / 1000.0, DT_CAP)

        screen.fill(BLACK)
        screen.blit(scoreText, scoreTextRect)
        screen.blit(livesText, livesTextRect)

        scoreText = font.render("Score : " + str(score), True, WHITE)
        livesText = font.render("Lives : " + str(lives), True, WHITE)

        # If all the blocks are destroyed, then we repopulate them
        if not listOfBlocks:
            listOfBlocks = populateBlocks(
                blockWidth, blockHeight, horizontalGap, verticalGap)

        # All the lives are over. So, the gameOver() function is called
        if lives <= 0:
            running = gameOver()

            while listOfBlocks:
                listOfBlocks.pop(0)

            lives = 3
            score = 0
            ball.speed = BALL_SPEED
            ball.reset(striker.getRect())
            balls = [ball]          # kembali ke 1 bola
            powerUps = []           # tanda yang belum ditangkap dibuang
            floatingTexts = []
            listOfBlocks = populateBlocks(
                blockWidth, blockHeight, horizontalGap, verticalGap)

        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # Tombol P = memunculkan tanda x3 untuk mencoba fitur ini
            if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                powerUps.append(
                    PowerUp(random.randint(20, WIDTH - 20 - POWERUP_SIZE[0]),
                            120))

        # --- Input halus: dibaca SETIAP frame, bukan dari event ---
        keys = pygame.key.get_pressed()
        direction = 0
        if keys[pygame.K_LEFT]:
            direction -= 1
        if keys[pygame.K_RIGHT]:
            direction += 1
        # -------------------------------------------------------------------

        # Ringkasan keadaan (dipakai HUD & pengujian)
        GAME.update(striker=striker, balls=balls, blocks=listOfBlocks,
                    powerUps=powerUps, lives=lives, score=score, frame=None)

        # --- Tanda x3 jatuh: kalau kena papan, bola menjadi 3 ---
        for i in range(len(powerUps) - 1, -1, -1):
            pu = powerUps[i]
            pu.update(dt)

            if collisionChecker(striker.getRect(), pu.getRect()):
                balls = multiplyBalls(balls)
                floatingTexts.append(
                    FloatingText("BOLA x%d!" % len(balls),
                                 pu.getRect().centerx, pu.getRect().top))
                powerUps.pop(i)
            elif pu.getRect().top > HEIGHT:
                powerUps.pop(i)     # jatuh ke bawah, hilang
        # ---------------------------------------------------------

        # Collision check
        if hitCooldown > 0:
            hitCooldown -= 1

        for ball in list(balls):
            # bola vs papan
            if hitCooldown <= 0 and \
                    collisionChecker(striker.getRect(), ball.getRect()):
                ball.bounceOffStriker(striker.getRect())
                hitCooldown = 3

            # bola vs blok
            for block in list(listOfBlocks):
                if collisionChecker(block.getRect(), ball.getRect()):
                    ball.bounceOffBlock(block.getRect())
                    block.hit()

                    if block.getHealth() <= 0:
                        listOfBlocks.remove(block)
                        score += 5
                        for b in balls:
                            b.speed = min(b.speed + BALL_SPEED_STEP,
                                          BALL_SPEED_MAX)

                        # Peluang menjatuhkan tanda x3
                        if random.random() < POWERUP_CHANCE and \
                                len(powerUps) < 3:
                            powerUps.append(spawnPowerUp(block.getRect()))

                    # satu blok per bola per frame biar pantulannya tidak kacau
                    break

        # Update
        striker.update(direction, dt)

        # Bola yang jatuh dihapus. Kalau semuanya habis -> nyawa berkurang.
        for i in range(len(balls) - 1, -1, -1):
            if balls[i].update(dt):
                balls.pop(i)

        if not balls:
            lives -= 1
            print(lives)
            ball = Ball(0, HEIGHT - 150, 7, BALL_SPEED, WHITE)
            ball.reset(striker.getRect())
            balls = [ball]

        # Teks melayang ("BOLA x3!") naik lalu hilang
        for i in range(len(floatingTexts) - 1, -1, -1):
            if not floatingTexts[i].update(dt):
                floatingTexts.pop(i)

        # Display
        striker.display()

        for ball in balls:
            ball.display()

        for block in listOfBlocks:
            block.display()

        for pu in powerUps:
            pu.display()

        for ft in floatingTexts:
            ft.display()

        # Info jumlah bola di kanan bawah
        ballsText = font.render("Bola : " + str(len(balls)), True, YELLOW)
        screen.blit(ballsText, ballsText.get_rect(center=(WIDTH - 60,
                                                          HEIGHT - 10)))

        pygame.display.update()


if __name__ == "__main__":
    main()
    pygame.quit()
