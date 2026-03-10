import os
from diagrams import Diagram, Cluster, Edge
from diagrams.programming.language import Python

# Fix for Windows: Add Graphviz to PATH
os.environ["PATH"] += os.pathsep + r'C:\Program Files\Graphviz\bin'

from diagrams.onprem.client import User
from diagrams.generic.database import SQL
from diagrams.onprem.network import Nginx
from diagrams.onprem.container import Docker
from diagrams.saas.chat import Teams, Messenger
from diagrams.gcp.ml import NaturalLanguageAPI
from diagrams.gcp.storage import GCS
from diagrams.generic.blank import Blank
from diagrams.generic.storage import Storage

graph_attr = {
    "fontsize": "24",
    "bgcolor": "white",
    "fontname": "Verdana Bold",
    "pad": "1.0",
    "nodesep": "1.0",
    "ranksep": "1.5",
    "dpi": "300",
    "splines": "ortho",
    "concentrate": "true"
}

with Diagram("Report Attivita App Architecture", show=False, filename="docs/assets/architecture", direction="LR", graph_attr=graph_attr):
    user = User("Tecnico / Admin")

    with Cluster("External Services & Integrations"):
        gemini = NaturalLanguageAPI("Google Gemini AI\n(Revisione Report)")
        ngrok = Blank("Ngrok\n(External Tunnel)")
        outlook = Teams("Microsoft Outlook\n(Email Dispatch)")
        gsheets = GCS("Google Sheets\n(Export/Backup)")

    with Cluster("Infrastruttura (Docker)"):
        nginx = Nginx("Nginx Proxy\n(HTTPS/Routing)")
        app_container = Docker("Streamlit App\nContainer")
        
        with Cluster("Core Application"):
            entrypoint = Python("app.py\n(Streamlit)")
            
            with Cluster("Business Modules"):
                ai_engine = Python("ai_engine\n(Prompting)")
                auth_mod = Python("auth\n(2FA/Security)")
                instr_logic = Python("instrumentation\n(ISA S5.1)")
                shift_mgmt = Python("shift_mgmt\n(Turni)")
                data_mgmt = Python("data_mgmt\n(Logic)")
                
            with Cluster("Core Engine"):
                db_core = Python("database.py\n(Thread-Safe)")
                config_core = Python("config.py\n(Dynamic)")
                logger_core = Python("logging.py")

    with Cluster("Persistence & Data Sources"):
        sqlite_db = SQL("report-attivita.db (SQLite)")
        excel_legacy = Storage("Network Excel Files\n(Daily Tasks)")
        sync_script = Python("sync_data.py\n(Data Sync Service)")

    # Connections - Flusso Accesso
    user >> Edge(label="HTTPS", color="blue") >> ngrok >> nginx >> app_container
    app_container >> entrypoint
    
    # Internal Logic
    entrypoint >> auth_mod
    entrypoint >> data_mgmt
    entrypoint >> shift_mgmt
    
    auth_mod >> db_core
    data_mgmt >> db_core
    shift_mgmt >> db_core
    
    # AI & Instrumentation
    data_mgmt >> Edge(label="AI Request", color="cyan") >> ai_engine
    ai_engine >> Edge(label="API Call", color="red", style="dashed") >> gemini
    
    data_mgmt >> Edge(label="ISA Parsing", color="purple") >> instr_logic
    
    # Storage
    db_core >> Edge(label="SQL", color="orange") >> sqlite_db
    
    # Sync Service
    sync_script >> Edge(label="Parse", color="orange") >> excel_legacy
    sync_script >> Edge(label="Sync", color="orange") >> sqlite_db
    
    # External Output
    data_mgmt >> Edge(label="Dispatch", color="darkgreen") >> outlook
    data_mgmt >> Edge(label="Export", color="darkgreen") >> gsheets
    
    # System Overlays
    config_core >> Edge(style="dotted", color="gray") >> entrypoint
    logger_core >> Edge(style="dotted", color="gray") >> entrypoint
