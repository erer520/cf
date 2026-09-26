#!/usr/bin/env python3
"""
Cloudflare IP subscription generator
Generates 200-500 optimized IPs for Chinese users
"""
import argparse, asyncio, base64, ipaddress, json, logging, os, random, sys, time
from datetime import datetime, timezone
from pathlib import Path
import aiohttp

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

RANGES_URL = "https://www.cloudflare.com/ips-v4"
OUT = Path("data")

async def fetch_ranges(session):
    """Fetch Cloudflare IP ranges"""
    try:
        logger.info("Fetching Cloudflare IP ranges...")
        async with session.get(RANGES_URL, timeout=20) as r:
            r.raise_for_status()
            ranges = [ipaddress.ip_network(x.strip()) for x in (await r.text()).splitlines() if x.strip()]
            logger.info(f"Found {len(ranges)} IP ranges")
            return ranges
    except Exception as e:
        logger.error(f"Failed to fetch ranges: {e}")
        sys.exit(1)

def candidates(networks, count):
    """Generate candidate IPs from networks"""
    logger.info(f"Generating {count} candidate IPs...")
    result = []
    for net in networks:
        hosts = list(net.hosts())
        if len(hosts) <= count:
            result.extend(hosts)
        else:
            result.extend(random.sample(hosts, count))
    random.shuffle(result)
    logger.info(f"Generated {len(result)} candidates")
    return [str(x) for x in result]

async def probe(ip, session, url, host, sem):
    """Test single IP latency and availability"""
    async with sem:
        started = time.perf_counter()
        try:
            headers = {"Host": host} if host else {}
            async with session.get(
                url, 
                headers=headers, 
                timeout=aiohttp.ClientTimeout(total=8), 
                allow_redirects=False
            ) as r:
                elapsed = round((time.perf_counter() - started) * 1000, 2)
                if r.status < 500:
                    return {"ip": ip, "latency_ms": elapsed, "status": r.status}
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
    return None

async def main(count):
    """Main entry point"""
    OUT.mkdir(exist_ok=True)
    url = os.getenv("TEST_URL", "https://speed.cloudflare.com/__down?bytes=100000")
    host = os.getenv("TEST_HOST", "speed.cloudflare.com")
    
    logger.info(f"Test URL: {url}")
    logger.info(f"Test Host: {host}")
    
    connector = aiohttp.TCPConnector(family=__import__('socket').AF_INET, limit=100, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        networks = await fetch_ranges(session)
        ips = candidates(networks, max(count * 3, 600))
        
        logger.info(f"Testing {len(ips)} IPs (this may take a few minutes)...")
        sem = asyncio.Semaphore(100)
        results = await asyncio.gather(*(probe(x, session, url, host, sem) for x in ips))
    
    good = sorted((x for x in results if x), key=lambda x: x["latency_ms"])[:max(200, min(500, count))]
    
    if len(good) < 200:
        logger.error(f"Only {len(good)} reachable nodes, minimum 200 required")
        sys.exit(1)
    
    logger.info(f"Selected {len(good)} optimized nodes")
    
    # Generate outputs
    generated = datetime.now(timezone.utc).isoformat()
    
    # 1. Plain text IP list
    ips_content = "\n".join(f"http://{x['ip']}:80" for x in good) + "\n"
    (OUT / "ips.txt").write_text(ips_content, encoding="utf-8")
    logger.info("✓ Generated ips.txt")
    
    # 2. Base64 subscription
    encoded = base64.b64encode(ips_content.encode()).decode()
    (OUT / "base64.txt").write_text(encoded + "\n", encoding="utf-8")
    logger.info("✓ Generated base64.txt")
    
    # 3. JSON results with statistics
    stats = {
        "generated_at": generated,
        "count": len(good),
        "average_latency_ms": round(sum(x["latency_ms"] for x in good) / len(good), 2),
        "min_latency_ms": good[0]["latency_ms"],
        "max_latency_ms": good[-1]["latency_ms"],
        "nodes": good
    }
    (OUT / "results.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("✓ Generated results.json")
    
    # 4. Clash YAML config (if PyYAML available)
    try:
        import yaml
        clash_config = {
            "proxies": [
                {
                    "name": f"CF-{i+1:03d}",
                    "type": "http",
                    "server": x["ip"],
                    "port": 80
                }
                for i, x in enumerate(good)
            ],
            "proxy-groups": [
                {
                    "name": "🌍 Cloudflare",
                    "type": "select",
                    "proxies": [f"CF-{i+1:03d}" for i in range(len(good))]
                },
                {
                    "name": "⚡ Auto",
                    "type": "url-test",
                    "proxies": [f"CF-{i+1:03d}" for i in range(len(good))],
                    "url": "http://www.gstatic.com/generate_204",
                    "interval": 600
                }
            ],
            "rules": [
                "MATCH,🌍 Cloudflare"
            ]
        }
        (OUT / "clash.yaml").write_text(yaml.dump(clash_config, allow_unicode=True), encoding="utf-8")
        logger.info("✓ Generated clash.yaml")
    except ImportError:
        logger.warning("PyYAML not available, skipping clash.yaml")
    
    logger.info(f"\n{'='*50}")
    logger.info(f"✅ Success! Generated {len(good)} optimized IPs")
    logger.info(f"   Average latency: {stats['average_latency_ms']}ms")
    logger.info(f"   Fastest: {stats['min_latency_ms']}ms")
    logger.info(f"   Slowest: {stats['max_latency_ms']}ms")
    logger.info(f"{'='*50}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate optimized Cloudflare IPs")
    parser.add_argument("--count", type=int, default=300, help="Target number of IPs (200-500)")
    args = parser.parse_args()
    
    asyncio.run(main(args.count))
