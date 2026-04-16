import json
import os
import uuid
from datetime import datetime, timedelta

import streamlit as st

st.set_page_config(page_title="Domowa apka zadań", page_icon="🏠", layout="centered")

# --- STAŁE ---
DATA_FILE = "data.json"
GENERAL_TASK_LABEL = "Ogólne (kto pierwszy, ten lepszy)"
WORKERS = ["Bartek", "Tomek"]
USERS = ["Mama", *WORKERS]
ADMIN_USER = "Admin"
ADMIN_PASSWORD = "123"

PRESET_TASKS = [
    "Odkurzanie pokoju",
    "Odkurzanie parteru",
    "Odkurzanie 1 piętra",
    "Odkurzanie 2 piętra",
    "Odkurzanie łazienki",
    "Wyrzucenie śmieci",
    "Rozpakowanie zmywarki",
]

DEADLINE_HOURS = 24


# --- DANE ---
def default_data():
    return {
        "tasks": [],
        "history": [],
        "points": {worker: 0 for worker in WORKERS},
    }


def normalize_data(data):
    data = data or {}
    data.setdefault("tasks", [])
    data.setdefault("history", [])
    data.setdefault("points", {})

    # Migracja "Ja" -> "Bartek"
    if "Ja" in data["points"]:
        data["points"]["Bartek"] = data["points"].get("Bartek", 0) + data["points"].pop("Ja")

    for worker in WORKERS:
        data["points"].setdefault(worker, 0)

    # tylko WORKERS zbierają punkty
    data["points"] = {k: v for k, v in data["points"].items() if k in WORKERS}

    # migracje treści
    for task in data["tasks"]:
        if task.get("assignee") == "Ja":
            task["assignee"] = "Bartek"

        # deadline migration for old tasks
        if "deadline_at" not in task:
            raw_added = task.get("created_at") or task.get("date_added")
            try:
                added_dt = datetime.strptime(raw_added, "%Y-%m-%d %H:%M")
            except Exception:
                added_dt = datetime.now()
            task["created_at"] = added_dt.strftime("%Y-%m-%d %H:%M")
            task["deadline_at"] = (added_dt + timedelta(hours=DEADLINE_HOURS)).strftime("%Y-%m-%d %H:%M")

        # zasada: prywatne zadania = 0 pkt
        if task.get("assignee") in WORKERS:
            task["points"] = 0

    for entry in data["history"]:
        if entry.get("completed_by") == "Ja":
            entry["completed_by"] = "Bartek"

    return data


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return normalize_data(json.load(f))
            except json.JSONDecodeError:
                return default_data()
    return default_data()


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# --- SESSION STATE ---
if "db" not in st.session_state:
    st.session_state.db = load_data()
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False


# --- HELPERY ---
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def dt_to_str(dt: datetime):
    return dt.strftime("%Y-%m-%d %H:%M")


def parse_dt(dt_str: str):
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")


def is_overdue(task):
    try:
        return datetime.now() > parse_dt(task["deadline_at"])
    except Exception:
        return False


