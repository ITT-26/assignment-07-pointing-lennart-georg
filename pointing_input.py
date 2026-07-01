import argparse
import ctypes
import math
import os
import tempfile
import time


# arguments: what camera, debug window
parser = argparse.ArgumentParser()
parser.add_argument("--camera", "-c", type=int, default=0)
parser.add_argument("--debug", "-d", action="store_true", default=False)
args = parser.parse_args()


# get the screen size on Windows, macOS, or Linux
def get_screen_size():
    if hasattr(ctypes, "windll"):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            user32 = ctypes.windll.user32
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except Exception:
            pass

    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        return width, height
    except Exception:
        return 1920, 1080


# heavy imports come after argument parsing so --help stays fast
os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib"))
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from pynput.mouse import Button, Controller
from pynput import keyboard

VIDEO_ID = args.camera
DEBUG = args.debug

# One tracked hand drives the pointer.
NUM_HANDS = 1

MODEL_PATH = "./mediapipe_sample_code/hand_landmarker.task"

OPTIONS = vision.HandLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path=MODEL_PATH),
    num_hands=NUM_HANDS,
    running_mode=vision.RunningMode.VIDEO,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5
)
detector = vision.HandLandmarker.create_from_options(OPTIONS)

cap = cv2.VideoCapture(VIDEO_ID)
if not cap.isOpened():
    raise RuntimeError("Could not open camera")

# mouse controller
mouse = Controller()

# flag to exit the program
exit_program = False


# keyboard listener for exiting the program
def on_press(key):
    global exit_program
    if key == keyboard.Key.f12:
        exit_program = True


# start listener
listener = keyboard.Listener(on_press=on_press)
listener.start()

# screen dimensions
screen_width, screen_height = get_screen_size()

# is the left mouse button pressed
left_click = False

# smoothing values
smooth_x = 0.5
smooth_y = 0.5
alpha = 0.35  # lower -> smoother

# Camera coordinates are remapped to use the screen area comfortably.
x_min, x_max = 0.2, 0.8
y_min, y_max = 0.2, 0.8

# values for click detection
ANGLE_CLICK_THRESHOLD = 20
ANGLE_RELEASE_THRESHOLD = 25


# calculates the distance between two spots -> used for the marks in mediapipe
def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


# for keeping the mouse pointer inside the screen
def clamp(pos, low_thresh, high_thresh):
    return max(low_thresh, min(high_thresh, pos))


# remapping camera values for using the whole screen -> clamping is needed too for keeping the pointer inside the screen
def remap(pos, cam_min, cam_max):
    return clamp((pos - cam_min) / (cam_max - cam_min), 0.0, 1.0)


# check if the index finger is extended -> needs to be extended for the L-base pose
def is_index_extended(hand):
    return hand[8].y < hand[6].y < hand[5].y


# check if a finger is folded -> L-shape is used for input -> middle ring and pinky finger should be folded
def is_finger_folded(hand, tip_idx, end_idx):
    # is the tip of the finger below the other landmark -> finger folded
    return hand[tip_idx].y > hand[end_idx].y


# check if the hand is in L-shape
def is_l_shape(hand):
    # index finger extended, other fingers folded -> Thumb for clicking -> not checked
    index_ok = is_index_extended(hand)
    # check if the other fingers are folded (landmark ids for each finger)
    middle_folded = is_finger_folded(hand, 12, 10)
    ring_folded = is_finger_folded(hand, 16, 14)
    pinky_folded = is_finger_folded(hand, 20, 18)
    return index_ok and middle_folded and ring_folded and pinky_folded


started = False

# loop
while True:

    # Capture a frame from the webcam
    ret, frame = cap.read()
    if not ret or frame is None:
        time.sleep(0.01)
        continue

    # convert to Mediapipe's RGB image format
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

    # save current time for internal interpolation
    timestamp_ms = int(time.time() * 1000)

    # Detect hand landmarks from the input image.
    detection_result = detector.detect_for_video(mp_frame, timestamp_ms)

    # tell the user that mouse control has started -> only once
    if not started:
        print("MOUSE CONTROL STARTED")
        started = True

    # is the hand in L-shape
    l_shaped = False

    # angle between thumb and index finger
    angle = None

    # if a hand is detected
    if len(detection_result.hand_landmarks) > 0:
        # get the first hand
        hand = detection_result.hand_landmarks[0]

        # some landmarks for click detection
        index_tip = hand[8]

        # check if the hand is in L-shape
        l_shaped = is_l_shape(hand)

        # Pointer source
        x = 1.0 - index_tip.x
        y = index_tip.y

        # Remap to screen
        x = remap(x, x_min, x_max)
        y = remap(y, y_min, y_max)

        # if l-shaped hand
        if l_shaped:

            # Smooth pointer movement.
            smooth_x = smooth_x + alpha * (x - smooth_x)
            smooth_y = smooth_y + alpha * (y - smooth_y)

            # clamp to screen
            sx = int(clamp(smooth_x * (screen_width - 1), 0, screen_width - 1))
            sy = int(clamp(smooth_y * (screen_height - 1), 0, screen_height - 1))

            # set mouse position
            mouse.position = (sx, sy)

        # Click logic -> check angle between thumb and index finger -> if angle small -> click

        # thumb vector
        thumb_x = hand[4].x - hand[1].x
        thumb_y = hand[4].y - hand[1].y

        # index finger vector
        index_x = hand[8].x - hand[1].x
        index_y = hand[8].y - hand[1].y

        # angle between thumb and index finger
        denominator = math.hypot(thumb_x, thumb_y) * math.hypot(index_x, index_y)
        if denominator > 0:
            cosine = (thumb_x * index_x + thumb_y * index_y) / denominator
            cosine = clamp(cosine, -1.0, 1.0)
            angle = math.degrees(math.acos(cosine))

        # if l-shaped hand and angle small -> click
        if angle is not None and l_shaped and (not left_click) and angle < ANGLE_CLICK_THRESHOLD:
            mouse.press(Button.left)
            left_click = True
        # if left click
        elif left_click:
            # if not l-shaped or angle is too big -> release click
            if not l_shaped or angle is None or angle > ANGLE_RELEASE_THRESHOLD:
                mouse.release(Button.left)
                left_click = False

    # if no hand is detected -> release click if it was pressed
    else:
        if left_click:
            mouse.release(Button.left)
            left_click = False

    # debug info on the frame
    angle_text = f"{angle:.2f}" if angle is not None else "N/A"

    # print debug info on the frame
    cv2.putText(
        frame,
        f"L={l_shaped} angle={angle_text} click={'DOWN' if left_click else 'UP'}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    # show the frame with debug info
    if DEBUG:
        cv2.imshow("pointing input", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    if exit_program:
        break

# if the program is closed while the left mouse button is pressed -> release it
if left_click:
    mouse.release(Button.left)

# release the camera and close the window
listener.stop()
cap.release()
cv2.destroyAllWindows()
