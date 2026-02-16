# Usa un'immagine Python ufficiale come base
FROM python:3.11-slim

# Imposta la directory di lavoro nel container
WORKDIR /app

# Copia il file delle dipendenze
COPY requirements.txt .

# Installa le dipendenze:
# 1. Rimuove pywin32 (solo Windows)
# 2. Installa tutto il resto
# 3. Forza l'installazione di streamlit per sicurezza
RUN sed -i '/pywin32/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir streamlit==1.49.1

# Copia tutto il codice dell'applicazione
COPY . .

# Scarica i pacchetti NLTK necessari
RUN python -m nltk.downloader punkt stopwords punkt_tab

# Espone la porta
EXPOSE 8501

# Avvio diretto (il database viene gestito dal comando nel docker-compose)
CMD ["python", "-m", "streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
