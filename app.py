import streamlit as st
import json
import os
from datetime import datetime
import uuid

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="FamilyTasker", page_icon="🧹", layout="centered")

DATA_FILE = "data.json"

# --- FUNKCJE BAZY DANYCH (JSON) ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "tasks": [], 
        "history": [], 
        "points": {"Tomek": 0, "Ja": 0} # Zmień "Ja" na swoje imię, jeśli wolisz
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Inicjalizacja danych w sesji
if "db" not in st.session_state:
    st.session_state.db = load_data()

# --- FUNKCJE LOGIKI ---
def add_task(name, description, assignee, points):
    new_task = {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "assignee": assignee,
        "points": points,
        "date_added": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    st.session_state.db["tasks"].append(new_task)
    save_data(st.session_state.db)
    st.toast("Zadanie dodane pomyślnie! ✅")

def complete_task(task_id, user_name):
    tasks = st.session_state.db["tasks"]
    task_to_complete = next((t for t in tasks if t["id"] == task_id), None)
    
    if task_to_complete:
        # Usunięcie z aktywnych zadań
        st.session_state.db["tasks"] = [t for t in tasks if t["id"] != task_id]
        
        # Dodanie do historii
        history_entry = {
            "name": task_to_complete["name"],
            "completed_by": user_name,
            "points": task_to_complete["points"],
            "date_completed": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        st.session_state.db["history"].insert(0, history_entry) # Wstaw na początek
        
        # Ograniczenie historii do 50 ostatnich wpisów (żeby nie urosła w nieskończoność)
        st.session_state.db["history"] = st.session_state.db["history"][:50]
        
        # Dodanie punktów
        st.session_state.db["points"][user_name] += task_to_complete["points"]
        
        save_data(st.session_state.db)
        st.toast(f"Dobra robota! Wpada {task_to_complete['points']} pkt. 🎉")

# --- INTERFEJS UŻYTKOWNIKA ---

st.title("🧹 FamilyTasker")

# Sidebar - Wybór użytkownika
st.sidebar.title("Kto tu jest?")
current_user = st.sidebar.radio("Wybierz swój profil:", ["Mama", "Ja", "Tomek"])

st.sidebar.markdown("---")
st.sidebar.info("📌 **Wskazówka:** Dodaj tę stronę do ekranu domowego na telefonie, żeby działała jak apka!")

# --- PANEL MAMY (ADMIN) ---
if current_user == "Mama":
    st.header("👑 Panel Mamy - Dodawanie Zadań")
    
    with st.form("add_task_form", clear_on_submit=True):
        task_mode = st.radio("Wybierz typ zadania:", ["Ze spisu", "Nowe własne zadanie"], horizontal=True)
        
        if task_mode == "Ze spisu":
            task_name = st.selectbox("Wybierz zadanie:", [
                "Odkurzanie pokoju", 
                "Odkurzanie parteru", 
                "Odkurzanie 1 piętra", 
                "Odkurzanie 2 piętra", 
                "Odkurzanie łazienki"
            ])
        else:
            task_name = st.text_input("Wpisz nazwę nowego zadania:")
            
        task_desc = st.text_area("Opcjonalny opis (szczegóły):")
        task_assignee = st.selectbox("Dla kogo?", ["Ogólne (Kto pierwszy, ten lepszy)", "Ja", "Tomek"])
        task_points = st.number_input("Ile punktów za wykonanie?", min_value=1, value=10, step=5)
        
        submit_button = st.form_submit_button("Dodaj zadanie 🚀")
        
        if submit_button:
            if not task_name:
                st.error("Nazwa zadania nie może być pusta!")
            else:
                add_task(task_name, task_desc, task_assignee, task_points)
                st.rerun()

# --- PANEL SYNA (WYKONAWCA) ---
else:
    st.header(f"👋 Cześć {current_user}!")
    st.subheader("📋 Twoje zadania do zrobienia")
    
    tasks_to_show = [
        t for t in st.session_state.db["tasks"] 
        if t["assignee"] == current_user or t["assignee"] == "Ogólne (Kto pierwszy, ten lepszy)"
    ]
    
    if not tasks_to_show:
        st.success("Brak zadań na ten moment. Czysto i przyjemnie! 😎")
    else:
        for task in tasks_to_show:
            with st.container():
                st.markdown(f"### 🔹 {task['name']} ({task['points']} pkt)")
                if task['description']:
                    st.caption(f"📝 *{task['description']}*")
                
                assignee_badge = "🔴 Tylko dla Ciebie" if task["assignee"] == current_user else "🟢 Ogólne (kto pierwszy)"
                st.markdown(f"*{assignee_badge}* | Dodano: {task['date_added']}")
                
                if st.button("Zrobione ✅", key=task["id"]):
                    complete_task(task["id"], current_user)
                    st.rerun()
                st.divider()

# --- WSPÓLNA CZĘŚĆ (RANKING I HISTORIA) ---
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏆 Tabela Wyników")
    # Sortowanie rankingu
    sorted_points = sorted(st.session_state.db["points"].items(), key=lambda item: item[1], reverse=True)
    
    for rank, (user, points) in enumerate(sorted_points):
        medal = "🥇" if rank == 0 else "🥈" if rank == 1 else "🥉"
        st.markdown(f"**{medal} {user}:** {points} pkt")

with col2:
    st.subheader("🕒 Ostatnio zrobione")
    if not st.session_state.db["history"]:
        st.info("Brak historii zadań.")
    else:
        for h in st.session_state.db["history"][:10]: # Pokazuje 10 ostatnich
            st.markdown(f"**{h['name']}**")
            st.caption(f"Wykonawca: **{h['completed_by']}** (+{h['points']} pkt)")
            st.caption(f"Kiedy: {h['date_completed']}")
            st.markdown("---")