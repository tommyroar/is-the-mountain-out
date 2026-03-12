import yaml
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, UTC
from IPython.display import display, Image, HTML, clear_output
import ipywidgets as widgets

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
    def __init__(self, data_root='data', batch_size=20):
        self.data_root = Path(data_root)
        self.batch_size = batch_size
        self.labels = load_labels(self.data_root)
        self.state_file = self.data_root / "classifier_state.json"
        
        # Calculate total images in dataset for progress tracking
        print(f"Scanning {self.data_root} for images...")
        self.all_images = sorted([str(p.relative_to(self.data_root)) for p in self.data_root.rglob("*.jpg")])
        self.total_images = len(self.all_images)
        print(f"Found {self.total_images} total images.")

        # Load state (resume point)
        self.current_start_idx = 0
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.current_start_idx = state.get('last_index', 0)
                    print(f"Resuming from saved index: {self.current_start_idx}")
            except: pass

        # UI Components
        self.main_container = widgets.VBox()
        self.grid_container = widgets.GridBox(
            layout=widgets.Layout(grid_template_columns="repeat(2, 512px)", grid_gap="20px", justify_content="center")
        )
        self.stats_label = widgets.HTML()
        self.progress_bar = widgets.FloatProgress(
            value=0, min=0, max=100, description='Progress:',
            bar_style='info', layout=widgets.Layout(width='600px')
        )
        self.control_bar = widgets.HBox(layout=widgets.Layout(justify_content="center", margin="20px 0"))
        
        self.current_batch_images = []
        self.selected_indices = set()

    def _save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump({'last_index': self.current_start_idx}, f)

    def _get_next_batch(self):
        """Finds the next batch of images starting from the current_start_idx."""
        batch = []
        for i in range(self.current_start_idx, self.total_images):
            rel_path = self.all_images[i]
            if rel_path not in self.labels:
                batch.append({
                    'path': rel_path,
                    'abs_path': self.data_root / rel_path,
                    'index': i
                })
                if len(batch) >= self.batch_size:
                    self.current_start_idx = i
                    self._save_state()
                    return batch
        if not batch:
            self.current_start_idx = self.total_images
            self._save_state()
        return batch

    def refresh_ui(self):
        self.current_batch_images = self._get_next_batch()
        self.selected_indices = set()
        
        labeled_count = len(self.labels)
        out_count = list(self.labels.values()).count(1)
        not_count = list(self.labels.values()).count(0)
        
        percentage = (labeled_count / self.total_images * 100) if self.total_images > 0 else 0
        self.progress_bar.value = percentage
        
        stats_html = f"""
        <div style='text-align:center; font-family: sans-serif; margin-bottom: 10px;'>
            <div style='font-size: 18px;'><b>Total Progress:</b> {labeled_count} / {self.total_images} images (<b>{percentage:.1f}%</b>)</div>
            <div style='color: #666; font-size: 14px;'>
                Mountain Out: <span style='color: green; font-weight: bold;'>{out_count}</span> | 
                Not Out: <span style='color: #d9534f; font-weight: bold;'>{not_count}</span>
            </div>
            <div style='margin-top: 5px; color: #5bc0de; font-size: 12px;'>✓ Session state and labels are automatically checkpointed.</div>
        </div>
        """
        self.stats_label.value = stats_html
        
        if not self.current_batch_images:
            self.grid_container.children = [widgets.HTML("<h3 style='text-align:center; width:100%; color: green;'>🎉 All images in this directory have been labeled!</h3>")]
            self.control_bar.children = []
            return

        grid_items = []
        for i, item in enumerate(self.current_batch_images):
            with open(item['abs_path'], "rb") as f:
                img_widget = widgets.Image(value=f.read(), format='jpg', width=512)
            
            btn = widgets.ToggleButton(
                description="🏔️ MOUNTAIN IS OUT", 
                layout=widgets.Layout(width='512px', height='40px')
            )
            
            def make_toggle(idx, button):
                def on_toggle(change):
                    if change['new']: 
                        self.selected_indices.add(idx)
                        button.button_style = 'success'
                        button.icon = 'check-square-o'
                    else: 
                        self.selected_indices.discard(idx)
                        button.button_style = ''
                        button.icon = 'square-o'
                return on_toggle
                
            btn.observe(make_toggle(i, btn), names='value')
            grid_items.append(widgets.VBox([img_widget, btn]))
        
        self.grid_container.children = grid_items
        
        btn_submit = widgets.Button(
            description=f"Submit Batch (Unselected = NOT OUT)", 
            button_style='primary', 
            layout=widgets.Layout(width='600px', height='60px')
        )
        btn_submit.on_click(lambda _: self.submit_batch())
        self.control_bar.children = [btn_submit]

    def submit_batch(self):
        for i, item in enumerate(self.current_batch_images):
            path = item['path']
            self.labels[path] = 1 if i in self.selected_indices else 0
        save_labels(self.data_root, self.labels)
        self.refresh_ui()

    def start(self):
        header_html = """
        <div style="text-align: center; margin-bottom: 20px; font-family: sans-serif;">
            <h1 style="margin-bottom: 5px;">🏔️ Batch Mountain Classifier</h1>
            <h3 style="color: #d9534f; margin-top: 0;">Select images where the mountain IS out.</h3>
            <p><i>Unselected images are automatically marked as NOT OUT. Progress is saved on every submit.</i></p>
        </div>
        """
        self.main_container.children = [
            widgets.HTML(header_html),
            widgets.HBox([self.progress_bar], layout=widgets.Layout(justify_content="center")),
            self.stats_label,
            widgets.HTML("<hr>"),
            self.grid_container,
            widgets.HTML("<hr>"),
            self.control_bar
        ]
        display(self.main_container)
        self.refresh_ui()

