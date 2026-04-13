#!/usr/bin/env python3
# Telegram Bot - Admin Kontrollü

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

ADMIN_IDS = set(
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x
)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN bulunamadı")

# ==================== ADMIN CHECK ====================

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

# ==================== PANEL FETCH ====================

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
            token_input = soup.find("input", {"name": "_token"})
            token = token_input["value"] if token_input else ""

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

# ==================== TELEGRAM ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    await update.message.reply_text(
        "🤖 Veri Bot\n\n"
        "/veri\n"
        "/tether"
    )

async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    msg = await update.message.reply_text("⏳ Veriler çekiliyor...")

    try:
        await msg.edit_text("OK (panel kodları burada devam eder)")

    except Exception:
        await msg.edit_text("❌ Veri alınamadı")

async def tether(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    msg = await update.message.reply_text("⏳ Hesaplanıyor...")

    try:
        r = requests.get(TRON_API_URL, params={"address": TRX_ADDRESS}, timeout=10)
        data = r.json()

        trx = data.get("balance", 0) / 1_000_000
        usdt = 0.0

        for t in data.get("trc20token_balances", []):
            if t.get("tokenId") == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
                usdt = int(t.get("balance", 0)) / 1_000_000

        await msg.edit_text(
            f"📍 {TRX_ADDRESS}\n"
            f"⭐️ TRX: {trx:,.2f}\n"
            f"⭐️ USDT: ${usdt:,.2f}"
        )

    except:
        await msg.edit_text("❌ Bakiye okunamadı")

# ==================== MAIN ====================

def main():
    print("🤖 Bot başlatıldı")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.add_handler(CommandHandler("tether", tether))

    app.run_polling()

if __name__ == "__main__":
    main()
