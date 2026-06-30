import argparse
import math
import random
import pyglet
from pyglet import shapes
from pyglet.window import key


# Arguments
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--num-targets", type=int, default=10)
    p.add_argument("--distance", type=float, default=300.0)
    p.add_argument("--target-radius", type=float, default=25.0)
    return p.parse_args()


# Window size
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800


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

# start point in the middle
START_X = WINDOW_WIDTH // 2
START_Y = WINDOW_HEIGHT // 2
# start radius
START_R = 45

# target radius, distance to target, number of targets
TARGET_R = args.target_radius
DISTANCE_TO_TARGET = args.distance
NUM_TARGETS = args.num_targets

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

# random order of targets
order = list(range(NUM_TARGETS))
random.shuffle(order)
order_pos = 0


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
    global state, finished, order_pos

    # start after clicking in the start circle
    if state == "WAIT":
        if inside_circle(x, y, START_X, START_Y, START_R):
            state = "PLAY"
        return

    # if the test is running
    if state == "PLAY":
        # current target
        current_idx = order[order_pos]
        tx, ty = targets[current_idx]

        # check if the click is inside the target
        if inside_circle(x, y, tx, ty, TARGET_R):
            # next target
            order_pos += 1
            # done if all targets are hit
            if order_pos >= len(order):
                finished = True
                state = "DONE"


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
        msg = "Click the blue circle to start"
    elif state == "PLAY":
        msg = f"Target {order_pos + 1}/{len(order)}"
    else:
        msg = "Done! Press ESC to exit"

    # draw text
    label = pyglet.text.Label(
        msg, x=16, y=WINDOW_HEIGHT - 24, color=(255, 255, 255, 255))
    label.draw()


# update inteval
pyglet.clock.schedule_interval(update, 1 / 60.0)
pyglet.app.run()
