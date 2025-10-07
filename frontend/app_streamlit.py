import streamlit as st
from components.constant_components import main_header, sidebar_mode_selector

# === Page configuration ===
st.set_page_config(page_title="Gestor de Artículos", layout="wide")

# === Affichage du header principal avec instructions générales ===
main_header()

st.markdown("""
Bienvenido a la interfaz de gestión de artículos.  
Sigue las instrucciones paso a paso según el **modo de trabajo** que selecciones a la izquierda.  
Cada acción mostrará información clara, logs en tiempo real y mensajes de éxito o error para que sepas exactamente qué ocurre.
""")

# === Choix du mode via sidebar ===
modo = sidebar_mode_selector()
st.markdown("""
**Consejo:** Selecciona un modo y sigue las instrucciones que aparecerán en la pantalla.  
- 🗃️ **CRUD Colección**: Manipula directamente la base de datos MongoDB.  
- 🤖 **IA Artículos**: Procesa los artículos usando IA y genera publicaciones automáticas.  
- 📊 **Estadísticas**: Visualiza estadísticas precisas y gráficas de la colección de artículos.
""")

# === Import dynamique des pages selon le mode choisi ===
if modo == "CRUD Colección":
    st.markdown("### Modo CRUD Colección — Gestión de documentos")
    st.markdown("""
Aquí podrás **listar, eliminar o actualizar documentos** de la colección MongoDB.  
Cada acción mostrará mensajes de feedback claros y logs de lo que está ocurriendo.
""")
    from pages.crud_collection import render_crud_collection
    render_crud_collection()

elif modo == "IA Artículos":
    st.markdown("### Modo IA Artículos — Procesamiento inteligente")
    st.markdown("""
Este modo permite **importar artículos desde un enlace web, analizarlos y generar publicaciones sociales automáticamente**.  
Sigue las instrucciones que aparecerán paso a paso y observa los mensajes de log para entender cada operación.
""")
    from pages.ia_articles import render_ia_articles
    render_ia_articles()

elif modo == "📊 Estadísticas":
    st.markdown("### Modo Estadísticas — Análisis detallado")
    st.markdown("""
Visualiza **estadísticas precisas y gráficas** sobre tu colección de artículos:  
- Número de artículos totales y procesados  
- Distribución por idioma  
- Distribución por tags  
- Artículos agregados por mes  
- Artículos antiguos no procesados  
""")
    from pages.stats import render_stats_page
    render_stats_page()
