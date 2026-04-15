from datetime import date
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path("caisse_scolaire.db")
MONTHS = [
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
]


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mouvements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mois TEXT NOT NULL,
                date TEXT NOT NULL,
                designation TEXT NOT NULL,
                nom TEXT NOT NULL,
                classe TEXT NOT NULL,
                entree REAL NOT NULL DEFAULT 0,
                sortie REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def add_mouvement(mois, movement_date, designation, nom, classe, entree, sortie):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO mouvements (mois, date, designation, nom, classe, entree, sortie)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mois,
                movement_date.isoformat(),
                designation.strip(),
                nom.strip(),
                classe.strip(),
                float(entree or 0),
                float(sortie or 0),
            ),
        )
        conn.commit()


def delete_mouvement(row_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM mouvements WHERE id = ?", (row_id,))
        conn.commit()


def load_mouvements(mois=None):
    query = "SELECT id, mois, date, designation, nom, classe, entree, sortie FROM mouvements"
    params = ()
    if mois:
        query += " WHERE mois = ?"
        params = (mois,)
    query += " ORDER BY date ASC, id ASC"

    with get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["entree"] = df["entree"].astype(float)
    df["sortie"] = df["sortie"].astype(float)
    df["solde"] = df["entree"] - df["sortie"]
    df["solde_cumule"] = df["solde"].cumsum()
    return df


def format_table(df):
    display_df = df.rename(
        columns={
            "id": "ID",
            "mois": "Mois",
            "date": "Date",
            "designation": "Désignation",
            "nom": "Nom",
            "classe": "Classe",
            "entree": "Entrée",
            "sortie": "Sortie",
            "solde": "Solde",
            "solde_cumule": "Solde cumulé",
        }
    )
    return display_df[
        [
            "ID",
            "Date",
            "Désignation",
            "Nom",
            "Classe",
            "Entrée",
            "Sortie",
            "Solde",
            "Solde cumulé",
        ]
    ]


def show_month(mois):
    st.subheader(mois)

    with st.form(f"form-{mois}", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            movement_date = st.date_input("Date", value=date.today(), key=f"date-{mois}")
            nom = st.text_input("Nom", key=f"nom-{mois}")
        with col2:
            designation = st.text_input("Désignation", key=f"designation-{mois}")
            classe = st.text_input("Classe", key=f"classe-{mois}")
        with col3:
            entree = st.number_input("Entrée", min_value=0.0, step=100.0, format="%.2f", key=f"entree-{mois}")
            sortie = st.number_input("Sortie", min_value=0.0, step=100.0, format="%.2f", key=f"sortie-{mois}")

        submitted = st.form_submit_button("Ajouter")

    if submitted:
        if not designation.strip() or not nom.strip() or not classe.strip():
            st.error("Veuillez remplir la désignation, le nom et la classe.")
        elif entree == 0 and sortie == 0:
            st.error("Veuillez saisir une entrée ou une sortie.")
        else:
            add_mouvement(mois, movement_date, designation, nom, classe, entree, sortie)
            st.success("Ligne ajoutée.")
            st.rerun()

    df = load_mouvements(mois)

    if df.empty:
        st.info("Aucune donnée pour ce mois.")
        return

    total_entrees = df["entree"].sum()
    total_sorties = df["sortie"].sum()
    solde = total_entrees - total_sorties

    col1, col2, col3 = st.columns(3)
    col1.metric("Total entrées", f"{total_entrees:,.2f}".replace(",", " "))
    col2.metric("Total sorties", f"{total_sorties:,.2f}".replace(",", " "))
    col3.metric("Solde", f"{solde:,.2f}".replace(",", " "))

    st.dataframe(
        format_table(df),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Entrée": st.column_config.NumberColumn(format="%.2f"),
            "Sortie": st.column_config.NumberColumn(format="%.2f"),
            "Solde": st.column_config.NumberColumn(format="%.2f"),
            "Solde cumulé": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    st.write("Supprimer une ligne")
    options = {
        f"ID {row.id} — {row.date} — {row.designation} — {row.nom}": int(row.id)
        for row in df.itertuples(index=False)
    }
    selected_label = st.selectbox("Choisir la ligne à supprimer", list(options.keys()), key=f"delete-select-{mois}")
    if st.button("Supprimer la ligne sélectionnée", key=f"delete-button-{mois}"):
        delete_mouvement(options[selected_label])
        st.success("Ligne supprimée.")
        st.rerun()


def show_global_summary():
    df = load_mouvements()
    st.sidebar.header("Résumé")
    if df.empty:
        st.sidebar.write("Aucune donnée enregistrée.")
        return

    st.sidebar.metric("Entrées totales", f"{df['entree'].sum():,.2f}".replace(",", " "))
    st.sidebar.metric("Sorties totales", f"{df['sortie'].sum():,.2f}".replace(",", " "))
    st.sidebar.metric("Solde total", f"{df['solde'].sum():,.2f}".replace(",", " "))


def main():
    st.set_page_config(page_title="Caisse scolaire", layout="wide")
    init_db()

    st.title("Gestion de caisse scolaire")
    st.write("Ajoutez les entrées et sorties de caisse, mois par mois. Les données sont enregistrées dans SQLite.")

    show_global_summary()

    tabs = st.tabs(MONTHS)
    for tab, mois in zip(tabs, MONTHS):
        with tab:
            show_month(mois)


if __name__ == "__main__":
    main()
