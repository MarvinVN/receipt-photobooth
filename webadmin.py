"""Local web editor for the photobooth.

Run on the Pi:   python3 ~/photobooth/webadmin.py
Open on a phone: http://photobooth.local:8080   (same network as the Pi)

Served entirely from the Pi, no internet needed. Reuses renderer.compose()
and photobooth.print_image() so the editor and the physical button produce
identical receipts. Local-network tool: no authentication.
"""
import io
import shutil
from pathlib import Path

import yaml
from flask import Flask, abort, jsonify, render_template, request, send_file
from PIL import Image

import renderer
import photobooth        # reuse the print path

BASE        = Path.home() / "photobooth"
EVENTS      = BASE / "events"
ALLOWED_IMG = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
LAST_CAPTURE = Path("/tmp/last_capture.jpg")

app = Flask(__name__)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def safe_event_dir(name: str) -> Path:
    """Resolve an event name to its folder, rejecting traversal / bad names."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        abort(400, "Bad event name")
    d = EVENTS / name
    if not d.is_dir():
        abort(404, "No such event")
    return d


def list_events():
    return sorted(p.name for p in EVENTS.iterdir() if p.is_dir())


def active_name() -> str:
    f = EVENTS / "active.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else "default"


def valid_new_name(name: str) -> bool:
    return bool(name) and all(c.isalnum() or c in "-_" for c in name)


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("editor.html")


# --------------------------------------------------------------------------
# Event management
# --------------------------------------------------------------------------
@app.route("/api/events")
def api_events():
    return jsonify({"events": list_events(), "active": active_name()})


@app.route("/api/active", methods=["POST"])
def api_active():
    name = (request.json or {}).get("event", "")
    safe_event_dir(name)
    (EVENTS / "active.txt").write_text(name + "\n", encoding="utf-8")
    return jsonify({"ok": True, "active": name})


@app.route("/api/event/new", methods=["POST"])
def api_new():
    data = request.json or {}
    src = data.get("from") or active_name()
    new = (data.get("name") or "").strip()
    if not valid_new_name(new):
        return jsonify({"ok": False, "error": "Use letters, numbers, - or _ only."}), 400
    dst = EVENTS / new
    if dst.exists():
        return jsonify({"ok": False, "error": "An event with that name already exists."}), 400
    shutil.copytree(safe_event_dir(src), dst)
    return jsonify({"ok": True, "name": new})


@app.route("/api/event/<name>", methods=["GET"])
def api_get_event(name):
    d = safe_event_dir(name)
    meta = {}
    if (d / "event.yaml").exists():
        meta = yaml.safe_load((d / "event.yaml").read_text(encoding="utf-8")) or {}
    quips = (d / "quips.txt").read_text(encoding="utf-8") if (d / "quips.txt").exists() else ""
    template = (d / "template.yaml").read_text(encoding="utf-8") if (d / "template.yaml").exists() else ""
    return jsonify({"meta": meta, "quips": quips, "template": template,
                    "has_logo": (d / "logo.png").exists()})


@app.route("/api/event/<name>", methods=["POST"])
def api_save_event(name):
    d = safe_event_dir(name)
    data = request.json or {}

    # Validate the template YAML before writing anything, so a typo can't brick a print.
    if "template" in data:
        try:
            yaml.safe_load(data["template"])
        except yaml.YAMLError as e:
            return jsonify({"ok": False, "error": f"Template YAML error: {e}"}), 400

    if "meta" in data:
        header = "# Per-event content. Edited by the web editor.\n"
        body = yaml.safe_dump(data["meta"], sort_keys=False, allow_unicode=True)
        (d / "event.yaml").write_text(header + body, encoding="utf-8")
    if "quips" in data:
        (d / "quips.txt").write_text(data["quips"], encoding="utf-8")
    if "template" in data:
        (d / "template.yaml").write_text(data["template"], encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/event/<name>/logo", methods=["POST"])
def api_logo(name):
    d = safe_event_dir(name)
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "No file uploaded."}), 400
    if Path(f.filename).suffix.lower() not in ALLOWED_IMG:
        return jsonify({"ok": False, "error": "Unsupported image type."}), 400
    try:
        Image.open(f.stream).save(d / "logo.png")     # normalize to PNG
    except Exception as e:
        return jsonify({"ok": False, "error": f"Could not read image: {e}"}), 400
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Preview + print
# --------------------------------------------------------------------------
@app.route("/api/preview")
def api_preview():
    name = request.args.get("event") or active_name()
    d = safe_event_dir(name)
    photo = None
    if LAST_CAPTURE.exists():                          # show a real photo if we have one
        photo = Image.open(LAST_CAPTURE).convert("RGB")
    try:
        img = renderer.compose(d, photo)
    except Exception as e:
        abort(500, f"Render error: {e}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/print", methods=["POST"])
def api_print():
    name = (request.json or {}).get("event") or active_name()
    d = safe_event_dir(name)
    try:
        img = renderer.compose(d, None)                # layout test: placeholder photo
        photobooth.print_image(img)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
