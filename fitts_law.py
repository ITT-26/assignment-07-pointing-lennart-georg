import argparse
import math
import random
import csv
import os
import time
import json


# load config from file
def load_config(path):
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid config JSON: {e}")


# Arguments
def parse_args():

    # config parser
    pre = argparse.ArgumentParser(add_help=False)
    # default config file
    pre.add_argument("--config", type=str, default="fitts_config.json")
    known, _ = pre.parse_known_args()

    # load config
    cfg = load_config(known.config)

    # get from config or default
    def c(name, default):
        return cfg[name] if name in cfg else default

    # argument parser
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=str, default=known.config)
    p.add_argument("--pid", type=int, default=c("pid", 1))
    p.add_argument("--num-targets", type=int, default=c("num_targets", 10))
    p.add_argument("--distance", type=float, default=c("distance", 300))
    p.add_argument("--target-radius", type=float,
                   default=c("target_radius", 25))
    p.add_argument("--trials", type=int, default=c("trials", 1))
    p.add_argument("--condition", type=str, default=c("condition", "mouse"))
    p.add_argument("--latency-ms", type=int, default=c("latency_ms", 0))
    return p.parse_args()


# Window size
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800

# data directory
DATA_DIR = "data"


# check if point is in circle
def inside_circle(px, py, cx, cy, r):
    dx = px - cx
    dy = py - cy
    return dx * dx + dy * dy <= r * r


# make targets in a circle around the center point
def build_targets(center_x, center_y, distance, num_targets):
    targets = []
    for i in range(num_targets):
        angle = (2.0 * math.pi * i) / num_targets
        tx = center_x + distance * math.cos(angle)
        ty = center_y + distance * math.sin(angle)
        targets.append((tx, ty))
    return targets


# get arguments
args = parse_args()

# import pyglet after parsing so --help works without opening a display
import pyglet
pyglet.options["dpi_scaling"] = "stretch"
from pyglet import shapes
from pyglet.window import key

# latency in milliseconds
LATENCY_MS = max(0, args.latency_ms)

# condition name for logging and file names
CONDITION = args.condition.strip().replace(" ", "_")
if not CONDITION:
    CONDITION = "mouse"

# filename
filename = f"fitts_{args.num_targets}_{int(args.target_radius*2)}_{int(args.distance)}_{CONDITION}_{LATENCY_MS}_{args.pid}.csv"
os.makedirs(DATA_DIR, exist_ok=True)
csv_path = os.path.join(DATA_DIR, filename)

# file
csv_file = open(csv_path, "a", newline="", encoding="utf-8")
csv_writer = csv.writer(csv_file)

# make header if the file is empty
if os.path.getsize(csv_path) == 0:
    csv_writer.writerow([
        "iteration",
        "pid",
        "num_targets",
        "target_w",
        "target_d",
        "target_id",
        "condition",
        "latency_ms",
        "t_start_ms",
        "t_end_ms",
        "duration_ms",
    ])
    csv_file.flush()


# function to log a hit
def log_hit(target_id, t_end_ms):
    t_start_ms = last_target_time if last_target_time is not None else t_end_ms
    csv_writer.writerow([
        current_trial,
        args.pid,
        NUM_TARGETS,
        int(2 * TARGET_R),
        int(DISTANCE_TO_TARGET),
        target_id,
        CONDITION,
        LATENCY_MS,
        t_start_ms,
        t_end_ms,
        t_end_ms - t_start_ms,
    ])
    csv_file.flush()


# start point in the middle
START_X = WINDOW_WIDTH // 2
START_Y = WINDOW_HEIGHT // 2
# start radius
START_R = 45

# target radius, distance to target, number of targets
TARGET_R = args.target_radius
DISTANCE_TO_TARGET = args.distance
NUM_TARGETS = args.num_targets

# trials
TOTAL_TRIALS = args.trials
current_trial = 1

# make window
window = pyglet.window.Window(WINDOW_WIDTH, WINDOW_HEIGHT, "Fitts Test")

# mouse invisible
window.set_mouse_visible(False)

# mouse position
mouse_x = WINDOW_WIDTH / 2
mouse_y = WINDOW_HEIGHT / 2

# delayed cursor position
cursor_x = WINDOW_WIDTH / 2
cursor_y = WINDOW_HEIGHT / 2

# raw mouse history for latency
mouse_history = []

# state of the test
state = "WAIT"

# flag for finished
finished = False

