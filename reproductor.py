#!/usr/bin/env python3
import os
import sys
import random
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import vlc
except Exception:
    vlc = None

def get_config_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "config.json")

def load_config():
    config = {
        "volume": 80,
        "shuffle": True,
        "pinned": True,
        "x": 100,
        "y": 100,
        "width": 600,
        "height": 40,
        "bg_color": "#000000",
        "btn_color": "#333333",
        "font_color": "#FFFFFF",
        "playlist": "",
        "song_index": 0,
        "show_titlebar": True,
        "opacity": 100,
        "resizable": True
    }
    config_path = get_config_path()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config.update(json.load(f))
        except Exception:
            pass
    return config

def save_config(config):
    config_path = get_config_path()
    try:
        with open(config_path, "w") as f:
            json.dump(config, f)
    except Exception as e:
        print(f"Failed to save config: {e}")

def get_music_root():
    user_home = os.path.expanduser("~")
    return os.path.join(user_home, "Music")

def scan_playlists(root):
    playlists = {}
    if not os.path.isdir(root):
        return playlists
    
    for entry in sorted(os.listdir(root)):
        entry_path = os.path.join(root, entry)
        if os.path.isdir(entry_path):
            files = []
            for f in os.listdir(entry_path):
                if f.lower().endswith((".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg")):
                    files.append(os.path.join(entry_path, f))
            if files:
                playlists[entry] = sorted(files, key=lambda x: x.lower())
    
    for entry in sorted(os.listdir(root)):
        entry_path = os.path.join(root, entry)
        if os.path.isdir(entry_path):
            for sub_entry in sorted(os.listdir(entry_path)):
                sub_path = os.path.join(entry_path, sub_entry)
                if os.path.isdir(sub_path):
                    files = []
                    for f in os.listdir(sub_path):
                        if f.lower().endswith((".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg")):
                            files.append(os.path.join(sub_path, f))
                    if files:
                        key = f"{entry}/{sub_entry}"
                        playlists[key] = sorted(files, key=lambda x: x.lower())
    
    return playlists

