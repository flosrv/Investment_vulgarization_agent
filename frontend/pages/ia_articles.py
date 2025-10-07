import streamlit as st
import requests
from components.constant_components import show_feedback

API_IA_URL = "https://gradely-dee-greaseproof.ngrok-free.dev/ia"

def render_ia_articles():
    st.header("🤖 Inteligencia Artificial — Artículos")
    st.markdown("""
Este modo aplica funciones de **procesamiento y generación IA** sobre los artículos almacenados:
- Cargar artículos desde un enlace web  
- Limpiar y analizar el contenido  
- Generar automáticamente publicaciones sociales educativas  
""")

    accion = st.radio("Selecciona una acción:", [
        "Cargar artículo desde enlace",
        "Listar artículos existentes",
        "Generar publicaciones sociales"
    ])

    # --- Cargar artículo desde enlace ---
    if accion == "Cargar artículo desde enlace":
        st.subheader("📰 Agregar artículo desde una URL")
        link = st.text_input("URL del artículo a importar")
        if st.button("Importar artículo"):
            if not link:
                show_feedback(False, "Por favor, ingresa una URL válida.")
            else:
                try:
                    res = requests.post(f"{API_IA_URL}/add-link", params={"link": link})
                    if res.status_code == 200:
                        show_feedback(True, f"Artículo agregado: {res.json().get('article_id')}")
                    else:
                        show_feedback(False, f"Error: {res.text}")
                except Exception as e:
                    show_feedback(False, f"Error al agregar: {e}")

    # --- Listar artículos existentes ---
    elif accion == "Listar artículos existentes":
        st.subheader("🗂️ Lista de artículos guardados")
        if st.button("Mostrar artículos"):
            try:
                res = requests.get(f"{API_IA_URL}/all")
                res.raise_for_status()
                data = res.json()
                st.write(f"**{data.get('count', 0)} artículos registrados**")
                for a in data.get("articles", []):
                    st.markdown(f"""
**🧾 {a.get('name', 'Sin título')}**
- ID: `{a.get('_id')}`
- Procesado: `{a.get('processed')}`
- Enlace: [{a.get('link')}]({a.get('link')})
- Descripción: {a.get('description', '(sin descripción)')}
""")
            except Exception as e:
                show_feedback(False, f"Error al obtener artículos: {e}")

    # --- Generar publicaciones sociales ---
    elif accion == "Generar publicaciones sociales":
        st.subheader("📢 Generación automática de publicaciones sociales")
        count = st.number_input("Número de publicaciones por artículo", min_value=1, max_value=5, value=2)
        if st.button("Generar publicaciones"):
            try:
                res = requests.post(f"{API_IA_URL}/generate-posts", params={"count": count})
                if res.status_code == 200:
                    data = res.json()
                    show_feedback(True, data.get("message", "Publicaciones generadas con éxito."))
                    st.json(data.get("details", {}))
                else:
                    show_feedback(False, f"Error: {res.text}")
            except Exception as e:
                show_feedback(False, f"Error al generar: {e}")
