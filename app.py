import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import psycopg2

# --- 1. SERVIDOR HTTP DUMMY PARA RENDER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK - Worker running")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"Servidor HTTP dummy corriendo en el puerto {port}")
    server.serve_forever()


# --- 2. CONFIGURACIÓN Y LISTA DE ACTIVOS ---
FINNHUB_TOKEN = os.getenv("FINNHUB_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

ASSETS = [
    # Top 10 Stocks
    {"symbol": "NVDA", "category": "EQUITY"},
    {"symbol": "AAPL", "category": "EQUITY"},
    {"symbol": "GOOGL", "category": "EQUITY"},
    {"symbol": "MSFT", "category": "EQUITY"},
    {"symbol": "AMZN", "category": "EQUITY"},
    {"symbol": "AVGO", "category": "EQUITY"},
    {"symbol": "META", "category": "EQUITY"},
    {"symbol": "TSLA", "category": "EQUITY"},
    {"symbol": "BRK.B", "category": "EQUITY"},
    {"symbol": "LLY", "category": "EQUITY"},
    
    # Forex
    {"symbol": "OANDA:EUR_USD", "category": "FOREX"},
    {"symbol": "OANDA:USD_JPY", "category": "FOREX"},
    {"symbol": "OANDA:GBP_USD", "category": "FOREX"},
    {"symbol": "OANDA:USD_CHF", "category": "FOREX"},
    {"symbol": "OANDA:AUD_USD", "category": "FOREX"},
    
    # Crypto
    {"symbol": "BINANCE:BTCUSDT", "category": "CRYPTO"},
    {"symbol": "BINANCE:ETHUSDT", "category": "CRYPTO"},
    {"symbol": "BINANCE:USDTUSDC", "category": "CRYPTO"},
    {"symbol": "BINANCE:BNBUSDT", "category": "CRYPTO"},
    {"symbol": "BINANCE:SOLUSDT", "category": "CRYPTO"},
    
    # Rates / ETFs Réplica de Tesoro
    {"symbol": "IEF", "category": "RATES"},
    {"symbol": "SHY", "category": "RATES"}
]


# --- 3. FUNCIONES DE API Y BASE DE DATOS ---
def get_finnhub_quote(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_TOKEN}"
    try:
        res = requests.get(url, timeout=5).json()
        return res.get('c', None)
    except Exception as e:
        print(f"Error precio {symbol}: {e}")
        return None

def get_finnhub_rsi(symbol):
    url = f"https://finnhub.io/api/v1/scan/technical-indicator?symbol={symbol}&resolution=D&token={FINNHUB_TOKEN}"
    try:
        res = requests.get(url, timeout=5).json()
        return res.get('technicalAnalysis', {}).get('count', {}).get('rsi', None)
    except Exception as e:
        print(f"Error RSI {symbol}: {e}")
        return None

def save_to_neon(data_records):
    if not data_records:
        print("No hay registros para guardar en este ciclo.")
        return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        query = """
            INSERT INTO market_data (symbol, category, price, rsi)
            VALUES (%s, %s, %s, %s);
        """
        cur.executemany(query, data_records)
        conn.commit()
        cur.close()
        conn.close()
        print(f"--- [{time.strftime('%H:%M:%S')}] Guardados {len(data_records)} registros en Neon con exito ---")
    except Exception as e:
        print(f"Error en base de datos Neon: {e}")


# --- 4. BUCLE PRINCIPAL DE RECOLECCIÓN ---
def data_collector_loop():
    print("Iniciando bucle de recolección de datos...")
    
    if not FINNHUB_TOKEN or not DATABASE_URL:
        print("CRÍTICO: No se encontraron las variables FINNHUB_TOKEN o DATABASE_URL en Render.")
        return

    while True:
        records = []
        try:
            print("Consultando cotizaciones y RSI en Finnhub...")
            for asset in ASSETS:
                sym = asset["symbol"]
                cat = asset["category"]
                price = get_finnhub_quote(sym)
                rsi = get_finnhub_rsi(sym)
                
                if price is not None or rsi is not None:
                    records.append((sym, cat, price, rsi))
                
                time.sleep(1) # Respetar rate limits (60 peticiones/min)
            
            save_to_neon(records)
        except Exception as e:
            print(f"Error inesperado en el ciclo: {e}")
            
        print("Ciclo finalizado. Esperando 5 minutos para el próximo envío...")
        time.sleep(300)


# --- 5. PUNTO DE ENTRADA ---
if __name__ == "__main__":
    # Iniciar el recolector en un hilo en segundo plano
    collector_thread = threading.Thread(target=data_collector_loop, daemon=True)
    collector_thread.start()
    
    # Iniciar el servidor web en el hilo principal para que Render valide el healthcheck
    run_web_server()
