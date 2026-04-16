# =========================================================
# RANKING + HISTORIA + WYKRESY
# =========================================================
left, right = st.columns([1, 1])

with left:
    st.subheader("🏆 Ranking")
    ranking = sorted(st.session_state.db["points"].items(), key=lambda x: x[1], reverse=True)

    for i, (user, pts) in enumerate(ranking):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
        mark = "**" if user == current_user else ""
        st.markdown(f"{medal} {mark}{user}{mark}: **{pts} pkt**")

    if ranking:
        df_rank = pd.DataFrame(ranking, columns=["Użytkownik", "Punkty"]).sort_values("Punkty", ascending=True)
        st.caption("Aktualne punkty")
        # poziomy wykres = lepsza czytelność etykiet
        st.bar_chart(df_rank.set_index("Użytkownik"), horizontal=True)

with right:
    st.subheader("📈 Trend punktów")
    history = st.session_state.db["history"]

    if not history:
        st.info("Brak historii do wykresu.")
    else:
        # 1) punkty dzienne (czytelny trend)
        rows_daily = []
        # 2) kumulacja w czasie
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

        # --- wykres dzienny ---
        if rows_daily:
            df_daily = pd.DataFrame(rows_daily)
            daily_pivot = (
                df_daily.groupby(["date", "user"], as_index=False)["points"]
                .sum()
                .pivot(index="date", columns="user", values="points")
                .fillna(0)
                .sort_index()
            )
            for w in WORKERS:
                if w not in daily_pivot.columns:
                    daily_pivot[w] = 0
            daily_pivot = daily_pivot[WORKERS]

            st.caption("Punkty dziennie")
            st.line_chart(daily_pivot)

        # --- wykres kumulacyjny ---
        if rows_cum:
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

            st.caption("Kumulacja punktów")
            if len(df_line) >= 2:
                st.line_chart(df_line[WORKERS])
            else:
                st.info("Za mało danych na sensowny trend kumulacyjny (potrzeba min. 2 wpisów).")

        st.markdown("### 🕒 Ostatnie akcje")
        for entry in history[:8]:
            overdue_note = " • ⛔ po terminie
