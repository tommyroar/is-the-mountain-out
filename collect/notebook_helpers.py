import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, UTC
from IPython.display import display, Image, HTML, clear_output
import ipywidgets as widgets
import matplotlib.pyplot as plt

def get_job_captures(log_path):
    """Reads the collection log and returns a list of successful captures."""
    log_path = Path(log_path)
    if not log_path.exists():
        return []
    
    captures = []
    with open(log_path, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get('event') == 'CAPTURE' and entry.get('status') == 'SUCCESS':
                    meta = entry.get('metadata', {})
                    if 'image_path' in meta:
                        captures.append({
                            'timestamp': entry['timestamp'],
                            'path': meta['image_path'],
                            'step': meta.get('step_index', 'N/A'),
                            'metar': meta.get('metar_path')
                        })
            except:
                pass
    return sorted(captures, key=lambda x: x['timestamp'], reverse=True)

def get_directory_captures(root_dir):
    """Recursively finds all JPG images in a directory and pairs them with METAR files if present."""
    root_path = Path(root_dir)
    captures = []
    for img_path in root_path.rglob("*.jpg"):
        metar_path = img_path.parent.parent / "metar" / "metar.txt"
        if not metar_path.exists():
            metar_path = img_path.parent / "metar.txt"
            
        captures.append({
            'timestamp': path_to_timestamp(img_path),
            'path': str(img_path),
            'step': "Dir",
            'metar': str(metar_path) if metar_path.exists() else None
        })
    return sorted(captures, key=lambda x: x['timestamp'], reverse=True)

def path_to_timestamp(path):
    """Attempts to extract a readable string from the path/filename."""
    return path.stem.replace("_UTC", "").replace("_", " ")

def get_job_status(log_path):
    """Extracts the latest progress status from the logs."""
    log_path = Path(log_path)
    if not log_path.exists():
        return None
    
    latest_progress = None
    with open(log_path, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get('event') == 'PROGRESS' and entry.get('status') == 'STATUS':
                    latest_progress = entry.get('metadata')
            except:
                pass
    return latest_progress

def get_upcoming_schedule():
    """Parses the launchd plist and plan_state to calculate upcoming capture times."""
    plist_path = Path.home() / "Library/LaunchAgents/com.mountain.collector.plist"
    state_path = Path("data/plan_state.json")
    
    if not (plist_path.exists() and state_path.exists()):
        return []

    try:
        # Extract intervals from plist using simple XML parsing (regex-like)
        import re
        content = plist_path.read_text()
        # Find all strings that look like intervals (e.g., 29897s)
        intervals_raw = re.findall(r'<string>(\d+)s</string>', content)
        intervals = [int(i) for i in intervals_raw]
        
        with open(state_path, "r") as f:
            state = json.load(f)
        
        current_step = state.get("step_index", 0)
        next_run_ts = state.get("next_run")
        
        upcoming = []
        if next_run_ts:
            curr_time = datetime.fromtimestamp(next_run_ts, UTC)
            upcoming.append(curr_time)
            
            # Future steps
            for i in range(current_step + 1, len(intervals)):
                curr_time += timedelta(seconds=intervals[i])
                upcoming.append(curr_time)
        return upcoming
    except Exception as e:
        print(f"Error parsing schedule: {e}")
        return []

class CaptureBrowser:
    def __init__(self, log_path='data/collection.log', data_root='data'):
        self.log_path = log_path
        self.data_root = data_root
        self.all_captures = []
        self.main_output = widgets.Output()
        self.control_panel = widgets.Output()
        self.current_index = 0
        self.selected_session = "<ACTIVE>"

    def refresh_captures(self):
        if self.selected_session == "<ACTIVE>":
            self.all_captures = get_job_captures(self.log_path)
        else:
            self.all_captures = get_directory_captures(self.selected_session)

    def render_control_panel(self):
        with self.control_panel:
            clear_output(wait=True)
            
            # 1. Session Selection
            options = [("<ACTIVE>", "<ACTIVE>")]
            if Path(self.data_root).exists():
                subdirs = [d for d in Path(self.data_root).iterdir() if d.is_dir()]
                for d in sorted(subdirs, key=lambda x: x.name, reverse=True):
                    options.append((d.name, str(d)))
            
            session_select = widgets.Dropdown(
                options=options,
                value=self.selected_session,
                description='Session:',
                style={'description_width': 'initial'},
                layout=widgets.Layout(width='300px')
            )
            session_select.observe(self.handle_session_change, names='value')
            
            # 2. Statistics (Only if ACTIVE)
            stats_box = widgets.VBox([])
            plot_output = widgets.Output()
            
            if self.selected_session == "<ACTIVE>":
                status = get_job_status(self.log_path)
                if status:
                    progress = status.get('progress', 0)
                    total = status.get('total', 0)
                    percentage = status.get('percentage', 0)
                    remaining = max(0, total - progress)
                    
                    bar = widgets.IntProgress(
                        value=progress, min=0, max=total,
                        description=f'{percentage}%',
                        bar_style='success',
                        layout=widgets.Layout(width='400px')
                    )
                    
                    metrics_html = widgets.HTML(
                        value=f"""
                        <div style='margin: 10px 0;'>
                            <span style='margin-right: 20px;'><b>Completed:</b> {progress}</span>
                            <span style='margin-right: 20px;'><b>Remaining:</b> {remaining}</span>
                            <span><b>Total:</b> {total}</span>
                        </div>
                        """
                    )
                    stats_box = widgets.VBox([metrics_html, bar])
                
                # 3. Schedule Plot
                upcoming = get_upcoming_schedule()
                if upcoming:
                    with plot_output:
                        self.render_schedule_plot(upcoming)

            # Assemble Panel
            panel_layout = widgets.VBox([
                session_select,
                stats_box,
                plot_output
            ], layout=widgets.Layout(padding='15px', border='1px solid #ccc', margin='0 0 20px 0', background='#f9f9f9'))
            
            display(panel_layout)

    def render_schedule_plot(self, upcoming):
        """Renders a scatter plot of upcoming capture times."""
        plt.figure(figsize=(10, 3))
        
        # X = Days (relative to today), Y = Time of day (hours)
        now = datetime.now(UTC)
        days = [(d - now).total_seconds() / 86400 for d in upcoming]
        times = [d.hour + d.minute/60.0 for d in upcoming]
        
        plt.scatter(days, times, alpha=0.6, c='#1f77b4', edgecolors='none', s=50)
        
        plt.title("Upcoming Capture Schedule")
        plt.xlabel("Days from Now")
        plt.ylabel("Hour of Day (UTC)")
        plt.yticks(range(0, 25, 4))
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.show()

    def show_review_mode(self, index):
        with self.main_output:
            clear_output(wait=True)
            self.current_index = index
            
            cap = self.all_captures[index]
            img_path = Path(cap['path'])
            metar_path = Path(cap['metar']) if cap.get('metar') else None
            
            metar_text = metar_path.read_text().strip() if (metar_path and metar_path.exists()) else "Not available"
            metar_box = widgets.HTML(
                value=f"""
                <div style='border: 1px solid #2196f3; border-left: 5px solid #2196f3; padding: 10px; margin: 10px 0; background: #e3f2fd;'>
                    <b style='color: #1976d2;'>METAR Weather Data</b><br>
                    <code style='font-family: monospace;'>{metar_text}</code>
                </div>
                """
            )
            
            display(HTML(f"<h3>Step {cap['step']} <small style='color: #666;'>({cap['timestamp']})</small></h3>"))
            display(metar_box)
            
            if img_path.exists():
                display(Image(filename=str(img_path), width=1000))
            else:
                print(f"Image not found: {img_path}")

            btn_older = widgets.Button(description="← Older", layout=widgets.Layout(width='100px'))
            btn_gall = widgets.Button(description="Back to Gallery", button_style='info', layout=widgets.Layout(width='150px'))
            btn_newer = widgets.Button(description="Newer →", layout=widgets.Layout(width='100px'))
            
            if index >= len(self.all_captures) - 1: btn_older.disabled = True
            else: btn_older.on_click(lambda _: self.show_review_mode(index + 1))
                
            if index <= 0: btn_newer.disabled = True
            else: btn_newer.on_click(lambda _: self.show_review_mode(index - 1))
                
            btn_gall.on_click(lambda _: self.show_gallery_mode())
            display(widgets.HBox([btn_older, btn_gall, btn_newer], layout=widgets.Layout(margin='20px 0')))

    def show_gallery_mode(self):
        self.refresh_captures()
        with self.main_output:
            clear_output(wait=True)
            
            if not self.all_captures:
                label = "active session" if self.selected_session == "<ACTIVE>" else f"directory {self.selected_session}"
                print(f"No captures found in {label}.")
                return

            items = []
            for i, cap in enumerate(self.all_captures):
                img_path = Path(cap['path'])
                metar_path = Path(cap['metar']) if cap.get('metar') else None
                if not img_path.exists(): continue
                
                with open(img_path, "rb") as f:
                    image_widget = widgets.Image(value=f.read(), format='jpg', width=200, height=150)
                
                metar_preview = metar_path.read_text().strip() if (metar_path and metar_path.exists()) else "No weather data"
                metar_html = widgets.HTML(
                    value=f"<div style='width: 180px; font-size: 11px; color: #555; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: monospace;'>{metar_preview}</div>",
                    layout=widgets.Layout(margin='5px 0')
                )
                
                label = f"🔍 Step {cap['step']}" if cap['step'] != "Dir" else "🔍 Review"
                btn = widgets.Button(description=label, layout=widgets.Layout(width='200px'))
                def make_click_handler(idx): return lambda _: self.show_review_mode(idx)
                btn.on_click(make_click_handler(i))
                
                box = widgets.VBox([image_widget, metar_html, btn], 
                                   layout=widgets.Layout(margin='10px', align_items='center', border='1px solid #ddd', padding='5px'))
                items.append(box)
            
            grid = widgets.GridBox(items, layout=widgets.Layout(grid_template_columns="repeat(auto-fill, 225px)"))
            display(grid)

    def handle_session_change(self, change):
        self.selected_session = change['new']
        self.render_control_panel()
        self.show_gallery_mode()

    def start(self):
        display(self.control_panel)
        display(self.main_output)
        self.render_control_panel()
        self.show_gallery_mode()
