import pandas as pd
import datetime
import sys
from openpyxl import load_workbook
import re
import os
import json
import urllib.request
import time
import pyperclip
import urllib.parse

# --- FUNZIONE PER OTTENERE L'URL DI NGROK ---
def get_ngrok_url():
    url_api = "http://127.0.0.1:4040/api/tunnels"
    for _ in range(5):
        try:
            with urllib.request.urlopen(url_api) as response:
                data = json.loads(response.read().decode())
                for tunnel in data['tunnels']:
                    if tunnel['proto'] == 'https':
                        return tunnel['public_url']
        except Exception:
            time.sleep(2)
    return None

# --- CONFIGURAZIONE SCRIPT ---
path_giornaliera_base = r'\\192.168.11.251\Database_Tecnico_SMI\Giornaliere\Giornaliere 2025'
script_dir = os.path.dirname(os.path.abspath(__file__))
PATH_GESTIONALE = os.path.join(script_dir, 'Gestionale_Tecnici.xlsx')
USA_GIORNO_PRECEDENTE = False

# --- FUNZIONE DI RICERCA ATTIVITÀ ---
def trova_attivita(utente_completo, giorno, mese, anno):
    try:
        path_giornaliera_mensile = os.path.join(path_giornaliera_base, f"Giornaliera {mese:02d}-{anno}.xlsm")
        df_giornaliera = pd.read_excel(path_giornaliera_mensile, sheet_name=str(giorno), engine='openpyxl', header=None)
        df_range = df_giornaliera.iloc[3:45].copy()
        riga_utente = pd.DataFrame()
        
        for index, riga in df_range.iterrows():
            nome_in_giornaliera = str(riga[5]).strip()
            if not nome_in_giornaliera or nome_in_giornaliera.lower() == 'nan': continue
            parts_completo = utente_completo.lower().split()
            parts_giornaliera = nome_in_giornaliera.lower().split()
            match_trovato = False
            if len(parts_giornaliera) == 1 and parts_giornaliera[0] in parts_completo: match_trovato = True
            elif len(parts_giornaliera) == 2 and parts_giornaliera[1].endswith('.'):
                cognome_g, iniziale_g = parts_giornaliera[0], parts_giornaliera[1].replace('.', '')
                if cognome_g in parts_completo and any(p.startswith(iniziale_g) for p in parts_completo if p != cognome_g):
                    match_trovato = True
            if match_trovato:
                riga_utente = riga.to_frame().T
                break

        if riga_utente.empty: return []
        
        lista_attivita_finale = []
        for index, riga in riga_utente.iterrows():
            pdl_text, desc_text = str(riga[9]), str(riga[6])
            if pdl_text.lower() in ['nan', ''] or desc_text.lower() in ['nan', '']: continue
            
            lista_pdl = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)
            lista_descrizioni = [line.strip() for line in desc_text.splitlines() if line.strip()]

            for pdl, desc in zip(lista_pdl, lista_descrizioni):
                lista_attivita_finale.append({'pdl': pdl, 'attivita': desc})
        return lista_attivita_finale
    except FileNotFoundError:
        return []
    except Exception:
        return []

# --- INIZIO SCRIPT ---
URL_NGROK = get_ngrok_url()
if not URL_NGROK:
    sys.exit(1)

try:
    gestionale = pd.read_excel(PATH_GESTIONALE, sheet_name=None)
    df_contatti = gestionale['Contatti']
    
    for index, riga in df_contatti.iterrows():
        nome_utente_completo = str(riga['Nome Cognome']).strip()
        user_param = nome_utente_completo.split()[-1]
        if "Garro" in nome_utente_completo: user_param = "Garro L"
        user_param_encoded = urllib.parse.quote(user_param)
        link_questionario = f"{URL_NGROK}/?user={user_param_encoded}"
        df_contatti.at[index, 'Link Attività'] = link_questionario
        
    with pd.ExcelWriter(PATH_GESTIONALE, engine='openpyxl') as writer:
        df_contatti.to_excel(writer, sheet_name='Contatti', index=False)
        gestionale['TurniDisponibili'].to_excel(writer, sheet_name='TurniDisponibili', index=False)
        gestionale['Prenotazioni'].to_excel(writer, sheet_name='Prenotazioni', index=False)
        gestionale['SostituzioniPendenti'].to_excel(writer, sheet_name='SostituzioniPendenti', index=False)
        if 'Notifiche' in gestionale:
            gestionale['Notifiche'].to_excel(writer, sheet_name='Notifiche', index=False)
        if 'TurniInBacheca' in gestionale:
            gestionale['TurniInBacheca'].to_excel(writer, sheet_name='TurniInBacheca', index=False)
        if 'RichiesteMateriali' in gestionale:
            gestionale['RichiesteMateriali'].to_excel(writer, sheet_name='RichiesteMateriali', index=False)
        if 'RichiesteAssenze' in gestionale:
            gestionale['RichiesteAssenze'].to_excel(writer, sheet_name='RichiesteAssenze', index=False)

except Exception:
    sys.exit(1)

sys.exit(0)