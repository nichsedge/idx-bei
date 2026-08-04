import os
import json
import re
import datetime
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NetworkAlpha")

# Load environment variables
load_dotenv()

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, '../data')
ALL_COMPANIES_FILE = os.path.join(DATA_DIR, 'allCompanies.json')
COMPANY_DETAILS_FILE = os.path.join(DATA_DIR, 'companyDetailsByKodeEmiten.json')
FINANCIAL_RATIO_FILE = os.path.join(DATA_DIR, 'financial_ratio.json')
OUTPUT_FILE = os.path.join(DATA_DIR, 'network_alpha_data.json')

# Database configs
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB = os.getenv("POSTGRES_DB", "postgres")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# Define Blue Chip Stock codes (known high-market-cap, high-reputation Indonesian stocks)
BLUE_CHIPS = {
    "BBCA", "BBRI", "BMRI", "TLKM", "ASII", "BBNI", "UNVR", "KLBF", "ICBP", 
    "PGAS", "JSMR", "ADRO", "PTBA", "INDF", "GOTO", "AMRT", "SMGR", "UNTR", 
    "BRPT", "TPIA", "BYAN", "CPIN", "TCPI", "INKP", "ADMR"
}

def clean_name(name):
    """Clean Indonesian corporate names and titles for consistent deduplication."""
    if not name or not isinstance(name, str):
        return ""
    # Convert to uppercase
    n = name.strip().upper()
    # Remove punctuation except spaces
    n = re.sub(r'[^\w\s]', '', n)
    
    # Remove common corporate indicators if we want to isolate people
    # but keep them for shareholder networks. We clean titles first.
    titles = [
        r'\bDR\b', r'\bDRS\b', r'\bIR\b', r'\bPROF\b', r'\bKH\b', r'\bHJ\b', r'\bH\b',
        r'\bSH\b', r'\bMH\b', r'\bPHD\b', r'\bSE\b', r'\bMM\b', r'\bMSI\b', r'\bST\b',
        r'\bMT\b', r'\bBSC\b', r'\bMBA\b', r'\bMACC\b', r'\bAK\b', r'\bBBA\b', r'\bME\b'
    ]
    for title in titles:
        n = re.sub(title, '', n)
        
    # Collapse double spaces
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def is_corporate_name(name):
    """Identifies if a shareholder or entity is a corporation/proxy rather than an individual."""
    if not name:
        return False
    name_upper = name.upper()
    keywords = [
        "PT", "LTD", "LIMITED", "INC", "TBK", "MASYARAKAT", "SAHAM", "PENGENDALI", 
        "REPUBLIK", "GOVERNMENT", "FUND", "TRUST", "NOMINEES", "BANK", "ASSET", 
        "MANAGEMENT", "SECURITIES", "CORP", "CORPORATION", "CO", "SOCIETE", 
        "INVESTMENT", "HOLDINGS", "CAPITAL", "PENSION", "TREASURY"
    ]
    return any(keyword in name_upper for keyword in keywords)

