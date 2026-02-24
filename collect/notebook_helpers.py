import json
import os
from pathlib import Path
from IPython.display import display, Image, HTML, clear_output
import ipywidgets as widgets

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
    
    # Recursively find all jpg images
    for img_path in root_path.rglob("*.jpg"):
        # Look for a metar.txt in the same parent's sibling 'metar' directory 
        # (matching collector's structure) or in the same folder
        metar_path = img_path.parent.parent / "metar" / "metar.txt"
        if not metar_path.exists():
            metar_path = img_path.parent / "metar.txt"
            
        captures.append({
            'timestamp': datetime_from_path(img_path),
            'path': str(img_path),
            'step': "Dir",
            'metar': str(metar_path) if metar_path.exists() else None
        })
    
    return sorted(captures, key=lambda x: x['timestamp'], reverse=True)

def datetime_from_path(path):
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

class CaptureBrowser:
    def __init__(self, log_path='data/collection.log', data_root='data'):
        self.log_path = log_path
        self.data_root = data_root
        self.all_captures = []
        self.main_output = widgets.Output()
        self.current_index = 0
        self.selected_session = "<ACTIVE>"

    def refresh_captures(self):
        if self.selected_session == "<ACTIVE>":
            self.all_captures = get_job_captures(self.log_path)
        else:
            self.all_captures = get_directory_captures(self.selected_session)

    def display_status_header(self):
        if self.selected_session != "<ACTIVE>":
            return
            
        status = get_job_status(self.log_path)
        if not status:
            return
        
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
            <div style='margin-bottom: 10px;'>
                <span style='margin-right: 20px;'><b>Completed:</b> {progress}</span>
                <span style='margin-right: 20px;'><b>Remaining:</b> {remaining}</span>
                <span><b>Total:</b> {total}</span>
            </div>
            """
        )
        display(widgets.VBox([metrics_html, bar], layout=widgets.Layout(margin='0 0 20px 0')))

    def show_review_mode(self, index):
        with self.main_output:
            clear_output(wait=True)
            self.current_index = index
            
            cap = self.all_captures[index]
            img_path = Path(cap['path'])
            metar_path = Path(cap['metar']) if cap.get('metar') else None
            
            btn_older = widgets.Button(description="← Older", layout=widgets.Layout(width='100px'))
            btn_gall = widgets.Button(description="Back to Gallery", button_style='info', layout=widgets.Layout(width='150px'))
            btn_newer = widgets.Button(description="Newer →", layout=widgets.Layout(width='100px'))
            
            if index >= len(self.all_captures) - 1:
                btn_older.disabled = True
            else:
                btn_older.on_click(lambda _: self.show_review_mode(index + 1))
                
            if index <= 0:
                btn_newer.disabled = True
            else:
                btn_newer.on_click(lambda _: self.show_review_mode(index - 1))
                
            btn_gall.on_click(lambda _: self.show_gallery_mode())
            
            display(widgets.HBox([btn_older, btn_gall, btn_newer]))
            
            metar_text = "Not available"
            if metar_path and metar_path.exists():
                metar_text = metar_path.read_text().strip()
            
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

    def show_gallery_mode(self):
        self.refresh_captures()
        with self.main_output:
            clear_output(wait=True)
            self.display_status_header()
            
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
                
                btn = widgets.Button(description=f"Review Step {cap['step']}", layout=widgets.Layout(width='200px'))
                def make_click_handler(idx): return lambda _: self.show_review_mode(idx)
                btn.on_click(make_click_handler(i))
                
                box = widgets.VBox([image_widget, metar_html, btn], 
                                   layout=widgets.Layout(margin='10px', align_items='center', border='1px solid #ddd', padding='5px'))
                items.append(box)
            
            grid = widgets.GridBox(items, layout=widgets.Layout(grid_template_columns="repeat(auto-fill, 225px)"))
            display(grid)

    def handle_session_change(self, change):
        self.selected_session = change['new']
        self.show_gallery_mode()

    def start(self):
        # Build dropdown options: <ACTIVE> + subdirs of data_root
        options = [("<ACTIVE>", "<ACTIVE>")]
        if Path(self.data_root).exists():
            subdirs = [d for d in Path(self.data_root).iterdir() if d.is_dir()]
            for d in sorted(subdirs, key=lambda x: x.name, reverse=True):
                options.append((d.name, str(d)))
        
        session_select = widgets.Dropdown(
            options=options,
            value="<ACTIVE>",
            description='Session:',
            style={'description_width': 'initial'},
            layout=widgets.Layout(width='300px')
        )
        session_select.observe(self.handle_session_change, names='value')
        
        display(session_select)
        display(self.main_output)
        self.show_gallery_mode()
