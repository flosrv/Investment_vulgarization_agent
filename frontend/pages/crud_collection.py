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
- Eliminar un documento por ID  
- Actualizar el campo `processed`  
- Buscar, ver recientes, actualizar metadatos, eliminar condicionalmente y estadísticas
""")

    accion = st.radio("Selecciona una acción:", [
        "Listar todos los documentos",
        "Eliminar documento por ID",
        "Actualizar campo processed",
        "Artículos recientes",
        "Buscar artículos",
        "Actualizar metadatos",
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

    # --- Eliminar documento por ID ---
    elif accion == "Eliminar documento por ID":
        st.subheader("🗑️ Eliminar documento")
        doc_id = st.text_input(placeholder="ID del documento a eliminar")
        if st.button("Eliminar"):
            if not doc_id:
                show_feedback(False, "Por favor, ingresa un ID válido.")
            else:
                try:
                    res = requests.delete(f"{API_COLLECTIONS_URL}/delete/{doc_id}")
                    if res.status_code == 200:
                        show_feedback(True, "Documento eliminado correctamente.")
                    else:
                        show_feedback(False, f"Error: {res.text}")
                except Exception as e:
                    show_feedback(False, f"Fallo al eliminar: {e}")

    # --- Actualizar campo processed ---
    elif accion == "Actualizar campo processed":
        st.subheader("✏️ Actualizar campo 'processed'")
        doc_id = st.text_input(placeholder="ID del documento a modificar")
        new_val = st.selectbox("Nuevo valor:", [True, False])
        if st.button("Actualizar"):
            if not doc_id:
                show_feedback(False, "Por favor, ingresa un ID.")
            else:
                try:
                    res = requests.put(f"{API_COLLECTIONS_URL}/update/{doc_id}", params={"processed": new_val})
                    if res.status_code == 200:
                        show_feedback(True, "Campo actualizado correctamente.")
                    else:
                        show_feedback(False, f"Error: {res.text}")
                except Exception as e:
                    show_feedback(False, f"Fallo al actualizar: {e}")

    # --- Artículos recientes ---
    elif accion == "Artículos recientes":
        st.subheader("🆕 Últimos artículos añadidos")
        limit = st.number_input(placeholder="Número de artículos a mostrar", min_value=1, max_value=50, value=10)
        if st.button("Cargar recientes"):
            try:
                res = requests.get(f"{API_COLLECTIONS_URL}/recent", params={"limit": limit})
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
        query = st.text_input(placeholder="Palabras clave (separadas por comas)")
        limit = st.number_input(placeholder="Número máximo de resultados", min_value=1, max_value=50, value=20)
        if st.button("Buscar"):
            if not query:
                show_feedback(False, "Ingresa al menos una palabra clave para buscar.")
            else:
                # Séparer les mots-clés par virgules et nettoyer les espaces
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


    # --- Actualizar metadatos ---
    elif accion == "Actualizar metadatos":
        st.subheader("✏️ Actualizar tags o categoría")
        doc_id = st.text_input("ID del artículo")
        tags = st.text_input("Tags (separados por comas)")
        category = st.text_input("Categoría")
        if st.button("Actualizar metadatos"):
            if not doc_id:
                show_feedback(False, "Ingresa el ID del artículo.")
            else:
                try:
                    payload = {}
                    if tags:
                        payload["tags"] = [t.strip() for t in tags.split(",")]
                    if category:
                        payload["category"] = category
                    res = requests.patch(f"{API_COLLECTIONS_URL}/update-metadata/{doc_id}", json=payload)
                    if res.status_code == 200:
                        show_feedback(True, "Metadatos actualizados correctamente.")
                        st.json(res.json())
                    else:
                        show_feedback(False, f"Error: {res.text}")
                except Exception as e:
                    show_feedback(False, f"Fallo al actualizar metadatos: {e}")

    # --- Eliminar condicionalmente ---
    elif accion == "Eliminar condicionalmente":
        st.subheader("🗑️ Eliminación condicional")
        processed = st.selectbox("Processed:", [None, True, False])
        language = st.text_input("Idioma (opcional)")
        older_than_str = st.text_input("Eliminar si añadido antes de (YYYY-MM-DD)")
        older_than = None
        if older_than_str:
            try:
                older_than = datetime.strptime(older_than_str, "%Y-%m-%d")
            except ValueError:
                show_feedback(False, "Fecha inválida, usar formato YYYY-MM-DD")
        if st.button("Eliminar condicionalmente"):
            try:
                params = {}
                if processed is not None:
                    params["processed"] = processed
                if language:
                    params["language"] = language
                if older_than:
                    params["older_than"] = older_than.isoformat()
                res = requests.delete(f"{API_COLLECTIONS_URL}/bulk-delete", params=params)
                if res.status_code == 200:
                    show_feedback(True, f"Eliminación condicional ejecutada.")
                    st.json(res.json())
                else:
                    show_feedback(False, f"Error: {res.text}")
            except Exception as e:
                show_feedback(False, f"Fallo en eliminación condicional: {e}")

    # --- Ver estadísticas ---
    elif accion == "Ver estadísticas":
        st.subheader("📊 Estadísticas de la colección")
        if st.button("Cargar estadísticas"):
            try:
                res = requests.get(f"{API_COLLECTIONS_URL}/stats")
                res.raise_for_status()
                st.json(res.json())
            except Exception as e:
                show_feedback(False, f"Error al cargar estadísticas: {e}")
