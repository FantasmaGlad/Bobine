"""Proxy TCP jetable : limite le débit client->serveur (simule un Wi-Fi de salle) et ajoute une latence.
Usage : python3 throttle_proxy.py <Mo/s> <latence_ms> [port_ecoute] [port_cible]"""
import asyncio, sys
LISTEN = int(sys.argv[3]) if len(sys.argv) > 3 else 8079
TARGET = int(sys.argv[4]) if len(sys.argv) > 4 else 8000
RATE, LAT = int(float(sys.argv[1]) * 1_000_000), float(sys.argv[2]) / 1000
async def pipe(r, w, rate=None):
    try:
        while True:
            data = await r.read(16384)
            if not data: break
            if rate: await asyncio.sleep(len(data)/rate)
            w.write(data); await w.drain()
    except Exception: pass
    finally:
        try: w.close()
        except Exception: pass
async def handle(cr, cw):
    await asyncio.sleep(LAT)
    sr, sw = await asyncio.open_connection("127.0.0.1", TARGET)
    await asyncio.gather(pipe(cr, sw, RATE), pipe(sr, cw))
async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", LISTEN)
    async with srv: await srv.serve_forever()
asyncio.run(main())
