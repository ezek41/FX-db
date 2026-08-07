import os
import time
import requests
import psycopg2

# Configuración de credenciales (usá Variables de Entorno en Render)
FINNHUB_TOKEN = os.getenv("FINNHUB_TOKEN", "TU_FINNHUB_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "postgres://usuario:password@host/neondb")

# Lista organizada de activos
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
    {"symbol": "IEF", "category": "RATES"},  # US10Y
    {"symbol": "SHY", "category": "RATES"}   # US02Y
]

def get_finnhub_quote(symbol):
    """Obtiene el precio actual (c = current price)"""
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_TOKEN}"
    try:
        res = requests.get(url, timeout=5).json()
        return res.get('c', None)
    except Exception as e:
        print(f"Error consultando precio para {symbol}: {e}")
        return None

def get_finnhub_rsi(symbol):
    """Obtiene el indicador RSI directo desde Finnhub"""
    url = f"https://finnhub.io/api/v1/scan/technical-indicator?symbol={symbol}&resolution=D&token={FINNHUB_TOKEN}"
    try:
        res = requests.get(url, timeout=5).json()
        return res.get('technicalAnalysis', {}).get('count', {}).get('rsi', None)
    except Exception as e:
        print(f"Error consultando RSI para {symbol}: {e}")
        return None

def save_to_neon(data_records):
    """Inserta las lecturas masivas en la base de datos Neon"""
    if not data_records:
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
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Insertados {len(data_records)} registros en Neon.")
    except Exception as e:
        print(f"Error guardando en Neon: {e}")

def main():
    while True:
        records = []
        for asset in ASSETS:
            sym = asset["symbol"]
            cat = asset["category"]
            
            price = get_finnhub_quote(sym)
            rsi = get_finnhub_rsi(sym)
            
            if price is not None or rsi is not None:
                records.append((sym, cat, price, rsi))
            
            # Respetar rate limit de Finnhub (60 llamadas/min en Tier gratis)
            time.sleep(1)
        
        save_to_neon(records)
        # Esperar 5 minutos antes del próximo ciclo completo
        time.sleep(300)

if __name__ == "__main__":
    main()