def time_left_text(task):
    try:
        deadline = parse_dt(task["deadline_at"])
        diff = deadline - datetime.now()
        if diff.total_seconds() <= 0:
            return "⛔ Po terminie"
        hours = int(diff.total_seconds() // 3600)
        mins = int((diff.total_seconds() % 3600) // 60)
        return f"⏳ Zostało: {hours}h {mins}m"
    except Exception:
        return "⏳ Brak danych o terminie"


# --- AKCJE ---
def add_task(name, description, assignee, points):
    created_at = datetime.now()
    deadline_at = created_at + timedelta(hours=DEADLINE_HOURS)

    # prywatne zadania = 0 pkt
    if assignee in WORKERS:
        points = 0

    st.session_state.db["tasks"].append(
        {
            "id": str(uuid.uuid4()),
            "name": name.strip(),
            "description": description.strip(),
            "assignee": assignee,
            "points": int(points),
            "created_at": dt_to_str(created_at),
            "date_added": dt_to_str(created_at),  # zachowanie kompatybilności
            "deadline_at": dt_to_str(deadline_at),
        }
    )
    save_data(st.session_state.db)
    st.toast("Zadanie dodane ✅")


def complete_task(task_id, user_name):
    tasks = st.session_state.db["tasks"]

    if user_name not in st.session_state.db["points"]:
        st.error("Nieznany profil użytkownika. Wybierz profil ponownie.")
        return

    task_to_complete = next((t for t in tasks if t["id"] == task_id), None)
    if not task_to_complete:
        return

    st.session_state.db["tasks"] = [t for t in tasks if t["id"] != task_id]

    st.session_state.db["history"].insert(
        0,
        {
            "name": task_to_complete["name"],
            "completed_by": user_name,
            "points": int(task_to_complete["points"]),
            "was_overdue": is_overdue(task_to_complete),
            "date_completed": now_str(),
            "assignee": task_to_complete.get("assignee"),
        },
    )
    st.session_state.db["history"] = st.session_state.db["history"][:50]

    # punkty tylko dla zadań ogólnych (prywatne i tak mają 0)
    st.session_state.db["points"][user_name] += int(task_to_complete["points"])

    save_data(st.session_state.db)
    st.toast(f"Super! +{task_to_complete['points']} pkt 🎉")


# --- STYL ---
st.markdown(
    """
    <style>
        .stMainBlockContainer {padding-top: 1.2rem; max-width: 900px;}
        .welcome-note {text-align: center; opacity: .9; margin-bottom: .8rem;}
        .pill {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-right: .35rem;
        }
        .pill-general {background: #e0f2fe; color: #075985;}
        .pill-private {background: #f3e8ff; color: #6b21a8;}
        .pill-overdue {background: #fee2e2; color: #991b1b;}
        .task-box {
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 10px;
            background: #ffffff;
        }
        .task-box-overdue {
            border: 1px solid #ef4444 !important;
            background: #fff1f2 !important;
        }
        .soft-card {
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 10px 12px;
            margin-bottom: 8px;
            background: #fafafa;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏠 Domowy Tasker")
st.markdown("<p class='welcome-note'>Zadania domowe, terminy i punkty</p>", unsafe_allow_html=True)

# --- LOGOWANIE ---
if st.session_state.current_user is None and not st.session_state.is_admin:
    st.subheader("Wybierz profil")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("👑 Mama", use_container_width=True):
            st.session_state.current_user = "Mama"
            st.rerun()
    with c2:
        if st.button("🙋 Bartek", use_container_width=True):
            st.session_state.current_user = "Bartek"
            st.rerun()
    with c3:
        if st.button("🧢 Tomek", use_container_width=True):
            st.session_state.current_user = "Tomek"
            st.rerun()
    with c4:
        if st.button("🛡️ Admin", use_container_width=True):
            st.session_state.current_user = ADMIN_USER
            st.rerun()

    st.info("Najpierw wybierz profil.")
    st.stop()

# ekran hasła admina
if st.session_state.current_user == ADMIN_USER and not st.session_state.is_admin:
    st.subheader("Logowanie Admin")
    with st.form("admin_login_form", clear_on_submit=True):
        pwd = st.text_input("Hasło", type="password", placeholder="Wpisz hasło admina")
        submitted = st.form_submit_button("Zaloguj jako Admin")
        if submitted:
            if pwd == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.success("Zalogowano jako Admin ✅")
                st.rerun()
            else:
                st.error("Niepoprawne hasło.")

    if st.button("⬅️ Wróć do wyboru profilu"):
        st.session_state.current_user = None
        st.session_state.is_admin = False
        st.rerun()
    st.stop()

current_user = st.session_state.current_user
is_admin = st.session_state.is_admin

# top bar
left, right = st.columns([4, 1])
with left:
    role = "Admin" if is_admin else current_user
    st.caption(f"Zalogowano jako: **{role}**")
with right:
    if st.button("Wyloguj", use_container_width=True):
        st.session_state.current_user = None
        st.session_state.is_admin = False
        st.rerun()

st.divider()

# --- PANEL DODAWANIA ZADAŃ (MAMA + ADMIN) ---
if current_user == "Mama" or is_admin:
    st.header("Panel zarządzania zadaniami")

    task_mode = st.radio("Rodzaj zadania", ["Ze spisu", "Nowe zadanie"], horizontal=True)

    with st.form("add_task_form", clear_on_submit=True):
        if task_mode == "Ze spisu":
            task_name = st.selectbox("Wybierz zadanie z listy", PRESET_TASKS)
        else:
            task_name = st.text_input(
                "Wpisz nazwę nowego zadania",
                placeholder="Np. Umycie naczyń po kolacji",
            )

        task_desc = st.text_area("Opis (opcjonalnie)", placeholder="Dodatkowe wskazówki...")

        c1, c2 = st.columns(2)
        with c1:
            task_assignee = st.selectbox("Dla kogo?", [GENERAL_TASK_LABEL, *WORKERS])

        with c2:
            if task_assignee == GENERAL_TASK_LABEL:
                task_points = st.number_input("Punkty (zadanie ogólne)", min_value=1, value=10, step=1)
            else:
                st.text_input("Punkty (zadanie prywatne)", value="0", disabled=True)
                task_points = 0

        st.caption(f"⏱️ Deadline ustawiany automatycznie: **{DEADLINE_HOURS}h** od dodania zadania.")

        if st.form_submit_button("Dodaj zadanie ➕", use_container_width=True):
            if not task_name or not task_name.strip():
                st.error("Podaj nazwę zadania.")
            else:
                add_task(task_name, task_desc, task_assignee, task_points)
                st.rerun()

# --- PANEL WYKONYWANIA (WORKERS) ---
if current_user in WORKERS:
    st.header(f"Cześć {current_user} 👋")
    st.subheader("Twoje zadania")

    tasks_to_show = [
        t for t in st.session_state.db["tasks"]
        if t["assignee"] in [current_user, GENERAL_TASK_LABEL]
    ]

    if not tasks_to_show:
        st.success("Na teraz brak zadań. Super robota 😎")
    else:
        # najpierw pilne i przeterminowane
        tasks_to_show = sorted(tasks_to_show, key=lambda t: parse_dt(t["deadline_at"]))

        for task in tasks_to_show:
            overdue = is_overdue(task)
            assignee = task.get("assignee", GENERAL_TASK_LABEL)
            is_general = assignee == GENERAL_TASK_LABEL

            box_cls = "task-box task-box-overdue" if overdue else "task-box"
            st.markdown(f"<div class='{box_cls}'>", unsafe_allow_html=True)

            badges = []
            if is_general:
                badges.append("<span class='pill pill-general'>OGÓLNE</span>")
            else:
                badges.append("<span class='pill pill-private'>PRYWATNE</span>")
            if overdue:
                badges.append("<span class='pill pill-overdue'>PO TERMINIE</span>")

            st.markdown("".join(badges), unsafe_allow_html=True)
            st.markdown(f"### {task['name']}")
            if task.get("description"):
                st.caption(task["description"])

            pts_text = f"{task['points']} pkt" if is_general else "0 pkt (zadanie prywatne)"
            st.caption(
                f"👤 Dla: {assignee} • 🪙 {pts_text} • "
                f"🕒 Dodano: {task.get('created_at', task.get('date_added', '-'))} • "
                f"📅 Deadline: {task.get('deadline_at', '-')}"
            )
            st.caption(time_left_text(task))

            if st.button("Zrobione ✅", key=task["id"], use_container_width=True):
                complete_task(task["id"], current_user)
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

# ADMIN - podgląd wszystkich otwartych zadań
if is_admin:
    st.subheader("🛡️ Podgląd wszystkich aktywnych zadań")
    all_tasks = st.session_state.db["tasks"]
    if not all_tasks:
        st.info("Brak aktywnych zadań.")
    else:
        for t in sorted(all_tasks, key=lambda x: parse_dt(x["deadline_at"])):
            overdue = "🔴" if is_overdue(t) else "🟢"
            st.markdown(
                f"- {overdue} **{t['name']}** | dla: `{t['assignee']}` | "
                f"pkt: `{t['points']}` | deadline: `{t['deadline_at']}`"
            )

st.markdown("---")

# --- RANKING + HISTORIA ---
score_col, history_col = st.columns(2)

with score_col:
    st.subheader("🏆 Ranking")
    ranking = sorted(st.session_state.db["points"].items(), key=lambda item: item[1], reverse=True)
    for place, (user, points) in enumerate(ranking):
        medal = "🥇" if place == 0 else "🥈" if place == 1 else "🥉"
        user_label = f"**{user}**" if user == current_user else user
        st.markdown(f"{medal} {user_label}: **{points} pkt**")

with history_col:
    st.subheader("🕒 Ostatnie zadania")
    if not st.session_state.db["history"]:
        st.info("Brak historii.")
    else:
        for entry in st.session_state.db["history"][:10]:
            overdue_note = " • ⛔ po terminie" if entry.get("was_overdue") else ""
            st.markdown(f"**{entry['name']}**")
            st.caption(
                f"{entry['completed_by']} • +{entry['points']} pkt • {entry['date_completed']}{overdue_note}"
            )
