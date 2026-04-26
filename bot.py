#!/usr/bin/env python3
# Telegram Bot - Admin Kontrollü Full Versiyon

import os
import ssl
import asyncio
from datetime import datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup
import requests

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== ENV ====================

BOT_TOKEN = os.getenv("BOT_TOKEN")

PANEL1_URL = os.getenv("PANEL_URL")
PANEL1_USERNAME = os.getenv("USERNAME")
PANEL1_PASSWORD = os.getenv("PASSWORD")

VENUS_URL = os.getenv("VENUS_URL")
VENUS_USERNAME = os.getenv("VENUS_USERNAME")
VENUS_PASSWORD = os.getenv("VENUS_PASSWORD")

ADMIN_IDS = set(int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN bulunamadı")

# ==================== ADMIN ====================

def is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_IDS

async def deny(update: Update):
    await update.message.reply_text("hahhahaha yetkin yok.")

# ==================== TRX ====================

TRX_ADDRESS = "TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H"
TRON_API_URL = "https://apilist.tronscan.org/api/account"

# ==================== FORMAT ====================

def format_number(value):
    try:
        num = int(float(value))
        return f"{num:,}".replace(",", ".") + " TL"
    except:
        return "0 TL"

# ==================== PANEL ====================

async def fetch_site_data(session, reports_url, csrf, site_id, today):
    async with session.post(
        reports_url,
        headers={"X-CSRF-TOKEN": csrf},
        json={
            "site": site_id,
            "dateone": today,
            "datetwo": today,
            "bank": "",
            "user": ""
        }
    ) as r:
        data = await r.json()
        dep = data.get("deposit", [0, 0, 0])
        wth = data.get("withdraw", [0, 0, 0])

        return {
            "yat": dep[0],
            "yat_adet": int(dep[2] or 0),
            "cek": wth[0],
            "cek_adet": int(wth[2] or 0)
        }

async def fetch_panel(panel_url, username, password, sites, use_reports_plural=True):

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    login_url = f"{panel_url}/login"
    reports_url = f"{panel_url}/{'reports' if use_reports_plural else 'report'}/quickly"

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    async with aiohttp.ClientSession(connector=connector) as session:

        async with session.get(login_url) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            token = soup.find("input", {"name": "_token"})
            token = token["value"] if token else ""

        await session.post(login_url, data={
            "_token": token,
            "email": username,
            "password": password
        })

        async with session.get(reports_url) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            meta = soup.find("meta", {"name": "csrf-token"})
            csrf = meta["content"] if meta else ""

        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")

        tasks = [
            fetch_site_data(session, reports_url, csrf, info["id"], today)
            for info in sites.values()
        ]

        values = await asyncio.gather(*tasks)

        return dict(zip(sites.keys(), values))

# ==================== BOT ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    await update.message.reply_text("🤖 Veri Bot\n\n/veri\n/tether")

async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    msg = await update.message.reply_text("⏳ Veriler çekiliyor...")

    try:
        berlin = await fetch_panel(PANEL1_URL, PANEL1_USERNAME, PANEL1_PASSWORD, {
            "BERLİN": {"id": "f0db5b93-f3b0-4026-a8a9-6d62fa810e10"},
            "WinPanel": {"id": "2f271e79-7386-4af9-7cf2-e699904c2d0d"},
            "JaguarPanel": {"id": "698e467b-a871-4e18-978e-3d70adc534f4"},
            "SarıPanel": {"id": "e1874a83-f456-490d-83ad-1dcc1e1b61e0"},
            "Rİ": {"id": "12d991db-3ac3-4c63-9287-77b151cef14b"},
            "Fİ": {"id": "22ce3da9-7214-488a-b762-e8edd5f694c3"},
            "MX": {"id": "593f9e70-c9d3-4b3c-82ab-7abbdd9395bd"},
            "BC": {"id": "84b7ddb0-0db2-4f8a-92d1-2fde08599286"},
            "SKODA": {"id": "976b9d82-1346-4c85-9271-a2a02b552aab"},
        }, True)

        venus = await fetch_panel(VENUS_URL, VENUS_USERNAME, VENUS_PASSWORD, {
            "B": {"id": "9d282a4b-9664-4467-a53e-6b774cbf6d01"},
            "W": {"id": "48bedac9-2d1b-4a96-b736-e55de3fba453"},
            "T": {"id": "dee8e5a2-38ad-4006-8ad9-c622471e9e69"},
            "O": {"id": "d45c6fc9-bedd-4e3a-be0d-57aad4f958ea"},
            "L": {"id": "f685cc8d-e2a2-4d93-b4cb-b86d33b96e3f"},
            "JUMBO": {"id": "74aaa8d3-79de-4448-8414-22796848f33b"},
            "MİLOS": {"id": "527863a6-cf8e-438e-8979-d03da7eee6d3"},
            "BETOVİS": {"id": "d104651b-35f8-48e2-b0f4-862d70ee41fe"},
        }, False)

        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
        text = f"*{today}*\n\n"

        if berlin:
            text += "📊 BERLİN\n\n"
            for k, v in berlin.items():
                text += f"{k}\nYat: {format_number(v['yat'])} ({v['yat_adet']})\nÇek: {format_number(v['cek'])} ({v['cek_adet']})\n\n"

        if venus:
            text += "📊 VENUS\n\n"
            for k, v in venus.items():
                text += f"{k}\nYat: {format_number(v['yat'])} ({v['yat_adet']})\nÇek: {format_number(v['cek'])} ({v['cek_adet']})\n\n"

        await msg.edit_text(text, parse_mode="Markdown")

    except Exception as e:
        print(e)
        await msg.edit_text("❌ Veri alınamadı")

async def tether(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    msg = await update.message.reply_text("⏳ Hesaplanıyor...")

    try:
        r = requests.get(TRON_API_URL, params={"address": TRX_ADDRESS}, timeout=10)
        data = r.json()

        trx = data.get("balance", 0) / 1_000_000
        usdt = 0

        for t in data.get("trc20token_balances", []):
            if t.get("tokenId") == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
                usdt = int(t.get("balance", 0)) / 1_000_000

        await msg.edit_text(
            f"📍 {TRX_ADDRESS}\n"
            f"TRX: {trx:,.2f}\n"
            f"USDT: ${usdt:,.2f}"
        )

    except:
        await msg.edit_text("❌ Bakiye okunamadı")

# ==================== MAIN ====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.add_handler(CommandHandler("tether", tether))

    app.run_polling()

if __name__ == "__main__":
    main()
