"""Live mountain visibility detector.

Runs inference against the live webcam, writes state, and sends an ntfy
notification whenever the mountain transitions from Not Out to visible
(Full or Partial).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
import requests
import torch

# Make repo imports work when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from train.config_loader import ConfigLoader
from train.utils import WebcamStream, WeatherFetcher
from train.model import ConvNextLoRAModel


CLASS_NAMES = {0: "Not Out", 1: "Full", 2: "Partial"}
STATE_FILE = Path("data/detection_state.json")
NTFY_KEY_FILE = Path("ntfy.key")


def load_topic() -> str:
    return NTFY_KEY_FILE.read_text().strip()


PRIORITY_MAP = {"min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5, "max": 5}


def send_ntfy(topic: str, title: str, message: str, priority: str = "default", tags: str = "mountain") -> None:
    # Use the JSON publish API so unicode in title/message isn't constrained to latin-1 headers.
    r = requests.post(
        "https://ntfy.sh/",
        json={
            "topic": topic,
            "title": title,
            "message": message,
            "priority": PRIORITY_MAP.get(priority, 3),
            "tags": [tags] if isinstance(tags, str) else list(tags),
        },
        timeout=10,
    )
    r.raise_for_status()


def read_state() -> Optional[dict]:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


def run_inference(cfg: ConfigLoader) -> tuple[int, list[float], list[float]]:
    """Return (predicted_class, probabilities, weather_vector)."""
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = ConvNextLoRAModel(
        num_classes=3,
        rank=cfg.lora_settings["rank"],
        alpha=cfg.lora_settings["alpha"],
        target_modules=cfg.lora_settings["target_modules"],
        device=device,
        checkpoint_dir=cfg.checkpoint_dir,
    )

    weather = WeatherFetcher(cfg.metar_station).get_weather_vector()

    stream = WebcamStream(cfg.webcam_url, device=device)
    try:
        tensor = stream.capture_to_tensor()
    finally:
        stream.release()
    if tensor is None:
        raise RuntimeError("Webcam capture failed")

    model.model_dict.eval()
    with torch.no_grad():
        logits = model.forward(tensor.to(device), weather.unsqueeze(0).to(device))
        probs = torch.softmax(logits, dim=1)[0].tolist()
        pred = int(torch.argmax(logits, dim=1).item())
    return pred, probs, weather.tolist()


@click.group()
def cli():
    pass


@cli.command()
@click.option("--config", default="mountain.toml")
def check(config: str):
    """Run inference and notify on Not Out → visible transition."""
    cfg = ConfigLoader(config)
    pred, probs, weather = run_inference(cfg)

    prev = read_state() or {}
    prev_class = prev.get("predicted_class")

    now_iso = datetime.now(timezone.utc).isoformat()
    state = {
        "predicted_class": pred,
        "predicted_label": CLASS_NAMES[pred],
        "probabilities": {CLASS_NAMES[i]: probs[i] for i in range(3)},
        "weather": {"visibility_norm": weather[0], "ceiling_norm": weather[1]},
        "prev_class": prev_class,
        "updated_at": now_iso,
    }

    print(f"[{now_iso}] Prediction: {CLASS_NAMES[pred]} (prev: {CLASS_NAMES.get(prev_class, 'none')})")
    for i in range(3):
        print(f"  {CLASS_NAMES[i]:10s}: {probs[i]:.1%}")

    # Notify on transition from Not Out (0) to visible (1 or 2).
    notified = False
    if prev_class == 0 and pred in (1, 2):
        topic = load_topic()
        visible_pct = (probs[1] + probs[2]) * 100
        label = CLASS_NAMES[pred]
        send_ntfy(
            topic,
            title="🏔️ THE MOUNTAIN IS OUT",
            message=f"Mount Rainier is visible ({label}). Confidence: {visible_pct:.1f}%",
            priority="urgent",
            tags="mountain_snow_capped",
        )
        notified = True
        print(f"  ↳ Notification sent ({label}, {visible_pct:.1f}%)")

    state["notified"] = notified
    write_state(state)


@cli.command()
@click.option("--config", default="mountain.toml")
def test(config: str):
    """Run one inference and send a test notification with the result."""
    cfg = ConfigLoader(config)
    pred, probs, weather = run_inference(cfg)
    label = CLASS_NAMES[pred]
    visible_pct = (probs[1] + probs[2]) * 100

    topic = load_topic()
    msg = (
        f"Test: model predicts {label} "
        f"(Not Out {probs[0]:.1%} / Full {probs[1]:.1%} / Partial {probs[2]:.1%}). "
        f"Visibility chance: {visible_pct:.1f}%."
    )
    send_ntfy(topic, title="🏔️ Detector test", message=msg, priority="default", tags="test_tube")
    print(f"Sent test notification: {msg}")


if __name__ == "__main__":
    cli()
