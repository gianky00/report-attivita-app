# Gestione Turni e Attività

Questa è un'applicazione Streamlit per la gestione dei turni e delle attività dei tecnici.

## Guida all'Avvio Rapido (con Docker)

Segui questi passaggi per avviare l'applicazione in modo corretto e sicuro.

### Prerequisiti
- **Docker Desktop**: Assicurati che sia installato e **in esecuzione** sul tuo computer.

### Passaggi di Configurazione

1.  **Clona il Repository**
    Se non lo hai già fatto, clona il progetto sulla tua macchina locale.
    ```bash
    git clone https://github.com/gianky00/report-attivita-app.git
    cd report-attivita-app
    ```

2.  **Crea il File di Ambiente (`.env`)**
    Questo file conterrà il tuo token di Ngrok.
    - Trova il file `.env.example` nel progetto.
    - **Rinominalo in `.env`**.
    - Aprilo con un editor di testo e incolla il tuo token di autenticazione di Ngrok dopo `NGROK_AUTHTOKEN=`.

    *Esempio di file `.env` compilato:*
    ```
    NGROK_AUTHTOKEN=IL_TUO_TOKEN_PERSONALE_QUI
    ```
    > **Nota sulla sicurezza**: Il file `.gitignore` è già configurato per impedire che il tuo file `.env` venga caricato su GitHub. Mantieni il tuo token segreto.

3.  **Avvia l'Applicazione (come Amministratore)**
    Per permettere a Docker di funzionare correttamente su Windows, è fondamentale eseguire i comandi da un terminale con privilegi elevati.
    - Cerca **"Prompt dei comandi"** (o "PowerShell") nel menu Start.
    - Fai clic destro sull'icona e seleziona **"Esegui come amministratore"**.
    - Nel terminale da amministratore, naviga fino alla cartella del progetto (`report-attivita-app`).
    - Esegui il seguente comando per costruire l'immagine e avviare i servizi:
    ```bash
    docker-compose up --build
    ```

4.  **Accedi all'Applicazione**
    Dopo qualche istante, il terminale mostrerà i log di avvio. Cerca l'URL pubblico fornito da Ngrok (di solito termina con `.ngrok-free.app`) e aprilo nel tuo browser per usare l'applicazione.

## Struttura del Progetto

*   `app.py`: Il punto di ingresso principale dell'applicazione Streamlit.
*   `modules/`: Contiene la logica di business (es. autenticazione, gestione dati).
*   `pages/`: Contiene i moduli per le diverse pagine dell'applicazione.
*   `styles/`: Fogli di stile CSS.
*   `crea_database.py`: Script per inizializzare il database SQLite.
*   `Dockerfile`: Definisce l'ambiente per eseguire l'applicazione in un container Docker.
*   `docker-compose.yml`: Orchestra l'avvio dell'applicazione e del servizio Ngrok.