# ==========================================
# 1. LOAD FINANCIAL RATIOS
# ==========================================
def load_financial_ratios():
    """Load latest financial ratios from PostgreSQL or fallback to JSON."""
    ratios = {}
    db_success = False

    # Try PostgreSQL first
    try:
        from sqlalchemy import create_engine
        pg_url = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
        engine = create_engine(pg_url)
        # Check connection
        with engine.connect() as conn:
            query = """
            WITH latest_fs AS (
                SELECT code, MAX(fs_date) as latest_date
                FROM financial_ratios
                GROUP BY code
            )
            SELECT 
                sf.code, sf.stock_name, sf.sector, sf.sub_sector, sf.industry, sf.sub_industry,
                sf.fs_date, sf.assets, sf.liabilities, sf.equity, sf.sales, sf.ebt, 
                sf.profit_period, sf.profit_attr_owner, sf.eps, sf.book_value, 
                sf.per, sf.price_bv, sf.de_ratio, sf.roa, sf.roe, sf.npm
            FROM 
                financial_ratios sf
            JOIN 
                latest_fs lf ON sf.code = lf.code AND sf.fs_date = lf.latest_date
            """
            df = pd.read_sql(query, conn)
            # Convert to dictionary
            for _, row in df.iterrows():
                code = row['code']
                ratios[code] = {
                    'code': code,
                    'stock_name': row['stock_name'],
                    'sector': row['sector'],
                    'sub_sector': row['sub_sector'],
                    'industry': row['industry'],
                    'sub_industry': row['sub_industry'],
                    'fs_date': str(row['fs_date']) if row['fs_date'] else None,
                    'assets': float(row['assets']) if row['assets'] is not None else 0.0,
                    'liabilities': float(row['liabilities']) if row['liabilities'] is not None else 0.0,
                    'equity': float(row['equity']) if row['equity'] is not None else 0.0,
                    'sales': float(row['sales']) if row['sales'] is not None else 0.0,
                    'profit_period': float(row['profit_period']) if row['profit_period'] is not None else 0.0,
                    'eps': float(row['eps']) if row['eps'] is not None else 0.0,
                    'book_value': float(row['book_value']) if row['book_value'] is not None else 0.0,
                    'per': float(row['per']) if row['per'] is not None else 0.0,
                    'price_bv': float(row['price_bv']) if row['price_bv'] is not None else 0.0,
                    'de_ratio': float(row['de_ratio']) if row['de_ratio'] is not None else 0.0,
                    'roa': float(row['roa']) if row['roa'] is not None else 0.0,
                    'roe': float(row['roe']) if row['roe'] is not None else 0.0,
                    'npm': float(row['npm']) if row['npm'] is not None else 0.0
                }
            logger.info(f"Successfully loaded {len(ratios)} financial records from PostgreSQL.")
            db_success = True
    except Exception as e:
        logger.warning(f"Could not connect to PostgreSQL database ({e}). Falling back to JSON file.")

    # Fallback to JSON file
    if not db_success:
        if os.path.exists(FINANCIAL_RATIO_FILE):
            try:
                with open(FINANCIAL_RATIO_FILE, 'r') as f:
                    raw_data = json.load(f)
                
                # Group by code and take the latest record
                data_list = raw_data.get('data', [])
                sorted_data = sorted(data_list, key=lambda x: (x.get('code', ''), x.get('fsDate', '')), reverse=True)
                
                seen_codes = set()
                for item in sorted_data:
                    code = item.get('code')
                    if not code or code in seen_codes:
                        continue
                    seen_codes.add(code)
                    
                    ratios[code] = {
                        'code': code,
                        'stock_name': item.get('stockName'),
                        'sector': item.get('sector'),
                        'sub_sector': item.get('subSector'),
                        'industry': item.get('industry'),
                        'sub_industry': item.get('subIndustry'),
                        'fs_date': item.get('fsDate'),
                        'assets': float(item.get('assets', 0.0) or 0.0),
                        'liabilities': float(item.get('liabilities', 0.0) or 0.0),
                        'equity': float(item.get('equity', 0.0) or 0.0),
                        'sales': float(item.get('sales', 0.0) or 0.0),
                        'profit_period': float(item.get('profitPeriod', 0.0) or 0.0),
                        'eps': float(item.get('eps', 0.0) or 0.0),
                        'book_value': float(item.get('bookValue', 0.0) or 0.0),
                        'per': float(item.get('per', 0.0) or 0.0),
                        'price_bv': float(item.get('priceBV', 0.0) or 0.0),
                        'de_ratio': float(item.get('deRatio', 0.0) or 0.0),
                        'roa': float(item.get('roa', 0.0) or 0.0),
                        'roe': float(item.get('roe', 0.0) or 0.0),
                        'npm': float(item.get('npm', 0.0) or 0.0)
                    }
                logger.info(f"Successfully loaded {len(ratios)} financial records from local JSON file.")
            except Exception as e:
                logger.error(f"Error reading financial ratio JSON: {e}")
        else:
            logger.error(f"Financial ratio JSON not found at {FINANCIAL_RATIO_FILE}")

    return ratios