# start time for the current target
last_target_time = None

# make targets
targets = build_targets(START_X, START_Y, DISTANCE_TO_TARGET, NUM_TARGETS)


# reset for next trial
def reset_trial():
    global order, order_pos, state, last_target_time

    # random order
    order = list(range(NUM_TARGETS))
    random.shuffle(order)
    order_pos = 0

    # update state
    state = "WAIT"
    last_target_time = None


# random order for the trial
order = []
order_pos = 0
reset_trial()


# update mouse position
@window.event
def on_mouse_motion(x, y, dx, dy):
    global mouse_x, mouse_y
    mouse_x = x
    mouse_y = y


# update mouse position while dragging
@window.event
def on_mouse_drag(x, y, dx, dy, buttons, modifiers):
    global mouse_x, mouse_y
    mouse_x = x
    mouse_y = y


# exit on ESC
@window.event
def on_key_press(symbol, modifiers):
    if symbol == key.ESCAPE:
        window.close()


# update cursor position
def update(dt):
    global cursor_x, cursor_y

    now = int(time.time() * 1000)
    mouse_history.append((now, mouse_x, mouse_y))

    # keep only the small part of history needed for the latency setting
    cutoff = now - LATENCY_MS - 1000
    while len(mouse_history) > 1 and mouse_history[1][0] < cutoff:
        mouse_history.pop(0)

    # no latency -> normal mouse position
    if LATENCY_MS == 0:
        cursor_x = mouse_x
        cursor_y = mouse_y
        return

    target_time = now - LATENCY_MS
    delayed = mouse_history[0]
    for item in mouse_history:
        if item[0] <= target_time:
            delayed = item
        else:
            break

    cursor_x = delayed[1]
    cursor_y = delayed[2]


# mouse click event
@window.event
def on_mouse_press(x, y, button, modifiers):
    global state, finished, order_pos, current_trial, last_target_time

    click_x = cursor_x
    click_y = cursor_y

    # start after clicking in the start circle
    if state == "WAIT":
        if inside_circle(click_x, click_y, START_X, START_Y, START_R):
            state = "PLAY"
            last_target_time = int(time.time() * 1000)
        return

    # if the test is running
    if state == "PLAY":
        # current target
        current_target_id = order[order_pos]
        tx, ty = targets[current_target_id]

        # check if the click is inside the target
        if inside_circle(click_x, click_y, tx, ty, TARGET_R):
            t_end_ms = int(time.time() * 1000)
            # log hit
            log_hit(current_target_id, t_end_ms)
            last_target_time = t_end_ms
            # next target
            order_pos += 1
            # done if all targets are hit
            if order_pos >= len(order):
                # reset for next trial if there are more trials, else finish
                if current_trial < TOTAL_TRIALS:
                    current_trial += 1
                    reset_trial()
                else:
                    finished = True
                    state = "DONE"


@window.event
def on_close():
    csv_file.close()


@window.event
def on_draw():
    window.clear()

    # start circle color -> green if not waiting, blue if waiting
    start_color = (0, 170, 0) if state != "WAIT" else (0, 0, 180)
    # start circle
    start = shapes.Circle(START_X, START_Y, START_R, color=start_color)
    start.draw()

    # targets
    for i, (tx, ty) in enumerate(targets):
        # current target -> red
        if state == "PLAY" and i == order[order_pos]:
            color = (220, 0, 0)
        # if complete -> green
        elif state == "DONE":
            color = (0, 180, 0)
        # else -> gray
        else:
            color = (120, 120, 120)

        # draw target
        c = shapes.Circle(tx, ty, TARGET_R, color=color)
        c.draw()

    # cursor
    cursor = shapes.Circle(cursor_x, cursor_y,
                           6, color=(240, 240, 240))
    cursor.draw()

    # text for the current state
    if state == "WAIT":
        msg = f"Trial {current_trial}/{TOTAL_TRIALS}: Click the blue circle to start"
    elif state == "PLAY":
        msg = f"Trial {current_trial}/{TOTAL_TRIALS} | Target {order_pos + 1}/{len(order)}"
    else:
        msg = "Done! Press ESC to exit"

    # draw text
    label = pyglet.text.Label(
        msg, x=16, y=WINDOW_HEIGHT - 24, color=(255, 255, 255, 255))
    label.draw()


# update interval
pyglet.clock.schedule_interval(update, 1 / 60.0)
pyglet.app.run()
