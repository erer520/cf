#!/usr/bin/env python3
import argparse, asyncio, base64, ipaddress, json, os, random, time
from datetime import datetime, timezone
from pathlib import Path
import aiohttp

RANGES_URL = "https://www.cloudflare.com/ips-v4"
OUT = Path("data")

async def fetch_ranges(session):
    async with session.get(RANGES_URL, timeout=20) as r:
        r.raise_for_status()
        return [ipaddress.ip_network(x.strip()) for x in (await r.text()).splitlines() if x.strip()]

def candidates(networks, count):
    result = []
    for net in networks:
        hosts = list(net.hosts())
        if len(hosts) <= count:
            result.extend(hosts)
        else:
            result.extend(random.sample(hosts, count))
    random.shuffle(result)
    return [str(x) for x in result]

async def probe(ip, session, url, host, sem):
    async with sem:
        started = time.perf_counter()
        try:
            headers = {"Host": host} if host else {}
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8), allow_redirects=False) as r:
                elapsed = round((time.perf_counter() - started) * 1000, 2)
                if r.status < 500:
                    return {"ip": ip, "latency_ms": elapsed, "status": r.status}
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None

async def main(count):
    OUT.mkdir(exist_ok=True)
    url = os.getenv("TEST_URL", "https://speed.cloudflare.com/__down?bytes=100000")
    host = os.getenv("TEST_HOST", "speed.cloudflare.com")
    connector = aiohttp.TCPConnector(family=__import__('socket').AF_INET, limit=100, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        networks = await fetch_ranges(session)
        ips = candidates(networks, max(count * 3, 600))
        sem = asyncio.Semaphore(100)
        results = await asyncio.gather(*(probe(x, session, url, host, sem) for x in ips))
    good = sorted((x for x in results if x), key=lambda x: x["latency_ms"])[:max(200, min(500, count))]
    generated = datetime.now(timezone.utc).isoformat()
    (OUT / "ips.txt").write_text("\n".join(f"http://{x['ip']}:80" for x in good) + "\n", encoding="utf-8")
    encoded = base64.b64encode((OUT / "ips.txt").read_bytes()).decode()
    (OUT / "base64.txt").write_text(encoded + "\n", encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps({"generated_at": generated, "count": len(good), "nodes": good}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"selected {len(good)} nodes")
    if len(good) < 200:
        raise SystemExit("fewer than 200 reachable nodes; refusing to publish an undersized pool")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=300)
    asyncio.run(main(parser.parse_args().count))
