# Gestione Turni e Attività

Questa è un'applicazione Streamlit per la gestione dei turni e delle attività dei tecnici.

## Avvio con Docker

Per avviare l'applicazione, assicurati di avere Docker e Docker Compose installati.

1.  **Clona il repository:**
    ```bash
    git clone <URL_DEL_REPOSITORY>
    cd <NOME_DELLA_CARTELLA>
    ```

2.  **Configura Ngrok:**
    *   Rinomina il file `.env.example` in `.env`.
    *   Apri il file `.env` e incolla il tuo token di autenticazione di Ngrok. Puoi trovarlo sulla tua [dashboard di Ngrok](https://dashboard.ngrok.com/get-started/your-authtoken).

3.  **Avvia i servizi:**
    ```bash
    docker-compose up --build
    ```

    L'applicazione sarà accessibile tramite l'URL di Ngrok che vedrai nel terminale.

## Struttura del Progetto

*   `app.py`: Il punto di ingresso principale dell'applicazione Streamlit.
*   `modules/`: Contiene la logica di business (es. autenticazione, gestione dati).
*   `pages/`: Contiene i moduli per le diverse pagine dell'applicazione.
*   `styles/`: Fogli di stile CSS.
*   `crea_database.py`: Script per inizializzare il database SQLite.
*   `Dockerfile`: Definisce l'ambiente per eseguire l'applicazione in un container Docker.
*   `docker-compose.yml`: Orchestra l'avvio dell'applicazione e del servizio Ngrok.
