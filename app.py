import json
import os
import uuid
from datetime import datetime

import streamlit as st

st.set_page_config(page_title="Domowa apka zadań", page_icon="🏠", layout="centered")

DATA_FILE = "data.json"
GENERAL_TASK_LABEL = "Ogólne (kto pierwszy, ten lepszy)"
WORKERS = ["Bartek", "Tomek"]
USERS = ["Mama", *WORKERS]
PRESET_TASKS = [
    "Odkurzanie pokoju",
    "Odkurzanie parteru",
    "Odkurzanie 1 piętra",
    "Odkurzanie 2 piętra",
    "Odkurzanie łazienki",
]


def default_data():
    return {"tasks": [], "history": [], "points": {worker: 0 for worker in WORKERS}}


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

    data["points"] = {k: v for k, v in data["points"].items() if k in WORKERS}

    for task in data["tasks"]:
        if task.get("assignee") == "Ja":
            task["assignee"] = "Bartek"

    for entry in data["history"]:
        if entry.get("completed_by") == "Ja":
            entry["completed_by"] = "Bartek"

    return data


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return normalize_data(json.load(f))
    return default_data()


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


if "db" not in st.session_state:
    st.session_state.db = load_data()
if "current_user" not in st.session_state:
    st.session_state.current_user = None


def add_task(name, description, assignee, points):
    st.session_state.db["tasks"].append(
        {
            "id": str(uuid.uuid4()),
            "name": name.strip(),
            "description": description.strip(),
            "assignee": assignee,
            "points": points,
            "date_added": datetime.now().strftime("%Y-%m-%d %H:%M"),
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
            "points": task_to_complete["points"],
            "date_completed": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    )
    st.session_state.db["history"] = st.session_state.db["history"][:50]
    st.session_state.db["points"][user_name] += task_to_complete["points"]
    save_data(st.session_state.db)
    st.toast(f"Super! +{task_to_complete['points']} pkt 🎉")


st.markdown(
    """
    <style>
        .stMainBlockContainer {padding-top: 1.5rem;}
        .welcome-note {text-align: center; opacity: .9; margin-bottom: 1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏠 Domowy Tasker")
st.markdown("<p class='welcome-note'>Prosta apka do zadań i punktów domowych</p>", unsafe_allow_html=True)

if st.session_state.current_user is None:
    st.subheader("Kim jesteś?")
    left, mid, right = st.columns(3)
    with left:
        if st.button("👑 Mama", use_container_width=True):
            st.session_state.current_user = "Mama"
            st.rerun()
    with mid:
        if st.button("🙋 Bartek", use_container_width=True):
            st.session_state.current_user = "Bartek"
            st.rerun()
    with right:
        if st.button("🧢 Tomek", use_container_width=True):
            st.session_state.current_user = "Tomek"
            st.rerun()
    st.info("Najpierw wybierz profil, a potem wejdziesz do właściwego panelu.")
    st.stop()

current_user = st.session_state.current_user
top_left, top_right = st.columns([4, 1])
with top_left:
    st.caption(f"Zalogowano jako: **{current_user}**")
with top_right:
    if st.button("Zmień profil"):
        st.session_state.current_user = None
        st.rerun()

if current_user == "Mama":
    st.header("Panel mamy: dodawanie zadań")

    with st.form("add_task_form", clear_on_submit=True):
        task_mode = st.radio("Rodzaj zadania", ["Ze spisu", "Nowe zadanie"], horizontal=True)

        if task_mode == "Ze spisu":
            task_name = st.selectbox("Wybierz zadanie", PRESET_TASKS)
        else:
            task_name = st.text_input(
                "Wpisz nazwę nowego zadania",
                placeholder="Np. Umycie naczyń po kolacji",
                help="Wpisz krótką i jasną nazwę zadania.",
            )

        task_desc = st.text_area("Opis (opcjonalnie)")
        task_assignee = st.selectbox("Dla kogo?", [GENERAL_TASK_LABEL, *WORKERS])
        task_points = st.number_input("Punkty", min_value=1, value=10, step=1)

        if st.form_submit_button("Dodaj zadanie"):
            if not task_name.strip():
                st.error("Podaj nazwę zadania.")
            else:
                add_task(task_name, task_desc, task_assignee, task_points)
                st.rerun()
else:
    st.header(f"Cześć {current_user} 👋")
    st.subheader("Twoje zadania")

    tasks_to_show = [t for t in st.session_state.db["tasks"] if t["assignee"] in [current_user, GENERAL_TASK_LABEL]]

    if not tasks_to_show:
        st.success("Na teraz brak zadań. Super robota 😎")
    else:
        for task in tasks_to_show:
            with st.container(border=True):
                st.markdown(f"**{task['name']}** — {task['points']} pkt")
                if task.get("description"):
                    st.caption(task["description"])
                task_type = "Tylko dla Ciebie" if task["assignee"] == current_user else "Zadanie ogólne"
                st.caption(f"{task_type} • Dodano: {task['date_added']}")
                if st.button("Zrobione ✅", key=task["id"], use_container_width=True):
                    complete_task(task["id"], current_user)
                    st.rerun()

st.markdown("---")
score_col, history_col = st.columns(2)

with score_col:
    st.subheader("🏆 Ranking")
    ranking = sorted(st.session_state.db["points"].items(), key=lambda item: item[1], reverse=True)
    for place, (user, points) in enumerate(ranking):
        medal = "🥇" if place == 0 else "🥈" if place == 1 else "🥉"
        st.markdown(f"{medal} **{user}**: {points} pkt")

with history_col:
    st.subheader("🕒 Ostatnie zadania")
    if not st.session_state.db["history"]:
        st.info("Brak historii.")
    else:
        for entry in st.session_state.db["history"][:10]:
            st.markdown(f"**{entry['name']}**")
            st.caption(f"{entry['completed_by']} • +{entry['points']} pkt • {entry['date_completed']}")
