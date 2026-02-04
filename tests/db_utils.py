"""
Utility per l'inizializzazione del database di test.
Contiene lo schema SQL aggiornato del progetto.
"""

SCHEMA_SQL = """
CREATE TABLE contatti (
    Matricola TEXT PRIMARY KEY NOT NULL,
    "Nome Cognome" TEXT NOT NULL UNIQUE,
    Ruolo TEXT,
    PasswordHash TEXT,
    "Link Attività" TEXT,
    "2FA_Secret" TEXT
);
CREATE TABLE turni (
    ID_Turno TEXT PRIMARY KEY NOT NULL,
    Descrizione TEXT,
    Data TEXT,
    OrarioInizio TEXT,
    OrarioFine TEXT,
    PostiTecnico INTEGER,
    PostiAiutante INTEGER,
    Tipo TEXT
);
CREATE TABLE prenotazioni (
    ID_Prenotazione TEXT PRIMARY KEY NOT NULL,
    ID_Turno TEXT NOT NULL,
    Matricola TEXT NOT NULL,
    RuoloOccupato TEXT,
    Timestamp TEXT,
    FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE,
    FOREIGN KEY (Matricola) REFERENCES contatti(Matricola) ON DELETE CASCADE
);
CREATE TABLE shift_logs (
    ID_Modifica TEXT PRIMARY KEY NOT NULL,
    Timestamp TEXT,
    ID_Turno TEXT,
    Azione TEXT,
    UtenteOriginale TEXT,
    UtenteSubentrante TEXT,
    EseguitoDa TEXT
);
CREATE TABLE access_logs (timestamp TEXT, username TEXT, status TEXT);
CREATE TABLE notifiche (
    ID_Notifica TEXT PRIMARY KEY NOT NULL,
    Timestamp TEXT,
    Destinatario_Matricola TEXT NOT NULL,
    Messaggio TEXT,
    Stato TEXT,
    Link_Azione TEXT,
    FOREIGN KEY (Destinatario_Matricola)
        REFERENCES contatti(Matricola) ON DELETE CASCADE
);
CREATE TABLE report_da_validare (
    id_report TEXT PRIMARY KEY NOT NULL,
    pdl TEXT,
    descrizione_attivita TEXT,
    matricola_tecnico TEXT,
    nome_tecnico TEXT,
    stato_attivita TEXT,
    testo_report TEXT,
    data_compilazione TEXT,
    data_riferimento_attivita TEXT
);
"""
