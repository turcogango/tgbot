#!/usr/bin/env python3
"""
Telegram Bot - Berlin Panel Veri Botu
Railway uyumlu - TL formatlı
"""

import os
import ssl
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== ENV AYARLARI ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PANEL_URL = os.getenv("PANEL_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN bulunamadı! (Railway Variables)")

LOGIN_URL = f"{PANEL_URL}/login"
REPORTS_API_URL = f"{PANEL_URL}/reports/quickly"

# ==================== SITE ID'LERI ====================
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

# ==================== TL FORMAT ====================
def format_number(value):
    try:
        num = int(float(str(value).replace(',', '').replace(' ', '')))
        return f"{num:,}".replace(",", ".") + " TL"
    except:
        return f"{value} TL"

# ==================== VERI CEKME ====================
async def fetch_all_sites_data():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(LOGIN_URL) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            csrf = soup.find("input", {"name": "_token"})
            csrf_token = csrf["value"] if csrf else ""

        await session.post(LOGIN_URL, data={
            "_token": csrf_token,
            "email": USERNAME,
            "password": PASSWORD
        })

        async with session.get(REPORTS_API_URL) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            meta = soup.find("meta", {"name": "csrf-token"})
            api_csrf = meta["content"] if meta else ""

        today = datetime.now().strftime("%Y-%m-%d")
        result = {}

        for s in SITES.values():
            async with session.post(
                REPORTS_API_URL,
                headers={"X-CSRF-TOKEN": api_csrf},
                json={
                    "site": s["id"],
                    "dateone": today,
                    "datetwo": today,
                    "bank": "",
                    "user": ""
                }
            ) as r:
                data = await r.json()
                dep = data.get("deposit", [0, 0, 0])
                wth = data.get("withdraw", [0, 0, 0])

                result[s["name"]] = {
                    "yat": dep[0],
                    "cek": wth[0]
                }

        return today, result

# ==================== TELEGRAM ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎰 Berlin Panel Bot\n\n/veri - Günlük TL verileri"
    )

async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Veriler çekiliyor...")
    date, data = await fetch_all_sites_data()

    text = f"📊 *{date}*\n\n"
    for k, v in data.items():
        text += (
            f"🏷️ *{k}*\n"
            f"Yat: `{format_number(v['yat'])}` | "
            f"Çek: `{format_number(v['cek'])}`\n\n"
        )

    await msg.edit_text(text, parse_mode="Markdown")

# ==================== MAIN ====================
def main():
    print("🤖 Berlin Panel Bot başlatılıyor...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.run_polling()

if __name__ == "__main__":
    main()