# ==========================================
# 2. LOAD COMPANY NETWORKS
# ==========================================
def load_company_networks():
    """Load boards and ownership networks from Neo4j or fallback to JSON."""
    company_details = {}
    db_success = False

    # Try Neo4j first
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        # Test connection
        driver.verify_connectivity()
        
        with driver.session() as session:
            # Query all company nodes
            company_query = "MATCH (c:Company) RETURN c.kode AS code, c.companyName AS companyName"
            result = session.run(company_query)
            for record in result:
                code = record['code']
                company_details[code] = {
                    'directors': [],
                    'commissioners': [],
                    'shareholders': [],
                    'subsidiaries': []
                }
                
            # Query Directors
            dir_query = """
            MATCH (i:Insider)-[r:DIRECTOR_OF]->(c:Company) 
            RETURN c.kode AS code, i.name AS name, r.jabatan AS jabatan, r.afiliasi AS afiliasi
            """
            result = session.run(dir_query)
            for record in result:
                code = record['code']
                if code in company_details:
                    company_details[code]['directors'].append({
                        'name': record['name'],
                        'jabatan': record['jabatan'],
                        'afiliasi': record['afiliasi']
                    })
                    
            # Query Commissioners
            comm_query = """
            MATCH (i:Insider)-[r:COMMISSIONER_OF]->(c:Company) 
            RETURN c.kode AS code, i.name AS name, r.jabatan AS jabatan, r.independen AS independen
            """
            result = session.run(comm_query)
            for record in result:
                code = record['code']
                if code in company_details:
                    company_details[code]['commissioners'].append({
                        'name': record['name'],
                        'jabatan': record['jabatan'],
                        'independen': record['independen']
                    })

            # Query Shareholders
            sh_query = """
            MATCH (i:Insider)-[r:OWNS]->(c:Company) 
            RETURN c.kode AS code, i.name AS name, r.jumlah AS jumlah, r.persentase AS persentase, r.pengendali AS pengendali, r.kategori AS kategori
            """
            result = session.run(sh_query)
            for record in result:
                code = record['code']
                if code in company_details:
                    company_details[code]['shareholders'].append({
                        'name': record['name'],
                        'jumlah': float(record['jumlah']) if record['jumlah'] is not None else 0.0,
                        'persentase': float(record['persentase']) if record['persentase'] is not None else 0.0,
                        'pengendali': bool(record['pengendali']) if record['pengendali'] is not None else False,
                        'kategori': record['kategori']
                    })
            
            # Query Subsidiaries
            sub_query = """
            MATCH (s:Subsidiary)-[r:SUBSIDIARY_OF]->(c:Company) 
            RETURN c.kode AS code, s.name AS name, r.persentase AS persentase, s.bidangUsaha AS bidangUsaha
            """
            result = session.run(sub_query)
            for record in result:
                code = record['code']
                if code in company_details:
                    company_details[code]['subsidiaries'].append({
                        'name': record['name'],
                        'persentase': float(record['persentase']) if record['persentase'] is not None else 0.0,
                        'bidang_usaha': record['bidangUsaha']
                    })
                    
        driver.close()
        logger.info(f"Successfully loaded {len(company_details)} company networks from Neo4j.")
        db_success = True
    except Exception as e:
        logger.warning(f"Could not connect to Neo4j database ({e}). Falling back to JSON file.")

    # Fallback to JSON file
    if not db_success:
        if os.path.exists(COMPANY_DETAILS_FILE):
            try:
                with open(COMPANY_DETAILS_FILE, 'r') as f:
                    raw_details = json.load(f)
                
                for code, item in raw_details.items():
                    # Parse directors
                    dirs = []
                    for d in item.get('Direktur', []):
                        dirs.append({
                            'name': d.get('Nama', ''),
                            'jabatan': d.get('Jabatan', 'DIREKTUR'),
                            'afiliasi': d.get('Afiliasi', False)
                        })
                        
                    # Parse commissioners
                    comms = []
                    for k in item.get('Komisaris', []):
                        comms.append({
                            'name': k.get('Nama', ''),
                            'jabatan': k.get('Jabatan', 'KOMISARIS'),
                            'independen': k.get('Independen', False)
                        })
                        
                    # Parse shareholders
                    shs = []
                    for s in item.get('PemegangSaham', []):
                        shs.append({
                            'name': s.get('Nama', ''),
                            'jumlah': float(s.get('Jumlah', 0.0) or 0.0),
                            'persentase': float(s.get('Persentase', 0.0) or 0.0),
                            'pengendali': s.get('Pengendali', False),
                            'kategori': s.get('Kategori', '')
                        })
                        
                    # Parse subsidiaries
                    subs = []
                    for sub in item.get('AnakPerusahaan', []):
                        subs.append({
                            'name': sub.get('Nama', ''),
                            'persentase': float(sub.get('Persentase', 0.0) or 0.0),
                            'bidang_usaha': sub.get('BidangUsaha', '')
                        })
                        
                    company_details[code] = {
                        'directors': dirs,
                        'commissioners': comms,
                        'shareholders': shs,
                        'subsidiaries': subs
                    }
                logger.info(f"Successfully loaded {len(company_details)} company networks from local JSON file.")
            except Exception as e:
                logger.error(f"Error reading company details JSON: {e}")
        else:
            logger.error(f"Company details JSON not found at {COMPANY_DETAILS_FILE}")

    return company_details