class MusicMinimalPlayer:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        
        self.music_root = get_music_root()
        self.playlists = scan_playlists(self.music_root)
        self.playlist_names = sorted(self.playlists.keys())
        
        self.current_playlist_files = []
        if self.playlist_names:
            saved_playlist = self.config.get("playlist", "")
            if saved_playlist in self.playlist_names:
                self.current_playlist_name = saved_playlist
            else:
                self.current_playlist_name = self.playlist_names[0]
            self.current_playlist_files = self.playlists.get(self.current_playlist_name, [])
        
        self.current_index = self.config.get("song_index", 0)
        if self.current_index >= len(self.current_playlist_files):
            self.current_index = 0
        
        self.instance = vlc.Instance() if vlc is not None else None
        self.player = self.instance.media_player_new() if self.instance is not None else None
        self.player_monitor_running = False
        self.player_monitor_thread = None
        self.time_monitor_running = False
        self.time_monitor_thread = None
        
        self.setup_window()
        self.build_ui()
        self._load_current_playlist()
        self.start_player_monitor()
        self.start_time_monitor()
    
    def setup_window(self):
        self.root.title("Music Minimal Player")
        self.root.geometry(f"{self.config['width']}x{self.config['height']}+{self.config['x']}+{self.config['y']}")
        self.root.configure(bg=self.config["bg_color"])
        
        if self.config["show_titlebar"]:
            self.root.overrideredirect(False)
        else:
            self.root.overrideredirect(True)
        
        self.root.attributes("-alpha", self.config["opacity"] / 100.0)
        
        if self.config["resizable"]:
            self.root.resizable(True, True)
        else:
            self.root.resizable(False, False)
        
        self.root.attributes("-topmost", 1 if self.config["pinned"] else 0)
        if self.config["pinned"]:
            self.root.lift()
        
        self.root.bind("<Configure>", self.on_window_configure)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def start_move(self, event):
        self.x = event.x
        self.y = event.y
    
    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
    
    def build_ui(self):
        bg_color = self.config["bg_color"]
        btn_color = self.config["btn_color"]
        font_color = self.config["font_color"]
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", 
                       fieldbackground=btn_color,
                       background=btn_color,
                       foreground=font_color,
                       arrowcolor=font_color,
                       borderwidth=0,
                       padding=0)
        style.map("TCombobox",
                 fieldbackground=[('readonly', btn_color)],
                 foreground=[('readonly', font_color)])
        
        main_frame = tk.Frame(self.root, bg=bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        self.prev_btn = self.create_button(main_frame, "◀", self.prev_song, btn_color, font_color)
        self.prev_btn.pack(side=tk.LEFT, padx=0)
        
        self.play_btn = self.create_button(main_frame, "▶", self.toggle_play, btn_color, font_color)
        self.play_btn.pack(side=tk.LEFT, padx=0)
        
        self.next_btn = self.create_button(main_frame, "▶", self.next_song, btn_color, font_color)
        self.next_btn.pack(side=tk.LEFT, padx=0)
        
        self.song_label = tk.Label(
            main_frame,
            text="No song playing",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 9),
            width=20,
            anchor="center"
        )
        self.song_label.pack(side=tk.LEFT, padx=0)
        
        self.time_label = tk.Label(
            main_frame,
            text="00:00",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 8),
            width=8,
            anchor="center"
        )
        self.time_label.pack(side=tk.LEFT, padx=0)
        
        self.volume_down_btn = self.create_button(main_frame, "-", self.volume_down, btn_color, font_color)
        self.volume_down_btn.pack(side=tk.LEFT, padx=0)
        
        self.volume_up_btn = self.create_button(main_frame, "+", self.volume_up, btn_color, font_color)
        self.volume_up_btn.pack(side=tk.LEFT, padx=0)
        
        self.drag_btn = self.create_drag_button(main_frame, "::", bg_color, font_color)
        self.drag_btn.pack(side=tk.LEFT, padx=0)
        
        self.options_btn = self.create_button(main_frame, "⚙", self.open_options, btn_color, font_color)
        self.options_btn.pack(side=tk.LEFT, padx=0)
        
        self.close_btn = self.create_button(main_frame, "×", self.on_close, bg_color, font_color)
        self.close_btn.pack(side=tk.LEFT, padx=0)
    
    def create_button(self, parent, text, command, bg_color, fg_color):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg_color,
            fg=fg_color,
            activebackground=bg_color,
            activeforeground=fg_color,
            relief=tk.FLAT,
            width=3,
            height=1,
            font=("Arial", 10, "bold"),
            bd=0
        )
        return btn
    
    def create_drag_button(self, parent, text, bg_color, fg_color):
        btn = tk.Button(
            parent,
            text=text,
            bg=bg_color,
            fg=fg_color,
            activebackground=bg_color,
            activeforeground=fg_color,
            relief=tk.FLAT,
            width=3,
            height=1,
            font=("Arial", 10, "bold"),
            bd=0,
            cursor="fleur"
        )
        btn.bind("<Button-1>", self.start_move)
        btn.bind("<B1-Motion>", self.do_move)
        return btn
    
    def on_window_configure(self, event):
        if event.widget == self.root:
            self.config["width"] = event.width
            self.config["height"] = event.height
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            self.config["x"] = x
            self.config["y"] = y
            save_config(self.config)
    
    def refresh_playlists(self):
        self.playlists = scan_playlists(self.music_root)
        self.playlist_names = sorted(self.playlists.keys())
        
        if self.playlist_names:
            if self.current_playlist_name not in self.playlist_names:
                self.current_playlist_name = self.playlist_names[0]
            self.current_playlist_files = self.playlists.get(self.current_playlist_name, [])
        else:
            self.current_playlist_name = None
            self.current_playlist_files = []
        
        self.current_index = 0
        self._load_current_playlist()
    
    def on_playlist_change(self, playlist_name):
        self.current_playlist_name = playlist_name
        self.config["playlist"] = self.current_playlist_name
        save_config(self.config)
        self.current_index = 0
        self._load_current_playlist()
    
    def on_shuffle_toggle(self):
        self.config["shuffle"] = self.config.get("shuffle", True)
        save_config(self.config)
    
    def volume_up(self):
        current_vol = self.config["volume"]
        new_vol = min(100, current_vol + 10)
        self.config["volume"] = new_vol
        if hasattr(self, 'player') and self.player is not None:
            self.player.audio_set_volume(new_vol)
        save_config(self.config)
    
    def volume_down(self):
        current_vol = self.config["volume"]
        new_vol = max(0, current_vol - 10)
        self.config["volume"] = new_vol
        if hasattr(self, 'player') and self.player is not None:
            self.player.audio_set_volume(new_vol)
        save_config(self.config)
    
    def toggle_pin(self):
        self.config["pinned"] = self.config.get("pinned", True)
        self.root.attributes("-topmost", 1 if self.config["pinned"] else 0)
        if self.config["pinned"]:
            self.root.lift()
        save_config(self.config)
    
    def _load_current_playlist(self):
        self.current_playlist_files = self.playlists.get(self.current_playlist_name, [])
        if not self.current_playlist_files:
            self.song_label.config(text="No files in playlist")
            return
        self.play_song_at_index(self.current_index)
    
    def play_song_at_index(self, idx):
        if not self.current_playlist_files:
            return
        if idx < 0 or idx >= len(self.current_playlist_files):
            return
        self.current_index = idx
        file_path = self.current_playlist_files[self.current_index]
        
        self.config["song_index"] = self.current_index
        save_config(self.config)
        
        title = os.path.basename(file_path)
        if vlc is not None and self.instance is not None:
            try:
                media = self.instance.media_new(file_path)
                media.parse()
                t = media.get_meta(vlc.Meta.Title)
                if t:
                    title = t
                self.player.set_media(media)
                self.player.play()
                self.player.audio_set_volume(self.config["volume"])
            except Exception as e:
                print(f"Error playing {file_path}: {e}")
                return
        
        self.song_label.config(text=title)
        self.play_btn.config(text="⏸")
    
    def open_options(self):
        options_window = tk.Toplevel(self.root)
        options_window.title("Configuration")
        options_window.geometry("380x540")
        options_window.configure(bg=self.config["bg_color"])
        options_window.transient(self.root)
        options_window.grab_set()
        options_window.resizable(False, True)
        
        bg_color = self.config["bg_color"]
        btn_color = self.config["btn_color"]
        font_color = self.config["font_color"]
        
        container_frame = tk.Frame(options_window, bg=bg_color)
        container_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(container_frame, bg=bg_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(container_frame, orient="vertical", command=canvas.yview, width=15)
        scrollable_frame = tk.Frame(canvas, bg=bg_color)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        def on_canvas_configure(event):
            canvas_width = event.width
            container_width = int(canvas_width * 0.9)
            canvas.create_window(canvas_width // 2, 0, window=scrollable_frame, anchor="n", width=container_width)
        
        canvas.bind("<Configure>", on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        def unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        main_container = tk.Frame(scrollable_frame, bg=bg_color, relief=tk.RAISED, bd=2)
        main_container.pack(expand=True, fill="both", padx=15, pady=15)
        
        tk.Label(main_container, text="Background Color:", bg=bg_color, fg=font_color).pack(anchor="w", padx=10, pady=(2, 0))
        bg_color_entry = tk.Entry(main_container, width=30)
        bg_color_entry.insert(0, bg_color)
        bg_color_entry.pack(anchor="w", padx=10, pady=(0, 2))
        
        tk.Label(main_container, text="Button Color:", bg=bg_color, fg=font_color).pack(anchor="w", padx=10, pady=(2, 0))
        btn_color_entry = tk.Entry(main_container, width=30)
        btn_color_entry.insert(0, btn_color)
        btn_color_entry.pack(anchor="w", padx=10, pady=(0, 2))
        
        tk.Label(main_container, text="Font Color:", bg=bg_color, fg=font_color).pack(anchor="w", padx=10, pady=(2, 0))
        font_color_entry = tk.Entry(main_container, width=30)
        font_color_entry.insert(0, font_color)
        font_color_entry.pack(anchor="w", padx=10, pady=(0, 8))
        
        shuffle_var = tk.BooleanVar(value=self.config["shuffle"])
        shuffle_check = tk.Checkbutton(main_container, variable=shuffle_var,
                                      text="Shuffle Playback",
                                      bg=bg_color, fg=font_color,
                                      selectcolor=btn_color,
                                      activebackground=bg_color, activeforeground=font_color)
        shuffle_check.pack(anchor="w", padx=10, pady=(0, 2))
        
        pinned_var = tk.BooleanVar(value=self.config["pinned"])
        pinned_check = tk.Checkbutton(main_container, variable=pinned_var,
                                      text="Always on Top",
                                      bg=bg_color, fg=font_color,
                                      selectcolor=btn_color,
                                      activebackground=bg_color, activeforeground=font_color)
        pinned_check.pack(anchor="w", padx=10, pady=(0, 2))
        
        show_titlebar_var = tk.BooleanVar(value=self.config["show_titlebar"])
        show_titlebar_check = tk.Checkbutton(main_container, variable=show_titlebar_var,
                                            text="Show Titlebar & Border",
                                            bg=bg_color, fg=font_color,
                                            selectcolor=btn_color,
                                            activebackground=bg_color, activeforeground=font_color)
        show_titlebar_check.pack(anchor="w", padx=10, pady=(0, 2))
        
        resizable_var = tk.BooleanVar(value=self.config["resizable"])
        resizable_check = tk.Checkbutton(main_container, variable=resizable_var,
                                         text="Resizable Window",
                                         bg=bg_color, fg=font_color,
                                         selectcolor=btn_color,
                                         activebackground=bg_color, activeforeground=font_color)
        resizable_check.pack(anchor="w", padx=10, pady=(0, 8))
        
        tk.Label(main_container, text="Opacity (%):", bg=bg_color, fg=font_color).pack(anchor="w", padx=10, pady=(2, 0))
        opacity_scale = tk.Scale(main_container, from_=30, to=100, orient=tk.HORIZONTAL,
                                bg=bg_color, fg=font_color,
                                highlightthickness=0,
                                activebackground=bg_color, troughcolor=btn_color)
        opacity_scale.set(self.config["opacity"])
        opacity_scale.pack(anchor="w", padx=10, pady=(0, 8))
        
        tk.Label(main_container, text="Playlist:", bg=bg_color, fg=font_color).pack(anchor="w", padx=10, pady=(2, 0))
        playlist_var = tk.StringVar(value=self.current_playlist_name if self.current_playlist_name else "")
        playlist_combo = ttk.Combobox(main_container, textvariable=playlist_var,
                                     values=self.playlist_names,
                                     state="readonly",
                                     width=30)
        playlist_combo.bind("<<ComboboxSelected>>", lambda e: self.on_playlist_change(playlist_var.get()))
        playlist_combo.pack(anchor="w", padx=10, pady=(0, 2))
        
        refresh_btn = tk.Button(main_container, text="Refresh Playlists",
                               bg=btn_color, fg=font_color, relief=tk.FLAT,
                               command=self.refresh_playlists)
        refresh_btn.pack(anchor="w", padx=10, pady=(0, 8))
        
        button_frame = tk.Frame(main_container, bg=bg_color)
        button_frame.pack(pady=(0, 10))
        
        def save_colors():
            self.config["bg_color"] = bg_color_entry.get()
            self.config["btn_color"] = btn_color_entry.get()
            self.config["font_color"] = font_color_entry.get()
            self.config["shuffle"] = shuffle_var.get()
            self.config["pinned"] = pinned_var.get()
            self.config["show_titlebar"] = show_titlebar_var.get()
            self.config["opacity"] = opacity_scale.get()
            self.config["resizable"] = resizable_var.get()
            self.root.attributes("-topmost", 1 if self.config["pinned"] else 0)
            if self.config["pinned"]:
                self.root.lift()
            save_config(self.config)
            self.apply_settings()
            options_window.destroy()
        
        def reset_to_default():
            self.config["bg_color"] = "#000000"
            self.config["btn_color"] = "#333333"
            self.config["font_color"] = "#FFFFFF"
            self.config["shuffle"] = True
            self.config["pinned"] = True
            self.config["show_titlebar"] = True
            self.config["opacity"] = 100
            self.config["resizable"] = True
            bg_color_entry.delete(0, tk.END)
            bg_color_entry.insert(0, self.config["bg_color"])
            btn_color_entry.delete(0, tk.END)
            btn_color_entry.insert(0, self.config["btn_color"])
            font_color_entry.delete(0, tk.END)
            font_color_entry.insert(0, self.config["font_color"])
            shuffle_var.set(self.config["shuffle"])
            pinned_var.set(self.config["pinned"])
            show_titlebar_var.set(self.config["show_titlebar"])
            opacity_scale.set(self.config["opacity"])
            resizable_var.set(self.config["resizable"])
            self.root.attributes("-topmost", 1 if self.config["pinned"] else 0)
            if self.config["pinned"]:
                self.root.lift()
            save_config(self.config)
            self.apply_settings()
        
        reset_btn = tk.Button(button_frame, text="Reset", command=reset_to_default,
                            bg=btn_color, fg=font_color, relief=tk.RAISED, bd=2)
        reset_btn.pack(side=tk.LEFT, padx=5)
        
        save_btn = tk.Button(button_frame, text="Save", command=save_colors,
                           bg=btn_color, fg=font_color, relief=tk.RAISED, bd=2)
        save_btn.pack(side=tk.LEFT, padx=5)
    
    def apply_colors(self):
        bg_color = self.config["bg_color"]
        btn_color = self.config["btn_color"]
        font_color = self.config["font_color"]
        
        self.root.configure(bg=bg_color)
        self.song_label.configure(bg=bg_color, fg=font_color)
        self.time_label.configure(bg=bg_color, fg=font_color)
        self.play_btn.configure(bg=btn_color, fg=font_color)
        self.prev_btn.configure(bg=btn_color, fg=font_color)
        self.next_btn.configure(bg=btn_color, fg=font_color)
        self.options_btn.configure(bg=btn_color, fg=font_color)
        self.volume_up_btn.configure(bg=btn_color, fg=font_color)
        self.volume_down_btn.configure(bg=btn_color, fg=font_color)
        self.drag_btn.configure(bg=bg_color, fg=font_color)
        self.close_btn.configure(bg=bg_color, fg=font_color)
    
    def apply_settings(self):
        bg_color = self.config["bg_color"]
        btn_color = self.config["btn_color"]
        font_color = self.config["font_color"]
        
        self.root.configure(bg=bg_color)
        self.song_label.configure(bg=bg_color, fg=font_color)
        self.time_label.configure(bg=bg_color, fg=font_color)
        self.play_btn.configure(bg=btn_color, fg=font_color)
        self.prev_btn.configure(bg=btn_color, fg=font_color)
        self.next_btn.configure(bg=btn_color, fg=font_color)
        self.options_btn.configure(bg=btn_color, fg=font_color)
        self.volume_up_btn.configure(bg=btn_color, fg=font_color)
        self.volume_down_btn.configure(bg=btn_color, fg=font_color)
        self.drag_btn.configure(bg=btn_color, fg=font_color)
        self.close_btn.configure(bg=btn_color, fg=font_color)
        
        if self.config["show_titlebar"]:
            self.root.overrideredirect(False)
        else:
            self.root.overrideredirect(True)
        
        self.root.attributes("-alpha", self.config["opacity"] / 100.0)
        
        if self.config["resizable"]:
            self.root.resizable(True, True)
        else:
            self.root.resizable(False, False)
        
        self.root.attributes("-topmost", 1 if self.config["pinned"] else 0)
        if self.config["pinned"]:
            self.root.lift()
    
    def toggle_play(self):
        if self.player is not None and self.player.is_playing():
            self.player.pause()
            self.play_btn.config(text="▶")
        else:
            if self.player is not None:
                self.player.play()
                self.play_btn.config(text="⏸")
    
    def next_song(self):
        if not self.current_playlist_files:
            return
        if self.config["shuffle"]:
            self.current_index = random.randrange(len(self.current_playlist_files))
        else:
            self.current_index = (self.current_index + 1) % len(self.current_playlist_files)
        self.play_song_at_index(self.current_index)
    
    def prev_song(self):
        if not self.current_playlist_files:
            return
        if self.config["shuffle"]:
            self.current_index = random.randrange(len(self.current_playlist_files))
        else:
            self.current_index = (self.current_index - 1) % len(self.current_playlist_files)
        self.play_song_at_index(self.current_index)
    
    def start_player_monitor(self):
        if self.player is None or self.player_monitor_running:
            return
        self.player_monitor_running = True
        self.player_monitor_thread = threading.Thread(target=self.monitor_player, daemon=True)
        self.player_monitor_thread.start()
    
    def start_time_monitor(self):
        if self.player is None or self.time_monitor_running:
            return
        self.time_monitor_running = True
        self.time_monitor_thread = threading.Thread(target=self.monitor_time, daemon=True)
        self.time_monitor_thread.start()
    
    def monitor_player(self):
        while self.player_monitor_running:
            try:
                if self.player is not None and self.player.is_playing():
                    time.sleep(0.5)
                else:
                    time.sleep(0.5)
                    if self.player is not None and not self.player.is_playing() and self.current_playlist_files:
                        self.check_song_ended()
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(1)
    
    def check_song_ended(self):
        try:
            if self.player is not None and self.current_playlist_files:
                state = self.player.get_state()
                if state == vlc.State.Ended or state == vlc.State.NothingSpecial:
                    threading.Thread(target=self.next_song, daemon=True).start()
        except Exception as e:
            print(f"Error checking song end: {e}")
    
    def monitor_time(self):
        while self.time_monitor_running:
            try:
                if self.player is not None and self.current_playlist_files:
                    self.update_time_display()
                time.sleep(1)
            except Exception as e:
                print(f"Time monitor error: {e}")
                time.sleep(1)
    
    def update_time_display(self):
        try:
            if self.player is not None:
                current_time = self.player.get_time()
                time_str = self.format_time(current_time)
                self.time_label.config(text=time_str)
        except Exception as e:
            print(f"Error updating time display: {e}")
    
    def format_time(self, milliseconds):
        total_seconds = milliseconds // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def on_close(self, event=None):
        self.player_monitor_running = False
        self.time_monitor_running = False
        self.config["shuffle"] = self.config.get("shuffle", True)
        self.config["pinned"] = self.config.get("pinned", True)
        self.config["x"] = self.root.winfo_x()
        self.config["y"] = self.root.winfo_y()
        self.config["width"] = self.root.winfo_width()
        self.config["height"] = self.root.winfo_height()
        save_config(self.config)
        try:
            if self.player is not None:
                self.player.stop()
        except Exception:
            pass
        self.root.destroy()

def main():
    config = load_config()
    root = tk.Tk()
    root.title("Music Minimal Player")
    root.geometry(f"{config['width']}x{config['height']}+{config['x']}+{config['y']}")
    root.configure(bg=config["bg_color"])
    root.attributes("-topmost", config["pinned"])
    
    if config["show_titlebar"]:
        root.overrideredirect(False)
    else:
        root.overrideredirect(True)
    
    root.attributes("-alpha", config["opacity"] / 100.0)
    
    if config["resizable"]:
        root.resizable(True, True)
    else:
        root.resizable(False, False)
    
    app = MusicMinimalPlayer(root)
    
    root.mainloop()

if __name__ == "__main__":
    main()
