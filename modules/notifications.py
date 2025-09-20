import pandas as pd
import datetime

def leggi_notifiche(gestionale_data, utente):
    df_notifiche = gestionale_data.get('notifiche')

    required_cols = ['ID_Notifica', 'Timestamp', 'Destinatario', 'Messaggio', 'Stato', 'Link_Azione']
    if df_notifiche is None or df_notifiche.empty:
        return pd.DataFrame(columns=required_cols)

    user_notifiche = df_notifiche[df_notifiche['Destinatario'] == utente].copy()

    if user_notifiche.empty:
        return user_notifiche

    user_notifiche['Timestamp'] = pd.to_datetime(user_notifiche['Timestamp'], errors='coerce')
    return user_notifiche.sort_values(by='Timestamp', ascending=False)

def crea_notifica(gestionale_data, destinatario, messaggio, link_azione=""):
    if 'notifiche' not in gestionale_data:
        gestionale_data['notifiche'] = pd.DataFrame(columns=['ID_Notifica', 'Timestamp', 'Destinatario', 'Messaggio', 'Stato', 'Link_Azione'])

    new_id = f"N_{int(datetime.datetime.now().timestamp())}"
    timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    nuova_notifica = pd.DataFrame([{
        'ID_Notifica': new_id,
        'Timestamp': timestamp,
        'Destinatario': destinatario,
        'Messaggio': messaggio,
        'Stato': 'non letta',
        'Link_Azione': link_azione
    }])

    gestionale_data['notifiche'] = pd.concat([gestionale_data['notifiche'], nuova_notifica], ignore_index=True)
    return True

def segna_notifica_letta(gestionale_data, id_notifica):
    if 'notifiche' not in gestionale_data or gestionale_data['notifiche'].empty:
        return False

    df_notifiche = gestionale_data['notifiche']
    idx = df_notifiche[df_notifiche['ID_Notifica'] == id_notifica].index

    if not idx.empty:
        df_notifiche.loc[idx, 'Stato'] = 'letta'
        return True
    return False
