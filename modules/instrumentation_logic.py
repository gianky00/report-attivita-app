import re

# ISA S5.1 Knowledge Base (semplificata e adattata)
# Mappa le lettere a una funzione/componente e a un tipo generico
ISA_KB = {
    # Funzioni/Componenti chiave (spesso l'ultima lettera o una combinazione)
    'C': {'name': 'Regolatore', 'type': '[CONTROLLORE]'},
    'V': {'name': 'Valvola', 'type': '[ATUTTATORE]'},
    'T': {'name': 'Trasmettitore', 'type': '[TRASMETTITORE]'},
    'E': {'name': 'Elemento primario', 'type': '[SENSORE]'},
    'I': {'name': 'Indicatore', 'type': '[INDICATORE]'},
    'R': {'name': 'Registratore', 'type': '[REGISTRATORE]'},
    'S': {'name': 'Interruttore', 'type': '[SWITCH]'},
    'Y': {'name': 'Relè/Convertitore', 'type': '[LOGICA_AUSILIARIA]'},

    # Combinazioni speciali che hanno la precedenza
    'CV': {'name': 'Valvola di Controllo', 'type': '[ATUTTATORE]'},
    'RC': {'name': 'Controllore e Registratore', 'type': '[CONTROLLORE]'},
    'PSV': {'name': 'Valvola di Sicurezza Pressione', 'type': '[VALVOLA_SICUREZZA]'},
    'TT': {'name': 'Trasmettitore di Temperatura', 'type': '[TRASMETTITORE]'},
    'PT': {'name': 'Trasmettitore di Pressione', 'type': '[TRASMETTITORE]'},
    'LT': {'name': 'Trasmettitore di Livello', 'type': '[TRASMETTITORE]'},
    'FT': {'name': 'Trasmettitore di Portata', 'type': '[TRASMETTITORE]'},
}

# Mappatura delle variabili misurate (solitamente la prima lettera)
MEASURED_VARIABLE_KB = {
    'F': 'Portata',
    'P': 'Pressione',
    'T': 'Temperatura',
    'L': 'Livello',
    'A': 'Analisi',
    'S': 'Velocità',
    'V': 'Vibrazione',
    'W': 'Peso',
    'Q': 'Quantità',
}

def parse_instrument_tag(tag):
    """
    Analizza un tag di strumentazione per estrarre le sue parti.
    Gestisce formati come FCV301 e F301RC.
    Ritorna un dizionario con le informazioni o None se il formato non è valido.
    """
    tag = tag.strip().upper()

    # Pattern per formati come: FCV301, TT301, PSV100A
    match1 = re.fullmatch(r'([A-Z]+)(\d+)([A-Z]*)', tag)
    # Pattern per formati come: F301RC, T301C
    match2 = re.fullmatch(r'([A-Z])(\d+)([A-Z]+)', tag)

    prefix, loop_num, suffix = '', '', ''
    is_suffix_style = False
    if match2:
        prefix = match2.group(1)
        loop_num = match2.group(2)
        suffix = match2.group(3)
        is_suffix_style = True
    elif match1:
        prefix = match1.group(1)
        loop_num = match1.group(2)
        suffix = match1.group(3) # Può essere vuoto
    else:
        return None # Formato non riconosciuto

    instrument_type = 'Sconosciuto'
    description = 'Dispositivo generico'

    # Le lettere che definiscono la funzione sono nel suffisso (es. F301RC) o nel prefisso (es. FCV301)
    key_letters = suffix if is_suffix_style and suffix else prefix

    # 1. Controlla le combinazioni speciali (più specifiche)
    if key_letters in ISA_KB:
        instrument_type = ISA_KB[key_letters]['type']
        description = ISA_KB[key_letters]['name']
    # 2. Se non è una combinazione speciale, analizza le singole lettere.
    # L'ultima lettera è spesso la più significativa per il tipo di dispositivo.
    elif len(key_letters) > 0 and key_letters[-1] in ISA_KB:
        main_func_char = key_letters[-1]
        # Caso speciale: 'T' può essere Temperatura o Trasmettitore. Se è la prima lettera, è quasi sempre Temperatura.
        # Se è dopo altre lettere (es. PT, LT), è Trasmettitore.
        if main_func_char == 'T' and len(key_letters) > 1:
             # È un trasmettitore, es. PT, LT, FT
            instrument_type = ISA_KB['T']['type']
            description = ISA_KB['T']['name']
        elif main_func_char in ISA_KB:
            instrument_type = ISA_KB[main_func_char]['type']
            description = ISA_KB[main_func_char]['name']

    # Aggiungi la descrizione della variabile misurata (basata sulla prima lettera del prefisso)
    measured_var_char = prefix[0]
    if measured_var_char in MEASURED_VARIABLE_KB:
        variable_name = MEASURED_VARIABLE_KB[measured_var_char]
        full_description = f"{description} di {variable_name.lower()}"
    else:
        full_description = description

    return {
        'tag': tag,
        'loop': loop_num,
        'type': instrument_type,
        'description': full_description,
        'variable': MEASURED_VARIABLE_KB.get(measured_var_char, 'Sconosciuta')
    }

