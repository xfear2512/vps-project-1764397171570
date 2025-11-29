import asyncio
import aiohttp
import random
import re
import string
import os
from dotenv import load_dotenv

# ========== CONFIG ==========
BASE_URL = "https://snote.vip/notes/"
CONCURRENT = 10  # tốc độ an toàn
CODE_LENGTH = 6
CHARSET = string.ascii_uppercase + string.digits
PAUSE_MINUTES = 20
PAUSE_SECONDS = PAUSE_MINUTES * 60

CHECKED_FILE = "checked_urls.txt"
LOG_DIR = "logs"
VALID_FILE = os.path.join(LOG_DIR, "all_valid_links.txt")
TG_FILE = os.path.join(LOG_DIR, "telegram_links.txt")

load_dotenv()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

checked_urls = set()
file_lock = asyncio.Lock()
stats = {"scan": 0, "found": 0}


# ========== Helper ==========
def gen_code():
    return "".join(random.choices(CHARSET, k=CODE_LENGTH))

def ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)

def load_checked_urls():
    if os.path.exists(CHECKED_FILE):
        with open(CHECKED_FILE, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url:
                    checked_urls.add(url)
    print(f"[INIT] Loaded {len(checked_urls)} URLs đã quét.")

async def append_line(fp, text):
    async with file_lock:
        with open(fp, "a", encoding="utf-8") as f:
            f.write(text + "\n")

async def notify(msg):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(DISCORD_WEBHOOK_URL, json={"content": msg})
    except:
        pass


# ========== Scanner ==========
async def scan_one(session):
    code = gen_code()
    url = BASE_URL + code

    if url in checked_urls:
        return False
    checked_urls.add(url)
    await append_line(CHECKED_FILE, url)

    await asyncio.sleep(random.uniform(0.5, 1.8))

    try:
        async with session.get(url, timeout=10) as res:
            text = await res.text(errors="ignore")
            stats["scan"] += 1

            if res.status in (429, 403) and "rate" in text.lower():
                msg = f"🛑 Bị rate-limit! {url}"
                print(msg)
                await notify(msg)
                return True

            if res.status == 200:
                await append_line(VALID_FILE, url)

                if "t.me" in text:
                    matches = re.findall(r'https://t\.me/[^\s"<>]+', text)
                    if matches:
                        stats["found"] += 1
                        msg = f"🔥 FOUND Telegram #{stats['found']}:\n{url}\n{matches}"
                        print(msg)
                        await append_line(TG_FILE, f"{url} → {matches}")
                        await notify(msg)

            if stats["scan"] % 100 == 0:
                print(f"📊 Scanned {stats['scan']} | Found {stats['found']}")

    except Exception as e:
        print("ERR:", e)

    return False


# ========== Main Loop ==========
async def main():
    ensure_log_dir()
    load_checked_urls()
    
    await notify("🚀 Safe Scanner Windows STARTED!")

    async with aiohttp.ClientSession() as session:
        while True:
            results = await asyncio.gather(*(scan_one(session) for _ in range(CONCURRENT)))

            if any(results):
                msg = f"⏸ Dừng {PAUSE_MINUTES} phút tránh limit"
                print(msg)
                await notify(msg)
                await asyncio.sleep(PAUSE_SECONDS)
                resume = "▶️ Resume tiếp tục sau khi pause"
                print(resume)
                await notify(resume)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Dừng bởi bạn.")
        asyncio.run(notify("⛔ Scanner stopped bởi user"))
