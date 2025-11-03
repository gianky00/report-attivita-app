# Usa un'immagine Python ufficiale come base
FROM python:3.11-slim

# Imposta la directory di lavoro nel container
WORKDIR /app

# Copia il file delle dipendenze e installale
# Questo passaggio viene eseguito separatamente per sfruttare la cache di Docker
COPY requirements.txt .

# Installa le dipendenze, ignorando l'errore se pywin32 non è disponibile
# RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements.txt || (grep -v "pywin32" requirements.txt > requirements_no_win.txt && pip install --no-cache-dir -r requirements_no_win.txt)


# Copia tutto il codice dell'applicazione nella directory di lavoro
COPY . .

# Scarica i pacchetti NLTK necessari
RUN python -m nltk.downloader punkt stopwords punkt_tab

# Espone la porta su cui Streamlit verrà eseguito
EXPOSE 8501

# Comando per avviare l'applicazione
# 1. Esegue lo script per creare il database
# 2. Avvia l'applicazione Streamlit
CMD ["sh", "-c", "python crea_database.py && python learning_module.py && streamlit run app.py --server.port=8501 --server.address=0.0.0.0"]
