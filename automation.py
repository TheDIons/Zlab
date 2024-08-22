import os
import cv2
import numpy as np
import mss
import time
import win32gui
import win32api
import win32con
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk
import threading
import json
import torch
import pathlib
import random
from functools import lru_cache

temp = pathlib.PosixPath
pathlib.PosixPath = pathlib.WindowsPath

CONFIG_FILE = "selected_windows.json"

class DeviceAutomation:
    def __init__(self, window_title, index, yolo_model):
        self.window_title = window_title
        self.hwnd = None
        self.running = False
        self.paused = False
        self.last_pin_entry_time = None
        self.last_green_time = None
        self.last_confirm_time = None
        self.monitor = {"top": 0, "left": 0, "width": 0, "height": 0}
        self.index = index
        self.find_window()
        self.thread = None
        self.yolo_model = yolo_model
        self.template_cache = {}
        self.pin_entry_lock = threading.Lock()
        self.last_pin_entry_time = None

    def find_window(self):
        self.hwnd = win32gui.FindWindow(None, self.window_title)
        if self.hwnd == 0:
            raise Exception(f"Window '{self.window_title}' not found")

    def get_window_rect(self):
        rect = win32gui.GetWindowRect(self.hwnd)
        self.monitor["top"], self.monitor["left"], self.monitor["width"], self.monitor["height"] = rect[1], rect[0], rect[2] - rect[0], rect[3] - rect[1]

    def resize_template(self, template, scale):
        # Create a cache key
        cache_key = (template.shape, scale)

        # Check if the result is already in cache
        if cache_key in self.template_cache:
            return self.template_cache[cache_key]

        # If not in cache, compute the resized template
        new_width = int(template.shape[1] * scale)
        new_height = int(template.shape[0] * scale)
        resized_template = cv2.resize(template, (new_width, new_height))

        # Store in cache
        self.template_cache[cache_key] = resized_template

        return resized_template

    def find_template(self, frame, templates, threshold=0.8, scales=[0.95, 1.0, 1.05]):
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for template in templates:
            for scale in scales:
                resized_template = self.resize_template(template, scale)
                result = cv2.matchTemplate(frame_gray, resized_template, cv2.TM_CCOEFF_NORMED)
                locations = np.where(result >= threshold)
                if locations[0].size > 0:
                    return (locations[1][0] + resized_template.shape[1] // 2,
                            locations[0][0] + resized_template.shape[0] // 2)
        return None

    def click_bg_window(self, x, y):
        lParam = win32api.MAKELONG(x, y)
        win32api.SendMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        win32api.SendMessage(self.hwnd, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, lParam)

    def set_window_size(self, width=215, height=515):
        cols = 6
        row = self.index // cols
        col = self.index % cols
        x_pos = col * width
        y_pos = row * height
        win32gui.MoveWindow(self.hwnd, x_pos, y_pos, width, height, True)

    def enter_pin(self):
        with self.pin_entry_lock:
            current_time = datetime.now()
            if self.last_pin_entry_time is None or (current_time - self.last_pin_entry_time) > timedelta(seconds=1):
                if not self.running:
                    return
                time.sleep(0.02)
                if not self.running:
                    return
                time.sleep(0.05) #delays
                self.click_bg_window(107, 420)
                for _ in range(5):
                    time.sleep(0.04)
                    if not self.running:
                        return
                    self.click_bg_window(169, 415)
                self.last_pin_entry_time = current_time

    def load_templates(self, folder_path):
        templates = []
        for filename in os.listdir(folder_path):
            if filename.endswith(".png"):
                template = cv2.imread(os.path.join(folder_path, filename), 0)
                templates.append(template)
        return templates

    def find_start_point(self, frame, template_folder):
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for filename in os.listdir(template_folder):
            if filename.endswith('.png'):
                template_path = os.path.join(template_folder, filename)
                template = cv2.imread(template_path, 0)
                result = cv2.matchTemplate(frame_gray, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                if max_val >= 0.8:
                    return max_loc[0] + template.shape[1] // 2, max_loc[1] + template.shape[0] // 2
        return None

    def solve_captcha(self):
        print(f"Solving captcha for window: {self.window_title}")
        self.get_window_rect()
        with mss.mss() as sct:
            frame = np.array(sct.grab(self.monitor))
            results = self.yolo_model(frame)

            start_point = self.find_start_point(frame, "img/start_points")
            if start_point is None:
                print("Couldn't find the starting point for dragging.")
                return False

            valid_results = [
                (int((x1 + x2) // 2), int((y1 + y2) // 2), int(x2 - x1))
                for x1, y1, x2, y2, conf, cls in results.xyxy[0].cpu().numpy()
                if conf > 0.8
            ]

            if not valid_results:
                print("No valid captcha targets found.")
                return False

            center_x, center_y, width = valid_results[0]
            start_x, start_y = start_point

            # Calculate the distance to travel
            distance = center_x - start_x

            # Implement variable offset based on distance
            if distance < 30:  # Near start
                offset = -1  # Slight negative offset to prevent overshooting
            elif distance > 55 and distance < 80:  # Far from start
                offset = 5  # Larger positive offset to ensure reaching
            elif distance >= 80 and distance < 95:  # Far from start
                offset = 6
            elif distance >= 95 and distance < 105:  # Far from start
                offset = 7
            elif distance >= 105:  # Far from start
                offset = 8
            else:  # Middle range
                offset = 2  # Small positive offset for fine-tuning

            end_x = int(center_x + offset)

            print(f"Puzzle center: ({center_x}, {center_y})")
            print(f"Puzzle width: {width}")
            print(f"Drag start: ({start_x}, {start_y})")
            print(f"Drag end: ({end_x}, {start_y})")
            print(f"Distance: {distance}, Offset: {offset}")

            # Perform the drag with a shorter duration
            self.drag_mouse(start_x, start_y, end_x, start_y, duration=0.1)

            # Reduced wait time for animations to settle
            time.sleep(0.3)

            return True

        return False

    def drag_mouse(self, start_x, start_y, end_x, end_y, duration=0.1):
        # Calculate distance
        distance = abs(end_x - start_x)

        # Adjust duration based on distance
        adjusted_duration = min(max(duration, distance / 200), 0.2)  # Limit between 0.8 and 1.2 seconds

        lParam_start = win32api.MAKELONG(int(start_x), int(start_y))
        lParam_end = win32api.MAKELONG(int(end_x), int(end_y))

        win32gui.SetForegroundWindow(self.hwnd)
        time.sleep(0.05)

        win32api.SendMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam_start)

        steps = 10
        total_distance = end_x - start_x

        for i in range(steps + 1):
            progress = i / steps
            # Use a different easing function for more natural movement
            eased_progress = self.ease_out_quad(progress)

            current_x = int(start_x + total_distance * eased_progress)
            current_y = int(start_y)

            lParam_move = win32api.MAKELONG(current_x, current_y)
            win32api.SendMessage(self.hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lParam_move)

            time.sleep(adjusted_duration / steps)

        win32api.SendMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, lParam_end)

        time.sleep(0.05)

    @staticmethod
    def ease_out_quad(t):
        return 1 - (1 - t) * (1 - t)


    def automation_loop(self, pin_template_folder, glo_template_folder, glo2_template_folder, green_template_folder,
                    confirm_template_folder):
        self.running = True
        try:
            self.get_window_rect()

            pin_templates = self.load_templates(pin_template_folder)
            glo_templates = self.load_templates(glo_template_folder)
            glo2_templates = self.load_templates(glo2_template_folder)
            green_templates = self.load_templates(green_template_folder)
            confirm_templates = self.load_templates(confirm_template_folder)
            start_point_templates = self.load_templates(start_point_template_folder)

            with mss.mss() as sct:
                while self.running:
                    if self.paused:
                        time.sleep(0.1)
                        continue

                    frame = np.array(sct.grab(self.monitor))
                    try:
                        green_coordinates = self.find_template(frame, green_templates)
                        if green_coordinates:
                            if self.last_green_time is None or datetime.now() - self.last_green_time > timedelta(seconds=5):
                                self.click_bg_window(173, 133)
                                self.last_green_time = datetime.now()

                        start_coordinates = self.find_template(frame,start_point_templates)
                        if start_coordinates:
                            print(f"Captcha detected for window: {self.window_title}")
                            if self.solve_captcha():
                                print(f"Captcha solved for window: {self.window_title}")
                            else:
                                print(f"Failed to solve captcha for window: {self.window_title}")
                            continue  # Skip other checks this cycle

                        pin_coordinates = self.find_template(frame, pin_templates)
                        if pin_coordinates:
                            self.enter_pin()
                            continue

                        glo_coordinates = self.find_template(frame, glo_templates)
                        if glo_coordinates:
                            time.sleep(1)
                            self.click_bg_window(148, 467)

                        glo2_coordinates = self.find_template(frame, glo2_templates)
                        if glo2_coordinates:
                            time.sleep(0.5)
                            self.click_bg_window(29, 139)

                        confirm_coordinates = self.find_template(frame, confirm_templates)
                        if confirm_coordinates:
                            if self.last_confirm_time is None or datetime.now() - self.last_confirm_time > timedelta(milliseconds=250):
                                self.click_bg_window(48, 466)
                                self.last_confirm_time = datetime.now()

                    except Exception as e:
                        print(f"Error in automation loop: {e}")

                    if not self.running:
                        break

                    time.sleep(0.1)
        except Exception as e:
            print(f"Automation loop error: {e}")

    def start(self, pin_template_folder, glo_template_folder, glo2_template_folder, green_template_folder,
              confirm_template_folder):
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self.automation_loop, args=(
                pin_template_folder, glo_template_folder, glo2_template_folder, green_template_folder, confirm_template_folder))
            self.thread.start()

    def stop(self):
        if self.thread is not None:
            self.running = False
            self.thread.join()
            self.thread = None

    def refresh(self):
        self.click_bg_window(107, 450)
        time.sleep(0.5)
        self.click_bg_window(36, 450)

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

# Global variables
devices = []
selected_windows = []
root = None
window_var = None
window_menu = None
device_listbox = None
start_all_button = None
stop_all_button = None
status_label = None

# Helper functions
def list_windows():
    def winEnumHandler(hwnd, ctx):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                running_windows.append(title)

    running_windows = []
    win32gui.EnumWindows(winEnumHandler, None)
    return running_windows

def update_window_list():
    window_list = list_windows()
    window_menu['values'] = window_list

def save_selected_windows(selected_windows):
    with open(CONFIG_FILE, 'w') as file:
        json.dump(selected_windows, file)

def load_selected_windows():
    global selected_windows
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            selected_windows = json.load(file)
    return selected_windows

def refresh_device_list():
    device_listbox.delete(0, tk.END)
    for device in devices:
        device_listbox.insert(tk.END, device.window_title)
    update_buttons_state()

# Use absolute paths to the template folders
pin_template_folder = "img/pin"
glo_template_folder = "img/glo"
glo2_template_folder = "img/glo2"
green_template_folder = "img/green"
confirm_template_folder = "img/confirm"
start_point_template_folder = "img/start_points"

# Initialize YOLO model
yolo_model = torch.hub.load('ultralytics/yolov5', 'custom', path='models/best.pt', force_reload=True)
yolo_model.eval()
if torch.cuda.is_available():
    yolo_model = yolo_model.cuda()

# GUI functions
def add_device(window_title, index=None):
    global devices
    if any(device.window_title == window_title for device in devices):
        print(f"Window '{window_title}' is already added.")
        return

    index = len(devices) if index is None else index
    try:
        device = DeviceAutomation(window_title, index, yolo_model)
        devices.append(device)
        refresh_device_list()
        save_selected_windows([device.window_title for device in devices])
    except Exception as e:
        print(e)

def remove_device():
    global devices
    selected_indices = device_listbox.curselection()
    if not selected_indices:
        return
    index = selected_indices[0]
    devices[index].stop()
    device_listbox.delete(index)
    del devices[index]
    save_selected_windows([device.window_title for device in devices])
    for i, device in enumerate(devices):
        device.index = i
        device.set_window_size()

def start_all():
    for device in devices:
        device.start(pin_template_folder, glo_template_folder, glo2_template_folder, green_template_folder,
                     confirm_template_folder)
    update_buttons_state()
    status_label.config(text="Status: Running", foreground="green")

def stop_all():
    for device in devices:
        device.stop()
    update_buttons_state()
    status_label.config(text="Status: Stopped", foreground="red")

def resize_all():
    for device in devices:
        try:
            device.set_window_size()
        except Exception as e:
            print(e)

def refresh_all():
    for device in devices:
        device.pause()
    for device in devices:
        device.refresh()
    time.sleep(0.1)
    for device in devices:
        device.resume()

def update_buttons_state():
    running = any(device.running for device in devices)
    start_all_button.config(state=tk.DISABLED if running else tk.NORMAL)
    stop_all_button.config(state=tk.NORMAL if running else tk.DISABLED)

# Main application function
def start_main_application():
    global root, window_var, window_menu, device_listbox, start_all_button, stop_all_button, status_label, devices, selected_windows

    # Initialize the main window
    root = tk.Tk()
    root.title("Automation Control Panel")

    # Window title selection
    window_var = tk.StringVar()

    # Layout
    frame = ttk.Frame(root, padding="5")
    frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Window selection and controls
    window_select_frame = ttk.LabelFrame(frame, text="Window Selection", padding="5")
    window_select_frame.grid(row=0, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))

    ttk.Label(window_select_frame, text="Select Window Title:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
    window_menu = ttk.Combobox(window_select_frame, textvariable=window_var, state="readonly")
    window_menu.grid(row=0, column=1, padx=5, pady=2, sticky=(tk.W, tk.E))
    window_menu.bind("<Button-1>", lambda event: update_window_list())

    add_device_button = ttk.Button(window_select_frame, text="Add Device", command=lambda: add_device(window_var.get()))
    add_device_button.grid(row=0, column=2, padx=5, pady=2)

    # Device list
    device_list_frame = ttk.LabelFrame(frame, text="Devices", padding="5")
    device_list_frame.grid(row=1, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))

    device_listbox = tk.Listbox(device_list_frame, height=8)
    device_listbox.grid(row=0, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))

    remove_device_button = ttk.Button(device_list_frame, text="Remove Device", command=remove_device)
    remove_device_button.grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)

    # Control buttons
    control_frame = ttk.LabelFrame(frame, text="Controls", padding="5")
    control_frame.grid(row=2, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))

    start_all_button = ttk.Button(control_frame, text="Start All", command=start_all)
    start_all_button.grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)

    stop_all_button = ttk.Button(control_frame, text="Stop All", command=stop_all)
    stop_all_button.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)

    resize_all_button = ttk.Button(control_frame, text="Resize All", command=resize_all)
    resize_all_button.grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)

    refresh_all_button = ttk.Button(control_frame, text="Refresh All", command=refresh_all)
    refresh_all_button.grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)

    # Status
    status_frame = ttk.LabelFrame(frame, text="Status", padding="5")
    status_frame.grid(row=3, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))

    status_label = ttk.Label(status_frame, text="Status: Stopped", foreground="red")
    status_label.grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)

    # Configure column weights
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)
    frame.columnconfigure(2, weight=1)

    # Load previously saved windows
    selected_windows = load_selected_windows()
    for i, window_title in enumerate(selected_windows):
        add_device(window_title, index=i)

    refresh_device_list()
    update_buttons_state()

    # Run the main loop
    root.mainloop()

if __name__ == "__main__":
    start_main_application()