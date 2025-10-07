# 🚀 launcher.py
import subprocess
import time

print("🔧 Démarrage du backend FastAPI...")
backend = subprocess.Popen(
    "uvicorn app.main:app --reload",
    shell=True
)

# Donne quelques secondes au backend pour démarrer
time.sleep(3)

print("💻 Démarrage du frontend Streamlit...")
frontend = subprocess.Popen(
    "streamlit run frontend/app_streamlit.py",
    shell=True
)

print("\n✅ Les deux services sont lancés !")
print("➡️ FastAPI : http://localhost:8000")
print("➡️ Streamlit : http://localhost:8501\n")

try:
    # Attend la fin des deux processus
    backend.wait()
    frontend.wait()
except KeyboardInterrupt:
    print("\n🛑 Arrêt manuel détecté, fermeture des services...")
    backend.terminate()
    frontend.terminate()
    print("👋 Tout a été arrêté proprement.")
