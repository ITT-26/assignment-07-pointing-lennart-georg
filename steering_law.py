# here goes your Steering Law application
# based on the Fitts Law application, but with a path instead of targets

import pyglet
from pyglet import shapes
from pyglet.window import key
import argparse
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
    pre.add_argument("--config", type=str, default="steering_config.json")
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
    p.add_argument("--path-length", type=int, default=c("path_length", 600))
    p.add_argument("--path-width", type=int, default=c("path_width", 100))
    p.add_argument("--trials", type=int, default=c("trials", 1))
    return p.parse_args()


# arguments
args = parse_args()

# data directory
DATA_DIR = "data"

# filename for the CSV file
filename = f"steering_{args.path_length}_{args.path_width}_{args.pid}.csv"

# csv path
csv_path = os.path.join(DATA_DIR, filename)

# file and writer
csv_file = open(csv_path, "a", newline="", encoding="utf-8")
csv_writer = csv.writer(csv_file)


# make header if the file is empty
if os.path.getsize(csv_path) == 0:
    csv_writer.writerow([
        "iteration",
        "pid",
        "path_length",
        "path_width",
        "error_count",
        "t_start_ms",
        "t_end_ms",
        "duration_ms",
    ])
    csv_file.flush()


# window size
WIDTH = 800
HEIGHT = 800

# trials
TOTAL_TRIALS = args.trials
current_trial = 1

# path parameters
PATH_LENGTH = args.path_length
PATH_WIDTH = args.path_width

# radii of the start and goal circles
START_R = 30
GOAL_R = 30

# path coordinates
path_x0 = (WIDTH - PATH_LENGTH) / 2
path_x1 = path_x0 + PATH_LENGTH
path_y = HEIGHT / 2
path_y0 = path_y - PATH_WIDTH / 2
path_y1 = path_y + PATH_WIDTH / 2

# start and goal coordinates
start_x, start_y = path_x0, path_y
goal_x, goal_y = path_x1, path_y

state = "WAIT"

# cursor position
cursor_x = WIDTH / 2
cursor_y = HEIGHT / 2

# error count
errors = 0

# timestamp for the start of the trial
start_time = None

# flag to track if the cursor is outside the path
was_outside = False

# window
window = pyglet.window.Window(WIDTH, HEIGHT, "Steering Law Test")
window.set_mouse_visible(False)


# reset for next trial
def reset_trial():
    global state, errors, was_outside
    state = "WAIT"
    errors = 0
    was_outside = False


# check if a point is inside a circle
def inside_circle(px, py, cx, cy, r):
    dx = px - cx
    dy = py - cy
    return dx * dx + dy * dy <= r * r


# check if a point is inside the path
def inside_path(x, y):
    return path_x0 <= x <= path_x1 and path_y0 <= y <= path_y1


# update mouse position
@window.event
def on_mouse_motion(x, y, dx, dy):
    global cursor_x, cursor_y
    cursor_x, cursor_y = x, y


# mouse press
@window.event
def on_mouse_press(x, y, button, modifiers):
    global state, errors, was_outside, start_time
    # start the test if the cursor is inside the start circle
    if state == "WAIT" and inside_circle(x, y, start_x, start_y, START_R):
        state = "PLAY"
        errors = 0
        was_outside = False
        # timestamp
        start_time = int(time.time() * 1000)


# log function
def log_trial():
    # timestamp for the end of the trial
    t_end_ms = int(time.time() * 1000)
    duration_ms = t_end_ms - start_time
    csv_writer.writerow([
        current_trial,
        args.pid,
        PATH_LENGTH,
        PATH_WIDTH,
        errors,
        start_time,
        t_end_ms,
        duration_ms,
    ])
    csv_file.flush()


# escape to exit
@window.event
def on_key_press(symbol, modifiers):
    if symbol == key.ESCAPE:
        window.close()


# update function for the loop
def update(dt):
    global state, errors, was_outside, current_trial

    # do nothing if the test is not running
    if state != "PLAY":
        return

    # check if the cursor is inside the path
    in_path = inside_path(cursor_x, cursor_y)
    if not in_path:
        # check if the cursor was already outside the path
        if not was_outside:
            errors += 1
        was_outside = True
    else:
        was_outside = False

    # check if the cursor is inside the goal circle
    if inside_circle(cursor_x, cursor_y, goal_x, goal_y, GOAL_R):
        # log the trial
        log_trial()

        # count up trial and reset if not finished
        if current_trial < TOTAL_TRIALS:
            current_trial += 1
            reset_trial()
        # all trials finished, set state to DONE
        else:
            state = "DONE"


@window.event
def on_close():
    csv_file.close()


@window.event
def on_draw():
    window.clear()

    # path
    path = shapes.Rectangle(path_x0, path_y0, PATH_LENGTH,
                            PATH_WIDTH, color=(90, 90, 90))
    path.draw()

    # start and goal color similar to Fitts Law application
    start_color = (0, 170, 0) if state != "WAIT" else (0, 0, 180)
    goal_color = (220, 0, 0) if state == "PLAY" else (120, 120, 120)
    if state == "DONE":
        goal_color = (0, 180, 0)

    # draw start, goal, and cursor
    start = shapes.Circle(start_x, start_y, START_R, color=start_color)
    goal = shapes.Circle(goal_x, goal_y, GOAL_R, color=goal_color)
    cursor = shapes.Circle(cursor_x, cursor_y, 6, color=(240, 240, 240))

    start.draw()
    goal.draw()
    cursor.draw()

    # message based on the state of the test
    if state == "WAIT":
        msg = f"Trial {current_trial}/{TOTAL_TRIALS}: Click blue circle to start"
    elif state == "PLAY":
        msg = f"Trial {current_trial}/{TOTAL_TRIALS} | Steer to red goal | errors: {errors}"
    else:
        msg = "Done! ESC to exit"

    # draw the message
    pyglet.text.Label(msg, x=16, y=HEIGHT - 24,
                      color=(255, 255, 255, 255)).draw()


# update interval
pyglet.clock.schedule_interval(update, 1 / 60.0)
pyglet.app.run()
