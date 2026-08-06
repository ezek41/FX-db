import asyncio
import json
import os
from datetime import datetime, timezone
import asyncpg
import websockets
from aiohttp import web

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

PAIRS = [
    "OANDA:EUR_USD", "OANDA:GBP_USD", "OANDA:USD_JPY", 
    "OANDA:USD_CAD", "OANDA:AUD_USD", "OANDA:EUR_GBP", 
    "OANDA:EUR_JPY", "OANDA:GBP_JPY"
]

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]

latest_prices = {}
base_prices = {}
db_pool = None

async def init_db():
    global db_pool
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set!")
    
    # Maneja la compatibilidad del prefijo de URL de PostgreSQL para asyncpg
    db_url = DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    db_pool = await asyncpg.create_pool(db_url)

def calculate_currency_strength():
    changes = {}
    for pair, price in latest_prices.items():
        if pair in base_prices and base_prices[pair] > 0:
            changes[pair] = ((price - base_prices[pair]) / base_prices[pair]) * 100
        else:
            changes[pair] = 0.0

    scores = {c: 0.0 for c in CURRENCIES}
    counts = {c: 0 for c in CURRENCIES}

    pair_map = [
        ("OANDA:EUR_USD", "EUR", "USD"),
        ("OANDA:GBP_USD", "GBP", "USD"),
        ("OANDA:USD_JPY", "USD", "JPY"),
        ("OANDA:USD_CAD", "USD", "CAD"),
        ("OANDA:AUD_USD", "AUD", "USD"),
        ("OANDA:EUR_GBP", "EUR", "GBP"),
        ("OANDA:EUR_JPY", "EUR", "JPY"),
        ("OANDA:GBP_JPY", "GBP", "JPY"),
    ]

    for pair, base, quote in pair_map:
        if pair in changes:
            change = changes[pair]
            scores[base] += change
            scores[quote] -= change
            counts[base] += 1
            counts[quote] += 1

    final_scores = {}
    for c in CURRENCIES:
        if counts[c] > 0:
            raw_avg = scores[c] / counts[c]
            scaled = max(-100.0, min(100.0, raw_avg * 100))
            final_scores[c] = round(scaled, 2)
        else:
            final_scores[c] = 0.0

    return final_scores

async def save_to_db(scores):
    now = datetime.now(timezone.utc)
    records = [(now, curr, score) for curr, score in scores.items()]
    async with db_pool.acquire() as conn:
        await conn.executemany(
            "INSERT INTO currency_strength (timestamp, currency, strength_score) VALUES ($1, $2, $3);",
            records
        )

async def strength_calculation_loop():
    while True:
        await asyncio.sleep(5)
        if latest_prices:
            scores = calculate_currency_strength()
            await save_to_db(scores)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Metrics sent to Neon: {scores}")

async def websocket_listener():
    if not FINNHUB_API_KEY:
        raise ValueError("FINNHUB_API_KEY environment variable is not set!")
    
    uri = f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}"
    async with websockets.connect(uri) as ws:
        for pair in PAIRS:
            await ws.send(json.dumps({"type": "subscribe", "symbol": pair}))

        async for message in ws:
            data = json.loads(message)
            if data.get("type") == "trade":
                for trade in data["data"]:
                    symbol = trade["s"]
                    price = trade["p"]
                    latest_prices[symbol] = price
                    if symbol not in base_prices:
                        base_prices[symbol] = price

# Servidor HTTP liviano para pasar la validación de Render (Health Check)
async def handle_health_check(request):
    return web.Response(text="Forex Ingestion Service is running OK!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_handle_check if 'handle_handle_check' in locals() else handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Health check HTTP server listening on port {port}")

async def main():
    await init_db()
    await start_web_server()
    await asyncio.gather(
        websocket_listener(),
        strength_calculation_loop()
    )

if __name__ == "__main__":
    asyncio.run(main())
