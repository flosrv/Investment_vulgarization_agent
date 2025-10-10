import subprocess, os, signal

def kill_process(name):
    for line in os.popen("tasklist").read().splitlines():
        if name in line:
            os.system(f"taskkill /F /IM {name}.exe")

# Fermer si déjà ouverts
kill_process("uvicorn")
kill_process("streamlit")
kill_process("ngrok")

# Relancer dans des terminaux séparés
subprocess.Popen('start cmd /k "uvicorn main:app --reload"', shell=True)
subprocess.Popen('start cmd /k "streamlit run frontend/app.py"', shell=True)
subprocess.Popen('start cmd /k "ngrok http 8000"', shell=True)
