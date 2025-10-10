import streamlit as st
from deep_translator import GoogleTranslator

# ==========================
# Traduction dynamique
# ==========================
def tr(text: str, user_lang: str = None) -> str:
    """
    Traduce dinámicamente un texto según el idioma del usuario.
    Por defecto, español.
    """
    if not user_lang:
        user_lang = st.session_state.get("user_lang", "es")
        st.session_state["user_lang"] = user_lang
    if user_lang == "es":
        return text
    try:
        return GoogleTranslator(source="es", target=user_lang).translate(text)
    except Exception:
        return text

# ==========================
# Feedback uniforme
# ==========================
def show_feedback(success: bool, msg: str):
    """
    Muestra un mensaje de éxito o error de manera consistente.
    """
    if success:
        st.success(msg)
    else:
        st.error(msg)


# ==========================
# Selector de mode en sidebar
# ==========================
def sidebar_mode_selector() -> str:
    st.sidebar.title("⚙️ Modo de trabajo")
    modo = st.sidebar.radio(
        "Selecciona un modo:",
        ["CRUD Colección", "IA Artículos", "📊 Estadísticas"],  # <-- ajout stats
        help=(
            "🗃️ CRUD Colección: Gestiona directamente los documentos de la base MongoDB.\n"
            "🤖 IA Artículos: Usa IA para analizar o generar contenido a partir de los artículos.\n"
            "📊 Estadísticas: Visualiza estadísticas precisas de la colección de artículos."
        )
    )
    st.sidebar.markdown(
        """
**Consejo:**  
Selecciona un modo y sigue las instrucciones que aparecerán en la pantalla.  
Cada acción mostrará logs, mensajes de éxito o error, y explicaciones paso a paso.
"""
    )
    return modo


# ==========================
# Composant de header principal
# ==========================
def main_header():
    """
    Muestra el header principal con instrucciones generales para el usuario.
    """
    st.title("📚 Gestor de Artículos — Interfaz API")
#     st.markdown("""
# Bienvenido a la interfaz de gestión de artículos y base de datos MongoDB.  
# Cada **modo de trabajo** tiene una función específica:

# - 🗃️ **CRUD Colección**: administrar directamente los documentos de la base MongoDB (ver, actualizar, eliminar).  
# - 🤖 **IA Artículos**: aplicar inteligencia artificial a los artículos (resumen, limpieza, generación de publicaciones).

# Sigue las instrucciones paso a paso y observa los logs para entender cada acción.
# """)
