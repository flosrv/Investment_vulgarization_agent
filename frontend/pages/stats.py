import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from components.constant_components import show_feedback
from datetime import datetime

API_STATS_URL = "https://gradely-dee-greaseproof.ngrok-free.dev"

def render_stats_page():
    st.header("📊 Estadísticas de la colección de artículos")

    st.markdown("""
Aquí puedes explorar estadísticas precisas de tu colección de artículos.  
Selecciona qué análisis quieres realizar y observa las visualizaciones interactivas.
""")

    # --- Boutons pour chaque type de stats ---
    st.subheader("Tipos de estadísticas disponibles")
    stats_options = st.multiselect(
        "Selecciona estadísticas a mostrar:",
        [
            "Totales y procesados",
            "Distribución por idioma",
            "Distribución por tags",
            "Artículos agregados por mes",
            "Artículos antiguos no procesados"
        ],
        default=["Totales y procesados"]
    )

    # --- Totales y procesados ---
    if "Totales y procesados" in stats_options:
        st.markdown("### 📌 Total de artículos y procesados")
        try:
            res = requests.get(f"{API_STATS_URL}/stats/overview")
            res.raise_for_status()
            data = res.json()
            total = data.get("total", 0)
            processed = data.get("processed", 0)
            st.metric("Total de artículos", total)
            st.metric("Artículos procesados", processed)
        except Exception as e:
            show_feedback(False, f"Error al cargar totales: {e}")

    # --- Distribución por idioma ---
    if "Distribución por idioma" in stats_options:
        st.markdown("### 🌐 Distribución por idioma")
        try:
            res = requests.get(f"{API_STATS_URL}/stats/by-language")
            res.raise_for_status()
            data = res.json()
            if data.get("languages"):
                df = pd.DataFrame(data["languages"])
                fig = px.pie(df, names="_id", values="count", title="Artículos por idioma")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de idiomas disponibles.")
        except Exception as e:
            show_feedback(False, f"Error al cargar idiomas: {e}")

    # --- Distribución por tags ---
    if "Distribución por tags" in stats_options:
        st.markdown("### 🏷️ Distribución por tags")
        try:
            res = requests.get(f"{API_STATS_URL}/stats/by-tag")
            res.raise_for_status()
            data = res.json()
            if data.get("tags"):
                df = pd.DataFrame(data["tags"])
                fig = px.bar(df, x="_id", y="count", title="Frecuencia de tags")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay tags registrados.")
        except Exception as e:
            show_feedback(False, f"Error al cargar tags: {e}")

    # --- Artículos agregados por mes ---
    if "Artículos agregados por mes" in stats_options:
        st.markdown("### 🗓️ Artículos agregados por mes")
        try:
            res = requests.get(f"{API_STATS_URL}/stats/by-month")
            res.raise_for_status()
            data = res.json()
            if data.get("monthly"):
                df = pd.DataFrame(data["monthly"])
                df["month"] = pd.to_datetime(df["_id"].apply(lambda x: f"{x['year']}-{x['month']:02d}-01"))
                fig = px.line(df, x="month", y="count", title="Artículos agregados por mes")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de artículos por mes.")
        except Exception as e:
            show_feedback(False, f"Error al cargar artículos por mes: {e}")

    # --- Artículos antiguos no procesados ---
    if "Artículos antiguos no procesados" in stats_options:
        st.markdown("### ⏳ Artículos antiguos no procesados")
        try:
            res = requests.get(f"{API_STATS_URL}/stats/oldest-unprocessed")
            res.raise_for_status()
            data = res.json()
            st.write(f"**{len(data.get('oldest_unprocessed', []))} artículos antiguos no procesados**")
            if data.get("oldest_unprocessed"):
                for a in data["oldest_unprocessed"]:
                    st.json(a)
        except Exception as e:
            show_feedback(False, f"Error al cargar artículos antiguos: {e}")
