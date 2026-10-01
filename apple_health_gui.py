#!/usr/bin/env python3
import os
import sys
import threading
from datetime import datetime, timedelta
from collections import defaultdict
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

def clean_tag(val):
    if not val:
        return ""
    prefixes = [
        "HKQuantityTypeIdentifier",
        "HKCategoryValueSleepAnalysis",
        "HKWorkoutActivityType",
        "HKCategoryValue",
        "HKCharacteristicTypeIdentifier",
        "HKCorrelationTypeIdentifier"
    ]
    for p in prefixes:
        val = val.replace(p, "")
    return val

def format_pace(w_type, dur_min, dist_km):
    if dist_km <= 0 or dur_min <= 0:
        return "-"
    w_lower = w_type.lower()
    if any(k in w_lower for k in ("running", "walking", "hiking")):
        pace_dec = dur_min / dist_km
        p_min = int(pace_dec)
        p_sec = int(round((pace_dec - p_min) * 60))
        if p_sec == 60:
            p_min += 1
            p_sec = 0
        return f"{p_min}:{p_sec:02d} /km"
    elif "cycling" in w_lower:
        speed = dist_km / (dur_min / 60.0)
        return f"{speed:.1f} km/h"
    return "-"

class HealthExporterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Apple Health — Export to Markdown")
        self.geometry("840x880")
        self.minsize(760, 800)

        self.style = ttk.Style(self)
        if "aqua" in self.style.theme_names():
            self.style.theme_use("aqua")

        self.create_variables()
        self.create_widgets()
        self.autodetect_input_file()

    def create_variables(self):
        # Paths
        self.xml_path_var = tk.StringVar()
        self.out_path_var = tk.StringVar(value=os.path.expanduser("~/Downloads/health_custom_export.md"))

        # Date range
        today = datetime.now().date()
        self.date_from_var = tk.StringVar(value="2024-01-01")
        self.date_to_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))

        # 1. Sports & Workouts
        self.opt_sport_run = tk.BooleanVar(value=True)
        self.opt_sport_bike = tk.BooleanVar(value=True)
        self.opt_sport_strength_trad = tk.BooleanVar(value=True)
        self.opt_sport_strength_func = tk.BooleanVar(value=True)
        self.opt_sport_core = tk.BooleanVar(value=True)
        self.opt_sport_yoga = tk.BooleanVar(value=True)
        self.opt_sport_other = tk.BooleanVar(value=False)

        # 2. Heart & Recovery
        self.opt_rhr = tk.BooleanVar(value=True)
        self.opt_hrv = tk.BooleanVar(value=True)
        self.opt_vo2 = tk.BooleanVar(value=True)
        self.opt_walk_hr = tk.BooleanVar(value=False)
        self.opt_hr_recovery = tk.BooleanVar(value=True)
        self.opt_hr_daily_summary = tk.BooleanVar(value=True)
        self.opt_raw_hr = tk.BooleanVar(value=False)

        # 3. Sleep & Physiology
        self.opt_sleep_stages = tk.BooleanVar(value=True)
        self.opt_sleep_resp = tk.BooleanVar(value=True)
        self.opt_sleep_spo2 = tk.BooleanVar(value=True)
        self.opt_sleep_temp = tk.BooleanVar(value=True)
        self.opt_sleep_disturb = tk.BooleanVar(value=True)

        # 4. Clinical & Vitals
        self.opt_bp = tk.BooleanVar(value=True)
        self.opt_glucose = tk.BooleanVar(value=True)
        self.opt_rings = tk.BooleanVar(value=True)
        self.opt_steps = tk.BooleanVar(value=True)

        self.is_processing = False

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="15 15 15 15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. File Selection
        files_frame = ttk.LabelFrame(main_frame, text=" 1. Source and Destination Files ", padding="10")
        files_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(files_frame, text="Apple Health export.xml:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(files_frame, textvariable=self.xml_path_var, width=50).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=3)
        ttk.Button(files_frame, text="Browse XML...", command=self.browse_xml).grid(row=0, column=2, pady=3)

        ttk.Label(files_frame, text="Output Markdown file (.md):").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(files_frame, textvariable=self.out_path_var, width=50).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=3)
        ttk.Button(files_frame, text="Save As...", command=self.browse_output).grid(row=1, column=2, pady=3)
        files_frame.columnconfigure(1, weight=1)

        # 2. Date Range
        dates_frame = ttk.LabelFrame(main_frame, text=" 2. Date Range ", padding="10")
        dates_frame.pack(fill=tk.X, pady=(0, 10))

        d_inputs = ttk.Frame(dates_frame)
        d_inputs.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(d_inputs, text="From (YYYY-MM-DD):").pack(side=tk.LEFT)
        ttk.Entry(d_inputs, textvariable=self.date_from_var, width=12).pack(side=tk.LEFT, padx=(5, 20))
        ttk.Label(d_inputs, text="To (YYYY-MM-DD):").pack(side=tk.LEFT)
        ttk.Entry(d_inputs, textvariable=self.date_to_var, width=12).pack(side=tk.LEFT, padx=5)

        d_presets = ttk.Frame(dates_frame)
        d_presets.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(d_presets, text="Quick Presets:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(d_presets, text="All Time", command=lambda: self.set_dates_preset("all")).pack(side=tk.LEFT, padx=2)
        ttk.Button(d_presets, text="This Year", command=lambda: self.set_dates_preset("ytd")).pack(side=tk.LEFT, padx=2)
        ttk.Button(d_presets, text="Last 12 Months", command=lambda: self.set_dates_preset("1y")).pack(side=tk.LEFT, padx=2)
        ttk.Button(d_presets, text="Last 6 Months", command=lambda: self.set_dates_preset("6m")).pack(side=tk.LEFT, padx=2)
        ttk.Button(d_presets, text="Last 30 Days", command=lambda: self.set_dates_preset("30d")).pack(side=tk.LEFT, padx=2)

        # 3. Metrics Selection Tabs
        metrics_frame = ttk.LabelFrame(main_frame, text=" 3. Select Metrics and Categories ", padding="10")
        metrics_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.notebook = ttk.Notebook(metrics_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Tab: Sports
        tab_sports = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_sports, text="Workouts & Sports")
        ttk.Label(tab_sports, text="Select Activities (Duration, Distance, Pace, Heart Rate, RPE, Calories):", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))
        ttk.Checkbutton(tab_sports, text="Running", variable=self.opt_sport_run).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_sports, text="Cycling", variable=self.opt_sport_bike).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_sports, text="Traditional Strength Training", variable=self.opt_sport_strength_trad).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_sports, text="Functional Strength Training", variable=self.opt_sport_strength_func).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_sports, text="Core Training", variable=self.opt_sport_core).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_sports, text="Yoga", variable=self.opt_sport_yoga).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_sports, text="Other Activities (HIIT, Walking, Hiking, Rowing, etc.)", variable=self.opt_sport_other).pack(anchor=tk.W, pady=3)

        # Tab: Heart & Recovery
        tab_heart = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_heart, text="Heart & Recovery")
        ttk.Label(tab_heart, text="Cardiovascular and Autonomic Metrics:", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))
        ttk.Checkbutton(tab_heart, text="Resting Heart Rate (RHR)", variable=self.opt_rhr).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_heart, text="Heart Rate Variability (HRV / SDNN)", variable=self.opt_hrv).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_heart, text="Cardio Fitness (VO2 Max)", variable=self.opt_vo2).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_heart, text="Walking Heart Rate Average", variable=self.opt_walk_hr).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_heart, text="Heart Rate Recovery (1 minute post-workout)", variable=self.opt_hr_recovery).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_heart, text="All-Day Heart Rate Profile (Daily average, min & max)", variable=self.opt_hr_daily_summary).pack(anchor=tk.W, pady=3)
        
        ttk.Separator(tab_heart, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Checkbutton(tab_heart, text="Raw Continuous Heart Rate (Individual readings with exact timestamp hh:mm)", variable=self.opt_raw_hr).pack(anchor=tk.W, pady=3)
        ttk.Label(tab_heart, text="*Note: Select raw heart rate only for short date intervals to avoid massive files.", font=("Helvetica", 9), foreground="#888888").pack(anchor=tk.W, padx=20)

        # Tab: Sleep
        tab_sleep = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_sleep, text="Sleep & Physiology")
        ttk.Label(tab_sleep, text="Sleep Architecture and Overnight Biometrics:", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))
        ttk.Checkbutton(tab_sleep, text="Sleep Stages (Deep, REM, Core, Awake)", variable=self.opt_sleep_stages).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_sleep, text="Sleeping Respiratory Rate", variable=self.opt_sleep_resp).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_sleep, text="Overnight Oxygen Saturation (SpO2)", variable=self.opt_sleep_spo2).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_sleep, text="Sleeping Wrist Temperature Deviation", variable=self.opt_sleep_temp).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_sleep, text="Breathing Disturbances during sleep", variable=self.opt_sleep_disturb).pack(anchor=tk.W, pady=3)

        # Tab: Medical
        tab_health = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_health, text="Clinical & Vitals")
        ttk.Label(tab_health, text="Clinical Records and Daily Totals:", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))
        ttk.Checkbutton(tab_health, text="Blood Pressure (Systolic / Diastolic mmHg)", variable=self.opt_bp).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_health, text="Blood Glucose", variable=self.opt_glucose).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_health, text="Daily Activity Rings (Move / Exercise / Stand)", variable=self.opt_rings).pack(anchor=tk.W, pady=3)
        ttk.Checkbutton(tab_health, text="Daily Step Count & Walking Distance", variable=self.opt_steps).pack(anchor=tk.W, pady=3)

        btn_bar = ttk.Frame(metrics_frame)
        btn_bar.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_bar, text="Select All", command=self.select_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_bar, text="Deselect All", command=self.deselect_all).pack(side=tk.LEFT)

        # 4. Progress and Start
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(5, 0))

        self.progress_bar = ttk.Progressbar(bottom_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))

        status_box = ttk.Frame(bottom_frame)
        status_box.pack(fill=tk.X)

        self.status_label = ttk.Label(status_box, text="Ready. Select parameters and click Generate.", font=("Helvetica", 10))
        self.status_label.pack(side=tk.LEFT)

        self.start_btn = ttk.Button(status_box, text="Generate Markdown File", command=self.start_export_thread)
        self.start_btn.pack(side=tk.RIGHT)

    def autodetect_input_file(self):
        common_places = [
            os.path.expanduser("~/Downloads/apple_health_export/export.xml"),
            os.path.expanduser("~/Downloads/export.xml"),
            "apple_health_export/export.xml",
            "export.xml"
        ]
        for p in common_places:
            if os.path.exists(p):
                self.xml_path_var.set(os.path.abspath(p))
                break

    def browse_xml(self):
        f = filedialog.askopenfilename(
            title="Select Apple Health XML File",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        if f: self.xml_path_var.set(f)

    def browse_output(self):
        f = filedialog.asksaveasfilename(
            title="Save Output Markdown File As",
            defaultextension=".md",
            filetypes=[("Markdown file", "*.md"), ("Text file", "*.txt")]
        )
        if f: self.out_path_var.set(f)

    def set_dates_preset(self, preset):
        today = datetime.now().date()
        self.date_to_var.set(today.strftime("%Y-%m-%d"))
        if preset == "all": self.date_from_var.set("2010-01-01")
        elif preset == "ytd": self.date_from_var.set(f"{today.year}-01-01")
        elif preset == "1y": self.date_from_var.set((today - timedelta(days=365)).strftime("%Y-%m-%d"))
        elif preset == "6m": self.date_from_var.set((today - timedelta(days=182)).strftime("%Y-%m-%d"))
        elif preset == "30d": self.date_from_var.set((today - timedelta(days=30)).strftime("%Y-%m-%d"))

    def get_all_checkbox_vars(self):
        return [
            self.opt_sport_run, self.opt_sport_bike, self.opt_sport_strength_trad,
            self.opt_sport_strength_func, self.opt_sport_core, self.opt_sport_yoga, self.opt_sport_other,
            self.opt_rhr, self.opt_hrv, self.opt_vo2, self.opt_walk_hr, self.opt_hr_recovery,
            self.opt_hr_daily_summary, self.opt_raw_hr,
            self.opt_sleep_stages, self.opt_sleep_resp, self.opt_sleep_spo2, self.opt_sleep_temp, self.opt_sleep_disturb,
            self.opt_bp, self.opt_glucose, self.opt_rings, self.opt_steps
        ]

    def select_all(self):
        for v in self.get_all_checkbox_vars():
            if v != self.opt_raw_hr:
                v.set(True)

    def deselect_all(self):
        for v in self.get_all_checkbox_vars(): v.set(False)

    def start_export_thread(self):
        if self.is_processing: return

        xml_path = self.xml_path_var.get().strip()
        out_path = self.out_path_var.get().strip()

        if not os.path.exists(xml_path):
            messagebox.showerror("Error", "The specified XML file does not exist.")
            return

        d_from = self.date_from_var.get().strip()
        d_to = self.date_to_var.get().strip()
        try:
            datetime.fromisoformat(d_from)
            datetime.fromisoformat(d_to)
        except Exception:
            messagebox.showerror("Date Format Error", "Dates must be in valid YYYY-MM-DD format.")
            return

        self.is_processing = True
        self.start_btn.config(state=tk.DISABLED)
        self.progress_bar.start(10)
        self.status_label.config(text="Processing XML file...")

        t = threading.Thread(target=self.process_export, args=(xml_path, out_path, d_from, d_to), daemon=True)
        t.start()

    def process_export(self, xml_path, out_path, d_from, d_to):
        start_time = datetime.now()

        do_run = self.opt_sport_run.get()
        do_bike = self.opt_sport_bike.get()
        do_s_trad = self.opt_sport_strength_trad.get()
        do_s_func = self.opt_sport_strength_func.get()
        do_core = self.opt_sport_core.get()
        do_yoga = self.opt_sport_yoga.get()
        do_other = self.opt_sport_other.get()
        any_sport = any([do_run, do_bike, do_s_trad, do_s_func, do_core, do_yoga, do_other])

        do_rhr = self.opt_rhr.get()
        do_hrv = self.opt_hrv.get()
        do_vo2 = self.opt_vo2.get()
        do_walk_hr = self.opt_walk_hr.get()
        do_hr_rec = self.opt_hr_recovery.get()
        do_hr_daily = self.opt_hr_daily_summary.get()
        do_raw_hr = self.opt_raw_hr.get()

        do_sleep = self.opt_sleep_stages.get()
        do_resp = self.opt_sleep_resp.get()
        do_spo2 = self.opt_sleep_spo2.get()
        do_temp = self.opt_sleep_temp.get()
        do_disturb = self.opt_sleep_disturb.get()
        any_sleep_bio = any([do_resp, do_spo2, do_temp, do_disturb])

        do_bp = self.opt_bp.get()
        do_glucose = self.opt_glucose.get()
        do_rings = self.opt_rings.get()
        do_steps = self.opt_steps.get()

        workouts = []
        daily_resting_hr = {}
        daily_hrv = defaultdict(list)
        daily_vo2 = {}
        daily_walk_hr = {}
        daily_hr_rec = {}
        daily_hr_stats = defaultdict(lambda: [0, 0.0, float('inf'), float('-inf')])
        raw_hr_records = []

        daily_sleep = defaultdict(lambda: defaultdict(float))
        daily_sleep_bio = defaultdict(lambda: {'resp': [], 'spo2': [], 'temp': [], 'disturb': []})

        bp_records = defaultdict(dict)
        glucose_records = []
        daily_rings = {}
        daily_steps = defaultdict(float)

        try:
            context = ET.iterparse(xml_path, events=('start', 'end'))
            root = None
            sample_count = 0

            for event, elem in context:
                tag = elem.tag.split('}')[-1]

                if event == 'start' and root is None:
                    root = elem
                    continue

                if event == 'end':
                    # 1. WORKOUTS
                    if tag == 'Workout' and any_sport:
                        start_raw = elem.attrib.get('startDate', '')
                        day = start_raw[:10]
                        if d_from <= day <= d_to:
                            w_type = clean_tag(elem.attrib.get('workoutActivityType', 'Other'))
                            w_low = w_type.lower()

                            include_w = False
                            if 'running' in w_low and do_run: include_w = True
                            elif 'cycling' in w_low and do_bike: include_w = True
                            elif 'traditionalstrength' in w_low and do_s_trad: include_w = True
                            elif 'functionalstrength' in w_low and do_s_func: include_w = True
                            elif 'core' in w_low and do_core: include_w = True
                            elif 'yoga' in w_low and do_yoga: include_w = True
                            elif do_other and not any(k in w_low for k in ('running', 'cycling', 'traditionalstrength', 'functionalstrength', 'core', 'yoga')):
                                include_w = True

                            if include_w:
                                dur = float(elem.attrib.get('duration', 0))
                                dist = float(elem.attrib.get('totalDistance', 0)) if 'totalDistance' in elem.attrib else 0.0
                                cal_raw = elem.attrib.get('totalEnergyBurned', '-')
                                cal = f"{float(cal_raw):.0f} kcal" if cal_raw != '-' else "-"

                                avg_hr, max_hr, rpe = "-", "-", "-"
                                for child in elem:
                                    ctag = child.tag.split('}')[-1]
                                    if ctag == 'WorkoutStatistics':
                                        st_type = child.attrib.get('type', '')
                                        if 'HeartRate' in st_type:
                                            if 'average' in child.attrib: avg_hr = f"{float(child.attrib['average']):.0f}"
                                            if 'maximum' in child.attrib: max_hr = f"{float(child.attrib['maximum']):.0f}"
                                        elif 'Distance' in st_type and dist == 0.0:
                                            dist = float(child.attrib.get('sum', 0))
                                    elif ctag == 'MetadataEntry':
                                        k = child.attrib.get('key', '')
                                        if any(term in k for term in ('Effort', 'RPE', 'Intensity')):
                                            rpe = child.attrib.get('value', '-')

                                workouts.append({
                                    'start': start_raw[:16],
                                    'type': w_type,
                                    'dur': f"{dur:.1f} min",
                                    'dist': f"{dist:.2f} km" if dist > 0 else "-",
                                    'pace': format_pace(w_type, dur, dist),
                                    'avg_hr': avg_hr,
                                    'max_hr': max_hr,
                                    'rpe': rpe,
                                    'cal': cal
                                })
                        elem.clear()

                    # 2. ACTIVITY SUMMARY / RINGS
                    elif tag == 'ActivitySummary' and do_rings:
                        day = elem.attrib.get('dateComponents', '')
                        if d_from <= day <= d_to:
                            move = f"{float(elem.attrib.get('activeEnergyBurned', 0)):.0f}/{float(elem.attrib.get('activeEnergyBurnedGoal', 0)):.0f}"
                            exe = f"{float(elem.attrib.get('appleExerciseTime', 0)):.0f}/{float(elem.attrib.get('appleExerciseTimeGoal', 0)):.0f}"
                            stand = f"{elem.attrib.get('appleStandHours', '0')}/{elem.attrib.get('appleStandHoursGoal', '0')}"
                            daily_rings[day] = (move, exe, stand)
                        elem.clear()

                    # 3. RECORDS
                    elif tag == 'Record':
                        start_raw = elem.attrib.get('startDate', '')
                        day = start_raw[:10]
                        time_stamp = start_raw[:16]

                        if d_from <= day <= d_to:
                            rtype = clean_tag(elem.attrib.get('type', ''))
                            val = elem.attrib.get('value', '')

                            # Heart & Recovery
                            if do_rhr and rtype == 'RestingHeartRate' and val:
                                daily_resting_hr[day] = float(val)
                            elif do_hrv and rtype == 'HeartRateVariabilitySDNN' and val:
                                daily_hrv[day].append(float(val))
                            elif do_vo2 and rtype == 'VO2Max' and val:
                                daily_vo2[day] = float(val)
                            elif do_walk_hr and rtype == 'WalkingHeartRateAverage' and val:
                                daily_walk_hr[day] = float(val)
                            elif do_hr_rec and rtype == 'HeartRateRecoveryOneMinute' and val:
                                daily_hr_rec[day] = float(val)
                            elif rtype == 'HeartRate' and val:
                                hr = float(val)
                                if do_hr_daily:
                                    st = daily_hr_stats[day]
                                    st[0] += 1; st[1] += hr
                                    if hr < st[2]: st[2] = hr
                                    if hr > st[3]: st[3] = hr
                                if do_raw_hr:
                                    raw_hr_records.append((time_stamp, f"{hr:.0f} bpm"))

                            # Sleep
                            elif do_sleep and rtype == 'SleepAnalysis':
                                stage = clean_tag(val)
                                s_str = elem.attrib.get('startDate', '')
                                e_str = elem.attrib.get('endDate', '')
                                if s_str and e_str:
                                    try:
                                        t1 = datetime.fromisoformat(s_str)
                                        t2 = datetime.fromisoformat(e_str)
                                        daily_sleep[day][stage] += (t2 - t1).total_seconds() / 60.0
                                    except Exception:
                                        pass

                            # Overnight Biometrics
                            elif do_resp and rtype == 'RespiratoryRate' and val:
                                daily_sleep_bio[day]['resp'].append(float(val))
                            elif do_spo2 and rtype == 'OxygenSaturation' and val:
                                v_spo2 = float(val)
                                if v_spo2 <= 1.0: v_spo2 *= 100.0
                                daily_sleep_bio[day]['spo2'].append(v_spo2)
                            elif do_temp and rtype == 'AppleSleepingWristTemperature' and val:
                                daily_sleep_bio[day]['temp'].append(float(val))
                            elif do_disturb and rtype == 'BreathingDisturbances' and val:
                                daily_sleep_bio[day]['disturb'].append(float(val))

                            # Clinical
                            elif do_bp and rtype == 'BloodPressureSystolic' and val:
                                bp_records[time_stamp]['sys'] = f"{float(val):.0f}"
                            elif do_bp and rtype == 'BloodPressureDiastolic' and val:
                                bp_records[time_stamp]['dia'] = f"{float(val):.0f}"
                            elif do_glucose and rtype == 'BloodGlucose' and val:
                                u = elem.attrib.get('unit', 'mg/dL')
                                glucose_records.append((time_stamp, f"{float(val):.1f}", u))

                            # Steps
                            elif do_steps and rtype == 'StepCount' and val:
                                daily_steps[day] += float(val)

                        sample_count += 1
                        if sample_count % 350000 == 0:
                            self.after(0, self.update_status, f"Processed {sample_count:,} records...")
                        elem.clear()

                    if tag in ('Workout', 'Record', 'ActivitySummary', 'ExportDate', 'Me'):
                        if root is not None and elem is not root:
                            root.clear()

            # --- WRITE MARKDOWN ---
            self.after(0, self.update_status, "Generating Markdown report...")

            with open(out_path, 'w', encoding='utf-8') as md:
                md.write("# Apple Health — Exported Data Summary\n\n")
                md.write(f"- **Date Range:** `{d_from}` to `{d_to}`\n")
                md.write(f"- **Generated on:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n---\n\n")

                # 1. WORKOUTS
                if any_sport:
                    md.write("## 1. Workouts Log\n\n")
                    if workouts:
                        md.write("| Date & Time | Activity | Duration | Distance | Pace / Speed | Avg HR | Max HR | RPE | Calories |\n")
                        md.write("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
                        for w in workouts:
                            md.write(f"| {w['start']} | {w['type']} | {w['dur']} | {w['dist']} | {w['pace']} | {w['avg_hr']} | {w['max_hr']} | {w['rpe']} | {w['cal']} |\n")
                    else:
                        md.write("*No workouts recorded for selected sports in this date range.*\n")
                    md.write("\n")

                # 2. HEART & RECOVERY (WITH ALL-DAY STATS INCLUDED)
                if any([do_rhr, do_hrv, do_vo2, do_walk_hr, do_hr_rec, do_hr_daily]):
                    md.write("## 2. Daily Heart Rate, Recovery & All-Day Metrics\n\n")
                    all_h_days = sorted(set(
                        list(daily_resting_hr.keys()) + list(daily_hrv.keys()) +
                        list(daily_vo2.keys()) + list(daily_walk_hr.keys()) +
                        list(daily_hr_rec.keys()) + list(daily_hr_stats.keys())
                    ))
                    if all_h_days:
                        cols = ["Date", "Resting HR"]
                        if do_hr_daily:
                            cols.extend(["Daily Avg HR", "Min HR", "Max HR", "HR Samples"])
                        cols.extend(["Avg HRV SDNN", "HRV Range", "VO2 Max", "Walking HR", "HR Recovery (1 min)"])

                        md.write("| " + " | ".join(cols) + " |\n")
                        md.write("|" + "|".join([":---:" for _ in cols]) + "|\n")

                        for d in all_h_days:
                            row = [d]
                            # Resting HR
                            row.append(f"{daily_resting_hr[d]:.0f} bpm" if d in daily_resting_hr else "-")

                            # All-Day HR
                            if do_hr_daily:
                                cnt, sm, mn, mx = daily_hr_stats[d]
                                if cnt > 0:
                                    row.extend([f"{sm/cnt:.0f} bpm", f"{mn:.0f} bpm", f"{mx:.0f} bpm", f"{cnt:,}"])
                                else:
                                    row.extend(["-", "-", "-", "0"])

                            # HRV
                            if d in daily_hrv and len(daily_hrv[d]) > 0:
                                v = daily_hrv[d]
                                row.append(f"{sum(v)/len(v):.1f} ms")
                                row.append(f"{min(v):.0f}-{max(v):.0f} ms ({len(v)})")
                            else:
                                row.extend(["-", "-"])

                            # VO2 Max, Walk HR, Recovery
                            row.append(f"{daily_vo2[d]:.1f}" if d in daily_vo2 else "-")
                            row.append(f"{daily_walk_hr[d]:.0f} bpm" if d in daily_walk_hr else "-")
                            row.append(f"-{daily_hr_rec[d]:.0f} bpm" if d in daily_hr_rec else "-")

                            md.write("| " + " | ".join(row) + " |\n")
                    else:
                        md.write("*No recovery data found for the selected period.*\n")
                    md.write("\n")

                # 3. SLEEP & OVERNIGHT PHYSIOLOGY
                if do_sleep or any_sleep_bio:
                    md.write("## 3. Sleep Architecture & Overnight Physiology\n\n")
                    all_sleep_days = sorted(set(list(daily_sleep.keys()) + list(daily_sleep_bio.keys())))
                    if all_sleep_days:
                        md.write("| Night Date | Total Sleep | Deep Sleep | REM Sleep | Core Sleep | Awake Time | Resp Rate | Overnight SpO2 | Wrist Temp Dev | Breathing Disturbances |\n")
                        md.write("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
                        def fmt_m(m): return f"{int(m//60)}h {int(m%60):02d}m" if m > 0 else "-"
                        for d in all_sleep_days:
                            st = daily_sleep.get(d, {})
                            dp, rm, cr, aw = st.get('AsleepDeep', 0), st.get('AsleepREM', 0), st.get('AsleepCore', 0), st.get('Awake', 0)
                            tot = dp + rm + cr
                            tot_str = fmt_m(tot) if tot > 0 else "-"
                            dp_str = fmt_m(dp) if dp > 0 else "-"
                            rm_str = fmt_m(rm) if rm > 0 else "-"
                            cr_str = fmt_m(cr) if cr > 0 else "-"
                            aw_str = fmt_m(aw) if aw > 0 else "-"

                            bio = daily_sleep_bio.get(d, {'resp': [], 'spo2': [], 'temp': [], 'disturb': []})
                            resp_s = f"{sum(bio['resp'])/len(bio['resp']):.1f} brpm" if bio['resp'] else "-"
                            spo2_s = f"{sum(bio['spo2'])/len(bio['spo2']):.1f} %" if bio['spo2'] else "-"
                            temp_s = f"{sum(bio['temp'])/len(bio['temp']):+.2f} °C" if bio['temp'] else "-"
                            dist_s = f"{sum(bio['disturb'])/len(bio['disturb']):.1f}" if bio['disturb'] else "-"

                            md.write(f"| {d} | {tot_str} | {dp_str} | {rm_str} | {cr_str} | {aw_str} | {resp_s} | {spo2_s} | {temp_s} | {dist_s} |\n")
                    else:
                        md.write("*No sleep sessions recorded for the selected period.*\n")
                    md.write("\n")

                # 4. CLINICAL & VITALS
                if do_bp or do_glucose:
                    md.write("## 4. Clinical & Vitals (Blood Pressure & Blood Glucose)\n\n")
                    if do_bp:
                        md.write("### Blood Pressure\n\n")
                        if bp_records:
                            md.write("| Date & Time | Systolic (mmHg) | Diastolic (mmHg) | Reading |\n")
                            md.write("|:---|:---:|:---:|:---:|\n")
                            for ts in sorted(bp_records.keys()):
                                sys_v = bp_records[ts].get('sys', '-')
                                dia_v = bp_records[ts].get('dia', '-')
                                md.write(f"| {ts} | {sys_v} | {dia_v} | {sys_v}/{dia_v} mmHg |\n")
                        else:
                            md.write("*No blood pressure records found.*\n")
                        md.write("\n")

                    if do_glucose:
                        md.write("### Blood Glucose\n\n")
                        if glucose_records:
                            md.write("| Date & Time | Glucose Level | Unit |\n")
                            md.write("|:---|:---:|:---:|\n")
                            for ts, val_g, unit_g in sorted(glucose_records, key=lambda x: x[0]):
                                md.write(f"| {ts} | {val_g} | {unit_g} |\n")
                        else:
                            md.write("*No blood glucose records found.*\n")
                        md.write("\n")

                # 5. ACTIVITY RINGS & STEPS
                if do_rings or do_steps:
                    md.write("## 5. Daily Activity Rings & Steps\n\n")
                    all_act_days = sorted(set(list(daily_rings.keys()) + list(daily_steps.keys())))
                    if all_act_days:
                        md.write("| Date | Move (Burned/Goal kcal) | Exercise (Min/Goal) | Stand (Hours/Goal) | Total Steps |\n")
                        md.write("|:---:|:---:|:---:|:---:|:---:|\n")
                        for d in all_act_days:
                            mv, ex, st = daily_rings.get(d, ("-", "-", "-"))
                            stp = f"{daily_steps[d]:,.0f}" if d in daily_steps and daily_steps[d] > 0 else "-"
                            md.write(f"| {d} | {mv} | {ex} | {st} | {stp} |\n")
                    md.write("\n")

                # 6. RAW CONTINUOUS HEART RATE (OPTIONAL)
                if do_raw_hr:
                    md.write("## 6. Raw Continuous Heart Rate Readings\n\n")
                    if raw_hr_records:
                        md.write("| Date & Time | Heart Rate (bpm) |\n")
                        md.write("|:---|:---:|\n")
                        for ts, hr_v in raw_hr_records:
                            md.write(f"| {ts} | {hr_v} |\n")
                    else:
                        md.write("*No raw heart rate readings found for the selected period.*\n")
                    md.write("\n")

            elapsed = datetime.now() - start_time
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            self.after(0, self.on_export_finished, True, f"Export completed successfully in {elapsed.seconds} seconds!\nFile saved at: {out_path}\nSize: {size_mb:.2f} MB")

        except Exception as e:
            self.after(0, self.on_export_finished, False, str(e))

    def update_status(self, text):
        self.status_label.config(text=text)

    def on_export_finished(self, success, msg):
        self.progress_bar.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.is_processing = False
        if success:
            self.status_label.config(text="Export completed successfully!")
            messagebox.showinfo("Success", msg)
        else:
            self.status_label.config(text="An error occurred.")
            messagebox.showerror("Export Error", f"Details:\n{msg}")

if __name__ == '__main__':
    app = HealthExporterApp()
    app.mainloop()