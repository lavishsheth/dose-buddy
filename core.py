"""Core logic for Dose Buddy: parsing model output, schedules, .ics export."""
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DATA_FILE = Path(__file__).with_name("schedule.json")

SYSTEM_PROMPT = """You read medicine instructions and return a schedule as JSON.
Return ONLY this JSON shape:
{"medicines":[{"name":"string","dose":"string","times":["HH:MM"],"days":0,"notes":"string"}]}

Rules:
- times use 24-hour HH:MM.
- days is how many days the course lasts. Use 0 if ongoing or not stated.
- Time mapping when no clock time is given: morning 08:00, afternoon 14:00,
  evening 18:00, night/bedtime 21:30, after breakfast 09:00, after lunch 14:00,
  after dinner 21:00.
- "once a day" = 08:00. "twice a day" = 08:00 and 20:00.
  "three times a day" = 08:00, 14:00, 20:00. "every 8 hours" = 06:00, 14:00, 22:00.
  "every 12 hours" = 08:00, 20:00. "every 6 hours" = 06:00, 12:00, 18:00, 00:00.
- Copy the medicine name and dose exactly as written. Never guess a name or dose.
  If something is unreadable, put "UNCLEAR" in that field.
- Put things like "with food" or "before meals" in notes.
- Output JSON only, no extra text."""

_TIME_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.I)


def clean_time(value):
    """Turn '8:00', '08:00', '8am', '9:30 pm' into 'HH:MM'. Returns None if invalid."""
    m = _TIME_RE.match(str(value))
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def parse_times(value):
    """Accept a list or a comma-separated string. Returns sorted unique valid HH:MM."""
    if value is None:
        return []
    parts = value if isinstance(value, (list, tuple)) else str(value).split(",")
    cleaned = {clean_time(p) for p in parts}
    return sorted(t for t in cleaned if t)


def normalize_med(m):
    try:
        days = int(m.get("days") or 0)
    except (TypeError, ValueError):
        days = 0
    return {
        "name": str(m.get("name", "")).strip(),
        "dose": str(m.get("dose", "")).strip(),
        "times": parse_times(m.get("times")),
        "days": max(days, 0),
        "notes": str(m.get("notes", "") or "").strip(),
    }


def extract_meds(text):
    """Parse the model's reply into a list of normalized medicines. Tolerates extra text."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    meds = data.get("medicines", []) if isinstance(data, dict) else data
    return [normalize_med(x) for x in meds if isinstance(x, dict)]


def is_active(med, start, day):
    offset = (day - start).days
    if offset < 0:
        return False
    return med["days"] == 0 or offset < med["days"]


def doses_for_day(meds, start, day):
    """Sorted list of (HH:MM, name, dose, notes) due on `day`."""
    out = []
    for med in meds:
        if is_active(med, start, day):
            for t in med["times"]:
                out.append((t, med["name"], med["dose"], med["notes"]))
    return sorted(out)


def save_schedule(person, start, meds):
    DATA_FILE.write_text(json.dumps(
        {"person": person, "start": start.isoformat(), "medicines": meds}, indent=2))


def load_schedule():
    if not DATA_FILE.exists():
        return None
    data = json.loads(DATA_FILE.read_text())
    data["start"] = date.fromisoformat(data["start"])
    return data


def _esc(s):
    return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def make_ics(person, start, meds):
    """Calendar file with one repeating alarm per dose. Works offline on any phone."""
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Dose Buddy//EN"]
    for med in meds:
        for t in med["times"]:
            h, m = t.split(":")
            begin = datetime(start.year, start.month, start.day, int(h), int(m))
            end = begin + timedelta(minutes=5)
            summary = _esc(f"Take {med['name']} {med['dose']}".strip())
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uuid.uuid4()}@dosebuddy",
                f"DTSTAMP:{now}",
                f"DTSTART:{begin.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{_esc(med['notes'] or 'Reminder for ' + person)}",
            ]
            lines.append("RRULE:FREQ=DAILY" + (f";COUNT={med['days']}" if med["days"] else ""))
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{summary}",
                      "TRIGGER:PT0M", "END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
