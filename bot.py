#!/usr/bin/env python3
"""
Telegram Bot - Berlin Panel Veri Botu
API üzerinden site bazlı veri çeker
"""

import os
import ssl
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== AYARLAR ====================

# ❗ ARTIK KODDA ŞİFRE YOK – ORTAM DEĞİŞKENİNDEN OKUNUR
BOT_TOKEN = os.getenv("BOT_TOKEN")
USERNAME = os.getenv("PANEL_USERNAME")
PASSWORD = os.getenv("PANEL_PASSWORD")

# Panel Bilgileri
PANEL_URL = "https://berlin.tronpanel.com"
LOGIN_URL = f"{PANEL_URL}/login"
REPORTS_API_URL = f"{PANEL_URL}/reports/quickly"

# Site ID'leri
SITES = {
    "berlin": {
        "id": "f0db5b93-f3b0-4026-a8a9-6d62fa810e10",
        "name": "Berlin"
    },
    "7finans": {
        "id": "fa2f40e9-b4ff-478f-9831-639e7551322a",
        "name": "7Finans"
    },
    "winpanel": {
        "id": "2f271e79-7386-4af9-7cf2-e699904c2d0d",
        "name": "WinPanel"
    },
    "777havale": {
        "id": "b8576d7f-fc11-47d3-9e6f-07e052308221",
        "name": "777Havale"
    }
}
# =================================================


def format_number(value):
    """Sayıyı kısa formata çevir (13m, 500k gibi)"""
    try:
        num = float(str(value).replace(',', '').replace(' ', ''))
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}m"
        elif num >= 1_000:
            return f"{num/1_000:.0f}k"
        return f"{num:.0f}"
    except Exception:
        return str(value)


async def fetch_all_sites_data() -> dict:
    """Tüm sitelerden API üzerinden veri çek"""

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        # 1️⃣ Login sayfasından CSRF token al
        async with session.get(LOGIN_URL) as response:
            login_page = await response.text()

        soup = BeautifulSoup(login_page, 'html.parser')
        csrf_input = soup.find('input', {'name': '_token'})
        csrf_token = csrf_input['value'] if csrf_input else ""

        # 2️⃣ Giriş yap
        login_data = {
            '_token': csrf_token,
            'email': USERNAME,
            'password': PASSWORD,
        }

        async with session.post(LOGIN_URL, data=login_data, allow_redirects=True) as response:
            if response.status != 200:
                return {"error": f"Giriş başarısız! Status: {response.status}"}

        # 3️⃣ Reports sayfasından CSRF token al
        async with session.get(REPORTS_API_URL) as response:
            reports_page = await response.text()

        soup = BeautifulSoup(reports_page, 'html.parser')
        csrf_meta = soup.find('meta', {'name': 'csrf-token'})
        csrf_token = csrf_meta['content'] if csrf_meta else ""

        if not csrf_token:
            return {"error": "CSRF token bulunamadı!"}

        today = datetime.now().strftime("%Y-%m-%d")
        all_data = {}

        # 4️⃣ Site bazlı veri çek
        for site_key, site_info in SITES.items():
            headers = {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': csrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json',
            }

            payload = {
                'site': site_info['id'],
                'bank': '',
                'dateone': today,
                'datetwo': today,
                'user': ''
            }

            try:
                async with session.post(REPORTS_API_URL, headers=headers, json=payload) as response:
                    data = await response.json() if response.status == 200 else {}

                deposit = data.get('deposit', [0, 0, 0])
                withdraw = data.get('withdraw', [0, 0, 0])

                all_data[site_key] = {
                    "name": site_info['name'],
                    "yatirim": deposit[0],
                    "yatirim_adet": deposit[2],
                    "cekim": withdraw[0],
                    "cekim_adet": withdraw[2],
                }

            except Exception as e:
                all_data[site_key] = {
                    "name": site_info['name'],
                    "error": str(e)
                }

        return {"success": True, "sites": all_data, "date": today}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎰 *Berlin Panel Bot*\n\n"
        "/veri → Günlük panel verileri",
        parse_mode="Markdown"
    )


async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wait_msg = await update.message.reply_text("⏳ Veriler çekiliyor...")

    data = await fetch_all_sites_data()

    if "error" in data:
        await wait_msg.edit_text(f"❌ {data['error']}")
        return

    lines = [f"📊 *Panel Verileri* ({data['date']})\n━━━━━━━━━━━━━━\n"]

    for site in data['sites'].values():
        lines.append(
            f"🏷️ *{site['name']}*\n"
            f"Yat: `{format_number(site.get('yatirim', 0))}` | "
            f"Çek: `{format_number(site.get('cekim', 0))}`\n"
        )

    await wait_msg.edit_text("\n".join(lines), parse_mode="Markdown")


def main() -> None:
    print("🤖 Berlin Panel Bot başlatılıyor...")

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN bulunamadı! (Railway Variables)")

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("veri", veri))
    application.run_polling()


if __name__ == "__main__":
    main()
