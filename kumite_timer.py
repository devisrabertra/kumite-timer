import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
import cv2
from PIL import Image, ImageTk, ImageDraw, ImageFont
import numpy as np
import threading
import os
from datetime import datetime
import json
import queue

class JudoTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("Kumite Timer - Operator")
        self.root.geometry("1400x800")
        self.root.configure(bg="#2c3e50")
        
        # Variabel timer
        self.running = False
        self.paused = False
        self.match_time = 240
        self.remaining_time = self.match_time
        self.time_up = False
        self.blink_state = False
        
        self.last_update_time = 0
        self.update_interval = 16
        self.timer_update_id = None
        
        self.last_camera_update = 0
        self.camera_update_interval = 33
        
        # Variabel skor
        self.aka_score = 0
        self.ao_score = 0
        self.aka_senshu = False
        self.ao_senshu = False
        
        # Variabel nama dan kontingen
        self.aka_name = "AKA"
        self.aka_contingent = "-"
        self.ao_name = "AO"
        self.ao_contingent = "-"
        
        # Dictionary untuk status wasit
        self.ao_judges = {"CH1": False, "CH2": False, "CH3": False, "HC": False, "H": False}
        self.aka_judges = {"CH1": False, "CH2": False, "CH3": False, "HC": False, "H": False}
        
        # Window display untuk penonton
        self.display_window = None
        self.display_fullscreen = False
        
        # Variabel untuk kamera dan perekaman
        self.camera = None
        self.camera_running = False
        self.current_frame = None
        self.camera_window = None
        self.camera_update_id = None
        
        # Variabel perekaman video utama
        self.recording = False
        self.video_writer = None
        self.record_start_time = 0
        self.video_files = []
        self.recording_thread = None
        self.frame_capture_thread = None
        self.video_folder = "video_recordings"
        
        # Variabel untuk perekaman thread-safe
        self.recording_queue = queue.Queue(maxsize=60)
        self.latest_frame = None
        self.recording_fps = 30
        self.frame_interval = 1.0 / self.recording_fps
        self.last_record_time = 0
        
        # ===== VARIABEL UNTUK VAR - DIPERBAIKI UNTUK REKAMAN BERULANG =====
        self.var_recording = False
        self.var_video_writer = None
        self.var_recording_thread = None
        self.var_recording_queue = queue.Queue(maxsize=60)
        self.var_record_start_time = 0
        self.var_video_files = []
        self.var_folder = os.path.join(self.video_folder, "var_recordings")
        self.var_auto_stop_id = None  # ID untuk timer auto-stop VAR
        self.var_counter = 0  # Counter untuk menghitung jumlah VAR
        
        # Variabel untuk tracking segmen video
        self.current_video_segment = None
        self.current_video_file = None
        self.current_video_timestamp = None
        self.current_video_duration = None
        self.video_segments = []
        
        # Variabel untuk tampilan wasit di display
        self.display_aka_judge_labels = {}
        self.display_ao_judge_labels = {}
        
        # Variabel khusus untuk timer display
        self.display_last_update = 0
        self.display_update_interval = 16
        self.display_update_id = None
        
        # Variabel untuk durasi timer di kamera
        self.camera_timer_label = None
        self.camera_timer_frame = None
        self.var_button = None  # Reference ke tombol VAR
        
        # Setup folder untuk penyimpanan video
        self.setup_video_folder()
        
        # Setup GUI
        self.setup_gui()
        
    def setup_video_folder(self):
        """Setup folder untuk menyimpan video"""
        if not os.path.exists(self.video_folder):
            os.makedirs(self.video_folder)
        
        # Setup folder khusus VAR
        if not os.path.exists(self.var_folder):
            os.makedirs(self.var_folder)
        
        # Buat file metadata untuk menyimpan informasi video
        self.metadata_file = os.path.join(self.video_folder, "video_metadata.json")
        self.var_metadata_file = os.path.join(self.var_folder, "var_metadata.json")
        
        if not os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'w') as f:
                json.dump([], f)
        
        if not os.path.exists(self.var_metadata_file):
            with open(self.var_metadata_file, 'w') as f:
                json.dump([], f)
    
    def setup_gui(self):
        # Main container dengan grid yang fleksibel
        main_frame = tk.Frame(self.root, bg="#2c3e50")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configure grid weights
        main_frame.grid_columnconfigure(0, weight=2)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # ===== LEFT PANEL =====
        left_panel = tk.Frame(main_frame, bg="#2c3e50")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Header Frame
        header_frame = tk.Frame(left_panel, bg="#2c3e50", height=60)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="KUMITE SCOREBOARD - OPERATOR", 
                              font=("Arial", 22, "bold"), 
                              fg="white", bg="#2c3e50")
        title_label.pack(expand=True)
        
        # ===== PENGATUR WAKTU =====
        time_setting_frame = tk.Frame(header_frame, bg="#2c3e50")
        time_setting_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(time_setting_frame, text="Set Waktu: ", 
                font=("Arial", 10), 
                fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Label(time_setting_frame, text="M:", 
                font=("Arial", 10), 
                fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=(5, 2))
        
        self.minute_var = tk.StringVar(value="4")
        minute_spinbox = tk.Spinbox(time_setting_frame, from_=0, to=30, textvariable=self.minute_var,
                                   width=4, font=("Arial", 10), bg="white", fg="black",
                                   justify=tk.CENTER)
        minute_spinbox.pack(side=tk.LEFT, padx=2)
        
        tk.Label(time_setting_frame, text="S:", 
                font=("Arial", 10), 
                fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=(10, 2))
        
        self.second_var = tk.StringVar(value="0")
        second_spinbox = tk.Spinbox(time_setting_frame, from_=0, to=59, textvariable=self.second_var,
                                   width=4, font=("Arial", 10), bg="white", fg="black",
                                   justify=tk.CENTER)
        second_spinbox.pack(side=tk.LEFT, padx=2)
        
        set_time_button = tk.Button(time_setting_frame, text="SET", 
                                   command=self.set_match_time,
                                   bg="#3498db", fg="white", 
                                   font=("Arial", 9, "bold"),
                                   width=6, height=1)
        set_time_button.pack(side=tk.LEFT, padx=(15, 5))
        
        self.current_time_label = tk.Label(time_setting_frame, 
                                          text="(04:00)", 
                                          font=("Arial", 10), 
                                          fg="#2ecc71", bg="#2c3e50")
        self.current_time_label.pack(side=tk.LEFT, padx=5)
        
        # ===== MAIN CONTENT FRAME =====
        content_frame = tk.Frame(left_panel, bg="#2c3e50")
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=2)
        content_frame.grid_columnconfigure(2, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=0)
        content_frame.grid_rowconfigure(2, weight=0)
        
        # ===== AO PANEL =====
        ao_frame = tk.Frame(content_frame, bg="#3498db", relief=tk.RAISED, bd=3)
        ao_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        
        ao_header = tk.Frame(ao_frame, bg="#2980b9", height=80)
        ao_header.pack(fill=tk.X)
        ao_header.pack_propagate(False)
        
        self.ao_name_var = tk.StringVar(value="AO")
        self.ao_name_label = tk.Label(ao_header, textvariable=self.ao_name_var, 
                                     font=("Arial", 20, "bold"), 
                                     fg="white", bg="#2980b9")
        self.ao_name_label.pack(expand=True, pady=(5, 0))
        
        self.ao_contingent_var = tk.StringVar(value="-")
        self.ao_contingent_label = tk.Label(ao_header, textvariable=self.ao_contingent_var, 
                                           font=("Arial", 14), 
                                           fg="white", bg="#2980b9")
        self.ao_contingent_label.pack(expand=True, pady=(0, 5))
        
        ao_edit_button = tk.Button(ao_header, text="✎", 
                                  font=("Arial", 10, "bold"),
                                  bg="#1abc9c", fg="white",
                                  width=3, height=1,
                                  command=lambda: self.edit_player_info('ao'))
        ao_edit_button.place(x=10, y=10)
        
        ao_score_frame = tk.Frame(ao_frame, bg="#3498db")
        ao_score_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(ao_score_frame, text="SCORE", 
                font=("Arial", 20, "bold"), 
                fg="white", bg="#3498db").pack()
        
        self.ao_score_label = tk.Label(ao_score_frame, text="0", 
                                      font=("Arial", 72, "bold"), 
                                      fg="white", bg="#3498db")
        self.ao_score_label.pack(expand=True)
        
        ao_senshu_frame = tk.Frame(ao_frame, bg="#3498db")
        ao_senshu_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.ao_senshu_var = tk.StringVar(value="")
        tk.Label(ao_senshu_frame, textvariable=self.ao_senshu_var,
                font=("Arial", 18, "bold"), 
                fg="yellow", bg="#3498db").pack()
        
        # ===== CENTER PANEL =====
        center_frame = tk.Frame(content_frame, bg="#2c3e50")
        center_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        timer_frame = tk.Frame(center_frame, bg="#2c3e50")
        timer_frame.pack(pady=(20, 10))
        
        self.timer_label = tk.Label(timer_frame, text="04:00:00",
                                   font=("Arial", 56, "bold"),
                                   fg="#2ecc71", bg="#2c3e50")
        self.timer_label.pack()
        
        self.status_label = tk.Label(center_frame, text="HAJIME",
                                    font=("Arial", 20, "bold"),
                                    fg="white", bg="#2c3e50")
        self.status_label.pack()
        
        button_frame = tk.Frame(center_frame, bg="#2c3e50")
        button_frame.pack(pady=20)
        
        top_button_frame = tk.Frame(button_frame, bg="#2c3e50")
        top_button_frame.pack()
        
        self.start_button = tk.Button(top_button_frame, text="START", 
                                     font=("Arial", 14, "bold"),
                                     bg="#27ae60", fg="white",
                                     width=10, height=1,
                                     command=self.start_timer)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = tk.Button(top_button_frame, text="PAUSE", 
                                     font=("Arial", 14, "bold"),
                                     bg="#f39c12", fg="white",
                                     width=10, height=1,
                                     command=self.pause_timer)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.continue_button = tk.Button(top_button_frame, text="CONTINUE", 
                                        font=("Arial", 14, "bold"),
                                        bg="#3498db", fg="white",
                                        width=10, height=1,
                                        command=self.continue_timer,
                                        state=tk.DISABLED)
        self.continue_button.pack(side=tk.LEFT, padx=5)
        
        bottom_button_frame = tk.Frame(button_frame, bg="#2c3e50")
        bottom_button_frame.pack(pady=(10, 0))
        
        self.reset_button = tk.Button(bottom_button_frame, text="RESET", 
                                     font=("Arial", 14, "bold"),
                                     bg="#e74c3c", fg="white",
                                     width=32, height=1,
                                     command=self.reset_match)
        self.reset_button.pack()
        
        display_button_frame = tk.Frame(center_frame, bg="#2c3e50")
        display_button_frame.pack(pady=10)
        
        tk.Button(display_button_frame, text="SHOW DISPLAY", 
                 font=("Arial", 12, "bold"),
                 bg="#9b59b6", fg="white",
                 width=15, height=1,
                 command=self.show_display_window).pack()
        
        self.recording_status_frame = tk.Frame(center_frame, bg="#2c3e50")
        self.recording_status_frame.pack(pady=5)
        
        self.recording_status_label = tk.Label(self.recording_status_frame, 
                                              text="● Perekaman: Tidak Aktif",
                                              font=("Arial", 10),
                                              fg="#e74c3c", bg="#2c3e50")
        self.recording_status_label.pack()
        
        self.var_status_frame = tk.Frame(center_frame, bg="#2c3e50")
        self.var_status_frame.pack(pady=2)
        
        self.var_status_label = tk.Label(self.var_status_frame, 
                                        text="● VAR: Tidak Aktif",
                                        font=("Arial", 10),
                                        fg="#7f8c8d", bg="#2c3e50")
        self.var_status_label.pack()
        
        # ===== AKA PANEL =====
        aka_frame = tk.Frame(content_frame, bg="#e74c3c", relief=tk.RAISED, bd=3)
        aka_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0), pady=5)
        
        aka_header = tk.Frame(aka_frame, bg="#c0392b", height=80)
        aka_header.pack(fill=tk.X)
        aka_header.pack_propagate(False)
        
        self.aka_name_var = tk.StringVar(value="AKA")
        self.aka_name_label = tk.Label(aka_header, textvariable=self.aka_name_var, 
                                      font=("Arial", 20, "bold"), 
                                      fg="white", bg="#c0392b")
        self.aka_name_label.pack(expand=True, pady=(5, 0))
        
        self.aka_contingent_var = tk.StringVar(value="-")
        self.aka_contingent_label = tk.Label(aka_header, textvariable=self.aka_contingent_var, 
                                            font=("Arial", 14), 
                                            fg="white", bg="#c0392b")
        self.aka_contingent_label.pack(expand=True, pady=(0, 5))
        
        aka_edit_button = tk.Button(aka_header, text="✎", 
                                   font=("Arial", 10, "bold"),
                                   bg="#1abc9c", fg="white",
                                   width=3, height=1,
                                   command=lambda: self.edit_player_info('aka'))
        aka_edit_button.place(x=10, y=10)
        
        aka_score_frame = tk.Frame(aka_frame, bg="#e74c3c")
        aka_score_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(aka_score_frame, text="SCORE", 
                font=("Arial", 20, "bold"), 
                fg="white", bg="#e74c3c").pack()
        
        self.aka_score_label = tk.Label(aka_score_frame, text="0", 
                                       font=("Arial", 72, "bold"), 
                                       fg="white", bg="#e74c3c")
        self.aka_score_label.pack(expand=True)
        
        aka_senshu_frame = tk.Frame(aka_frame, bg="#e74c3c")
        aka_senshu_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.aka_senshu_var = tk.StringVar(value="")
        tk.Label(aka_senshu_frame, textvariable=self.aka_senshu_var,
                font=("Arial", 18, "bold"), 
                fg="yellow", bg="#e74c3c").pack()
        
        # ===== JUDGES CONTROL =====
        judges_frame = tk.Frame(content_frame, bg="#2c3e50")
        judges_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=(10, 5))
        
        tk.Label(judges_frame, text="JUDGES CONTROL", 
                font=("Arial", 16, "bold"),
                fg="white", bg="#2c3e50").pack(pady=(0, 10))
        
        judges_control_frame = tk.Frame(judges_frame, bg="#2c3e50")
        judges_control_frame.pack()
        
        # AO Judges
        ao_judges_frame = tk.Frame(judges_control_frame, bg="#2c3e50")
        ao_judges_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(ao_judges_frame, text="AO Judges", 
                font=("Arial", 12, "bold"),
                fg="white", bg="#2c3e50").pack()
        
        ao_judges_icons = tk.Frame(ao_judges_frame, bg="#2c3e50")
        ao_judges_icons.pack(pady=5)
        
        self.ao_judge_labels = {}
        judge_positions = ["CH1", "CH2", "CH3", "HC", "H"]
        
        for judge in judge_positions:
            frame = tk.Frame(ao_judges_icons, bg="#2c3e50")
            frame.pack(side=tk.LEFT, padx=3)
            
            label = tk.Label(frame, text=judge,
                           font=("Arial", 12, "bold"),
                           fg="white", bg="#34495e",
                           width=4, height=1,
                           relief=tk.RAISED, bd=2)
            label.pack()
            label.bind("<Button-1>", lambda e, j=judge: self.toggle_judge('ao', j))
            self.ao_judge_labels[judge] = label
        
        tk.Frame(judges_control_frame, bg="#7f8c8d", width=2, height=40).pack(side=tk.LEFT, padx=20)
        
        # AKA Judges
        aka_judges_frame = tk.Frame(judges_control_frame, bg="#2c3e50")
        aka_judges_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(aka_judges_frame, text="AKA Judges", 
                font=("Arial", 12, "bold"),
                fg="white", bg="#2c3e50").pack()
        
        aka_judges_icons = tk.Frame(aka_judges_frame, bg="#2c3e50")
        aka_judges_icons.pack(pady=5)
        
        self.aka_judge_labels = {}
        
        for judge in judge_positions:
            frame = tk.Frame(aka_judges_icons, bg="#2c3e50")
            frame.pack(side=tk.LEFT, padx=3)
            
            label = tk.Label(frame, text=judge,
                           font=("Arial", 12, "bold"),
                           fg="white", bg="#34495e",
                           width=4, height=1,
                           relief=tk.RAISED, bd=2)
            label.pack()
            label.bind("<Button-1>", lambda e, j=judge: self.toggle_judge('aka', j))
            self.aka_judge_labels[judge] = label
        
        tk.Button(judges_frame, text="Reset All Judges", 
                 bg="#9b59b6", fg="white",
                 font=("Arial", 11, "bold"),
                 command=self.reset_all_judges).pack(pady=10)
        
        # ===== SCORE CONTROL =====
        score_control_frame = tk.Frame(content_frame, bg="#2c3e50")
        score_control_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=(5, 0))
        
        # AO Score Controls
        ao_controls_frame = tk.Frame(score_control_frame, bg="#2c3e50")
        ao_controls_frame.pack(side=tk.LEFT, padx=20, pady=10)
        
        tk.Label(ao_controls_frame, text="AO CONTROLS", 
                font=("Arial", 14, "bold"),
                fg="white", bg="#2c3e50").pack(pady=(0, 10))
        
        ao_buttons_frame = tk.Frame(ao_controls_frame, bg="#2c3e50")
        ao_buttons_frame.pack()
        
        # Baris 1: YUKO
        yuko_ao_frame = tk.Frame(ao_buttons_frame, bg="#2c3e50")
        yuko_ao_frame.grid(row=0, column=0, columnspan=3, padx=3, pady=3)
        
        tk.Button(yuko_ao_frame, text="YUKO +1", bg="#2980b9", fg="white",
                 font=("Arial", 10, "bold"), width=8,
                 command=lambda: self.adjust_score('ao', 1)).pack(side=tk.LEFT, padx=2)
        
        tk.Button(yuko_ao_frame, text="YUKO -1", bg="#34495e", fg="white",
                 font=("Arial", 10, "bold"), width=8,
                 command=lambda: self.adjust_score('ao', -1)).pack(side=tk.LEFT, padx=2)
        
        tk.Label(yuko_ao_frame, text="(1)", 
                font=("Arial", 10, "bold"),
                fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=5)
        
        # Baris 2: WAZA-ARI
        wazaari_ao_frame = tk.Frame(ao_buttons_frame, bg="#2c3e50")
        wazaari_ao_frame.grid(row=1, column=0, columnspan=3, padx=3, pady=3)
        
        tk.Button(wazaari_ao_frame, text="WAZA-ARI +2", bg="#2980b9", fg="white",
                 font=("Arial", 10, "bold"), width=10,
                 command=lambda: self.adjust_score('ao', 2)).pack(side=tk.LEFT, padx=2)
        
        tk.Button(wazaari_ao_frame, text="WAZA-ARI -2", bg="#34495e", fg="white",
                 font=("Arial", 10, "bold"), width=10,
                 command=lambda: self.adjust_score('ao', -2)).pack(side=tk.LEFT, padx=2)
        
        tk.Label(wazaari_ao_frame, text="(2)", 
                font=("Arial", 10, "bold"),
                fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=5)
        
        # Baris 3: IPPON
        ippon_ao_frame = tk.Frame(ao_buttons_frame, bg="#2c3e50")
        ippon_ao_frame.grid(row=2, column=0, columnspan=3, padx=3, pady=3)
        
        tk.Button(ippon_ao_frame, text="IPPON +3", bg="#2980b9", fg="white",
                 font=("Arial", 10, "bold"), width=8,
                 command=lambda: self.adjust_score('ao', 3)).pack(side=tk.LEFT, padx=2)
        
        tk.Button(ippon_ao_frame, text="IPPON -3", bg="#34495e", fg="white",
                 font=("Arial", 10, "bold"), width=8,
                 command=lambda: self.adjust_score('ao', -3)).pack(side=tk.LEFT, padx=2)
        
        tk.Label(ippon_ao_frame, text="(3)", 
                font=("Arial", 10, "bold"),
                fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=5)
        
        # Baris 4: SENSHU
        tk.Button(ao_buttons_frame, text="SENSHU", bg="#2980b9", fg="white",
                 font=("Arial", 11, "bold"),
                 command=lambda: self.toggle_senshu('ao')).grid(row=3, column=0, columnspan=3, pady=10, sticky=tk.EW)
        
        tk.Frame(score_control_frame, bg="#7f8c8d", width=2, height=150).pack(side=tk.LEFT, padx=20)
        
        # AKA Score Controls
        aka_controls_frame = tk.Frame(score_control_frame, bg="#2c3e50")
        aka_controls_frame.pack(side=tk.RIGHT, padx=20, pady=10)
        
        tk.Label(aka_controls_frame, text="AKA CONTROLS", 
                font=("Arial", 14, "bold"),
                fg="white", bg="#2c3e50").pack(pady=(0, 10))
        
        aka_buttons_frame = tk.Frame(aka_controls_frame, bg="#2c3e50")
        aka_buttons_frame.pack()
        
        # Baris 1: YUKO
        yuko_aka_frame = tk.Frame(aka_buttons_frame, bg="#2c3e50")
        yuko_aka_frame.grid(row=0, column=0, columnspan=3, padx=3, pady=3)
        
        tk.Button(yuko_aka_frame, text="YUKO +1", bg="#c0392b", fg="white",
                 font=("Arial", 10, "bold"), width=8,
                 command=lambda: self.adjust_score('aka', 1)).pack(side=tk.LEFT, padx=2)
        
        tk.Button(yuko_aka_frame, text="YUKO -1", bg="#34495e", fg="white",
                 font=("Arial", 10, "bold"), width=8,
                 command=lambda: self.adjust_score('aka', -1)).pack(side=tk.LEFT, padx=2)
        
        tk.Label(yuko_aka_frame, text="(1)", 
                font=("Arial", 10, "bold"),
                fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=5)
        
        # Baris 2: WAZA-ARI
        wazaari_aka_frame = tk.Frame(aka_buttons_frame, bg="#2c3e50")
        wazaari_aka_frame.grid(row=1, column=0, columnspan=3, padx=3, pady=3)
        
        tk.Button(wazaari_aka_frame, text="WAZA-ARI +2", bg="#c0392b", fg="white",
                 font=("Arial", 10, "bold"), width=10,
                 command=lambda: self.adjust_score('aka', 2)).pack(side=tk.LEFT, padx=2)
        
        tk.Button(wazaari_aka_frame, text="WAZA-ARI -2", bg="#34495e", fg="white",
                 font=("Arial", 10, "bold"), width=10,
                 command=lambda: self.adjust_score('aka', -2)).pack(side=tk.LEFT, padx=2)
        
        tk.Label(wazaari_aka_frame, text="(2)", 
                font=("Arial", 10, "bold"),
                fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=5)
        
        # Baris 3: IPPON
        ippon_aka_frame = tk.Frame(aka_buttons_frame, bg="#2c3e50")
        ippon_aka_frame.grid(row=2, column=0, columnspan=3, padx=3, pady=3)
        
        tk.Button(ippon_aka_frame, text="IPPON +3", bg="#c0392b", fg="white",
                 font=("Arial", 10, "bold"), width=8,
                 command=lambda: self.adjust_score('aka', 3)).pack(side=tk.LEFT, padx=2)
        
        tk.Button(ippon_aka_frame, text="IPPON -3", bg="#34495e", fg="white",
                 font=("Arial", 10, "bold"), width=8,
                 command=lambda: self.adjust_score('aka', -3)).pack(side=tk.LEFT, padx=2)
        
        tk.Label(ippon_aka_frame, text="(3)", 
                font=("Arial", 10, "bold"),
                fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=5)
        
        # Baris 4: SENSHU
        tk.Button(aka_buttons_frame, text="SENSHU", bg="#c0392b", fg="white",
                 font=("Arial", 11, "bold"),
                 command=lambda: self.toggle_senshu('aka')).grid(row=3, column=0, columnspan=3, pady=10, sticky=tk.EW)
        
        # ===== RIGHT PANEL (Camera) =====
        right_panel = tk.Frame(main_frame, bg="#2c3e50")
        right_panel.grid(row=0, column=1, sticky="nsew")
        
        # Camera Header
        camera_header = tk.Frame(right_panel, bg="#34495e", height=150)
        camera_header.pack(fill=tk.X)
        camera_header.pack_propagate(False)
        
        tk.Label(camera_header, text="LIVE CAMERA", 
                font=("Arial", 18, "bold"), 
                fg="white", bg="#34495e").pack(pady=(10, 5))
        
        # PENGATUR WAKTU DI KAMERA
        camera_time_frame = tk.Frame(camera_header, bg="#34495e")
        camera_time_frame.pack(pady=(0, 5))
        
        tk.Label(camera_time_frame, text="Set Waktu:", 
                font=("Arial", 10), 
                fg="white", bg="#34495e").pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Label(camera_time_frame, text="M:", 
                font=("Arial", 10), 
                fg="white", bg="#34495e").pack(side=tk.LEFT, padx=(0, 2))
        
        self.cam_minute_var = tk.StringVar(value="4")
        cam_minute_spinbox = tk.Spinbox(camera_time_frame, from_=0, to=30, textvariable=self.cam_minute_var,
                                       width=4, font=("Arial", 10), bg="white", fg="black",
                                       justify=tk.CENTER)
        cam_minute_spinbox.pack(side=tk.LEFT, padx=2)
        
        tk.Label(camera_time_frame, text="S:", 
                font=("Arial", 10), 
                fg="white", bg="#34495e").pack(side=tk.LEFT, padx=(5, 2))
        
        self.cam_second_var = tk.StringVar(value="0")
        cam_second_spinbox = tk.Spinbox(camera_time_frame, from_=0, to=59, textvariable=self.cam_second_var,
                                       width=4, font=("Arial", 10), bg="white", fg="black",
                                       justify=tk.CENTER)
        cam_second_spinbox.pack(side=tk.LEFT, padx=2)
        
        cam_set_time_button = tk.Button(camera_time_frame, text="SET", 
                                       command=self.set_match_time_from_camera,
                                       bg="#3498db", fg="white", 
                                       font=("Arial", 9, "bold"),
                                       width=6, height=1)
        cam_set_time_button.pack(side=tk.LEFT, padx=(10, 5))
        
        # Tombol untuk melihat rekaman
        video_controls_frame = tk.Frame(camera_header, bg="#34495e")
        video_controls_frame.pack(pady=(0, 5))
        
        tk.Button(video_controls_frame, text="VIEW RECORDINGS", 
                 bg="#9b59b6", fg="white",
                 font=("Arial", 10, "bold"),
                 command=self.show_video_library).pack(side=tk.LEFT, padx=5)
        
        tk.Button(video_controls_frame, text="VIEW VAR", 
                 bg="#e67e22", fg="white",
                 font=("Arial", 10, "bold"),
                 command=self.show_var_library).pack(side=tk.LEFT, padx=5)
        
        # Camera Control Buttons
        camera_control_frame = tk.Frame(right_panel, bg="#2c3e50")
        camera_control_frame.pack(fill=tk.X, pady=(5, 5))
        
        tk.Button(camera_control_frame, text="START CAMERA", 
                 bg="#27ae60", fg="white",
                 font=("Arial", 11, "bold"),
                 command=self.start_camera).pack(side=tk.LEFT, padx=5, pady=5)
        
        tk.Button(camera_control_frame, text="STOP CAMERA", 
                 bg="#e74c3c", fg="white",
                 font=("Arial", 11, "bold"),
                 command=self.stop_camera).pack(side=tk.LEFT, padx=5, pady=5)
        
        tk.Button(camera_control_frame, text="FULLSCREEN", 
                 bg="#9b59b6", fg="white",
                 font=("Arial", 11, "bold"),
                 command=self.show_camera_fullscreen).pack(side=tk.LEFT, padx=5, pady=5)
        
        # ===== TOMBOL VAR - DENGAN STATE MANAGEMENT YANG LEBIH BAIK =====
        self.var_button = tk.Button(camera_control_frame, text="VAR", 
                                   bg="#e67e22", fg="white",
                                   font=("Arial", 11, "bold", "underline"),
                                   width=8,
                                   command=self.trigger_var)
        self.var_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Camera Display Area
        camera_display_frame = tk.Frame(right_panel, bg="black", relief=tk.SUNKEN, bd=3)
        camera_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.camera_label = tk.Label(camera_display_frame, bg="black")
        self.camera_label.pack(expand=True, fill=tk.BOTH)
        
        # Timer di kamera
        self.camera_timer_frame = tk.Frame(camera_display_frame, bg="black")
        self.camera_timer_frame.place(relx=0.5, rely=0.95, anchor="center")
        
        self.camera_timer_label = tk.Label(
            self.camera_timer_frame, 
            text="04:00:00",
            font=("Arial", 36, "bold"),
            fg="#2ecc71",
            bg="black",
            padx=20,
            pady=10
        )
        self.camera_timer_label.pack()
        
        # Camera Status
        camera_status_frame = tk.Frame(right_panel, bg="#2c3e50")
        camera_status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.camera_status_label = tk.Label(camera_status_frame, text="● Kamera tidak aktif", 
                                           font=("Arial", 11), 
                                           fg="#e74c3c", bg="#2c3e50")
        self.camera_status_label.pack()
        
        # Camera Info
        info_frame = tk.Frame(right_panel, bg="#2c3e50")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(info_frame, text="Tips Perekaman:", 
                font=("Arial", 10, "bold"),
                fg="white", bg="#2c3e50").pack(anchor=tk.W, padx=10)
        
        tk.Label(info_frame, text="• Perekaman otomatis saat timer START", 
                font=("Arial", 9),
                fg="#bdc3c7", bg="#2c3e50").pack(anchor=tk.W, padx=20)
        
        tk.Label(info_frame, text="• VAR: Rekam segmen saat PAUSE (dapat dilakukan berulang)", 
                font=("Arial", 9),
                fg="#e67e22", bg="#2c3e50").pack(anchor=tk.W, padx=20)
        
        tk.Label(info_frame, text="• Video disimpan di folder 'video_recordings'", 
                font=("Arial", 9),
                fg="#bdc3c7", bg="#2c3e50").pack(anchor=tk.W, padx=20)
    
    # ===== FUNGSI VAR - DIPERBAIKI UNTUK REKAMAN BERULANG =====
    def update_var_button_state(self):
        """Memperbarui status tombol VAR berdasarkan kondisi"""
        if not self.camera_running:
            self.var_button.config(state=tk.DISABLED, bg="#7f8c8d", text="VAR")
        elif self.var_recording:
            self.var_button.config(state=tk.NORMAL, bg="#e67e22", text="● VAR REC")
        elif self.paused:
            self.var_button.config(state=tk.NORMAL, bg="#27ae60", text="VAR READY")
        else:
            self.var_button.config(state=tk.DISABLED, bg="#7f8c8d", text="VAR")
    
    def trigger_var(self):
        """Memproses permintaan VAR - dapat dilakukan berulang kali"""
        if not self.camera_running:
            messagebox.showwarning("Peringatan", "Kamera tidak aktif!")
            return
        
        if not self.paused:
            messagebox.showwarning("Peringatan", "VAR hanya dapat digunakan saat pertandingan di-PAUSE!")
            return
        
        # Jika sedang merekam VAR, tawarkan untuk menghentikan atau memulai baru
        if self.var_recording:
            if messagebox.askyesno("VAR - Sedang Merekam", 
                                  "VAR sedang merekam. Apakah Anda ingin menghentikan rekaman saat ini dan memulai yang baru?"):
                self.stop_var_recording()
                self.start_var_recording()
            return
        
        # Konfirmasi untuk memulai VAR baru
        if messagebox.askyesno("VAR - Video Assistant Referee", 
                              f"Apakah Anda ingin merekam segmen VAR ke-{self.var_counter + 1}?\n\n"
                              "Video akan disimpan di folder VAR."):
            self.start_var_recording()
    
    def start_var_recording(self):
        """Memulai perekaman VAR untuk segmen tertentu"""
        try:
            # Hentikan perekaman utama jika sedang berlangsung
            if self.recording:
                self.stop_recording()
            
            # Setup VAR recording
            self.var_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            match_time = f"{int(self.remaining_time//60):02d}m{int(self.remaining_time%60):02d}s"
            
            # Nama file VAR dengan counter
            filename = f"VAR_{self.var_counter:02d}_{timestamp}_{match_time}_{self.aka_name}_vs_{self.ao_name}.mp4"
            filepath = os.path.join(self.var_folder, filename)
            
            # Dapatkan frame size dari kamera
            width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Setup video writer untuk VAR
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.var_video_writer = cv2.VideoWriter(filepath, fourcc, self.recording_fps, (width, height))
            
            if not self.var_video_writer.isOpened():
                raise Exception("Tidak dapat membuat file VAR")
            
            self.var_recording = True
            self.var_record_start_time = time.time()
            self.var_status_label.config(text=f"● VAR: Merekam #{self.var_counter}", fg="#e67e22")
            
            # Kosongkan queue VAR
            while not self.var_recording_queue.empty():
                try:
                    self.var_recording_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Mulai thread perekaman VAR
            self.var_recording_thread = threading.Thread(
                target=self.var_recording_worker,
                daemon=True
            )
            self.var_recording_thread.start()
            
            # Catat segmen video
            self.current_video_segment = {
                "filepath": filepath,
                "filename": filename,
                "var_number": self.var_counter,
                "timestamp": timestamp,
                "match_time": match_time,
                "start_time": time.strftime("%H:%M:%S"),
                "remaining_time": self.remaining_time,
                "aka_score": self.aka_score,
                "ao_score": self.ao_score,
                "aka_senshu": self.aka_senshu,
                "ao_senshu": self.ao_senshu,
                "aka_name": self.aka_name,
                "ao_name": self.ao_name,
                "aka_contingent": self.aka_contingent,
                "ao_contingent": self.ao_contingent
            }
            
            # Cancel timer auto-stop sebelumnya jika ada
            if self.var_auto_stop_id:
                self.root.after_cancel(self.var_auto_stop_id)
            
            # Set timer untuk menghentikan VAR recording otomatis setelah 30 detik
            self.var_auto_stop_id = self.root.after(30000, self.check_and_stop_var_recording)
            
            # Update tombol VAR
            self.update_var_button_state()
            
            print(f"VAR Recording #{self.var_counter} started: {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal memulai VAR:\n{str(e)}")
            self.var_recording = False
            self.update_var_button_state()
    
    def var_recording_worker(self):
        """Thread worker untuk menulis frame VAR ke video"""
        frames_written = 0
        start_time = time.time()
        
        while self.var_recording:
            try:
                frame = self.var_recording_queue.get(timeout=1.0)
                
                if frame is None:
                    break
                
                # Tambahkan overlay VAR khusus
                frame_with_overlay = self.add_var_overlay(frame)
                
                if self.var_video_writer:
                    self.var_video_writer.write(frame_with_overlay)
                    frames_written += 1
                
                self.var_recording_queue.task_done()
                
                if frames_written % 100 == 0:
                    elapsed = time.time() - start_time
                    print(f"VAR #{self.var_counter} frames: {frames_written}, FPS: {frames_written/elapsed:.1f}")
                
            except queue.Empty:
                # Ambil frame dari queue utama jika queue VAR kosong
                if self.latest_frame is not None:
                    try:
                        frame_copy = self.latest_frame.copy()
                        self.var_recording_queue.put(frame_copy, timeout=0.05, block=False)
                    except queue.Full:
                        pass
                continue
            except Exception as e:
                print(f"Error in VAR recording worker: {e}")
                break
        
        print(f"VAR #{self.var_counter} recording stopped. Frames: {frames_written}")
    
    def add_var_overlay(self, frame):
        """Menambahkan overlay khusus untuk video VAR"""
        try:
            height, width = frame.shape[:2]
            
            # Tambahkan overlay lengkap seperti biasa
            frame = self.add_comprehensive_overlay(frame)
            
            # Tambahkan watermark VAR
            var_text = f"VAR REVIEW #{self.var_counter}"
            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = width / 800
            thickness = int(font_scale * 3)
            
            text_size = cv2.getTextSize(var_text, font, font_scale, thickness)[0]
            text_x = width - text_size[0] - 20
            text_y = text_size[1] + 20
            
            # Background untuk teks VAR
            cv2.rectangle(frame, 
                         (text_x - 10, text_y - text_size[1] - 10),
                         (text_x + text_size[0] + 10, text_y + 10),
                         (0, 0, 0), -1)
            
            # Teks VAR
            cv2.putText(frame, var_text, (text_x, text_y),
                       font, font_scale, (0, 165, 255), thickness, cv2.LINE_AA)
            
            # Tambahkan timestamp review
            review_time = datetime.now().strftime("%H:%M:%S")
            time_text = f"Review: {review_time}"
            time_size = cv2.getTextSize(time_text, font, font_scale * 0.7, thickness - 1)[0]
            time_x = width - time_size[0] - 20
            time_y = text_y + text_size[1] + 30
            
            cv2.putText(frame, time_text, (time_x, time_y),
                       font, font_scale * 0.7, (255, 255, 255), thickness - 1, cv2.LINE_AA)
            
            return frame
            
        except Exception as e:
            print(f"Error adding VAR overlay: {e}")
            return frame
    
    def check_and_stop_var_recording(self):
        """Memeriksa dan menghentikan perekaman VAR"""
        if self.var_recording:
            # Jika masih dalam keadaan pause, lanjutkan rekaman
            if self.paused:
                # Tampilkan notifikasi bahwa VAR masih merekam
                self.var_status_label.config(text=f"● VAR: Merekam #{self.var_counter} (30s)", fg="#e67e22")
                # Schedule lagi 30 detik berikutnya
                self.var_auto_stop_id = self.root.after(30000, self.check_and_stop_var_recording)
            else:
                # Jika timer dilanjutkan, hentikan VAR recording
                self.stop_var_recording()
    
    def stop_var_recording(self):
        """Menghentikan perekaman VAR"""
        if self.var_recording:
            var_number = self.var_counter
            print(f"Stopping VAR #{var_number} recording...")
            self.var_recording = False
            
            # Cancel timer auto-stop
            if self.var_auto_stop_id:
                self.root.after_cancel(self.var_auto_stop_id)
                self.var_auto_stop_id = None
            
            # Beri signal ke thread untuk berhenti
            try:
                self.var_recording_queue.put(None, timeout=0.5, block=False)
            except:
                pass
            
            # Tunggu thread selesai
            if hasattr(self, 'var_recording_thread') and self.var_recording_thread:
                self.var_recording_thread.join(timeout=2.0)
                self.var_recording_thread = None
            
            # Hentikan video writer
            if self.var_video_writer:
                self.var_video_writer.release()
                self.var_video_writer = None
            
            self.var_status_label.config(text="● VAR: Tidak Aktif", fg="#7f8c8d")
            
            # Update metadata VAR
            if self.current_video_segment:
                self.current_video_segment["end_time"] = time.strftime("%H:%M:%S")
                self.current_video_segment["duration"] = time.time() - self.var_record_start_time
                self.save_var_metadata(self.current_video_segment)
                self.video_segments.append(self.current_video_segment)
                self.current_video_segment = None
            
            # Update tombol VAR
            self.update_var_button_state()
            
            print(f"VAR #{var_number} recording stopped")
            
            # Mulai ulang perekaman utama jika timer masih berjalan
            if self.running and not self.recording:
                self.start_recording()
    
    def save_var_metadata(self, video_info):
        """Menyimpan metadata video VAR"""
        try:
            # Baca metadata yang ada
            if os.path.exists(self.var_metadata_file):
                with open(self.var_metadata_file, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = []
            
            # Tambahkan timestamp untuk identifikasi
            video_info["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            video_info["duration_seconds"] = round(video_info.get("duration", 0), 2)
            
            metadata.append(video_info)
            
            # Simpan kembali
            with open(self.var_metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
                
            print(f"VAR metadata saved: {video_info['filename']}")
                
        except Exception as e:
            print(f"Error saving VAR metadata: {e}")
    
    def show_var_library(self):
        """Menampilkan library video VAR"""
        var_window = tk.Toplevel(self.root)
        var_window.title("VAR Library - Rekaman Video Assistant Referee")
        var_window.geometry("1000x700")
        var_window.configure(bg="#2c3e50")
        
        # Header
        header_frame = tk.Frame(var_window, bg="#34495e", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="VAR - VIDEO ASSISTANT REFEREE", 
                font=("Arial", 18, "bold"), 
                fg="white", bg="#34495e").pack(expand=True, pady=15)
        
        # Stats
        stats_frame = tk.Frame(var_window, bg="#2c3e50")
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(stats_frame, text=f"Total VAR Recordings: {self.var_counter}", 
                font=("Arial", 12, "bold"),
                fg="#e67e22", bg="#2c3e50").pack(side=tk.LEFT)
        
        # Main content
        content_frame = tk.Frame(var_window, bg="#2c3e50")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Scrollable frame
        canvas = tk.Canvas(content_frame, bg="#2c3e50", highlightthickness=0)
        scrollbar = tk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#2c3e50")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Load metadata VAR
        try:
            if os.path.exists(self.var_metadata_file):
                with open(self.var_metadata_file, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = []
            
            if not metadata:
                tk.Label(scrollable_frame, text="Belum ada rekaman VAR", 
                        font=("Arial", 14), 
                        fg="white", bg="#2c3e50").pack(pady=20)
            else:
                # Tampilkan video VAR terbaru pertama
                for i, video in enumerate(reversed(metadata)):
                    var_item_frame = tk.Frame(scrollable_frame, bg="#34495e", relief=tk.RAISED, bd=2)
                    var_item_frame.pack(fill=tk.X, pady=5, padx=10)
                    
                    # Header dengan label VAR
                    header_var = tk.Frame(var_item_frame, bg="#e67e22", height=30)
                    header_var.pack(fill=tk.X)
                    header_var.pack_propagate(False)
                    
                    tk.Label(header_var, text=f"VAR #{video.get('var_number', i+1)}", 
                            font=("Arial", 11, "bold"),
                            fg="white", bg="#e67e22").pack(side=tk.LEFT, padx=10)
                    
                    tk.Label(header_var, text=video['saved_at'], 
                            font=("Arial", 10),
                            fg="white", bg="#e67e22").pack(side=tk.RIGHT, padx=10)
                    
                    # Info video
                    info_frame = tk.Frame(var_item_frame, bg="#34495e")
                    info_frame.pack(fill=tk.X, padx=10, pady=10)
                    
                    # Match info
                    match_label = tk.Label(info_frame, 
                                         text=f"Pertandingan: {video['aka_name']} ({video['aka_contingent']}) vs {video['ao_name']} ({video['ao_contingent']})",
                                         font=("Arial", 11, "bold"),
                                         fg="white", bg="#34495e")
                    match_label.pack(anchor=tk.W, pady=(0, 5))
                    
                    # Time and score
                    time_score_frame = tk.Frame(info_frame, bg="#34495e")
                    time_score_frame.pack(fill=tk.X, pady=(0, 5))
                    
                    tk.Label(time_score_frame, 
                            text=f"Waktu: {video['match_time']} | Skor: AKA {video['aka_score']} - AO {video['ao_score']}",
                            font=("Arial", 10),
                            fg="#bdc3c7", bg="#34495e").pack(side=tk.LEFT)
                    
                    # Duration
                    duration_text = f"Durasi: {video.get('duration_seconds', 0):.1f} detik"
                    tk.Label(info_frame, text=duration_text,
                            font=("Arial", 10),
                            fg="#2ecc71", bg="#34495e").pack(anchor=tk.W, pady=(0, 5))
                    
                    # Senshu info
                    senshu_text = []
                    if video.get('aka_senshu'):
                        senshu_text.append("AKA Senshu")
                    if video.get('ao_senshu'):
                        senshu_text.append("AO Senshu")
                    if senshu_text:
                        tk.Label(info_frame, text=f"Senshu: {', '.join(senshu_text)}",
                                font=("Arial", 10),
                                fg="yellow", bg="#34495e").pack(anchor=tk.W, pady=(0, 5))
                    
                    # Button frame
                    button_frame = tk.Frame(var_item_frame, bg="#34495e")
                    button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
                    
                    tk.Button(button_frame, text="PLAY VAR", 
                             bg="#e67e22", fg="white",
                             font=("Arial", 10, "bold"),
                             command=lambda f=video['filepath']: self.play_video(f)).pack(side=tk.LEFT, padx=2)
                    
                    tk.Button(button_frame, text="OPEN FOLDER", 
                             bg="#3498db", fg="white",
                             font=("Arial", 10, "bold"),
                             command=lambda f=video['filepath']: self.open_video_folder(f)).pack(side=tk.LEFT, padx=2)
                    
                    tk.Button(button_frame, text="DELETE", 
                             bg="#e74c3c", fg="white",
                             font=("Arial", 10, "bold"),
                             command=lambda f=video['filepath'], m=metadata, idx=len(metadata)-1-i, w=var_window: self.delete_var_video(f, m, idx, w)).pack(side=tk.LEFT, padx=2)
                    
        except Exception as e:
            tk.Label(scrollable_frame, text=f"Error loading VAR videos: {e}", 
                    font=("Arial", 12), 
                    fg="white", bg="#2c3e50").pack(pady=20)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Tombol close
        tk.Button(var_window, text="CLOSE", 
                 bg="#e74c3c", fg="white",
                 font=("Arial", 11, "bold"),
                 command=var_window.destroy).pack(pady=10)
    
    def delete_var_video(self, filepath, metadata, index, parent_window):
        """Menghapus video VAR"""
        if not messagebox.askyesno("Konfirmasi", "Apakah Anda yakin ingin menghapus video VAR ini?"):
            return
        
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            
            metadata.pop(index)
            with open(self.var_metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            parent_window.destroy()
            self.show_var_library()
            
            messagebox.showinfo("Berhasil", "Video VAR berhasil dihapus!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menghapus video VAR:\n{str(e)}")
    
    # ===== FUNGSI PENGATUR WAKTU =====
    def set_match_time(self):
        """Fungsi untuk mengatur waktu pertandingan dari panel kiri"""
        try:
            minutes = int(self.minute_var.get())
            seconds = int(self.second_var.get())
            
            if minutes < 0 or minutes > 30:
                raise ValueError("Menit harus antara 0-30")
            if seconds < 0 or seconds > 59:
                raise ValueError("Detik harus antara 0-59")
            if minutes == 0 and seconds == 0:
                raise ValueError("Waktu tidak boleh 0")
            
            self.cam_minute_var.set(str(minutes))
            self.cam_second_var.set(str(seconds))
            
            self.match_time = minutes * 60 + seconds
            self.remaining_time = self.match_time
            
            self.update_all_timer_displays()
            
            time_text = f"({minutes:02d}:{seconds:02d})"
            self.current_time_label.config(text=time_text, fg="#2ecc71")
            
        except ValueError as e:
            messagebox.showerror("Error", f"Masukkan waktu yang valid:\n{str(e)}")
    
    def set_match_time_from_camera(self):
        """Fungsi untuk mengatur waktu pertandingan dari panel kamera"""
        try:
            minutes = int(self.cam_minute_var.get())
            seconds = int(self.cam_second_var.get())
            
            if minutes < 0 or minutes > 30:
                raise ValueError("Menit harus antara 0-30")
            if seconds < 0 or seconds > 59:
                raise ValueError("Detik harus antara 0-59")
            if minutes == 0 and seconds == 0:
                raise ValueError("Waktu tidak boleh 0")
            
            self.minute_var.set(str(minutes))
            self.second_var.set(str(seconds))
            
            self.match_time = minutes * 60 + seconds
            self.remaining_time = self.match_time
            
            self.update_all_timer_displays()
            
            time_text = f"({minutes:02d}:{seconds:02d})"
            self.current_time_label.config(text=time_text, fg="#2ecc71")
            
        except ValueError as e:
            messagebox.showerror("Error", f"Masukkan waktu yang valid:\n{str(e)}")
    
    def update_all_timer_displays(self):
        """Update tampilan timer di semua lokasi"""
        self.update_timer_display()
        self.update_camera_timer_display()
        
        if self.display_window and self.display_window.winfo_exists():
            self.update_display_timer()
    
    def update_camera_timer_display(self):
        """Update tampilan timer di kamera"""
        if self.camera_timer_label:
            total_seconds = int(self.remaining_time)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            centiseconds = int((self.remaining_time - total_seconds) * 100)
            
            self.camera_timer_label.config(text=f"{minutes:02d}:{seconds:02d}:{centiseconds:02d}")
            
            if self.remaining_time <= 10:
                self.camera_timer_label.config(fg="#e74c3c")
            elif self.remaining_time <= 30:
                self.camera_timer_label.config(fg="#f39c12")
            else:
                self.camera_timer_label.config(fg="#2ecc71")
            
            if self.time_up:
                self.camera_timer_label.config(bg="#e74c3c", fg="white")
            elif self.paused:
                self.camera_timer_label.config(bg="#f39c12", fg="black")
            else:
                self.camera_timer_label.config(bg="black")
    
    # ===== FUNGSI KAMERA DAN PEREKAMAN =====
    def start_camera(self):
        """Memulai kamera"""
        if not self.camera_running:
            try:
                self.camera = cv2.VideoCapture(0)
                
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self.camera.set(cv2.CAP_PROP_FPS, 30)
                
                if not self.camera.isOpened():
                    messagebox.showerror("Error", "Tidak dapat membuka kamera")
                    return
                
                self.camera_running = True
                self.camera_status_label.config(text="● Kamera aktif", fg="#2ecc71")
                
                self.update_camera_timer_display()
                self.start_camera_update()
                self.update_var_button_state()
                
            except Exception as e:
                messagebox.showerror("Error", f"Gagal membuka kamera:\n{str(e)}")
    
    def start_camera_update(self):
        """Memulai loop update kamera"""
        if self.camera_running:
            self.update_camera_frame()
    
    def update_camera_frame(self):
        """Update frame kamera dengan after()"""
        if self.camera_running and self.camera:
            try:
                ret, frame = self.camera.read()
                if ret:
                    self.latest_frame = frame.copy()
                    
                    # Jika VAR sedang merekam, kirim frame ke queue VAR
                    if self.var_recording:
                        try:
                            frame_copy = self.latest_frame.copy()
                            self.var_recording_queue.put(frame_copy, timeout=0.05, block=False)
                        except queue.Full:
                            pass
                    
                    try:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        height, width = frame_rgb.shape[:2]
                        max_height = self.camera_label.winfo_height()
                        max_width = self.camera_label.winfo_width()
                        
                        if max_width > 1 and max_height > 1:
                            aspect_ratio = width / height
                            new_width = min(max_width, int(max_height * aspect_ratio))
                            new_height = min(max_height, int(max_width / aspect_ratio))
                            
                            if new_width > 0 and new_height > 0:
                                frame_resized = cv2.resize(frame_rgb, (new_width, new_height))
                                self.current_frame = ImageTk.PhotoImage(
                                    Image.fromarray(frame_resized))
                                self.camera_label.config(image=self.current_frame)
                    except Exception as e:
                        print(f"Error displaying frame: {e}")
                
                if self.camera_running:
                    self.update_camera_timer_display()
                    self.camera_update_id = self.root.after(33, self.update_camera_frame)
                
            except Exception as e:
                print(f"Camera error: {e}")
                self.stop_camera()
    
    def stop_camera(self):
        """Menghentikan kamera"""
        self.camera_running = False
        
        if self.recording:
            self.stop_recording()
        
        if self.var_recording:
            self.stop_var_recording()
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        if self.camera_update_id:
            self.root.after_cancel(self.camera_update_id)
            self.camera_update_id = None
        
        self.camera_status_label.config(text="● Kamera tidak aktif", fg="#e74c3c")
        self.camera_label.config(image='')
        self.update_var_button_state()
    
    def add_comprehensive_overlay(self, frame):
        """Menambahkan overlay lengkap ke frame video"""
        try:
            height, width = frame.shape[:2]
            
            base_font_scale = width / 1500
            base_font_scale = max(0.5, min(1.2, base_font_scale))
            
            font = cv2.FONT_HERSHEY_DUPLEX
            thickness = int(base_font_scale * 2)
            
            black_color = (0, 0, 0)
            white_color = (255, 255, 255)
            aka_color = (0, 0, 255)
            ao_color = (255, 0, 0)
            yellow_color = (0, 255, 255)
            green_color = (0, 255, 0)
            orange_color = (0, 165, 255)
            
            # Timer
            total_seconds = int(self.remaining_time)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            centiseconds = int((self.remaining_time - total_seconds) * 100)
            timer_text = f"TIME: {minutes:02d}:{seconds:02d}:{centiseconds:02d}"
            
            # Status
            if self.time_up:
                status_text = "TIME UP!"
                status_color = aka_color
            elif self.paused and not self.running:
                status_text = "YAME"
                status_color = orange_color
            else:
                status_text = "HAJIME"
                status_color = green_color
            
            # Score
            aka_score_text = f"AKA: {self.aka_score}"
            ao_score_text = f"AO: {self.ao_score}"
            
            # Nama
            aka_info_text = f"{self.aka_name}"
            if self.aka_contingent != "-":
                aka_info_text += f" ({self.aka_contingent})"
            if self.aka_senshu:
                aka_info_text += " [SENSHU]"
            
            ao_info_text = f"{self.ao_name}"
            if self.ao_contingent != "-":
                ao_info_text += f" ({self.ao_contingent})"
            if self.ao_senshu:
                ao_info_text += " [SENSHU]"
            
            # Judges
            ao_judges_text = "AO Judges: "
            ao_active_judges = [j for j, active in self.ao_judges.items() if active]
            ao_judges_text += ", ".join(ao_active_judges) if ao_active_judges else "None"
            
            aka_judges_text = "AKA Judges: "
            aka_active_judges = [j for j, active in self.aka_judges.items() if active]
            aka_judges_text += ", ".join(aka_active_judges) if aka_active_judges else "None"
            
            # Background overlay
            overlay_top_height = int(height * 0.18)
            cv2.rectangle(frame, (0, 0), (width, overlay_top_height), black_color, -1)
            
            # Timer dan status di kiri
            left_margin = int(width * 0.02)
            line_height = int(overlay_top_height / 5)
            
            timer_font_scale = base_font_scale * 1.1
            timer_thickness = int(timer_font_scale * 3)
            cv2.putText(frame, timer_text, (left_margin, line_height * 2),
                       font, timer_font_scale, white_color, timer_thickness, cv2.LINE_AA)
            
            status_font_scale = base_font_scale * 1.0
            cv2.putText(frame, status_text, (left_margin, line_height * 4),
                       font, status_font_scale, status_color, int(status_font_scale * 2), cv2.LINE_AA)
            
            # Score di tengah
            center_x = int(width / 2)
            
            aka_score_font_scale = base_font_scale * 1.8
            aka_score_x = center_x - int(width * 0.3)
            cv2.putText(frame, aka_score_text, (aka_score_x, line_height * 2),
                       font, aka_score_font_scale, aka_color, int(aka_score_font_scale * 3), cv2.LINE_AA)
            
            aka_info_font_scale = base_font_scale * 0.9
            cv2.putText(frame, aka_info_text, (aka_score_x, line_height * 4),
                       font, aka_info_font_scale, aka_color, int(aka_info_font_scale * 2), cv2.LINE_AA)
            
            ao_score_font_scale = base_font_scale * 1.8
            ao_score_x = center_x + int(width * 0.1)
            cv2.putText(frame, ao_score_text, (ao_score_x, line_height * 2),
                       font, ao_score_font_scale, ao_color, int(ao_score_font_scale * 3), cv2.LINE_AA)
            
            ao_info_font_scale = base_font_scale * 0.9
            cv2.putText(frame, ao_info_text, (ao_score_x, line_height * 4),
                       font, ao_info_font_scale, ao_color, int(ao_info_font_scale * 2), cv2.LINE_AA)
            
            # Garis pemisah
            cv2.line(frame, (center_x, line_height * 1), (center_x, line_height * 4), white_color, 2)
            
            # Judges di bawah
            overlay_bottom_height = int(height * 0.12)
            overlay_bottom_y = height - overlay_bottom_height
            cv2.rectangle(frame, (0, overlay_bottom_y), (width, height), black_color, -1)
            cv2.rectangle(frame, (0, overlay_bottom_y), (width, height), white_color, 2)
            
            # Title JUDGES
            judges_title_font_scale = base_font_scale * 1.1
            judges_title_text = "JUDGES"
            judges_title_size = cv2.getTextSize(judges_title_text, font, judges_title_font_scale, int(judges_title_font_scale * 2))[0]
            judges_title_x = center_x - judges_title_size[0] // 2
            cv2.putText(frame, judges_title_text, (judges_title_x, overlay_bottom_y + line_height),
                       font, judges_title_font_scale, yellow_color, int(judges_title_font_scale * 2), cv2.LINE_AA)
            
            # Judges AO
            ao_judges_font_scale = base_font_scale * 0.8
            cv2.putText(frame, ao_judges_text, (int(width * 0.05), overlay_bottom_y + line_height * 3),
                       font, ao_judges_font_scale, ao_color, int(ao_judges_font_scale * 2), cv2.LINE_AA)
            
            # Judges AKA
            cv2.putText(frame, aka_judges_text, (int(width * 0.55), overlay_bottom_y + line_height * 3),
                       font, ao_judges_font_scale, aka_color, int(ao_judges_font_scale * 2), cv2.LINE_AA)
            
            # Efek waktu habis
            if self.time_up:
                if self.blink_state:
                    timer_bg_top_left = (left_margin - 10, line_height * 2 - timer_font_scale * 30)
                    timer_bg_bottom_right = (left_margin + cv2.getTextSize(timer_text, font, timer_font_scale, timer_thickness)[0][0] + 10, 
                                            line_height * 2 + 10)
                    cv2.rectangle(frame, timer_bg_top_left, timer_bg_bottom_right, aka_color, -1)
                    cv2.putText(frame, timer_text, (left_margin, line_height * 2),
                               font, timer_font_scale, white_color, timer_thickness, cv2.LINE_AA)
            
            # Efek pause
            elif self.paused:
                pause_text = "PAUSED"
                pause_font_scale = base_font_scale * 1.5
                pause_size = cv2.getTextSize(pause_text, font, pause_font_scale, int(pause_font_scale * 3))[0]
                pause_x = center_x - pause_size[0] // 2
                pause_y = int(height * 0.5)
                
                overlay = frame.copy()
                cv2.rectangle(overlay, (pause_x - 20, pause_y - pause_size[1] - 20),
                            (pause_x + pause_size[0] + 20, pause_y + 20), black_color, -1)
                cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
                cv2.putText(frame, pause_text, (pause_x, pause_y),
                           font, pause_font_scale, orange_color, int(pause_font_scale * 3), cv2.LINE_AA)
            
            return frame
            
        except Exception as e:
            print(f"Error adding comprehensive overlay: {e}")
            return frame
    
    # ===== FUNGSI PEREKAMAN VIDEO UTAMA =====
    def recording_worker(self):
        """Thread worker untuk menulis frame ke video"""
        frames_written = 0
        start_time = time.time()
        
        while self.recording:
            try:
                frame = self.recording_queue.get(timeout=1.0)
                
                if frame is None:
                    break
                
                frame_with_overlay = self.add_comprehensive_overlay(frame)
                
                if self.video_writer:
                    self.video_writer.write(frame_with_overlay)
                    frames_written += 1
                
                self.recording_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in recording worker: {e}")
                break
        
        print(f"Recording worker stopped. Total frames: {frames_written}")
    
    def capture_frames_for_recording(self):
        """Thread untuk mengambil frame dari kamera untuk perekaman"""
        last_capture_time = 0
        
        while self.recording and self.camera_running:
            try:
                current_time = time.time()
                
                if current_time - last_capture_time >= self.frame_interval:
                    if self.latest_frame is not None:
                        try:
                            frame_copy = self.latest_frame.copy()
                            self.recording_queue.put(frame_copy, timeout=0.05, block=False)
                        except queue.Full:
                            pass
                        
                        last_capture_time = current_time
                    else:
                        time.sleep(0.01)
                else:
                    time_to_wait = self.frame_interval - (current_time - last_capture_time)
                    if time_to_wait > 0:
                        time.sleep(time_to_wait * 0.5)
                        
            except Exception as e:
                print(f"Error in frame capture: {e}")
                break
        
        print("Frame capture thread stopped")
    
    def start_recording(self):
        """Memulai perekaman video utama"""
        if not self.camera_running:
            messagebox.showwarning("Peringatan", "Start kamera terlebih dahulu!")
            return
        
        if self.recording:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            match_duration = f"{int(self.match_time//60)}m{int(self.match_time%60)}s"
            
            width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.recording_fps
            
            filename = f"match_{timestamp}_{match_duration}_{self.aka_name}_vs_{self.ao_name}.mp4"
            filepath = os.path.join(self.video_folder, filename)
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
            
            if not self.video_writer.isOpened():
                raise Exception("Tidak dapat membuat file video")
            
            self.recording = True
            self.record_start_time = time.time()
            self.recording_status_label.config(text="● Perekaman: Aktif", fg="#2ecc71")
            
            while not self.recording_queue.empty():
                try:
                    self.recording_queue.get_nowait()
                except queue.Empty:
                    break
            
            self.recording_thread = threading.Thread(
                target=self.recording_worker, 
                daemon=True
            )
            self.recording_thread.start()
            
            self.frame_capture_thread = threading.Thread(
                target=self.capture_frames_for_recording,
                daemon=True
            )
            self.frame_capture_thread.start()
            
            self.current_video_file = filepath
            self.current_video_timestamp = timestamp
            self.current_video_duration = match_duration
            
            print(f"Started recording: {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal memulai perekaman:\n{str(e)}")
            self.recording = False
    
    def stop_recording(self):
        """Menghentikan perekaman video utama"""
        if self.recording:
            print("Stopping recording...")
            self.recording = False
            
            time.sleep(0.1)
            
            try:
                self.recording_queue.put(None, timeout=0.5, block=False)
            except:
                pass
            
            if hasattr(self, 'recording_thread') and self.recording_thread:
                self.recording_thread.join(timeout=2.0)
                self.recording_thread = None
            
            if hasattr(self, 'frame_capture_thread') and self.frame_capture_thread:
                self.frame_capture_thread.join(timeout=2.0)
                self.frame_capture_thread = None
            
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            
            self.recording_status_label.config(text="● Perekaman: Tidak Aktif", fg="#e74c3c")
            
            if hasattr(self, 'current_video_file'):
                self.save_video_metadata()
                self.current_video_file = None
            
            print("Recording stopped")
    
    def save_video_metadata(self):
        """Menyimpan metadata video utama"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = []
            
            actual_duration = time.time() - self.record_start_time if hasattr(self, 'record_start_time') else 0
            minutes = int(actual_duration // 60)
            seconds = int(actual_duration % 60)
            
            video_info = {
                "filepath": self.current_video_file,
                "filename": os.path.basename(self.current_video_file),
                "timestamp": self.current_video_timestamp,
                "match_duration_planned": self.current_video_duration,
                "match_duration_actual": f"{minutes}m{seconds}s",
                "duration_seconds": round(actual_duration, 2),
                "start_time": time.strftime("%H:%M:%S", time.localtime(self.record_start_time)),
                "end_time": time.strftime("%H:%M:%S"),
                "aka_name": self.aka_name,
                "aka_contingent": self.aka_contingent,
                "ao_name": self.ao_name,
                "ao_contingent": self.ao_contingent,
                "aka_score": self.aka_score,
                "ao_score": self.ao_score,
                "aka_senshu": self.aka_senshu,
                "ao_senshu": self.ao_senshu,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            metadata.append(video_info)
            
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
                
            print(f"Metadata saved: {video_info['filename']}")
            
        except Exception as e:
            print(f"Error saving metadata: {e}")
    
    # ===== FUNGSI TIMER UTAMA =====
    def start_timer(self):
        """Memulai timer dari awal dan perekaman otomatis"""
        if self.running:
            return
        
        self.running = True
        self.paused = False
        self.time_up = False
        self.blink_state = False
        
        self.start_time = time.time()
        self.remaining_time = self.match_time
        self.target_end_time = self.start_time + self.match_time
        
        self.status_label.config(text="HAJIME", fg="#2ecc71")
        
        self.start_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL)
        self.continue_button.config(state=tk.DISABLED)
        
        self.update_all_timer_displays()
        
        if self.camera_running and not self.recording:
            self.start_recording()
        
        if hasattr(self, 'blink_after_id'):
            self.root.after_cancel(self.blink_after_id)
        
        self.start_timer_update()
        self.update_var_button_state()
        
        if self.display_window and self.display_window.winfo_exists():
            self.start_display_timer()
    
    def pause_timer(self):
        """Menjeda timer"""
        if self.running:
            self.running = False
            self.paused = True
            
            self.pause_remaining_time = max(0, self.target_end_time - time.time())
            self.remaining_time = self.pause_remaining_time
            
            self.status_label.config(text="YAME", fg="#f39c12")
            
            self.update_all_timer_displays()
            
            self.start_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.DISABLED)
            self.continue_button.config(state=tk.NORMAL)
            
            if self.timer_update_id:
                self.root.after_cancel(self.timer_update_id)
                self.timer_update_id = None
            
            if self.display_update_id:
                if self.display_window and self.display_window.winfo_exists():
                    self.display_window.after_cancel(self.display_update_id)
                self.display_update_id = None
            
            # Update tombol VAR - sekarang aktif karena pause
            self.update_var_button_state()
    
    def continue_timer(self):
        """Melanjutkan timer setelah pause"""
        if not self.running and self.paused:
            # Hentikan VAR recording jika sedang berlangsung
            if self.var_recording:
                self.stop_var_recording()
            
            self.running = True
            self.paused = False
            
            self.start_time = time.time() - (self.match_time - self.remaining_time)
            self.target_end_time = self.start_time + self.match_time
            
            self.status_label.config(text="HAJIME", fg="#2ecc71")
            
            self.update_all_timer_displays()
            
            self.start_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL)
            self.continue_button.config(state=tk.DISABLED)
            
            if self.camera_running and not self.recording:
                self.start_recording()
            
            self.start_timer_update()
            self.update_var_button_state()
            
            if self.display_window and self.display_window.winfo_exists():
                self.start_display_timer()
    
    def start_timer_update(self):
        """Memulai loop update timer utama"""
        if self.running:
            self.update_timer_loop()
    
    def update_timer_loop(self):
        """Loop update timer utama"""
        if self.running:
            current_time = time.time()
            self.remaining_time = max(0, self.target_end_time - current_time)
            
            self.update_all_timer_displays()
            
            if self.remaining_time <= 0:
                self.time_up = True
                self.running = False
                self.status_label.config(text="TIME UP!", fg="#e74c3c")
                
                self.update_all_timer_displays()
                
                self.start_button.config(state=tk.NORMAL)
                self.pause_button.config(state=tk.DISABLED)
                self.continue_button.config(state=tk.DISABLED)
                
                if self.recording:
                    self.stop_recording()
                
                if self.var_recording:
                    self.stop_var_recording()
                
                if self.display_update_id:
                    if self.display_window and self.display_window.winfo_exists():
                        self.display_window.after_cancel(self.display_update_id)
                    self.display_update_id = None
                
                self.update_var_button_state()
                self.start_blink()
                return
            
            self.timer_update_id = self.root.after(self.update_interval, self.update_timer_loop)
    
    def reset_match(self):
        """Reset pertandingan"""
        self.running = False
        self.paused = False
        self.time_up = False
        self.blink_state = False
        
        self.remaining_time = self.match_time
        
        self.update_all_timer_displays()
        
        self.status_label.config(text="HAJIME", fg="white")
        
        if self.recording:
            self.stop_recording()
        
        if self.var_recording:
            self.stop_var_recording()
        
        if self.timer_update_id:
            self.root.after_cancel(self.timer_update_id)
            self.timer_update_id = None
        
        if self.display_update_id:
            if self.display_window and self.display_window.winfo_exists():
                self.display_window.after_cancel(self.display_update_id)
            self.display_update_id = None
        
        if hasattr(self, 'blink_after_id'):
            self.root.after_cancel(self.blink_after_id)
        
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
        self.continue_button.config(state=tk.DISABLED)
        
        self.timer_label.config(bg="#2c3e50", fg="#2ecc71")
        
        if self.display_window and self.display_window.winfo_exists():
            self.display_timer_label.config(bg="#000000", fg="#2ecc71")
            self.display_status_label.config(text="HAJIME", fg="white")
        
        # Reset scores
        self.aka_score = 0
        self.ao_score = 0
        self.aka_senshu = False
        self.ao_senshu = False
        
        self.aka_score_label.config(text="0")
        self.ao_score_label.config(text="0")
        self.aka_senshu_var.set("")
        self.ao_senshu_var.set("")
        
        if self.display_window and self.display_window.winfo_exists():
            self.display_aka_score_label.config(text="0")
            self.display_ao_score_label.config(text="0")
            self.display_aka_senshu_var.set("")
            self.display_ao_senshu_var.set("")
        
        # Reset VAR counter
        self.var_counter = 0
        
        self.reset_all_judges()
        self.update_var_button_state()
        
        print("Match reset successfully")
    
    def update_timer_display(self):
        """Update tampilan timer utama"""
        total_seconds = int(self.remaining_time)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        centiseconds = int((self.remaining_time - total_seconds) * 100)
        
        self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}:{centiseconds:02d}")
        
        if self.remaining_time <= 10:
            self.timer_label.config(fg="#e74c3c")
        elif self.remaining_time <= 30:
            self.timer_label.config(fg="#f39c12")
        else:
            self.timer_label.config(fg="#2ecc71")
    
    def start_display_timer(self):
        """Memulai update timer di display window"""
        if self.display_window and self.display_window.winfo_exists() and self.running:
            if self.display_update_id:
                self.display_window.after_cancel(self.display_update_id)
            
            self.update_display_timer_loop()
    
    def update_display_timer_loop(self):
        """Loop update timer untuk display window"""
        if not (self.display_window and self.display_window.winfo_exists()):
            return
            
        if self.running:
            self.update_display_timer()
            self.display_update_id = self.display_window.after(self.display_update_interval, self.update_display_timer_loop)
    
    def update_display_timer(self):
        """Update timer di display window"""
        if not (self.display_window and self.display_window.winfo_exists()):
            return
            
        total_seconds = int(self.remaining_time)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        centiseconds = int((self.remaining_time - total_seconds) * 100)
        
        self.display_timer_label.config(text=f"{minutes:02d}:{seconds:02d}:{centiseconds:02d}")
        
        if self.remaining_time <= 10:
            color = "#e74c3c"
        elif self.remaining_time <= 30:
            color = "#f39c12"
        else:
            color = "#2ecc71"
        
        self.display_timer_label.config(fg=color)
        
        if self.time_up:
            self.display_status_label.config(text="TIME UP!", fg="#e74c3c")
        elif self.running:
            self.display_status_label.config(text="HAJIME", fg="#2ecc71")
        elif self.paused:
            self.display_status_label.config(text="YAME", fg="#f39c12")
        else:
            self.display_status_label.config(text="HAJIME", fg="white")
        
        if self.time_up:
            self.blink_state = not self.blink_state
            if self.blink_state:
                self.display_timer_label.config(bg="#e74c3c", fg="white")
            else:
                self.display_timer_label.config(bg="#000000", fg="#e74c3c")
    
    def start_blink(self):
        """Mulai efek blink saat waktu habis"""
        if self.time_up:
            self.blink_state = not self.blink_state
            if self.blink_state:
                self.timer_label.config(bg="#e74c3c", fg="white")
                if self.display_window and self.display_window.winfo_exists():
                    self.display_timer_label.config(bg="#e74c3c", fg="white")
                if self.camera_timer_label:
                    self.camera_timer_label.config(bg="#e74c3c", fg="white")
            else:
                self.timer_label.config(bg="#2c3e50", fg="#e74c3c")
                if self.display_window and self.display_window.winfo_exists():
                    self.display_timer_label.config(bg="#000000", fg="#e74c3c")
                if self.camera_timer_label:
                    self.camera_timer_label.config(bg="black", fg="#e74c3c")
            
            self.blink_after_id = self.root.after(800, self.start_blink)
    
    def adjust_score(self, player, points):
        """Menyesuaikan skor"""
        if player == 'aka':
            new_score = self.aka_score + points
            if new_score < 0:
                new_score = 0
            self.aka_score = new_score
            self.aka_score_label.config(text=str(self.aka_score))
            if self.display_window and self.display_window.winfo_exists():
                self.display_aka_score_label.config(text=str(self.aka_score))
        else:
            new_score = self.ao_score + points
            if new_score < 0:
                new_score = 0
            self.ao_score = new_score
            self.ao_score_label.config(text=str(self.ao_score))
            if self.display_window and self.display_window.winfo_exists():
                self.display_ao_score_label.config(text=str(self.ao_score))
    
    def reset_score(self, player):
        """Reset skor untuk pemain tertentu"""
        if player == 'aka':
            self.aka_score = 0
            self.aka_score_label.config(text="0")
            if self.display_window and self.display_window.winfo_exists():
                self.display_aka_score_label.config(text="0")
        else:
            self.ao_score = 0
            self.ao_score_label.config(text="0")
            if self.display_window and self.display_window.winfo_exists():
                self.display_ao_score_label.config(text="0")
    
    def toggle_senshu(self, player):
        """Toggle status senshu"""
        if player == 'aka':
            self.aka_senshu = not self.aka_senshu
            self.aka_senshu_var.set("SENSHU" if self.aka_senshu else "")
            if self.display_window and self.display_window.winfo_exists():
                self.display_aka_senshu_var.set("SENSHU" if self.aka_senshu else "")
        else:
            self.ao_senshu = not self.ao_senshu
            self.ao_senshu_var.set("SENSHU" if self.ao_senshu else "")
            if self.display_window and self.display_window.winfo_exists():
                self.display_ao_senshu_var.set("SENSHU" if self.ao_senshu else "")
    
    def toggle_judge(self, player, judge):
        """Toggle status wasit"""
        if player == 'aka':
            self.aka_judges[judge] = not self.aka_judges[judge]
            color = "yellow" if self.aka_judges[judge] else "white"
            bg_color = "#e67e22" if self.aka_judges[judge] else "#34495e"
            self.aka_judge_labels[judge].config(fg=color, bg=bg_color)
            
            if judge in self.display_aka_judge_labels:
                if self.aka_judges[judge]:
                    self.display_aka_judge_labels[judge].config(bg="#e74c3c", fg="white")
                else:
                    self.display_aka_judge_labels[judge].config(bg="#7f8c8d", fg="white")
        else:
            self.ao_judges[judge] = not self.ao_judges[judge]
            color = "yellow" if self.ao_judges[judge] else "white"
            bg_color = "#e67e22" if self.ao_judges[judge] else "#34495e"
            self.ao_judge_labels[judge].config(fg=color, bg=bg_color)
            
            if judge in self.display_ao_judge_labels:
                if self.ao_judges[judge]:
                    self.display_ao_judge_labels[judge].config(bg="#3498db", fg="white")
                else:
                    self.display_ao_judge_labels[judge].config(bg="#7f8c8d", fg="white")
    
    def reset_all_judges(self):
        """Reset semua wasit"""
        for judge in self.ao_judges:
            self.ao_judges[judge] = False
            self.ao_judge_labels[judge].config(fg="white", bg="#34495e")
            
            if judge in self.display_ao_judge_labels:
                self.display_ao_judge_labels[judge].config(bg="#7f8c8d", fg="white")
        
        for judge in self.aka_judges:
            self.aka_judges[judge] = False
            self.aka_judge_labels[judge].config(fg="white", bg="#34495e")
            
            if judge in self.display_aka_judge_labels:
                self.display_aka_judge_labels[judge].config(bg="#7f8c8d", fg="white")
    
    def edit_player_info(self, player):
        """Membuka dialog untuk mengedit info pemain"""
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Edit Info {player.upper()}")
        edit_window.geometry("400x350")
        edit_window.configure(bg="#2c3e50")
        edit_window.resizable(False, False)
        
        edit_window.transient(self.root)
        edit_window.grab_set()
        
        header_frame = tk.Frame(edit_window, bg="#34495e", height=50)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text=f"EDIT INFO {player.upper()}", 
                font=("Arial", 16, "bold"), 
                fg="white", bg="#34495e").pack(expand=True)
        
        content_frame = tk.Frame(edit_window, bg="#2c3e50")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        tk.Label(content_frame, text="Nama Atlet:", 
                font=("Arial", 12), 
                fg="white", bg="#2c3e50").pack(anchor=tk.W, pady=(10, 5))
        
        name_var = tk.StringVar()
        if player == 'aka':
            name_var.set(self.aka_name)
        else:
            name_var.set(self.ao_name)
        
        name_entry = tk.Entry(content_frame, textvariable=name_var,
                             font=("Arial", 12), 
                             bg="white", fg="black",
                             width=30)
        name_entry.pack(fill=tk.X, pady=(0, 15))
        name_entry.select_range(0, tk.END)
        name_entry.focus_set()
        
        tk.Label(content_frame, text="Kontingen:", 
                font=("Arial", 12), 
                fg="white", bg="#2c3e50").pack(anchor=tk.W, pady=(5, 5))
        
        contingent_var = tk.StringVar()
        if player == 'aka':
            contingent_var.set(self.aka_contingent)
        else:
            contingent_var.set(self.ao_contingent)
        
        contingent_entry = tk.Entry(content_frame, textvariable=contingent_var,
                                   font=("Arial", 12), 
                                   bg="white", fg="black",
                                   width=30)
        contingent_entry.pack(fill=tk.X, pady=(0, 20))
        
        button_frame = tk.Frame(content_frame, bg="#2c3e50")
        button_frame.pack(fill=tk.X)
        
        def save_info():
            new_name = name_var.get().strip()
            new_contingent = contingent_var.get().strip()
            
            if new_name:
                if player == 'aka':
                    self.aka_name = new_name
                    self.aka_contingent = new_contingent if new_contingent else "-"
                    self.aka_name_var.set(self.aka_name)
                    self.aka_contingent_var.set(self.aka_contingent)
                    
                    if self.display_window and self.display_window.winfo_exists():
                        self.display_aka_name_var.set(self.aka_name)
                        self.display_aka_contingent_var.set(self.aka_contingent)
                else:
                    self.ao_name = new_name
                    self.ao_contingent = new_contingent if new_contingent else "-"
                    self.ao_name_var.set(self.ao_name)
                    self.ao_contingent_var.set(self.ao_contingent)
                    
                    if self.display_window and self.display_window.winfo_exists():
                        self.display_ao_name_var.set(self.ao_name)
                        self.display_ao_contingent_var.set(self.ao_contingent)
                
                edit_window.destroy()
            else:
                messagebox.showwarning("Peringatan", "Nama atlet tidak boleh kosong!")
        
        def reset_info():
            if player == 'aka':
                self.aka_name = "AKA"
                self.aka_contingent = "-"
                self.aka_name_var.set(self.aka_name)
                self.aka_contingent_var.set(self.aka_contingent)
                
                if self.display_window and self.display_window.winfo_exists():
                    self.display_aka_name_var.set(self.aka_name)
                    self.display_aka_contingent_var.set(self.aka_contingent)
            else:
                self.ao_name = "AO"
                self.ao_contingent = "-"
                self.ao_name_var.set(self.ao_name)
                self.ao_contingent_var.set(self.ao_contingent)
                
                if self.display_window and self.display_window.winfo_exists():
                    self.display_ao_name_var.set(self.ao_name)
                    self.display_ao_contingent_var.set(self.ao_contingent)
            
            edit_window.destroy()
        
        tk.Button(button_frame, text="SAVE", 
                 bg="#27ae60", fg="white",
                 font=("Arial", 11, "bold"),
                 width=10,
                 command=save_info).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="RESET", 
                 bg="#e74c3c", fg="white",
                 font=("Arial", 11, "bold"),
                 width=10,
                 command=reset_info).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="CANCEL", 
                 bg="#7f8c8d", fg="white",
                 font=("Arial", 11, "bold"),
                 width=10,
                 command=edit_window.destroy).pack(side=tk.RIGHT, padx=5)
        
        edit_window.bind('<Return>', lambda e: save_info())
    
    def show_camera_fullscreen(self):
        """Menampilkan kamera di window terpisah fullscreen"""
        if not self.camera_running:
            messagebox.showwarning("Peringatan", "Start kamera terlebih dahulu!")
            return
        
        if not self.camera_window or not self.camera_window.winfo_exists():
            self.camera_window = tk.Toplevel(self.root)
            self.camera_window.title("Live Camera - Fullscreen")
            self.camera_window.configure(bg="black")
            
            self.camera_window.attributes('-fullscreen', True)
            
            fullscreen_frame = tk.Frame(self.camera_window, bg="black")
            fullscreen_frame.pack(fill=tk.BOTH, expand=True)
            
            self.fullscreen_label = tk.Label(fullscreen_frame, bg="black")
            self.fullscreen_label.pack(expand=True, fill=tk.BOTH)
            
            fullscreen_timer_frame = tk.Frame(fullscreen_frame, bg="black")
            fullscreen_timer_frame.place(relx=0.5, rely=0.95, anchor="center")
            
            self.fullscreen_timer_label = tk.Label(
                fullscreen_timer_frame, 
                text="04:00:00",
                font=("Arial", 48, "bold"),
                fg="#2ecc71",
                bg="black",
                padx=30,
                pady=15
            )
            self.fullscreen_timer_label.pack()
            
            if self.recording:
                recording_label = tk.Label(fullscreen_frame, text="● RECORDING", 
                                         font=("Arial", 16, "bold"),
                                         fg="#e74c3c", bg="black")
                recording_label.place(x=20, y=20)
            
            if self.var_recording:
                var_label = tk.Label(fullscreen_frame, text=f"● VAR #{self.var_counter} RECORDING", 
                                   font=("Arial", 16, "bold"),
                                   fg="#e67e22", bg="black")
                var_label.place(x=20, y=60)
            
            exit_button = tk.Button(fullscreen_frame, text="EXIT FULLSCREEN (ESC)",
                                   font=("Arial", 12, "bold"),
                                   bg="#e74c3c", fg="white",
                                   command=self.exit_camera_fullscreen)
            exit_button.pack(side=tk.BOTTOM, pady=10)
            
            self.camera_window.bind('<Escape>', lambda e: self.exit_camera_fullscreen())
            
            self.update_fullscreen_camera()
    
    def exit_camera_fullscreen(self):
        """Keluar dari mode fullscreen kamera"""
        if self.camera_window and self.camera_window.winfo_exists():
            self.camera_window.destroy()
            self.camera_window = None
    
    def update_fullscreen_camera(self):
        """Update kamera di window fullscreen"""
        if self.camera_window and self.camera_window.winfo_exists() and self.camera_running:
            try:
                if self.latest_frame is not None:
                    frame_rgb = cv2.cvtColor(self.latest_frame, cv2.COLOR_BGR2RGB)
                    width = self.camera_window.winfo_width()
                    height = self.camera_window.winfo_height()
                    
                    if width > 1 and height > 1:
                        frame_resized = cv2.resize(frame_rgb, (width, height))
                        img = ImageTk.PhotoImage(Image.fromarray(frame_resized))
                        self.fullscreen_label.config(image=img)
                        self.fullscreen_label.image = img
                    
                    self.update_fullscreen_timer()
                
                if self.camera_window.winfo_exists():
                    self.camera_window.after(40, self.update_fullscreen_camera)
                
            except Exception as e:
                print(f"Fullscreen camera error: {e}")
    
    def update_fullscreen_timer(self):
        """Update timer di window fullscreen"""
        if hasattr(self, 'fullscreen_timer_label'):
            total_seconds = int(self.remaining_time)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            centiseconds = int((self.remaining_time - total_seconds) * 100)
            
            self.fullscreen_timer_label.config(text=f"{minutes:02d}:{seconds:02d}:{centiseconds:02d}")
            
            if self.remaining_time <= 10:
                self.fullscreen_timer_label.config(fg="#e74c3c")
            elif self.remaining_time <= 30:
                self.fullscreen_timer_label.config(fg="#f39c12")
            else:
                self.fullscreen_timer_label.config(fg="#2ecc71")
    
    def show_video_library(self):
        """Menampilkan library video yang telah direkam"""
        video_window = tk.Toplevel(self.root)
        video_window.title("Video Library - Rekaman Pertandingan")
        video_window.geometry("900x700")
        video_window.configure(bg="#2c3e50")
        
        header_frame = tk.Frame(video_window, bg="#34495e", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="REKAMAN PERTANDINGAN", 
                font=("Arial", 18, "bold"), 
                fg="white", bg="#34495e").pack(expand=True, pady=15)
        
        content_frame = tk.Frame(video_window, bg="#2c3e50")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        canvas = tk.Canvas(content_frame, bg="#2c3e50", highlightthickness=0)
        scrollbar = tk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#2c3e50")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = []
            
            if not metadata:
                tk.Label(scrollable_frame, text="Belum ada rekaman video", 
                        font=("Arial", 14), 
                        fg="white", bg="#2c3e50").pack(pady=20)
            else:
                for i, video in enumerate(reversed(metadata)):
                    video_frame = tk.Frame(scrollable_frame, bg="#34495e", relief=tk.RAISED, bd=2)
                    video_frame.pack(fill=tk.X, pady=5, padx=10)
                    
                    info_frame = tk.Frame(video_frame, bg="#34495e")
                    info_frame.pack(fill=tk.X, padx=10, pady=10)
                    
                    date_label = tk.Label(info_frame, 
                                         text=f"Tanggal: {video['timestamp'][:8]} | Waktu: {video['start_time']} - {video.get('end_time', '')}",
                                         font=("Arial", 11, "bold"),
                                         fg="white", bg="#34495e")
                    date_label.pack(anchor=tk.W)
                    
                    player_info_frame = tk.Frame(info_frame, bg="#34495e")
                    player_info_frame.pack(fill=tk.X, pady=(5, 0))
                    
                    aka_info = tk.Label(player_info_frame, 
                                       text=f"AKA: {video['aka_name']} ({video['aka_contingent']})",
                                       font=("Arial", 10, "bold"),
                                       fg="#e74c3c", bg="#34495e")
                    aka_info.pack(side=tk.LEFT, padx=(0, 20))
                    
                    ao_info = tk.Label(player_info_frame, 
                                      text=f"AO: {video['ao_name']} ({video['ao_contingent']})",
                                      font=("Arial", 10, "bold"),
                                      fg="#3498db", bg="#34495e")
                    ao_info.pack(side=tk.LEFT)
                    
                    duration_text = f"Durasi: {video.get('match_duration_planned', '')} (Rencana) | {video.get('match_duration_actual', '')} (Aktual) - {video.get('duration_seconds', 0):.1f} detik"
                    duration_label = tk.Label(info_frame, 
                                            text=duration_text,
                                            font=("Arial", 10),
                                            fg="#bdc3c7", bg="#34495e")
                    duration_label.pack(anchor=tk.W, pady=(5, 0))
                    
                    score_label = tk.Label(info_frame, 
                                         text=f"Skor: AKA {video['aka_score']} - AO {video['ao_score']}",
                                         font=("Arial", 10),
                                         fg="#2ecc71", bg="#34495e")
                    score_label.pack(anchor=tk.W, pady=(5, 0))
                    
                    senshu_text = []
                    if video.get('aka_senshu'):
                        senshu_text.append("AKA Senshu")
                    if video.get('ao_senshu'):
                        senshu_text.append("AO Senshu")
                    if senshu_text:
                        senshu_label = tk.Label(info_frame, 
                                              text=f"Senshu: {', '.join(senshu_text)}",
                                              font=("Arial", 10),
                                              fg="yellow", bg="#34495e")
                        senshu_label.pack(anchor=tk.W, pady=(5, 0))
                    
                    button_frame = tk.Frame(video_frame, bg="#34495e")
                    button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
                    
                    tk.Button(button_frame, text="PLAY", 
                             bg="#27ae60", fg="white",
                             font=("Arial", 10, "bold"),
                             command=lambda f=video['filepath']: self.play_video(f)).pack(side=tk.LEFT, padx=2)
                    
                    tk.Button(button_frame, text="OPEN FOLDER", 
                             bg="#3498db", fg="white",
                             font=("Arial", 10, "bold"),
                             command=lambda f=video['filepath']: self.open_video_folder(f)).pack(side=tk.LEFT, padx=2)
                    
                    tk.Button(button_frame, text="DELETE", 
                             bg="#e74c3c", fg="white",
                             font=("Arial", 10, "bold"),
                             command=lambda f=video['filepath'], m=metadata, idx=len(metadata)-1-i, w=video_window: self.delete_video(f, m, idx, w)).pack(side=tk.LEFT, padx=2)
                    
        except Exception as e:
            tk.Label(scrollable_frame, text=f"Error loading videos: {e}", 
                    font=("Arial", 12), 
                    fg="white", bg="#2c3e50").pack(pady=20)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        tk.Button(video_window, text="CLOSE", 
                 bg="#e74c3c", fg="white",
                 font=("Arial", 11, "bold"),
                 command=video_window.destroy).pack(pady=10)
    
    def play_video(self, filepath):
        """Memutar video"""
        if not os.path.exists(filepath):
            messagebox.showerror("Error", "File video tidak ditemukan!")
            return
        
        try:
            cap = cv2.VideoCapture(filepath)
            
            if not cap.isOpened():
                messagebox.showerror("Error", "Tidak dapat memutar video!")
                return
            
            video_window = tk.Toplevel(self.root)
            video_window.title(f"Playing: {os.path.basename(filepath)}")
            video_window.geometry("800x600")
            video_window.configure(bg="black")
            
            video_frame = tk.Frame(video_window, bg="black")
            video_frame.pack(fill=tk.BOTH, expand=True)
            
            video_label = tk.Label(video_frame, bg="black")
            video_label.pack(expand=True)
            
            control_frame = tk.Frame(video_window, bg="black")
            control_frame.pack(fill=tk.X, pady=5)
            
            def update_video_frame():
                ret, frame = cap.read()
                if ret:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    window_width = video_label.winfo_width()
                    window_height = video_label.winfo_height()
                    
                    if window_width > 1 and window_height > 1:
                        height, width = frame_rgb.shape[:2]
                        aspect_ratio = width / height
                        
                        if window_width / window_height > aspect_ratio:
                            new_height = window_height
                            new_width = int(window_height * aspect_ratio)
                        else:
                            new_width = window_width
                            new_height = int(window_width / aspect_ratio)
                        
                        if new_width > 0 and new_height > 0:
                            frame_resized = cv2.resize(frame_rgb, (new_width, new_height))
                            img = Image.fromarray(frame_resized)
                            imgtk = ImageTk.PhotoImage(image=img)
                            video_label.imgtk = imgtk
                            video_label.configure(image=imgtk)
                    
                    video_window.after(33, update_video_frame)
                else:
                    cap.release()
                    video_window.destroy()
            
            update_video_frame()
            
            tk.Button(control_frame, text="CLOSE", 
                     bg="#e74c3c", fg="white",
                     font=("Arial", 10, "bold"),
                     command=lambda: [cap.release(), video_window.destroy()]).pack(side=tk.RIGHT, padx=10)
            
            video_window.protocol("WM_DELETE_WINDOW", lambda: [cap.release(), video_window.destroy()])
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal memutar video:\n{str(e)}")
    
    def open_video_folder(self, filepath):
        """Membuka folder yang berisi video"""
        try:
            folder = os.path.dirname(filepath)
            if os.path.exists(folder):
                if os.name == 'nt':
                    os.startfile(folder)
                elif os.name == 'posix':
                    import subprocess
                    subprocess.run(['xdg-open', folder])
            else:
                messagebox.showwarning("Peringatan", "Folder tidak ditemukan!")
        except Exception as e:
            messagebox.showerror("Error", f"Tidak dapat membuka folder:\n{str(e)}")
    
    def delete_video(self, filepath, metadata, index, parent_window):
        """Menghapus video"""
        if not messagebox.askyesno("Konfirmasi", "Apakah Anda yakin ingin menghapus video ini?"):
            return
        
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            
            metadata.pop(index)
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            parent_window.destroy()
            self.show_video_library()
            
            messagebox.showinfo("Berhasil", "Video berhasil dihapus!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menghapus video:\n{str(e)}")
    
    # ===== FUNGSI DISPLAY WINDOW =====
    def show_display_window(self):
        """Membuat window baru untuk display penonton"""
        if self.display_window is None or not self.display_window.winfo_exists():
            self.display_window = tk.Toplevel(self.root)
            self.display_window.title("KUMITE DISPLAY - Penonton")
            self.display_window.configure(bg="#000000")
            
            screen_width = self.display_window.winfo_screenwidth()
            screen_height = self.display_window.winfo_screenheight()
            display_width = int(screen_width * 0.9)
            display_height = int(screen_height * 0.85)
            
            self.display_window.geometry(f"{display_width}x{display_height}+50+50")
            self.display_window.resizable(True, True)
            
            self.setup_display_window()
            
            self.display_window.bind("<Configure>", self.on_display_resize)
            
        else:
            self.display_window.lift()
    
    def setup_display_window(self):
        """Setup tampilan responsif untuk monitor penonton"""
        for widget in self.display_window.winfo_children():
            widget.destroy()
        
        main_container = tk.Frame(self.display_window, bg="#000000")
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        control_frame = tk.Frame(main_container, bg="#000000")
        control_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Button(control_frame, text="TOGGLE FULL SCREEN", 
                 font=("Arial", 12, "bold"),
                 bg="#9b59b6", fg="white",
                 command=self.toggle_fullscreen).pack(side=tk.LEFT)
        
        tk.Button(control_frame, text="CLOSE DISPLAY", 
                 font=("Arial", 12, "bold"),
                 bg="#e74c3c", fg="white",
                 command=self.close_display_window).pack(side=tk.RIGHT)
        
        header_frame = tk.Frame(main_container, bg="#000000")
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.display_title_label = tk.Label(header_frame, text="KUMITE TOURNAMENT", 
                                          font=("Arial", 36, "bold"), 
                                          fg="white", bg="#000000")
        self.display_title_label.pack(side=tk.LEFT)
        
        self.display_status_label = tk.Label(header_frame, text="HAJIME",
                                           font=("Arial", 32, "bold"),
                                           fg="#2ecc71", bg="#000000")
        self.display_status_label.pack(side=tk.RIGHT)
        
        timer_frame = tk.Frame(main_container, bg="#000000")
        timer_frame.pack(fill=tk.X, pady=(0, 30))
        
        self.display_timer_label = tk.Label(timer_frame, text="04:00:00",
                                          font=("Arial", 96, "bold"),
                                          fg="#2ecc71", bg="#000000")
        self.display_timer_label.pack(expand=True)
        
        score_panels_frame = tk.Frame(main_container, bg="#000000")
        score_panels_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 30))
        
        score_panels_frame.grid_columnconfigure(0, weight=1)
        score_panels_frame.grid_columnconfigure(1, weight=1)
        score_panels_frame.grid_rowconfigure(0, weight=1)
        
        # AO Panel
        ao_display_frame = tk.Frame(score_panels_frame, bg="#3498db", relief=tk.RAISED, bd=5)
        ao_display_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        ao_display_frame.grid_rowconfigure(0, weight=0)
        ao_display_frame.grid_rowconfigure(1, weight=2)
        ao_display_frame.grid_rowconfigure(2, weight=0)
        ao_display_frame.grid_columnconfigure(0, weight=1)
        
        ao_display_header = tk.Frame(ao_display_frame, bg="#2980b9", height=120)
        ao_display_header.grid(row=0, column=0, sticky="ew")
        ao_display_header.grid_propagate(False)
        
        self.display_ao_name_var = tk.StringVar(value=self.ao_name)
        self.display_ao_name_label = tk.Label(ao_display_header, textvariable=self.display_ao_name_var, 
                                             font=("Arial", 28, "bold"), 
                                             fg="white", bg="#2980b9")
        self.display_ao_name_label.pack(expand=True, pady=(10, 0))
        
        self.display_ao_contingent_var = tk.StringVar(value=self.ao_contingent)
        self.display_ao_contingent_label = tk.Label(ao_display_header, textvariable=self.display_ao_contingent_var, 
                                                   font=("Arial", 22), 
                                                   fg="white", bg="#2980b9")
        self.display_ao_contingent_label.pack(expand=True, pady=(0, 10))
        
        ao_score_display = tk.Frame(ao_display_frame, bg="#3498db")
        ao_score_display.grid(row=1, column=0, sticky="nsew")
        
        self.display_ao_score_label = tk.Label(ao_score_display, text="0", 
                                             font=("Arial", 180, "bold"), 
                                             fg="white", bg="#3498db")
        self.display_ao_score_label.pack(expand=True)
        
        self.display_ao_senshu_var = tk.StringVar(value="")
        self.display_ao_senshu_label = tk.Label(ao_display_frame, textvariable=self.display_ao_senshu_var,
                                              font=("Arial", 36, "bold"), 
                                              fg="yellow", bg="#3498db")
        self.display_ao_senshu_label.grid(row=2, column=0, pady=15)
        
        # AKA Panel
        aka_display_frame = tk.Frame(score_panels_frame, bg="#e74c3c", relief=tk.RAISED, bd=5)
        aka_display_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        aka_display_frame.grid_rowconfigure(0, weight=0)
        aka_display_frame.grid_rowconfigure(1, weight=2)
        aka_display_frame.grid_rowconfigure(2, weight=0)
        aka_display_frame.grid_columnconfigure(0, weight=1)
        
        aka_display_header = tk.Frame(aka_display_frame, bg="#c0392b", height=120)
        aka_display_header.grid(row=0, column=0, sticky="ew")
        aka_display_header.grid_propagate(False)
        
        self.display_aka_name_var = tk.StringVar(value=self.aka_name)
        self.display_aka_name_label = tk.Label(aka_display_header, textvariable=self.display_aka_name_var, 
                                              font=("Arial", 28, "bold"), 
                                              fg="white", bg="#c0392b")
        self.display_aka_name_label.pack(expand=True, pady=(10, 0))
        
        self.display_aka_contingent_var = tk.StringVar(value=self.aka_contingent)
        self.display_aka_contingent_label = tk.Label(aka_display_header, textvariable=self.display_aka_contingent_var, 
                                                    font=("Arial", 22), 
                                                    fg="white", bg="#c0392b")
        self.display_aka_contingent_label.pack(expand=True, pady=(0, 10))
        
        aka_score_display = tk.Frame(aka_display_frame, bg="#e74c3c")
        aka_score_display.grid(row=1, column=0, sticky="nsew")
        
        self.display_aka_score_label = tk.Label(aka_score_display, text="0", 
                                              font=("Arial", 180, "bold"), 
                                              fg="white", bg="#e74c3c")
        self.display_aka_score_label.pack(expand=True)
        
        self.display_aka_senshu_var = tk.StringVar(value="")
        self.display_aka_senshu_label = tk.Label(aka_display_frame, textvariable=self.display_aka_senshu_var,
                                               font=("Arial", 36, "bold"), 
                                               fg="yellow", bg="#e74c3c")
        self.display_aka_senshu_label.grid(row=2, column=0, pady=15)
        
        # Judges Display
        judges_display_frame = tk.Frame(main_container, bg="#000000")
        judges_display_frame.pack(fill=tk.X, pady=(0, 10))
        
        ao_judges_display = tk.Frame(judges_display_frame, bg="#000000")
        ao_judges_display.pack(side=tk.LEFT, expand=True)
        
        ao_judges_title = tk.Label(ao_judges_display, text="AO Judges", 
                                  font=("Arial", 24, "bold"),
                                  fg="white", bg="#000000")
        ao_judges_title.pack(pady=(0, 10))
        
        self.display_ao_judges_frame = tk.Frame(ao_judges_display, bg="#000000")
        self.display_ao_judges_frame.pack()
        
        aka_judges_display = tk.Frame(judges_display_frame, bg="#000000")
        aka_judges_display.pack(side=tk.RIGHT, expand=True)
        
        aka_judges_title = tk.Label(aka_judges_display, text="AKA Judges", 
                                   font=("Arial", 24, "bold"),
                                   fg="white", bg="#000000")
        aka_judges_title.pack(pady=(0, 10))
        
        self.display_aka_judges_frame = tk.Frame(aka_judges_display, bg="#000000")
        self.display_aka_judges_frame.pack()
        
        self.create_judges_display_widgets()
        
        self.update_display_window()
        self.display_window.protocol("WM_DELETE_WINDOW", self.close_display_window)
    
    def create_judges_display_widgets(self):
        """Membuat widget untuk tampilan wasit di display"""
        for widget in self.display_ao_judges_frame.winfo_children():
            widget.destroy()
        for widget in self.display_aka_judges_frame.winfo_children():
            widget.destroy()
        
        self.display_ao_judge_labels = {}
        self.display_aka_judge_labels = {}
        
        judge_positions = ["CH1", "CH2", "CH3", "HC", "H"]
        
        for judge in judge_positions:
            if self.ao_judges[judge]:
                bg_color = "#3498db"
            else:
                bg_color = "#7f8c8d"
            
            label = tk.Label(self.display_ao_judges_frame, text=judge,
                           font=("Arial", 20, "bold"),
                           fg="white", bg=bg_color,
                           width=6, height=2,
                           relief=tk.RAISED, bd=3)
            label.pack(side=tk.LEFT, padx=5)
            self.display_ao_judge_labels[judge] = label
        
        for judge in judge_positions:
            if self.aka_judges[judge]:
                bg_color = "#e74c3c"
            else:
                bg_color = "#7f8c8d"
            
            label = tk.Label(self.display_aka_judges_frame, text=judge,
                           font=("Arial", 20, "bold"),
                           fg="white", bg=bg_color,
                           width=6, height=2,
                           relief=tk.RAISED, bd=3)
            label.pack(side=tk.LEFT, padx=5)
            self.display_aka_judge_labels[judge] = label
    
    def on_display_resize(self, event):
        """Handle window resize event"""
        if event.widget == self.display_window:
            self.update_display_fonts()
    
    def update_display_fonts(self):
        """Update font sizes based on window size"""
        if not (self.display_window and self.display_window.winfo_exists()):
            return
            
        width = self.display_window.winfo_width()
        height = self.display_window.winfo_height()
        
        if width > 0 and height > 0:
            min_dimension = min(width, height)
            
            timer_font_size = max(48, min(150, int(min_dimension / 15)))
            score_font_size = max(40, min(120, int(min_dimension / 20)))
            name_font_size = max(20, min(40, int(min_dimension / 30)))
            contingent_font_size = max(16, min(30, int(min_dimension / 35)))
            title_font_size = max(24, min(48, int(min_dimension / 25)))
            status_font_size = max(20, min(40, int(min_dimension / 30)))
            judges_font_size = max(12, min(28, int(min_dimension / 40)))
            judges_title_font_size = max(16, min(32, int(min_dimension / 35)))
            senshu_font_size = max(20, min(40, int(min_dimension / 30)))
            
            self.display_title_label.config(font=("Arial", title_font_size, "bold"))
            self.display_status_label.config(font=("Arial", status_font_size, "bold"))
            self.display_timer_label.config(font=("Arial", timer_font_size, "bold"))
            self.display_ao_score_label.config(font=("Arial", score_font_size, "bold"))
            self.display_aka_score_label.config(font=("Arial", score_font_size, "bold"))
            self.display_ao_name_label.config(font=("Arial", name_font_size, "bold"))
            self.display_aka_name_label.config(font=("Arial", name_font_size, "bold"))
            self.display_ao_contingent_label.config(font=("Arial", contingent_font_size))
            self.display_aka_contingent_label.config(font=("Arial", contingent_font_size))
            self.display_ao_senshu_label.config(font=("Arial", senshu_font_size, "bold"))
            self.display_aka_senshu_label.config(font=("Arial", senshu_font_size, "bold"))
            
            for judge in self.display_ao_judge_labels:
                self.display_ao_judge_labels[judge].config(
                    font=("Arial", judges_font_size, "bold"),
                    width=max(4, min(8, int(min_dimension / 150))),
                    height=2
                )
            
            for judge in self.display_aka_judge_labels:
                self.display_aka_judge_labels[judge].config(
                    font=("Arial", judges_font_size, "bold"),
                    width=max(4, min(8, int(min_dimension / 150))),
                    height=2
                )
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode untuk display window"""
        if self.display_window and self.display_window.winfo_exists():
            self.display_fullscreen = not self.display_fullscreen
            self.display_window.attributes('-fullscreen', self.display_fullscreen)
            
            if not self.display_fullscreen:
                screen_width = self.display_window.winfo_screenwidth()
                screen_height = self.display_window.winfo_screenheight()
                display_width = int(screen_width * 0.9)
                display_height = int(screen_height * 0.85)
                self.display_window.geometry(f"{display_width}x{display_height}+50+50")
            
            self.update_display_fonts()
    
    def update_display_window(self):
        """Update tampilan display window (non-timer elements)"""
        if not (self.display_window and self.display_window.winfo_exists()):
            return
            
        self.display_ao_score_label.config(text=str(self.ao_score))
        self.display_aka_score_label.config(text=str(self.aka_score))
        
        self.display_ao_name_var.set(self.ao_name)
        self.display_ao_contingent_var.set(self.ao_contingent)
        self.display_aka_name_var.set(self.aka_name)
        self.display_aka_contingent_var.set(self.aka_contingent)
        
        self.display_ao_senshu_var.set("SENSHU" if self.ao_senshu else "")
        self.display_aka_senshu_var.set("SENSHU" if self.aka_senshu else "")
        
        self.update_judges_display_colors()
    
    def update_judges_display_colors(self):
        """Update warna pada label wasit"""
        if not (self.display_window and self.display_window.winfo_exists()):
            return
            
        for judge in self.display_ao_judge_labels:
            if self.ao_judges[judge]:
                self.display_ao_judge_labels[judge].config(bg="#3498db")
            else:
                self.display_ao_judge_labels[judge].config(bg="#7f8c8d")
        
        for judge in self.display_aka_judge_labels:
            if self.aka_judges[judge]:
                self.display_aka_judge_labels[judge].config(bg="#e74c3c")
            else:
                self.display_aka_judge_labels[judge].config(bg="#7f8c8d")
    
    def close_display_window(self):
        """Menutup display window"""
        if self.display_window and self.display_window.winfo_exists():
            if self.display_update_id:
                self.display_window.after_cancel(self.display_update_id)
                self.display_update_id = None
            
            self.display_window.destroy()
        self.display_window = None
        self.display_fullscreen = False
        self.display_ao_judge_labels = {}
        self.display_aka_judge_labels = {}

if __name__ == "__main__":
    root = tk.Tk()
    
    style = ttk.Style()
    style.theme_use('clam')
    
    app = JudoTimer(root)
    root.mainloop()