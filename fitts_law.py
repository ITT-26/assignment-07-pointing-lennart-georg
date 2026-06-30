import argparse
import math
import random
import pyglet
from pyglet import shapes
from pyglet.window import key
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

# filename
filename = f"fitts_{args.num_targets}_{int(args.target_radius*2)}_{int(args.distance)}_{args.pid}.csv"
csv_path = os.path.join(DATA_DIR, filename)

# file
csv_file = open(csv_path, "a", newline="")
csv_writer = csv.writer(csv_file)

# make header if the file is empty
if os.path.getsize(csv_path) == 0:
    csv_writer.writerow([
        "iteration", "pid", "num_targets", "target_w", "target_d", "target_id", "timestamp"
    ])
    csv_file.flush()


# function to log a hit
def log_hit(target_id):
    csv_writer.writerow([
        current_trial,
        args.pid,
        NUM_TARGETS,
        int(2 * TARGET_R),
        int(DISTANCE_TO_TARGET),
        target_id,
        int(time.time() * 1000),
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

# cursor postion starts with none
cursor_draw_x = WINDOW_WIDTH / 2
cursor_draw_y = WINDOW_HEIGHT / 2

# state of the test
state = "WAIT"

# flag for finished
finished = False

# make targets
targets = build_targets(START_X, START_Y, DISTANCE_TO_TARGET, NUM_TARGETS)


# reset for next trial
def reset_trial():
    global order, order_pos, state

    # random order
    order = list(range(NUM_TARGETS))
    random.shuffle(order)
    order_pos = 0

    # update state
    state = "WAIT"


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


# exit on ESC
@window.event
def on_key_press(symbol, modifiers):
    if symbol == key.ESCAPE:
        window.close()


# update cursor position
def update(dt):
    global cursor_draw_x, cursor_draw_y
    cursor_draw_x += (mouse_x - cursor_draw_x)
    cursor_draw_y += (mouse_y - cursor_draw_y)


# mouse click event
@window.event
def on_mouse_press(x, y, button, modifiers):
    global state, finished, order_pos, current_trial

    # start after clicking in the start circle
    if state == "WAIT":
        if inside_circle(x, y, START_X, START_Y, START_R):
            state = "PLAY"
        return

    # if the test is running
    if state == "PLAY":
        # current target
        current_target_id = order[order_pos]
        tx, ty = targets[current_target_id]

        # check if the click is inside the target
        if inside_circle(x, y, tx, ty, TARGET_R):
            # log hit
            log_hit(current_target_id)
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
    cursor = shapes.Circle(cursor_draw_x, cursor_draw_y,
                           6, color=(240, 240, 240))
    cursor.draw()

    # text for the current state
    if state == "WAIT":
        msg = f"Trial {current_trial}/{TOTAL_TRIALS} | Target {order_pos + 1}/{len(order)}"
    elif state == "PLAY":
        msg = f"Trial {current_trial}/{TOTAL_TRIALS}: Click the blue circle to start"
    else:
        msg = "Done! Press ESC to exit"

    # draw text
    label = pyglet.text.Label(
        msg, x=16, y=WINDOW_HEIGHT - 24, color=(255, 255, 255, 255))
    label.draw()


# update inteval
pyglet.clock.schedule_interval(update, 1 / 60.0)
pyglet.app.run()
