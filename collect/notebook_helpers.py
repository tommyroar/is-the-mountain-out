import yaml
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, UTC
from IPython.display import display, Image, HTML, clear_output
import ipywidgets as widgets
import matplotlib.pyplot as plt

def get_data_root():
    """Resolves data root: ENV > .mountain_data_root file > default 'data'."""
    root_env = os.environ.get("MOUNTAIN_DATA_ROOT")
    if root_env:
        return root_env
        
    state_file = Path("data/.mountain_data_root")
    if state_file.exists():
        return state_file.read_text().strip()
        
    return "data"

def load_labels(data_root):
    """Loads the training index from labels.yaml."""
    labels_path = Path(data_root) / "labels.yaml"
    if labels_path.exists():
        with open(labels_path, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

def save_labels(data_root, labels):
    """Saves the training index to labels.yaml."""
    labels_path = Path(data_root) / "labels.yaml"
    with open(labels_path, 'w') as f:
        yaml.safe_dump(labels, f)

class MountainClassifier:
    def __init__(self, data_root='data'):
        self.data_root = Path(data_root)
        self.labels = load_labels(self.data_root)
        self.all_captures = self._scan_captures()
        self.unlabeled_indices = [i for i, c in enumerate(self.all_captures) if c['path'] not in self.labels]
        self.current_unlabeled_idx = 0
        
        self.main_container = widgets.VBox()
        self.status_label = widgets.HTML()
        self.img_container = widgets.Box()
        self.stats_box = widgets.HTML()

    def _scan_captures(self):
        """Recursively finds all JPG images in the data root."""
        captures = []
        for img_path in self.data_root.rglob("*.jpg"):
            # Skip if in a 'test' directory or similar if needed
            rel_path = str(img_path.relative_to(self.data_root))
            captures.append({
                'path': rel_path,
                'abs_path': img_path,
                'timestamp': path_to_timestamp(img_path)
            })
        return sorted(captures, key=lambda x: x['timestamp'], reverse=True)

    def refresh_stats(self):
        total = len(self.all_captures)
        labeled = len(self.labels)
        out_count = list(self.labels.values()).count(1)
        not_out_count = list(self.labels.values()).count(0)
        
        self.stats_box.value = f"""
        <div style='display: flex; gap: 20px; margin-bottom: 10px; font-family: sans-serif;'>
            <div><b>Total:</b> {total}</div>
            <div style='color: green;'><b>Labeled:</b> {labeled}</div>
            <div style='color: #d9534f;'><b>Unlabeled:</b> {total - labeled}</div>
            <div style='border-left: 1px solid #ccc; padding-left: 20px;'>
                <b>Out (1):</b> {out_count} | <b>Not Out (0):</b> {not_out_count}
            </div>
        </div>
        """

    def classify(self, label):
        if self.current_unlabeled_idx < len(self.unlabeled_indices):
            idx = self.unlabeled_indices[self.current_unlabeled_idx]
            cap = self.all_captures[idx]
            
            if label is not None:
                self.labels[cap['path']] = label
                save_labels(self.data_root, self.labels)
            
            self.current_unlabeled_idx += 1
            self.render_current()

    def render_current(self):
        self.refresh_stats()
        
        if self.current_unlabeled_idx >= len(self.unlabeled_indices):
            self.status_label.value = "<h3>🎉 All images in this directory have been labeled!</h3>"
            self.img_container.children = []
            return

        idx = self.unlabeled_indices[self.current_unlabeled_idx]
        cap = self.all_captures[idx]
        
        self.status_label.value = f"<h3>Classifying: <small style='color: #666;'>{cap['path']} ({cap['timestamp']})</small></h3>"
        
        with open(cap['abs_path'], "rb") as f:
            img_widget = widgets.Image(value=f.read(), format='jpg', width=800)
        
        self.img_container.children = [img_widget]

    def start(self):
        btn_out = widgets.Button(description="MOUNTAIN IS OUT (1)", button_style='success', layout=widgets.Layout(width='200px', height='50px'))
        btn_not = widgets.Button(description="NOT OUT (0)", button_style='danger', layout=widgets.Layout(width='200px', height='50px'))
        btn_skip = widgets.Button(description="SKIP", button_style='warning', layout=widgets.Layout(width='100px', height='50px'))
        
        btn_out.on_click(lambda _: self.classify(1))
        btn_not.on_click(lambda _: self.classify(0))
        btn_skip.on_click(lambda _: self.classify(None))
        
        controls = widgets.HBox([btn_out, btn_not, btn_skip], layout=widgets.Layout(margin='20px 0', gap='10px'))
        
        self.main_container.children = [self.stats_box, self.status_label, self.img_container, controls]
        display(self.main_container)
        self.render_current()

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
        # Use a VBox container instead of Output to prevent scroll jumping
        self.main_container = widgets.VBox()
        self.control_container = widgets.VBox()
        self.current_index = 0
        self.selected_session = "<ACTIVE>"

    def refresh_captures(self):
        if self.selected_session == "<ACTIVE>":
            self.all_captures = get_job_captures(self.log_path)
        else:
            self.all_captures = get_directory_captures(self.selected_session)

    def render_control_panel(self):
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
                    clear_output(wait=True)
                    self.render_schedule_plot(upcoming)

        # Assemble Panel
        panel_layout = widgets.VBox([
            session_select,
            stats_box,
            plot_output
        ], layout=widgets.Layout(padding='15px', border='1px solid #ccc', margin='0 0 20px 0', background='#f9f9f9'))
        
        self.control_container.children = [panel_layout]

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
        
        header = widgets.HTML(f"<h3>Step {cap['step']} <small style='color: #666;'>({cap['timestamp']})</small></h3>")
        
        if img_path.exists():
            with open(img_path, "rb") as f:
                img_widget = widgets.Image(value=f.read(), format='jpg', width=1000)
        else:
            img_widget = widgets.HTML(f"Image not found: {img_path}")

        btn_older = widgets.Button(description="← Older", layout=widgets.Layout(width='100px'))
        btn_gall = widgets.Button(description="Back to Gallery", button_style='info', layout=widgets.Layout(width='150px'))
        btn_newer = widgets.Button(description="Newer →", layout=widgets.Layout(width='100px'))
        
        if index >= len(self.all_captures) - 1: btn_older.disabled = True
        else: btn_older.on_click(lambda _: self.show_review_mode(index + 1))
            
        if index <= 0: btn_newer.disabled = True
        else: btn_newer.on_click(lambda _: self.show_review_mode(index - 1))
            
        btn_gall.on_click(lambda _: self.show_gallery_mode())
        nav_box = widgets.HBox([btn_older, btn_gall, btn_newer], layout=widgets.Layout(margin='20px 0'))
        
        self.main_container.children = [header, metar_box, img_widget, nav_box]

    def show_gallery_mode(self):
        self.refresh_captures()
        
        if not self.all_captures:
            label = "active session" if self.selected_session == "<ACTIVE>" else f"directory {self.selected_session}"
            self.main_container.children = [widgets.HTML(f"No captures found in {label}.")]
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
            
            btn = widgets.Button(description="🔍", layout=widgets.Layout(width='200px'))
            btn.on_click(lambda _, idx=i: self.show_review_mode(idx))
            
            box = widgets.VBox([image_widget, metar_html, btn], 
                                layout=widgets.Layout(margin='10px', align_items='center', border='1px solid #ddd', padding='5px'))
            items.append(box)
        
        grid = widgets.GridBox(items, layout=widgets.Layout(grid_template_columns="repeat(auto-fill, 225px)"))
        self.main_container.children = [grid]

    def handle_session_change(self, change):
        self.selected_session = change['new']
        self.render_control_panel()
        self.show_gallery_mode()

    def start(self):
        display(self.control_container)
        display(self.main_container)
        self.render_control_panel()
        self.show_gallery_mode()
