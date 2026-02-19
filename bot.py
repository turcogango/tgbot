#!/usr/bin/env python3
# Telegram Bot - BERLİN & MADRİD Panel - Railway Uyumlu (Stabil)

import os
import ssl
import asyncio
from datetime import datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup
import requests

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== ENV AYARLARI ====================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# PANEL 1 -> BERLİN  (senin variable isimlerinle)
PANEL1_URL = os.getenv("PANEL_URL")
PANEL1_USERNAME = os.getenv("USERNAME")
PANEL1_PASSWORD = os.getenv("PASSWORD")

# PANEL 2 -> MADRİD (senin variable isimlerinle)
PANEL2_URL = os.getenv("PANEL2_URL")
PANEL2_USERNAME = os.getenv("PANEL2_USERNAME")
PANEL2_PASSWORD = os.getenv("PANEL2_PASSWORD")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN bulunamadı")

# ==================== TRX AYARLARI ====================

TRX_ADDRESS = "TSjQYavgJBGPr8iV3zH7qo1bx927qKVMwA"
TRON_API_URL = "https://apilist.tronscan.org/api/account"

# ==================== PANEL SITE ID'LERI ====================

PANEL1_SITES = {
    "WinPanel": {"id": "2f271e79-7386-4af9-7cf2-e699904c2d0d"},
    "JaguarPanel": {"id": "698e467b-a871-4e18-978e-3d70adc534f4"},
}

PANEL2_SITES = {
    "777Havale": {"id": "b8576d7f-fc11-47d3-9e6f-07e052308221"},
    "7pay-TİKSO": {"id": "fa2009f2-8197-48d6-aa4f-dc6f65be7da9"},
}

# ==================== TL FORMAT ====================

def format_number(value):
    try:
        num = int(float(value))
        return f"{num:,}".replace(",", ".") + " TL"
    except:
        return "0 TL"

# ==================== PANEL VERI CEKME ====================

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

async def fetch_panel(panel_url, username, password, sites):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    login_url = f"{panel_url}/login"
    reports_url = f"{panel_url}/reports/quickly"

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

        results = {}
        for name, info in sites.items():
            results[name] = await fetch_site_data(
                session, reports_url, csrf, info["id"], today
            )

        return results

# ==================== TELEGRAM KOMUTLARI ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Veri Bot\n\n"
        "/veri - Günlük panel verileri\n"
        "/tether - TRX & USDT bakiyesi"
    )

async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Veriler çekiliyor...")

    try:
        berlin = await fetch_panel(
            PANEL1_URL, PANEL1_USERNAME, PANEL1_PASSWORD, PANEL1_SITES
        )
        madrid = await fetch_panel(
            PANEL2_URL, PANEL2_USERNAME, PANEL2_PASSWORD, PANEL2_SITES
        )

        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
        text = f"*{today}*\n\n"

        text += "📊 *BERLİN*\n\n"
        for k, v in berlin.items():
            text += (
                f"{k}\n"
                f"Yat: {format_number(v['yat'])} ({v['yat_adet']} adet)\n"
                f"Çek: {format_number(v['cek'])} ({v['cek_adet']} adet)\n\n"
            )

        text += "📊 *MADRİD*\n\n"
        for k, v in madrid.items():
            text += (
                f"{k}\n"
                f"Yat: {format_number(v['yat'])} ({v['yat_adet']} adet)\n"
                f"Çek: {format_number(v['cek'])} ({v['cek_adet']} adet)\n\n"
            )

        await msg.edit_text(text, parse_mode="Markdown")

    except Exception as e:
        print("HATA:", e)
        await msg.edit_text("❌ Veri alınamadı")

async def tether(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    print("🤖 Veri Bot başlatıldı")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.add_handler(CommandHandler("tether", tether))

    app.run_polling()

if __name__ == "__main__":
    main()
