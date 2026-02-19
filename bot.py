#!/usr/bin/env python3
"""
Telegram Bot - BERLİN & MADRİD
GRUP uyumlu | 23:59 otomatik rapor
"""

import os
import ssl
import asyncio
from datetime import datetime, timedelta, time

import aiohttp
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== ENV ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")

PANEL1_URL = os.getenv("PANEL_URL")
PANEL1_USERNAME = os.getenv("USERNAME")
PANEL1_PASSWORD = os.getenv("PASSWORD")

PANEL2_URL = os.getenv("PANEL2_URL")
PANEL2_USERNAME = os.getenv("PANEL2_USERNAME")
PANEL2_PASSWORD = os.getenv("PANEL2_PASSWORD")

# ==================== TRX ====================
TRX_ADDRESS = "TSjQYavgJBGPr8iV3zH7qo1bx927qKVMwA"
TRON_API_URL = "https://apilist.tronscan.org/api/account"

# ==================== SITE ID ====================
PANEL1_SITES = {
    "WinPanel": {"id": "2f271e79-7386-4af9-7cf2-e699904c2d0d"},
    "JaguarPanel": {"id": "698e467b-a871-4e18-978e-3d70adc534f4"},
}

PANEL2_SITES = {
    "777Havale": {"id": "b8576d7f-fc11-47d3-9e6f-07e052308221"},
    "7pay-TİKSO": {"id": "fa2009f2-8197-48d6-aa4f-dc6f65be7da9"},
}

# ==================== GRUP KAYIT ====================
ACTIVE_CHATS = set()

# ==================== FORMAT ====================
def tl(v):
    try:
        return f"{int(float(v)):,}".replace(",", ".") + " TL"
    except:
        return "0 TL"

# ==================== PANEL ====================
async def fetch_site(s, url, csrf, sid, name, today):
    try:
        async with s.post(
            url,
            headers={"X-CSRF-TOKEN": csrf},
            json={"site": sid, "dateone": today, "datetwo": today, "bank": "", "user": ""},
        ) as r:
            d = await r.json()
            dep = d.get("deposit", [0, 0, 0])
            wth = d.get("withdraw", [0, 0, 0])
            return name, {
                "yat": dep[0],
                "cek": wth[0],
            }
    except:
        return name, {"yat": 0, "cek": 0}

async def fetch_panel(url, user, pwd, sites):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as s:
        async with s.get(f"{url}/login") as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            token = soup.find("input", {"name": "_token"})["value"]

        await s.post(f"{url}/login", data={"_token": token, "email": user, "password": pwd})

        async with s.get(f"{url}/reports/quickly") as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            csrf = soup.find("meta", {"name": "csrf-token"})["content"]

        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")

        tasks = [
            fetch_site(s, f"{url}/reports/quickly", csrf, v["id"], k, today)
            for k, v in sites.items()
        ]
        return dict(await asyncio.gather(*tasks))

# ==================== RAPOR ====================
async def send_daily_report(bot, chat_id):
    p1, p2 = await asyncio.gather(
        fetch_panel(PANEL1_URL, PANEL1_USERNAME, PANEL1_PASSWORD, PANEL1_SITES),
        fetch_panel(PANEL2_URL, PANEL2_USERNAME, PANEL2_PASSWORD, PANEL2_SITES),
    )

    date = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
    text = f"*{date}*\n\n📊 *BERLİN*\n\n"

    for k, v in p1.items():
        text += f"*{k}*\nYat: {tl(v['yat'])}\nÇek: {tl(v['cek'])}\n\n"

    text += "📊 *MADRİD*\n\n"
    for k, v in p2.items():
        text += f"*{k}*\nYat: {tl(v['yat'])}\nÇek: {tl(v['cek'])}\n\n"

    await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    await bot.send_message(chat_id=chat_id, text="🎆🎇 ABİİ 🔥🔥🔥 PARA YAĞIYOR 💸💸💸")

# ==================== KOMUTLAR ====================
async def aktif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ACTIVE_CHATS.add(chat_id)
    await update.message.reply_text("✅ Grup aktif edildi\n⏰ Her gün 23:59 otomatik rapor")

async def pasif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ACTIVE_CHATS.discard(chat_id)
    await update.message.reply_text("❌ Grup pasif edildi")

# ==================== JOB ====================
async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in list(ACTIVE_CHATS):
        try:
            await send_daily_report(context.bot, chat_id)
            await asyncio.sleep(2)
        except:
            pass

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("aktif", aktif))
    app.add_handler(CommandHandler("pasif", pasif))

    app.job_queue.run_daily(daily_job, time=time(hour=23, minute=59))

    print("🤖 Grup uyumlu bot çalışıyor")
    app.run_polling()

if __name__ == "__main__":
    main()
