from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT = Path(__file__).resolve().parent / "goldbachs_conjecture.gif"

N_MAX = 50
FPS = 12
MOVE_FRAMES = 3
BLUE_FRAMES = 4
HOLD_FRAMES = 1
STAGE_FRAMES = MOVE_FRAMES + BLUE_FRAMES + HOLD_FRAMES

W = H = 700
MARGIN = 55
PLOT = 590
SCALE = PLOT / N_MAX

def xy(x, y):
    return MARGIN + x * SCALE, H - MARGIN - y * SCALE

try:
    font = ImageFont.truetype("DejaVuSans.ttf", 15)
    small = ImageFont.truetype("DejaVuSans.ttf", 12)
except:
    font = small = ImageFont.load_default()

dead = set()
orange = set()
states = {}

for p in range(2, N_MAX + 1):
    for k in range(2, p + 1):
        n = p * k
        if n <= N_MAX:
            dead.add(n)

    for x in range(2, 2*p + 1):
        for y in range(2, x + 1):
            if p < x + y <= 2*p and x not in dead and y not in dead:
                orange.add((x, y))

    states[p] = (set(dead), set(orange))

def draw_mouse_cursor(d, x):
    """Small mouse-like cursor below the x-axis, connected to the x-axis position."""
    cx, axis_y = xy(x, 0)
    top = axis_y + 8
    bottom = axis_y + 42
    width = 16

    # thin guide stem
    d.line((cx, axis_y + 2, cx, top), fill=(40,120,216), width=2)

    # mouse body: rounded rectangle, with a small wheel
    d.rounded_rectangle(
        (cx - width/2, top, cx + width/2, bottom),
        radius=6,
        fill=(245,245,245),
        outline=(40,120,216),
        width=2
    )
    d.line((cx, top + 5, cx, top + 15), fill=(40,120,216), width=2)
    d.ellipse((cx - 2, top + 7, cx + 2, top + 11), fill=(40,120,216))

frames = []

for frame in range(N_MAX * STAGE_FRAMES):
    stage = frame // STAGE_FRAMES
    local = frame % STAGE_FRAMES

    if stage == 0:
        p = None
        dead_now = set()
        orange_now = set()
        cursor = 2
        blue_progress = None
    else:
        p = min(stage + 1, N_MAX)
        dead_now, orange_now = states[p]
        prev = max(2, p - 1)

        if local < MOVE_FRAMES:
            t = local / max(1, MOVE_FRAMES - 1)
            cursor = prev + (p - prev) * t
            blue_progress = None
        elif p >= 4 and p % 2 == 0 and local < MOVE_FRAMES + BLUE_FRAMES:
            cursor = p
            blue_progress = (local - MOVE_FRAMES) / max(1, BLUE_FRAMES - 1)
        else:
            cursor = p
            blue_progress = None

    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)

    # Vector-like grid
    for n in range(0, N_MAX + 1, 5):
        gx, _ = xy(n, 0)
        _, gy = xy(0, n)
        d.line((gx, MARGIN, gx, H-MARGIN), fill=(225,225,225), width=1)
        d.line((MARGIN, gy, W-MARGIN, gy), fill=(225,225,225), width=1)

    # Axes
    x0, y0 = xy(0, 0)
    d.line((MARGIN, y0, W-MARGIN, y0), fill=(35,35,35), width=2)
    d.line((x0, MARGIN, x0, H-MARGIN), fill=(35,35,35), width=2)

    # Smaller persistent orange points
    for x, y in orange_now:
        px, py = xy(x, y)
        r = 2.2
        d.ellipse((px-r, py-r, px+r, py+r), fill=(251,140,0))

    # Axis points, reduced radius
    for n in range(2, N_MAX + 1):
        px, _ = xy(n, 0)
        _, py = xy(0, n)

        if n in dead_now:
            c = (102,107,112)
            cyellow = (102,107,112)
        else:
            c = (229,57,53)
            cyellow = (253,216,53)

        r = 2.8
        d.ellipse((px-r,y0-r,px+r,y0+r), fill=c)
        d.ellipse((x0-r,py-r,x0+r,py+r), fill=cyellow)

    # Prime subscripts on x-axis: show "p" below each prime the cursor has passed
    # A number is prime if it's >= 2 and not in dead_now (never extinguished).
    # Only show labels for primes the cursor has already moved past.
    for n in range(2, N_MAX + 1):
        if n in dead_now:
            continue  # composite, not prime
        # Only show label once cursor has strictly passed this prime
        if cursor <= n:
            continue
        px, _ = xy(n, 0)
        label = str(n)
        # Center the text below the x-axis point, above the cursor area
        bbox = d.textbbox((0, 0), label, font=small)
        tw = bbox[2] - bbox[0]
        tx = px - tw / 2
        ty = y0 + 14
        # Only draw if it doesn't overlap the cursor (cursor body starts at y0+8)
        # Place label just below axis, cursor is further down
        d.text((tx, ty), label, fill=(229, 57, 53), font=small)

    # -1, 0, 1 markers
    for n in (-1, 0, 1):
        px, _ = xy(n, 0)
        if MARGIN-20 <= px <= W-MARGIN+20:
            d.ellipse((px-2, y0-2, px+2, y0+2), fill=(176,176,176))
        _, py = xy(0, n)
        if MARGIN-20 <= py <= H-MARGIN+20:
            d.ellipse((x0-2, py-2, x0+2, py+2), fill=(176,176,176))

    # Completed blue lines; active line is handled separately.
    if p is not None:
        if p >= 4 and p % 2 == 0 and blue_progress is not None:
            completed_even = range(4, p, 2)
        else:
            completed_even = range(4, p + 1, 2)

        for n in completed_even:
            pts = [xy(n*i/80, n - n*i/80) for i in range(81)]
            d.line(pts, fill=(65,125,180), width=1)

    # Active blue light
    if p is not None and p >= 4 and p % 2 == 0 and blue_progress is not None:
        n = p
        x_end = n * blue_progress
        pts = [xy(n + (x_end-n)*i/80, n - (n + (x_end-n)*i/80)) for i in range(81)]
        d.line(pts, fill=(25,118,210), width=3)

        gx, gy = xy(x_end, n-x_end)
        r = 4
        d.ellipse((gx-r, gy-r, gx+r, gy+r), fill=(25,118,210))

    # Mouse-like cursor below x-axis
    draw_mouse_cursor(d, cursor)

    # Labels
    if p is None:
        title = "Initial State"
        subtitle = "Unlit interior points are invisible"
    elif p >= 4 and p % 2 == 0 and blue_progress is not None:
        title = f"n = {p}"
        subtitle = f"Goldbach light: x + y = {p}   |   Cursor paused"
    elif p >= 4 and p % 2 == 0:
        title = f"n = {p}"
        subtitle = f"Goldbach line x + y = {p} completed"
    else:
        title = f"p = {p}"
        subtitle = f"Extinguish 2p, 3p, ..., p²   |   Orange: p < x+y <= 2p"

    d.text((MARGIN, 15), title, fill=(25,25,25), font=font)
    d.text((MARGIN, 38), subtitle, fill=(70,70,70), font=small)
    d.text(
        (MARGIN, H-30),
        "RED: x-axis   YELLOW: y-axis   ORANGE: lit   BLUE: Goldbach lines",
        fill=(70,70,70), font=small
    )

    frames.append(im)

frames[0].save(
    OUTPUT,
    save_all=True,
    append_images=frames[1:],
    duration=round(1000/FPS),
    loop=0,
    optimize=False
)

print(OUTPUT)
