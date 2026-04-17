# Usa un'immagine Python ufficiale come base
FROM python:3.11-slim

# Imposta la directory di lavoro nel container
WORKDIR /app

# Installa Poetry
RUN pip install --no-cache-dir poetry

# Copia i file delle dipendenze
COPY pyproject.toml poetry.lock* ./

# Configura Poetry per non creare un ambiente virtuale nel container e installa le dipendenze
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --without dev

# Copia tutto il codice dell'applicazione
COPY . .

# Scarica i pacchetti NLTK necessari
RUN python -m nltk.downloader punkt stopwords punkt_tab

# Espone la porta
EXPOSE 8501

# Avvio diretto (il database viene gestito dal comando nel docker-compose)
CMD ["python", "-m", "streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
