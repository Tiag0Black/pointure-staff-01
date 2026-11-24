import os
import csv
import io
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "staff-management-public-site")
database_url = os.environ.get("DATABASE_URL", "sqlite:///staff_management.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    # Utilise le pilote Psycopg 3 installé dans requirements.txt.
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

PARIS = ZoneInfo("Europe/Paris")
GRADES = ["Administrateur", "Responsable", "Modérateur", "Helper", "Staff"]

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    staff_name = db.Column(db.String(80), nullable=False, index=True)
    grade = db.Column(db.String(40), nullable=False)
    # Datetimes are stored as naive UTC values for consistent database behavior.
    started_at = db.Column(db.DateTime, nullable=False, index=True)
    ended_at = db.Column(db.DateTime, nullable=True, index=True)

    @property
    def duration_seconds(self):
        end = self.ended_at or datetime.utcnow()
        return max(0, int((end - self.started_at).total_seconds()))

def local_time(value, fmt="%H:%M"):
    if value is None:
        return "—"
    return value.replace(tzinfo=timezone.utc).astimezone(PARIS).strftime(fmt)

def fmt_duration(seconds):
    hours, rem = divmod(int(seconds), 3600)
    minutes = rem // 60
    return f"{hours} h {minutes:02d} min"

def current_week_bounds():
    now_local = datetime.now(PARIS)
    monday_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now_local.weekday())
    next_monday_local = monday_local + timedelta(days=7)
    start_utc = monday_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = next_monday_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc, monday_local, next_monday_local

def weekly_seconds_for(name):
    start_utc, end_utc, _, _ = current_week_bounds()
    now = datetime.utcnow()
    rows = Service.query.filter(
        func.lower(Service.staff_name) == name.lower(),
        Service.started_at < end_utc,
        func.coalesce(Service.ended_at, now) > start_utc
    ).all()
    total = 0
    for row in rows:
        stop = min(row.ended_at or now, end_utc)
        begin = max(row.started_at, start_utc)
        total += max(0, int((stop - begin).total_seconds()))
    return total

@app.context_processor
def inject_helpers():
    return {"fmt_duration": fmt_duration, "local_time": local_time, "grades": GRADES, "timedelta": timedelta}

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/start")
def start_service():
    name = request.form.get("name", "").strip()
    grade = request.form.get("grade", "").strip()
    if not name or len(name) > 80 or grade not in GRADES:
        flash("Entre un nom valide et sélectionne un grade.", "error")
        return redirect(url_for("index"))

    active = Service.query.filter(
        func.lower(Service.staff_name) == name.lower(),
        Service.ended_at.is_(None)
    ).first()
    if active:
        flash("Un service est déjà en cours pour ce nom.", "error")
        return redirect(url_for("my_history", name=name))

    db.session.add(Service(staff_name=name, grade=grade, started_at=datetime.utcnow()))
    db.session.commit()
    flash(f"Service lancé pour {name}.", "success")
    return redirect(url_for("my_history", name=name))

@app.post("/stop")
def stop_service():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Indique ton nom pour arrêter le service.", "error")
        return redirect(url_for("index"))
    active = Service.query.filter(
        func.lower(Service.staff_name) == name.lower(),
        Service.ended_at.is_(None)
    ).order_by(Service.started_at.desc()).first()
    if not active:
        flash("Aucun service en cours pour ce nom.", "error")
        return redirect(url_for("index"))
    active.ended_at = datetime.utcnow()
    db.session.commit()
    flash("Heure de fin enregistrée et durée calculée.", "success")
    return redirect(url_for("my_history", name=name))

@app.route("/historique")
def history_lookup():
    name = request.args.get("name", "").strip()
    if not name:
        return redirect(url_for("index"))
    return redirect(url_for("my_history", name=name))

@app.route("/historique/<name>")
def my_history(name):
    rows = Service.query.filter(
        func.lower(Service.staff_name) == name.lower()
    ).order_by(Service.started_at.desc()).limit(200).all()
    active = next((r for r in rows if r.ended_at is None), None)
    return render_template(
        "history.html", name=name, rows=rows, active=active,
        weekly=fmt_duration(weekly_seconds_for(name))
    )

@app.get("/admin")
def admin_dashboard():
    start_utc, end_utc, start_local, end_local = current_week_bounds()
    services = Service.query.order_by(Service.started_at.desc()).limit(500).all()
    active_count = Service.query.filter(Service.ended_at.is_(None)).count()
    names = db.session.query(Service.staff_name).distinct().all()
    members = []
    for (name,) in names:
        member_rows = Service.query.filter(func.lower(Service.staff_name) == name.lower()).order_by(Service.started_at.asc()).all()
        current = next((r for r in reversed(member_rows) if r.ended_at is None), None)
        seconds = weekly_seconds_for(name)
        latest_grade = member_rows[-1].grade if member_rows else ""
        members.append({
            "name": name,
            "grade": current.grade if current else latest_grade,
            "active": current is not None,
            "weekly_seconds": seconds
        })
    members.sort(key=lambda m: m["weekly_seconds"], reverse=True)
    total_week = sum(m["weekly_seconds"] for m in members)
    return render_template("admin.html", members=members, services=services,
                           active_count=active_count, total_week=total_week,
                           week_start=start_local, week_end=end_local)

@app.get("/admin/export.csv")
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Nom STAFF", "Grade", "Début (heure de Paris)", "Fin (heure de Paris)", "Durée (minutes)"])
    rows = Service.query.order_by(Service.started_at.desc()).all()
    for row in rows:
        writer.writerow([
            row.staff_name, row.grade, local_time(row.started_at, "%d/%m/%Y %H:%M:%S"),
            local_time(row.ended_at, "%d/%m/%Y %H:%M:%S") if row.ended_at else "En service",
            round(row.duration_seconds / 60)
        ])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=pointages_staff.csv"})

@app.get("/health")
def health():
    return {"status": "ok"}

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