# ==========================================
# 3. ANALYSIS PIPELINE
# ==========================================
def run_analysis_pipeline():
    """Runs the integrated network and financial analysis."""
    logger.info("Starting Analysis Pipeline...")
    
    # Load raw data
    ratios = load_financial_ratios()
    networks = load_company_networks()
    
    # Join keys
    all_codes = set(ratios.keys()).union(set(networks.keys()))
    logger.info(f"Analyzing {len(all_codes)} unique stock codes.")
    
    # 3.1 Calculate Estimated Market Capitalization for each company
    # This helps compute value of insider holdings and rank company size
    market_caps = {}
    for code in all_codes:
        f_data = ratios.get(code, {})
        equity = f_data.get('equity', 0.0)
        price_bv = f_data.get('price_bv', 0.0)
        per = f_data.get('per', 0.0)
        net_profit = f_data.get('profit_period', 0.0)
        
        # Calculate market cap estimate
        mcap = 0.0
        if price_bv > 0 and equity > 0:
            mcap = price_bv * equity
        elif per > 0 and net_profit > 0:
            mcap = per * net_profit
        elif equity > 0:
            mcap = equity  # Assume PBV = 1.0
        else:
            mcap = f_data.get('assets', 0.0) * 0.5  # Assumed as 50% of assets if equity is missing
            
        market_caps[code] = mcap

    # 3.2 Map out Director Networks & Owner Networks
    # Find overlapping insiders across companies
    insider_to_companies = {}
    shareholder_to_companies = {}
    
    for code, net_data in networks.items():
        # Map directors
        for d in net_data['directors']:
            insider_name = clean_name(d['name'])
            if not insider_name:
                continue
            if insider_name not in insider_to_companies:
                insider_to_companies[insider_name] = []
            insider_to_companies[insider_name].append({
                'code': code,
                'role': 'Director',
                'title': d['jabatan']
            })
            
        # Map commissioners
        for k in net_data['commissioners']:
            insider_name = clean_name(k['name'])
            if not insider_name:
                continue
            if insider_name not in insider_to_companies:
                insider_to_companies[insider_name] = []
            insider_to_companies[insider_name].append({
                'code': code,
                'role': 'Commissioner',
                'title': k['jabatan']
            })
            
        # Map shareholders
        for s in net_data['shareholders']:
            sh_name = clean_name(s['name'])
            if not sh_name:
                continue
            if sh_name not in shareholder_to_companies:
                shareholder_to_companies[sh_name] = []
            shareholder_to_companies[sh_name].append({
                'code': code,
                'jumlah': s['jumlah'],
                'persentase': s['persentase'],
                'pengendali': s['pengendali'],
                'raw_name': s['name']
            })

    # 3.3 Find "Super Insiders" (Individual retail tycoons/wealthy stakeholders)
    # We filter out corporate names, and sum up their estimated holdings value
    super_insiders_dict = {}
    
    for sh_name, holdings in shareholder_to_companies.items():
        if is_corporate_name(sh_name):
            continue
            
        total_value = 0.0
        active_holdings = []
        
        for h in holdings:
            code = h['code']
            percentage = h['persentase']
            mcap = market_caps.get(code, 0.0)
            holding_value = (percentage / 100.0) * mcap
            
            if holding_value > 0:
                total_value += holding_value
                active_holdings.append({
                    'code': code,
                    'percentage': percentage,
                    'value': holding_value,
                    'is_controller': h['pengendali']
                })
                
        # Also check if this insider serves on the board of any companies
        connected_roles = []
        if sh_name in insider_to_companies:
            for role_data in insider_to_companies[sh_name]:
                connected_roles.append({
                    'code': role_data['code'],
                    'role': role_data['role'],
                    'title': role_data['title']
                })
                
        # Filter: To be a "Super Insider", they must hold > 5 billion IDR in shares 
        # OR sit on the board of > 1 listed company with shares owned
        if total_value > 5000.0 or len(active_holdings) >= 2 or (len(active_holdings) >= 1 and len(connected_roles) >= 1):
            # Resolve the raw name (take the longest/nicest raw name)
            raw_name = sorted([h['raw_name'] for h in holdings], key=len, reverse=True)[0]
            
            super_insiders_dict[sh_name] = {
                'name': raw_name,
                'clean_name': sh_name,
                'total_value': total_value,
                'holdings': active_holdings,
                'connected_roles': connected_roles
            }

    # 3.4 Group Conglomerate Networks (by corporate controlling shareholders)
    conglomerates_dict = {}
    for sh_name, holdings in shareholder_to_companies.items():
        # A conglomerate controller must be a corporate name (or super insider controller) 
        # and control (pengendali = True or percentage > 20%) multiple companies
        controlled_companies = []
        for h in holdings:
            if h['pengendali'] or h['persentase'] >= 20.0:
                controlled_companies.append(h['code'])
                
        if len(controlled_companies) >= 2 and is_corporate_name(sh_name):
            raw_name = sorted([h['raw_name'] for h in holdings], key=len, reverse=True)[0]
            conglomerates_dict[sh_name] = {
                'controller_name': raw_name,
                'clean_name': sh_name,
                'companies': list(set(controlled_companies))
            }

    # 3.5 Calculate scores and build output list for each company
    companies_list = []
    
    for code in all_codes:
        f_data = ratios.get(code, {})
        net_data = networks.get(code, {
            'directors': [],
            'commissioners': [],
            'shareholders': [],
            'subsidiaries': []
        })
        
        # Financial Ratios
        roe = f_data.get('roe', 0.0)
        roa = f_data.get('roa', 0.0)
        npm = f_data.get('npm', 0.0)
        de_ratio = f_data.get('de_ratio', 0.0)
        per = f_data.get('per', 0.0)
        price_bv = f_data.get('price_bv', 0.0)
        
        # 1. Financial Health Score (out of 40)
        f_score = 0.0
        if roe >= 20.0:
            f_score += 15.0
        elif roe >= 15.0:
            f_score += 10.0
        elif roe >= 10.0:
            f_score += 5.0
        elif roe < 0.0:
            f_score -= 10.0 # penalty for losing money
            
        if de_ratio > 0:
            if de_ratio <= 0.5:
                f_score += 15.0
            elif de_ratio <= 1.0:
                f_score += 10.0
            elif de_ratio <= 2.0:
                f_score += 5.0
        else:
            f_score += 5.0 # assume moderate leverage if missing
            
        if npm >= 20.0:
            f_score += 10.0
        elif npm >= 10.0:
            f_score += 7.0
        elif npm >= 5.0:
            f_score += 3.0
            
        f_score = max(0.0, min(40.0, f_score))
        
        # 2. Valuation Score (out of 30)
        v_score = 0.0
        # PE Ratio Scoring
        if 0.0 < per < 10.0:
            v_score += 15.0
        elif 10.0 <= per < 15.0:
            v_score += 10.0
        elif 15.0 <= per < 25.0:
            v_score += 5.0
            
        # PBV Ratio Scoring
        if 0.0 < price_bv < 1.0:
            v_score += 15.0
        elif 1.0 <= price_bv < 1.5:
            v_score += 10.0
        elif 1.5 <= price_bv < 3.0:
            v_score += 5.0
            
        v_score = max(0.0, min(30.0, v_score))
        
        # 3. Network Connection Score (out of 30)
        n_score = 0.0
        
        # A. Shared directors/commissioners with Blue Chip companies
        has_blue_chip_bridge = False
        shared_directors = []
        
        # Find all board members of this company
        board_names = []
        for d in net_data['directors']:
            b_name = clean_name(d['name'])
            if b_name:
                board_names.append(b_name)
        for k in net_data['commissioners']:
            b_name = clean_name(k['name'])
            if b_name:
                board_names.append(b_name)
                
        # Check if any board member sits on a Blue Chip board
        for b_name in board_names:
            if b_name in insider_to_companies:
                connected_companies = [r['code'] for r in insider_to_companies[b_name]]
                # Filter out current company
                connected_companies = [c for c in connected_companies if c != code]
                
                # Check for blue chip overlap
                blue_overlap = set(connected_companies).intersection(BLUE_CHIPS)
                if blue_overlap:
                    has_blue_chip_bridge = True
                    shared_directors.append({
                        'insider_name': b_name,
                        'connected_to': list(blue_overlap)
                    })
                    
        if has_blue_chip_bridge:
            n_score += 12.0
            
        # B. Super-Insider Alignment
        has_super_insider = False
        for s in net_data['shareholders']:
            sh_name = clean_name(s['name'])
            if sh_name in super_insiders_dict and s['persentase'] >= 1.0:
                has_super_insider = True
                break
                
        if has_super_insider:
            n_score += 10.0
            
        # C. Conglomerate strength
        is_in_strong_conglom = False
        for s in net_data['shareholders']:
            sh_name = clean_name(s['name'])
            if sh_name in conglomerates_dict:
                # Check average ROE of this conglomerate's companies
                conglom_codes = conglomerates_dict[sh_name]['companies']
                conglom_roes = [ratios.get(c, {}).get('roe', 0.0) for c in conglom_codes if c in ratios]
                if conglom_roes and (sum(conglom_roes) / len(conglom_roes)) >= 15.0:
                    is_in_strong_conglom = True
                    break
                    
        if is_in_strong_conglom:
            n_score += 8.0
            
        n_score = max(0.0, min(30.0, n_score))
        
        # Calculate Total SMSS Score
        total_score = f_score + v_score + n_score
        
        # Build list of network codes for quick visual rendering in dashboard
        network_connections = set()
        for b_name in board_names:
            if b_name in insider_to_companies:
                for conn in insider_to_companies[b_name]:
                    if conn['code'] != code:
                        network_connections.add(conn['code'])
                        
        for s in net_data['shareholders']:
            sh_name = clean_name(s['name'])
            if sh_name in shareholder_to_companies:
                for conn in shareholder_to_companies[sh_name]:
                    if conn['code'] != code:
                        network_connections.add(conn['code'])
                        
        companies_list.append({
            'code': code,
            'name': f_data.get('stock_name') or next((c.get('companyName') for c in net_data.get('shareholders', []) if c.get('code') == code), code),
            'sector': f_data.get('sector', 'N/A'),
            'sub_sector': f_data.get('sub_sector', 'N/A'),
            'industry': f_data.get('industry', 'N/A'),
            'sub_industry': f_data.get('sub_industry', 'N/A'),
            'roe': roe,
            'roa': roa,
            'npm': npm,
            'de_ratio': de_ratio,
            'per': per,
            'price_bv': price_bv,
            'assets': f_data.get('assets', 0.0),
            'liabilities': f_data.get('liabilities', 0.0),
            'equity': f_data.get('equity', 0.0),
            'sales': f_data.get('sales', 0.0),
            'profit_period': f_data.get('profit_period', 0.0),
            'eps': f_data.get('eps', 0.0),
            'book_value': f_data.get('book_value', 0.0),
            'fs_date': f_data.get('fs_date', 'N/A'),
            'estimated_mcap': market_caps.get(code, 0.0),
            'board_members': [
                {
                    'name': d['name'],
                    'role': 'Director',
                    'title': d['jabatan']
                } for d in net_data['directors']
            ] + [
                {
                    'name': k['name'],
                    'role': 'Commissioner',
                    'title': k['jabatan']
                } for k in net_data['commissioners']
            ],
            'shareholders': [
                {
                    'name': s['name'],
                    'percentage': s['persentase'],
                    'is_controller': s['pengendali']
                } for s in net_data['shareholders']
            ],
            'subsidiaries': [
                {
                    'name': sub['name'],
                    'percentage': sub['persentase'],
                    'bidang_usaha': sub['bidang_usaha']
                } for sub in net_data['subsidiaries']
            ],
            'score': {
                'financial': f_score,
                'valuation': v_score,
                'network': n_score,
                'total': total_score
            },
            'network_connections': list(network_connections)[:15],  # Limit to top 15 connections
            'shared_directors': shared_directors
        })

    # Sort companies list by total score descending
    companies_list = sorted(companies_list, key=lambda x: x['score']['total'], reverse=True)

    # 3.6 Conglomerates formatting
    conglomerates_list = []
    for clean_id, conglom in conglomerates_dict.items():
        c_codes = conglom['companies']
        
        # Calculate aggregate metrics
        total_assets = 0.0
        roes = []
        pbvs = []
        
        for c in c_codes:
            f_data = ratios.get(c, {})
            total_assets += f_data.get('assets', 0.0)
            if 'roe' in f_data and f_data['roe'] > 0:
                roes.append(f_data['roe'])
            if 'price_bv' in f_data and f_data['price_bv'] > 0:
                pbvs.append(f_data['price_bv'])
                
        avg_roe = sum(roes) / len(roes) if roes else 0.0
        avg_pbv = sum(pbvs) / len(pbvs) if pbvs else 0.0
        
        conglomerates_list.append({
            'controller_name': conglom['controller_name'],
            'companies': c_codes,
            'total_assets': total_assets,
            'average_roe': avg_roe,
            'average_pbv': avg_pbv
        })
        
    conglomerates_list = sorted(conglomerates_list, key=lambda x: x['total_assets'], reverse=True)

    # Sort super insiders by portfolio value descending
    super_insiders_list = sorted(
        super_insiders_dict.values(),
        key=lambda x: x['total_value'],
        reverse=True
    )

    # Prepare final output structure
    output_data = {
        'companies': companies_list,
        'super_insiders': super_insiders_list,
        'conglomerates': conglomerates_list,
        'last_updated': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Save to file
    try:
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(output_data, f, indent=2)
        logger.info(f"Successfully generated analysis dashboard dataset at {OUTPUT_FILE}")
    except Exception as e:
        logger.error(f"Failed to save dashboard dataset: {e}")

if __name__ == "__main__":
    run_analysis_pipeline()