class CaptureBrowser:
    def __init__(self, log_path='data/collection.log', data_root='data', batch_size=20):
        self.log_path = Path(log_path)
        self.data_root = Path(data_root)
        self.batch_size = batch_size
        
        # UI Components
        self.main_container = widgets.VBox()
        self.grid_container = widgets.GridBox(
            layout=widgets.Layout(grid_template_columns="repeat(2, 512px)", grid_gap="20px", justify_content="center")
        )
        self.status_label = widgets.HTML()
        self.control_bar = widgets.HBox(layout=widgets.Layout(justify_content="center", margin="20px 0"))
        
        self.all_captures = []
        self.current_page = 0

    def _load_captures(self):
        """Loads all captures from the log file, newest first."""
        captures = []
        if not self.log_path.exists():
            return []
            
        with open(self.log_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("event") == "CAPTURE" and entry.get("status") == "SUCCESS":
                        meta = entry["metadata"]
                        captures.append({
                            "timestamp": entry["timestamp"],
                            "image": meta["image_path"],
                            "metar": meta.get("metar_path")
                        })
                except: continue
        return sorted(captures, key=lambda x: x["timestamp"], reverse=True)

    def refresh_ui(self):
        self.all_captures = self._load_captures()
        
        start = self.current_page * self.batch_size
        end = start + self.batch_size
        page_items = self.all_captures[start:end]
        
        self.status_label.value = f"<div style='text-align:center;'><b>Total Captures:</b> {len(self.all_captures)} | <b>Showing:</b> {start+1}-{min(end, len(self.all_captures))}</div>"
        
        if not page_items:
            self.grid_container.children = [widgets.HTML("<h3 style='text-align:center; width:100%;'>No captures found in log.</h3>")]
            return

        grid_items = []
        for item in page_items:
            abs_img = Path(item['image'])
            if not abs_img.exists(): 
                abs_img = self.data_root.parent / item['image']
                
            try:
                with open(abs_img, "rb") as f:
                    img_widget = widgets.Image(value=f.read(), format='jpg', width=512)
                
                metar_text = "N/A"
                if item['metar']:
                    metar_p = Path(item['metar'])
                    if not metar_p.exists(): metar_p = self.data_root.parent / item['metar']
                    if metar_p.exists():
                        with open(metar_p, "r") as f: metar_text = f.read().strip()
                
                info = widgets.HTML(f"<div style='font-size:11px; color:#666;'>{item['timestamp']}<br><code>{metar_text}</code></div>")
                grid_items.append(widgets.VBox([img_widget, info]))
            except: continue
        
        self.grid_container.children = grid_items
        
        btn_prev = widgets.Button(description="⬅️ Newer", disabled=(self.current_page == 0))
        btn_next = widgets.Button(description="Older ➡️", disabled=(end >= len(self.all_captures)))
        
        def go_prev(_): self.current_page -= 1; self.refresh_ui()
        def go_next(_): self.current_page += 1; self.refresh_ui()
        
        btn_prev.on_click(go_prev)
        btn_next.on_click(go_next)
        self.control_bar.children = [btn_prev, btn_next]

    def start(self):
        display(self.main_container)
        self.main_container.children = [
            widgets.HTML("<h1 style='text-align:center;'>🏔️ Capture Monitor</h1>"),
            self.status_label,
            widgets.HTML("<hr>"),
            self.grid_container,
            widgets.HTML("<hr>"),
            self.control_bar
        ]
        self.refresh_ui()
