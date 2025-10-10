import streamlit as st
import requests
from components.constant_components import show_feedback
from datetime import datetime

API_COLLECTIONS_URL = "https://gradely-dee-greaseproof.ngrok-free.dev/collections"

def render_crud_collection():
    st.header("🗃️ Operaciones CRUD sobre la colección MongoDB")
    st.markdown("""
Este modo te permite **manipular directamente los datos** en la colección MongoDB:
- Ver todos los documentos  
- Buscar, ver recientes, eliminar condicionalmente..
""")

    accion = st.radio("Selecciona una acción:", [
        "Listar todos los documentos",
        "Artículos recientes",
        "Buscar artículos",
        "Eliminar condicionalmente",
        "Ver estadísticas"
    ])

    # --- Listar todos los documentos ---
    if accion == "Listar todos los documentos":
        st.subheader("📄 Lista de documentos")
        if st.button("Cargar documentos"):
            try:
                res = requests.get(f"{API_COLLECTIONS_URL}/all")
                res.raise_for_status()
                data = res.json()
                st.write(f"**{data.get('count', 0)} documentos encontrados**")
                for d in data.get("articles", []):
                    st.json(d)
            except Exception as e:
                show_feedback(False, f"Error al listar documentos: {e}")

    # --- Artículos recientes ---
    elif accion == "Artículos recientes":
        st.subheader("🆕 Últimos artículos añadidos")
        limit = st.number_input(label="Número de artículos a mostrar", min_value=1, max_value=50, value=10)
        if st.button("Cargar recientes"):
            try:
                res = requests.get(f"{API_COLLECTIONS_URL}/recent/{limit}", headers={"accept": "application/json"})  # ici le path param correspond
                res.raise_for_status()
                data = res.json()
                st.write(f"**{data.get('count', 0)} artículos recientes**")
                for a in data.get("articles", []):
                    st.json(a)
            except Exception as e:
                show_feedback(False, f"Error al cargar artículos recientes: {e}")

    # --- Buscar artículos ---
    elif accion == "Buscar artículos":
        st.subheader("🔍 Búsqueda por palabras clave")
        query = st.text_input(label="Palabras clave", placeholder="Palabras clave (separadas por comas)")
        limit = st.number_input(label="Límite de resultados", min_value=1, max_value=50, value=20, help="Número máximo de artículos a mostrar")
        if st.button("Buscar"):
            if not query:
                show_feedback(False, "Ingresa al menos una palabra clave para buscar.")
            else:
                keywords = [q.strip() for q in query.split(",") if q.strip()]
                try:
                    res = requests.get(
                        f"{API_COLLECTIONS_URL}/search",
                        params={"keywords": ",".join(keywords), "limit": limit}
                    )
                    res.raise_for_status()
                    data = res.json()
                    st.write(f"**{data.get('count', 0)} resultados encontrados**")
                    for a in data.get("articles", []):
                        st.json(a)
                except Exception as e:
                    show_feedback(False, f"Error en búsqueda: {e}")

