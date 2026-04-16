import json
import os
import uuid
from datetime import datetime, timedelta, date

import pandas as pd
import streamlit as st

# =========================================================
# CONFIG (MOBILE FIRST)
# =========================================================
st.set_page_config(
    page_title="Domowy Tasker",
    page_icon="🏠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =========================================================
# STAŁE
# =========================================================
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
AUTO_REFRESH_SECONDS = 3600  # 1h

# =========================================================
# STYLE (IPHONE 12 MINI / 15 PRO)
# =========================================================
st.markdown(
    """
    <style>
    .block-container {
      max-width: 430px;
      padding-top: .65rem;
      padding-bottom: 1rem;
      padding-left: .75rem;
      padding-right: .75rem;
    }

    h1 { font-size: 1.55rem !important; margin-bottom: .15rem; }
    h2 { font-size: 1.2rem !important; margin-top: .35rem; }
    h3 { font-size: 1.05rem !important; margin-top: .2rem; }

    .welcome-note {
      opacity: .9;
      margin-bottom: .4rem;
      font-size: .92rem;
    }

    .stButton > button {
      width: 100%;
      min-height: 46px;
      border-radius: 12px;
      font-weight: 650;
    }

    .stTextInput input, .stTextArea textarea, .stNumberInput input {
      font-size: 16px !important; /* iOS zoom fix */
    }

    .task-card {
      border: 1px solid rgba(120,120,120,.35);
      border-radius: 13px;
      padding: 10px;
      margin-bottom: 9px;
      background: rgba(255,255,255,.02);
    }

    .task-overdue {
      border-color: #ef4444 !important;
      background: rgba(239,68,68,.10);
    }

    .pill {
      display: inline-block;
      padding: .18rem .52rem;
      border-radius: 999px;
      font-size: .72rem;
      font-weight: 700;
      margin-right: .25rem;
      margin-bottom: .25rem;
    }
    .pill-general { background: rgba(56,189,248,.20); color: #7dd3fc; }
    .pill-private { background: rgba(168,85,247,.20); color: #d8b4fe; }
    .pill-overdue { background: rgba(239,68,68,.20); color: #fca5a5; }

    .tiny { font-size: .82rem; opacity: .9; }

    [data-testid="collapsedControl"] { display: none; } /* chowa hamburger */
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# DANE
# =========================================================
def default_data():
    return {
        "tasks": [],
        "history": [],
        "points": {worker: 0 for worker in WORKERS},
    }


def dt_to_str(dt: datetime):
    return dt.strftime("%Y-%m-%d %H:%M")


def parse_dt(s: str):
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def normalize_data(data):
    data = data or {}
    data.setdefault("tasks", [])
    data.setdefault("history", [])
    data.setdefault("points", {})

    if "Ja" in data["points"]:
        data["points"]["Bartek"] = data["points"].get("Bartek", 0) + data["points"].pop("Ja")

    for worker in WORKERS:
        data["points"].setdefault(worker, 0)

    data["points"] = {k: v for k, v in data["points"].items() if k in WORKERS}

    for task in data["tasks"]:
        if task.get("assignee") == "Ja":
            task["assignee"] = "Bartek"

        if "created_at" not in task:
            task["created_at"] = task.get("date_added", dt_to_str(datetime.now()))

        if "deadline_at" not in task:
            try:
                created = parse_dt(task["created_at"])
            except Exception:
                created = datetime.now()
                task["created_at"] = dt_to_str(created)
            task["deadline_at"] = dt_to_str(created + timedelta(hours=DEADLINE_HOURS))

        # prywatne zadania = 0 pkt
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


# =========================================================
# SESSION
# =========================================================
if "db" not in st.session_state:
    st.session_state.db = load_data()
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "task_mode" not in st.session_state:
    st.session_state.task_mode = "Ze spisu"

# =========================================================
# HELPERY
# =========================================================
def force_hourly_refresh():
    st.markdown(
        f"""
        <script>
            setTimeout(function() {{
                window.location.reload();
            }}, {AUTO_REFRESH_SECONDS * 1000});
        </script>
        """,
        unsafe_allow_html=True,
    )


def is_overdue(task):
    try:
        return datetime.now() > parse_dt(task["deadline_at"])
    except Exception:
        return False


def time_left_text(task):
    try:
        diff = parse_dt(task["deadline_at"]) - datetime.now()
        total = int(diff.total_seconds())
        if total <= 0:
            return "⛔ Po terminie"
        h = total // 3600
        m = (total % 3600) // 60
        return f"⏳ Zostało: {h}h {m}m"
    except Exception:
        return "⏳ Brak deadline"


def count_open_overdue_tasks(tasks):
    return sum(1 for t in tasks if is_overdue(t))


def get_streak_for_user(user: str, history: list):
    done_days = set()
    for e in history:
        if e.get("completed_by") == user:
            try:
                done_days.add(parse_dt(e["date_completed"]).date())
            except Exception:
                continue

    streak = 0
    cursor = date.today()
    while cursor in done_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


# =========================================================
# AKCJE
# =========================================================
def add_task(name, description, assignee, points):
    created_at = datetime.now()
    deadline_at = created_at + timedelta(hours=DEADLINE_HOURS)

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
            "date_added": dt_to_str(created_at),
            "deadline_at": dt_to_str(deadline_at),
        }
    )
    save_data(st.session_state.db)
    st.toast("Zadanie dodane ✅")


def complete_task(task_id, user_name):
    tasks = st.session_state.db["tasks"]

    if user_name not in st.session_state.db["points"]:
        st.error("Nieznany profil użytkownika.")
        return

    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return

    st.session_state.db["tasks"] = [t for t in tasks if t["id"] != task_id]

    overdue = is_overdue(task)
    pts = int(task.get("points", 0))

    st.session_state.db["history"].insert(
        0,
        {
            "name": task["name"],
            "completed_by": user_name,
            "points": pts,
            "was_overdue": overdue,
            "date_completed": dt_to_str(datetime.now()),
            "assignee": task.get("assignee"),
        },
    )
    st.session_state.db["history"] = st.session_state.db["history"][:350]
    st.session_state.db["points"][user_name] += pts

    save_data(st.session_state.db)
    st.toast(f"Super! +{pts} pkt 🎉")


# =========================================================
# START
# =========================================================
force_hourly_refresh()

st.title("🏠 Domowy Tasker")
st.markdown(
    unsafe_allow_html=True,
)

# =========================================================
# LOGOWANIE
# =========================================================
if st.session_state.current_user is None and not st.session_state.is_admin:
    st.subheader("Wybierz profil")

    if st.button("👑 Mama", use_container_width=True):
        st.session_state.current_user = "Mama"
        st.rerun()
    if st.button("🙋 Bartek", use_container_width=True):
        st.session_state.current_user = "Bartek"
        st.rerun()
    if st.button("🧢 Tomek", use_container_width=True):
        st.session_state.current_user = "Tomek"
        st.rerun()
    if st.button("🛡️ Admin", use_container_width=True):
        st.session_state.current_user = ADMIN_USER
        st.rerun()

    st.info("Najpierw wybierz profil.")
    st.stop()

if st.session_state.current_user == ADMIN_USER and not st.session_state.is_admin:
    st.subheader("🔐 Logowanie Admin")
    with st.form("admin_login_form", clear_on_submit=True):
        pwd = st.text_input("Hasło", type="password")
        ok = st.form_submit_button("Zaloguj", use_container_width=True)
        if ok:
            if pwd == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.success("Zalogowano jako Admin ✅")
                st.rerun()
            else:
                st.error("Niepoprawne hasło.")

    if st.button("⬅️ Wróć do wyboru profilu", use_container_width=True):
        st.session_state.current_user = None
        st.session_state.is_admin = False
        st.rerun()
    st.stop()

current_user = st.session_state.current_user
is_admin = st.session_state.is_admin

top1, top2 = st.columns([3, 1])
with top1:
    role = "Admin" if is_admin else current_user
    st.caption(f"Zalogowano jako: **{role}**")
with top2:
    if st.button("Wyloguj", use_container_width=True):
        st.session_state.current_user = None
        st.session_state.is_admin = False
        st.rerun()

st.divider()

# =========================================================
# METRYKI (MOBILE)
# =========================================================
open_tasks = st.session_state.db["tasks"]
overdue_count = count_open_overdue_tasks(open_tasks)
general_count = sum(1 for t in open_tasks if t.get("assignee") == GENERAL_TASK_LABEL)
private_count = len(open_tasks) - general_count

r1c1, r1c2 = st.columns(2)
r1c1.metric("📌 Aktywne", len(open_tasks))
r1c2.metric("⛔ Po terminie", overdue_count)

r2c1, r2c2 = st.columns(2)
r2c1.metric("🌐 Ogólne", general_count)
r2c2.metric("👤 Prywatne", private_count)

s1, s2 = st.columns(2)
s1.metric("🔥 Bartek", f"{get_streak_for_user('Bartek', st.session_state.db['history'])} dni")
s2.metric("🔥 Tomek", f"{get_streak_for_user('Tomek', st.session_state.db['history'])} dni")

st.markdown("---")

# =========================================================
# MAMA: tylko dodawanie
# =========================================================
if current_user == "Mama":
    st.subheader("➕ Dodawanie zadań")

    st.session_state.task_mode = st.radio(
        "Rodzaj zadania",
        ["Ze spisu", "Nowe zadanie"],
        horizontal=True,
        index=0 if st.session_state.task_mode == "Ze spisu" else 1,
    )

    with st.form("add_task_form", clear_on_submit=True):
        if st.session_state.task_mode == "Ze spisu":
            task_name = st.selectbox("Wybierz zadanie", PRESET_TASKS)
        else:
            task_name = st.text_input("Nazwa nowego zadania", placeholder="Np. Posprzątaj biurko")

        task_desc = st.text_area("Opis (opcjonalnie)")
        task_assignee = st.selectbox("Dla kogo?", [GENERAL_TASK_LABEL, *WORKERS])

        if task_assignee == GENERAL_TASK_LABEL:
            task_points = st.number_input("Punkty", min_value=1, value=10, step=1)
        else:
            st.text_input("Punkty (prywatne)", value="0", disabled=True)
            task_points = 0

        st.caption(f"⏱️ Deadline ustawiany automatycznie: {DEADLINE_HOURS}h od dodania.")

        if st.form_submit_button("Dodaj zadanie ✅", use_container_width=True):
            if not task_name.strip():
                st.error("Podaj nazwę zadania.")
            else:
                add_task(task_name, task_desc, task_assignee, task_points)
                st.rerun()

    st.markdown("---")

# =========================================================
# ADMIN: prawie pełna kontrola
# =========================================================
if is_admin:
    st.subheader("🛡️ Panel Admina")
    tab1, tab2, tab3, tab4 = st.tabs(["⚙️ Punkty", "🗂️ Zadania", "🧾 Historia", "🧨 Narzędzia"])

    with tab1:
        st.markdown("### Edycja punktów")
        for w in WORKERS:
            val = st.number_input(
                f"Punkty — {w}",
                min_value=0,
                value=int(st.session_state.db["points"].get(w, 0)),
                step=1,
                key=f"points_{w}",
            )
            if st.button(f"Zapisz punkty: {w}", key=f"save_{w}", use_container_width=True):
                st.session_state.db["points"][w] = int(val)
                save_data(st.session_state.db)
                st.success(f"Zapisano punkty dla {w}")
                st.rerun()

    with tab2:
        st.markdown("### Zarządzanie aktywnymi zadaniami")
        tasks = st.session_state.db["tasks"]

        if not tasks:
            st.info("Brak aktywnych zadań.")
        else:
            for task in sorted(tasks, key=lambda t: parse_dt(t["deadline_at"])):
                overdue = is_overdue(task)
                card_class = "task-card task-overdue" if overdue else "task-card"
                st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)

                badges = []
                if task["assignee"] == GENERAL_TASK_LABEL:
                    badges.append("<span class='pill pill-general'>OGÓLNE</span>")
                else:
                    badges.append("<span class='pill pill-private'>PRYWATNE</span>")
                if overdue:
                    badges.append("<span class='pill pill-overdue'>PO TERMINIE</span>")
                st.markdown("".join(badges), unsafe_allow_html=True)

                st.markdown(f"**{task['name']}**")
                st.caption(f"Dodano: {task['created_at']} • Deadline: {task['deadline_at']}")

                new_name = st.text_input("Nazwa", value=task["name"], key=f"name_{task['id']}")
                new_desc = st.text_area("Opis", value=task.get("description", ""), key=f"desc_{task['id']}")
                new_assignee = st.selectbox(
                    "Dla kogo?",
                    [GENERAL_TASK_LABEL, *WORKERS],
                    index=([GENERAL_TASK_LABEL, *WORKERS].index(task["assignee"]) if task["assignee"] in [GENERAL_TASK_LABEL, *WORKERS] else 0),
                    key=f"asg_{task['id']}",
                )

                if new_assignee == GENERAL_TASK_LABEL:
                    new_points = st.number_input(
                        "Punkty",
                        min_value=1,
                        value=max(1, int(task.get("points", 1))),
                        step=1,
                        key=f"pts_{task['id']}",
                    )
                else:
                    st.text_input("Punkty", value="0", disabled=True, key=f"pts_dis_{task['id']}")
                    new_points = 0

                extra_h = st.number_input(
                    "Przedłuż deadline o godziny",
                    min_value=0,
                    max_value=168,
                    value=0,
                    step=1,
                    key=f"ext_{task['id']}",
                )

                if st.button("💾 Zapisz zmiany", key=f"save_task_{task['id']}", use_container_width=True):
                    task["name"] = new_name.strip() or task["name"]
                    task["description"] = new_desc.strip()
                    task["assignee"] = new_assignee
                    task["points"] = int(new_points) if new_assignee == GENERAL_TASK_LABEL else 0
                    if extra_h > 0:
                        task["deadline_at"] = dt_to_str(parse_dt(task["deadline_at"]) + timedelta(hours=int(extra_h)))

                    save_data(st.session_state.db)
                    st.success("Zapisano zmiany zadania.")
                    st.rerun()

                if st.button("🗑️ Usuń zadanie", key=f"del_{task['id']}", use_container_width=True):
                    st.session_state.db["tasks"] = [t for t in st.session_state.db["tasks"] if t["id"] != task["id"]]
                    save_data(st.session_state.db)
                    st.warning("Zadanie usunięte.")
                    st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.markdown("### Historia")
        hist = st.session_state.db["history"]
        if not hist:
            st.info("Brak historii.")
        else:
            for e in hist[:50]:
                overdue_note = " • ⛔ po terminie" if e.get("was_overdue") else ""
                st.markdown(f"**{e['name']}**")
                st.caption(f"{e['completed_by']} • +{e['points']} pkt • {e['date_completed']}{overdue_note}")

    with tab4:
        st.markdown("### Narzędzia")
        if st.button("♻️ Reset punktów", use_container_width=True):
            st.session_state.db["points"] = {w: 0 for w in WORKERS}
            save_data(st.session_state.db)
            st.success("Punkty zresetowane.")
            st.rerun()

        if st.button("🧹 Wyczyść historię", use_container_width=True):
            st.session_state.db["history"] = []
            save_data(st.session_state.db)
            st.success("Historia wyczyszczona.")
            st.rerun()

        if st.button("💣 Usuń wszystkie aktywne zadania", use_container_width=True):
            st.session_state.db["tasks"] = []
            save_data(st.session_state.db)
            st.warning("Usunięto wszystkie aktywne zadania.")
            st.rerun()

    st.markdown("---")

# =========================================================
# WORKER: lista i kończenie
# =========================================================
if current_user in WORKERS:
    st.subheader(f"🗂️ Zadania — {current_user}")

    tasks_to_show = [
        t for t in st.session_state.db["tasks"]
        if t["assignee"] in [current_user, GENERAL_TASK_LABEL]
    ]

    if not tasks_to_show:
        st.success("Brak aktywnych zadań 🎉")
    else:
        tasks_to_show = sorted(tasks_to_show, key=lambda t: parse_dt(t["deadline_at"]))

        for task in tasks_to_show:
            overdue = is_overdue(task)
            is_general = task["assignee"] == GENERAL_TASK_LABEL
            card_class = "task-card task-overdue" if overdue else "task-card"

            st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)

            badges = []
            badges.append("<span class='pill pill-general'>OGÓLNE</span>" if is_general else "<span class='pill pill-private'>PRYWATNE</span>")
            if overdue:
                badges.append("<span class='pill pill-overdue'>PO TERMINIE</span>")
            st.markdown("".join(badges), unsafe_allow_html=True)

            st.markdown(f"**{task['name']}**")
            if task.get("description"):
                st.caption(task["description"])

            pts_txt = f"{task['points']} pkt" if is_general else "0 pkt (prywatne)"
            st.markdown(f"<div class='tiny'>👤 Dla: {task['assignee']} • 🪙 {pts_txt}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='tiny'>🕒 Dodano: {task['created_at']} • 📅 Deadline: {task['deadline_at']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='tiny'>{time_left_text(task)}</div>", unsafe_allow_html=True)

            if st.button("Zrobione ✅", key=f"done_{task['id']}", use_container_width=True):
                complete_task(task["id"], current_user)
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

# =========================================================
# DÓŁ: ranking/trend/historia (taby)
# =========================================================
tabs = st.tabs(["🏆 Ranking", "📈 Trend", "🕒 Ostatnie akcje"])

with tabs[0]:
    ranking = sorted(st.session_state.db["points"].items(), key=lambda x: x[1], reverse=True)

    for i, (user, pts) in enumerate(ranking):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
        bold = "**" if user == current_user else ""
        st.markdown(f"{medal} {bold}{user}{bold}: **{pts} pkt**")

    if ranking:
        df_rank = pd.DataFrame(ranking, columns=["Użytkownik", "Punkty"]).sort_values("Punkty", ascending=True)
        st.caption("Aktualne punkty")
        st.bar_chart(df_rank.set_index("Użytkownik"), horizontal=True)

with tabs[1]:
    history = st.session_state.db["history"]
    if not history:
        st.info("Brak historii do wykresów.")
    else:
        rows_daily = []
        rows_cum = []

        for e in history:
            who = e.get("completed_by")
            if who not in WORKERS:
                continue
            try:
                dt = parse_dt(e.get("date_completed"))
            except Exception:
                continue

            pts = int(e.get("points", 0))
            rows_daily.append({"date": dt.date(), "user": who, "points": pts})
            rows_cum.append({"datetime": dt, "user": who, "points": pts})

        if rows_daily:
            st.caption("Punkty dziennie")
            df_daily = pd.DataFrame(rows_daily)
            daily = (
                df_daily.groupby(["date", "user"], as_index=False)["points"]
                .sum()
                .pivot(index="date", columns="user", values="points")
                .fillna(0)
                .sort_index()
            )
            for w in WORKERS:
                if w not in daily.columns:
                    daily[w] = 0
            daily = daily[WORKERS]
            st.line_chart(daily)

        if rows_cum:
            st.caption("Kumulacja punktów")
            df_cum = pd.DataFrame(rows_cum).sort_values("datetime")
            cumulative = {w: 0 for w in WORKERS}
            out = []
            for _, r in df_cum.iterrows():
                cumulative[r["user"]] += int(r["points"])
                row = {"datetime": r["datetime"]}
                for w in WORKERS:
                    row[w] = cumulative[w]
                out.append(row)

            df_line = pd.DataFrame(out).drop_duplicates(subset=["datetime"], keep="last").set_index("datetime")
            if len(df_line) >= 2:
                st.line_chart(df_line[WORKERS])
            else:
                st.info("Za mało danych na wykres kumulacyjny (min. 2 wpisy).")

with tabs[2]:
    history = st.session_state.db["history"]
    if not history:
        st.info("Brak historii.")
    else:
        for entry in history[:12]:
            overdue_note = " • ⛔ po terminie" if entry.get("was_overdue") else ""
            st.markdown(f"**{entry['name']}**")
            st.caption(
                f"{entry['completed_by']} • +{entry['points']} pkt • {entry['date_completed']}{overdue_note}"
            )

st.markdown("---")
st.caption("iPhone-ready • Auto-refresh: 1h • Deadline: 24h • Admin: full control")
