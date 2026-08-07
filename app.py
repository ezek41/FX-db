import os
import datetime
import requests
import psycopg2

FINNHUB_TOKEN = os.getenv("FINNHUB_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

ASSETS = [
    # Stocks
    {"symbol": "NVDA", "category": "EQUITY"},
    {"symbol": "AAPL", "category": "EQUITY"},
    {"symbol": "MSFT", "category": "EQUITY"},
    {"symbol": "GOOGL", "category": "EQUITY"},
    {"symbol": "AMZN", "category": "EQUITY"},
    
    # Forex
    {"symbol": "OANDA:EUR_USD", "category": "FOREX"},
    {"symbol": "OANDA:USD_JPY", "category": "FOREX"},
    {"symbol": "OANDA:GBP_USD", "category": "FOREX"},
    
    # Crypto
    {"symbol": "BINANCE:BTCUSDT", "category": "CRYPTO"},
    {"symbol": "BINANCE:ETHUSDT", "category": "CRYPTO"},
    {"symbol": "BINANCE:SOLUSDT", "category": "CRYPTO"},
    
    # Rates
    {"symbol": "IEF", "category": "RATES"},
    {"symbol": "SHY", "category": "RATES"}
]

def fetch_market_data():
    records = []
    print("Obteniendo cotizaciones y RSI...")
    for asset in ASSETS:
        sym = asset["symbol"]
        cat = asset["category"]
        
        # Precio
        p_url = f"https://finnhub.io/api/v1/quote?symbol={sym}&token={FINNHUB_TOKEN}"
        try:
            res_p = requests.get(p_url, timeout=5).json()
            price = res_p.get('c')
        except Exception as e:
            print(f"Error precio {sym}: {e}")
            price = None

        # RSI
        r_url = f"https://finnhub.io/api/v1/scan/technical-indicator?symbol={sym}&resolution=D&token={FINNHUB_TOKEN}"
        try:
            res_r = requests.get(r_url, timeout=5).json()
            rsi = res_r.get('technicalAnalysis', {}).get('count', {}).get('rsi')
        except Exception as e:
            print(f"Error RSI {sym}: {e}")
            rsi = None

        if price is not None or rsi is not None:
            records.append((sym, cat, price, rsi))
            
    return records

def fetch_macro_calendar():
    today = datetime.date.today()
    next_week = today + datetime.timedelta(days=7)
    
    url = f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={next_week}&token={FINNHUB_TOKEN}"
    events = []
    print("Obteniendo calendario macroeconómico...")
    try:
        res = requests.get(url, timeout=5).json()
        for item in res.get("economicCalendar", []):
            if item.get("country") in ["US", "EU", "GB"]:
                events.append((
                    item.get("time"),
                    item.get("country"),
                    item.get("event"),
                    item.get("actual"),
                    item.get("estimate"),
                    item.get("prev"),
                    item.get("impact")
                ))
    except Exception as e:
        print(f"Error al obtener macro events: {e}")
        
    return events

def save_to_neon(market_records, macro_records):
    if not DATABASE_URL:
        print("Error: DATABASE_URL no está configurada.")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        if market_records:
            q_market = "INSERT INTO market_data (symbol, category, price, rsi) VALUES (%s, %s, %s, %s);"
            cur.executemany(q_market, market_records)
            print(f"-> Guardados {len(market_records)} registros de precios/RSI.")
            
        if macro_records:
            q_macro = """
                INSERT INTO macro_events (event_date, country, event_name, actual, estimate, previous, impact)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """
            cur.executemany(q_macro, macro_records)
            print(f"-> Guardados {len(macro_records)} eventos macroeconómicos.")
            
        conn.commit()
        cur.close()
        conn.close()
        print("Proceso completado con éxito.")
    except Exception as e:
        print(f"Error en base de datos: {e}")

if __name__ == "__main__":
    if not FINNHUB_TOKEN or not DATABASE_URL:
        print("CRÍTICO: Faltan las variables FINNHUB_TOKEN o DATABASE_URL.")
    else:
        m_data = fetch_market_data()
        mac_data = fetch_macro_calendar()
        save_to_neon(m_data, mac_data)
