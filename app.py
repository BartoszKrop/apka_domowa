import json
import os
import uuid
from datetime import datetime

import streamlit as st

st.set_page_config(page_title="Domowa apka zadań", page_icon="🏠", layout="centered")

# --- STAŁE ---
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
    "Wyrzucenie śmieci",
    "Rozpakowanie zmywarki"
]

# --- LOGIKA DANYCH ---
def default_data():
    return {"tasks": [], "history": [], "points": {worker: 0 for worker in WORKERS}}

def normalize_data(data):
    data = data or {}
    data.setdefault("tasks", [])
    data.setdefault("history", [])
    data.setdefault("points", {})

    # Migracja dawnych użytkowników (np. "Ja" -> "Bartek")
    if "Ja" in data["points"]:
        data["points"]["Bartek"] = data["points"].get("Bartek", 0) + data["points"].pop("Ja")

    # Upewnienie się, że wszyscy pracownicy mają domyślne punkty
    for worker in WORKERS:
        data["points"].setdefault(worker, 0)

    # Oczyszczenie z usuniętych użytkowników
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
            try:
                return normalize_data(json.load(f))
            except json.JSONDecodeError:
                return default_data()
    return default_data()

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- INICJALIZACJA STANU ---
if "db" not in st.session_state:
    st.session_state.db = load_data()
if "current_user" not in st.session_state:
    st.session_state.current_user = None

# --- AKCJE ---
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

    # Usunięcie z listy zadań
    st.session_state.db["tasks"] = [t for t in tasks if t["id"] != task_id]
    
    # Dodanie do historii na sam początek (limit 50 ostatnich)
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
    
    # Dodanie punktów
    st.session_state.db["points"][user_name] += task_to_complete["points"]
    save_data(st.session_state.db)
    st.toast(f"Super! +{task_to_complete['points']} pkt 🎉")

# --- UI (INTERFEJS) ---
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

# 1. EKRAN LOGOWANIA
if st.session_state.current_user is None:
    st.subheader("Kim jesteś?")
    cols = st.columns(3)
    
    # Słownik ikon przypisanych do użytkowników dla łatwiejszego zarządzania
    user_icons = {"Mama": "👑 Mama", "Bartek": "🙋 Bartek", "Tomek": "🧢 Tomek"}
    
    for col, user in zip(cols, USERS):
        with col:
            if st.button(user_icons.get(user, user), use_container_width=True):
                st.session_state.current_user = user
                st.rerun()
                
    st.info("Najpierw wybierz profil, a potem wejdziesz do właściwego panelu.")
    st.stop()

# 2. GŁÓWNY WIDOK APLIKACJI
current_user = st.session_state.current_user
top_left, top_right = st.columns([4, 1])
with top_left:
    st.caption(f"Zalogowano jako: **{current_user}**")
with top_right:
    if st.button("Zmień profil", use_container_width=True):
        st.session_state.current_user = None
        st.rerun()

st.divider() # Delikatne oddzielenie nagłówka

# PANEL MAMY
if current_user == "Mama":
    st.header("Panel mamy: dodawanie zadań")

    # Radio musi być POZA formularzem, aby dynamicznie odświeżać stronę
    task_mode = st.radio("Rodzaj zadania", ["Ze spisu", "Nowe zadanie"], horizontal=True)

    with st.form("add_task_form", clear_on_submit=True):
        # Dynamiczne wyświetlanie odpowiedniego pola w zależności od wyboru
        if task_mode == "Ze spisu":
            task_name = st.selectbox("Wybierz zadanie z listy", PRESET_TASKS)
        else:
            task_name = st.text_input(
                "Wpisz nazwę nowego zadania",
                placeholder="Np. Umycie naczyń po kolacji",
                help="Wpisz krótką i jasną nazwę zadania.",
            )

        task_desc = st.text_area("Opis zadania (opcjonalnie)")
        
        col1, col2 = st.columns(2)
        with col1:
            task_assignee = st.selectbox("Dla kogo?", [GENERAL_TASK_LABEL, *WORKERS])
        with col2:
            task_points = st.number_input("Ilość punktów", min_value=1, value=10, step=1)

        if st.form_submit_button("Dodaj zadanie ➕", use_container_width=True):
            if not task_name or not task_name.strip():
                st.error("Podaj nazwę zadania przed zapisem!")
            else:
                add_task(task_name, task_desc, task_assignee, task_points)
                st.rerun()

# PANEL PRACOWNIKÓW
else:
    st.header(f"Cześć {current_user} 👋")
    st.subheader("Twoje aktualne zadania")

    tasks_to_show = [t for t in st.session_state.db["tasks"] if t["assignee"] in [current_user, GENERAL_TASK_LABEL]]

    if not tasks_to_show:
        st.success("Na ten moment brak zadań do wykonania. Super robota 😎")
    else:
        for task in tasks_to_show:
            with st.container(border=True):
                col_info, col_btn = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"**{task['name']}** — `{task['points']} pkt`")
                    if task.get("description"):
                        st.caption(task["description"])
                    task_type = "Tylko dla Ciebie" if task["assignee"] == current_user else "Ogólne"
                    st.caption(f"📌 {task_type} • 🗓️ {task['date_added']}")
                
                with col_btn:
                    # Wyśrodkowanie przycisku w kolumnie
                    st.write("") 
                    if st.button("Zrobione ✅", key=task["id"], use_container_width=True):
                        complete_task(task["id"], current_user)
                        st.rerun()

st.markdown("---")

# RANKING I HISTORIA (WIDOCZNE DLA WSZYSTKICH)
score_col, history_col = st.columns(2)

with score_col:
    st.subheader("🏆 Ranking punktów")
    ranking = sorted(st.session_state.db["points"].items(), key=lambda item: item[1], reverse=True)
    
    for place, (user, points) in enumerate(ranking):
        medal = "🥇" if place == 0 else "🥈" if place == 1 else "🥉"
        # Oznaczenie pogrubieniem jeśli to wynik aktualnie zalogowanego użytkownika
        user_display = f"**{user}**" if user == current_user else user
        st.markdown(f"### {medal} {user_display}: `{points} pkt`")

with history_col:
    st.subheader("🕒 Ostatnio wykonane")
    if not st.session_state.db["history"]:
        st.info("Brak historii zadań.")
    else:
        for entry in st.session_state.db["history"][:7]: # Zmniejszono do 7, żeby nie rozciągać za bardzo widoku
            with st.container(border=True):
                st.markdown(f"**{entry['name']}**")
                st.caption(f"👤 {entry['completed_by']} • 🪙 +{entry['points']} pkt • 🕒 {entry['date_completed']}")