def find_and_analyze_tags(text):
    """
    Trova tutti i tag di strumentazione nel testo e li analizza.
    Ritorna un dizionario raggruppato per numero di loop.
    """
    # Regex migliorato per trovare possibili tag. Evita di catturare parole normali.
    # Cerca parole che contengono un mix di lettere maiuscole e numeri.
    potential_tags = re.findall(r'\b[A-Z]{1,4}\d{2,4}[A-Z]{0,2}\b', text.upper())

    loops = {}
    analyzed_tags = []

    for tag in potential_tags:
        parsed_info = parse_instrument_tag(tag)
        if parsed_info and parsed_info['type'] != 'Sconosciuto':
            loop_id = parsed_info['loop']
            if loop_id not in loops:
                loops[loop_id] = []
            loops[loop_id].append(parsed_info)
            analyzed_tags.append(parsed_info)

    return loops, analyzed_tags

# Knowledge base per il troubleshooting
TROUBLESHOOTING_KB = {
    'keywords': {
        'termoresistenza': [
            "Suggerimento Termoresistenza (RTD): Se il segnale è a fondo scala o interrotto, verificare la continuità del sensore a 3 o 4 fili. Un valore infinito indica un sensore bruciato.",
            "Suggerimento RTD: Un segnale instabile può essere causato da cattive connessioni nella testa di giunzione o da vibrazioni meccaniche."
        ],
        'rtd': [
            "Suggerimento Termoresistenza (RTD): Se il segnale è a fondo scala o interrotto, verificare la continuità del sensore a 3 o 4 fili. Un valore infinito indica un sensore bruciato.",
            "Suggerimento RTD: Un segnale instabile può essere causato da cattive connessioni nella testa di giunzione o da vibrazioni meccaniche."
        ],
        'termocoppia': [
            "Suggerimento Termocoppia (TC): Un segnale a fondo scala (alto o basso) spesso indica una TC 'bruciata' o un circuito aperto.",
            "Suggerimento TC: Se il segnale è 'ballerino' o rumoroso, controllare la corretta messa a terra della calza e l'assenza di disturbi elettromagnetici (es. vicinanza a motori).",
            "Suggerimento TC: Verificare che il tipo di TC (es. K, J) sia corretto per il trasmettitore."
        ],
        'pressione differenziale': [
            "Suggerimento Pressione Differenziale: Se usato per misure di portata, verificare che le prese d'impulso (lato alta e bassa pressione) non siano ostruite o invertite.",
            "Suggerimento Pressione Differenziale: Per misure di livello su serbatoi pressurizzati, assicurarsi che la presa di bassa pressione (compensazione) sia libera."
        ],
        'flussimetro magnetico': [
            "Suggerimento Flussimetro Magnetico: Funziona solo con liquidi conduttivi. Un segnale a zero o instabile può indicare elettrodi sporchi o incrostati.",
            "Suggerimento Flussimetro Magnetico: Assicurarsi che il tubo di misura sia sempre pieno di liquido durante il funzionamento."
        ],
        'livellostato a galleggiante': [
            "Suggerimento Livellostato a Galleggiante: La causa più comune di guasto è il blocco meccanico del galleggiante a causa di sporco o incrostazioni."
        ],
        'radar': [
            "Suggerimento Radar Guidato/Libero: La presenza di schiuma o forte turbolenza sulla superficie del liquido può ingannare la misura, causando letture errate o instabili.",
            "Suggerimento Radar: Verificare che non ci siano ostacoli (es. tubi, agitatori) nel cono di misura del sensore."
        ],
        'primari': [
            "Suggerimento Prese Primarie: Se si parla di 'primari tappati' in un sistema di misura di portata, si fa riferimento alle prese di pressione a monte e a valle dell'elemento deprimente (es. orifizio). L'operazione corretta è lo spurgo (stasatura)."
        ]
    },
    'types': {
        '[ATUTTATORE]': [
            "Suggerimento Attuatore/Valvola: Verificare sempre la pressione di alimentazione dell'aria allo strumento (tipicamente richiesta dal posizionatore). Un filtro riduttore intasato è una causa comune di malfunzionamento.",
            "Suggerimento Valvola di Controllo: Se la valvola 'oscilla', il problema potrebbe essere un guadagno troppo elevato nel posizionatore o nel controllore del loop."
        ],
        '[CONTROLLORE]': [
            "Suggerimento Controllore: Se un loop è in manuale, il controllore non invierà alcun comando all'elemento finale di controllo. Verificare sempre la modalità (MAN/AUTO).",
            "Suggerimento Controllore: Parametri PID (Proporzionale, Integrale, Derivativo) non corretti possono causare instabilità o lentezza nella regolazione."
        ],
        '[TRASMETTITORE]': [
            "Suggerimento Trasmettitore: Oltre alla taratura dello zero e dello span, verificare che l'alimentazione elettrica (tipicamente 24Vdc su loop 4-20mA) sia stabile e corretta."
        ]
    }
}

def get_technical_suggestions(text):
    """
    Analizza il testo e restituisce una lista di suggerimenti tecnici pertinenti.
    """
    if not text:
        return []

    suggestions = set() # Usa un set per evitare duplicati
    lower_text = text.lower()

    # 1. Cerca suggerimenti basati su parole chiave
    for keyword, hints in TROUBLESHOOTING_KB['keywords'].items():
        if keyword in lower_text:
            for hint in hints:
                suggestions.add(hint)

    # 2. Cerca suggerimenti basati sui tipi di strumento trovati
    _, analyzed_tags = find_and_analyze_tags(text)
    for tag_info in analyzed_tags:
        instrument_type = tag_info['type']
        if instrument_type in TROUBLESHOOTING_KB['types']:
            for hint in TROUBLESHOOTING_KB['types'][instrument_type]:
                suggestions.add(hint)

    return list(suggestions)