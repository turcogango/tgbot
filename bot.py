#!/usr/bin/env python3
"""
Telegram Bot - PayPanel + TronPanel + TRX
Railway uyumlu - TL formatlı
"""

import os
import ssl
import asyncio
from datetime import datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== ENV AYARLARI ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")

PANEL1_URL = os.getenv("PANEL_URL")
PANEL1_USERNAME = os.getenv("USERNAME")
PANEL1_PASSWORD = os.getenv("PASSWORD")

# Panel 2 (TronPanel / Jaguar)
PANEL2_URL = "https://madrid.paneljaguar.com"
PANEL2_USERNAME = "ALFİ@123"
PANEL2_PASSWORD = "102030++"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN bulunamadı (Railway Variables)")

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
        num = int(float(str(value).replace(",", "").replace(" ", "")))
        return f"{num:,}".replace(",", ".") + " TL"
    except:
        return "0 TL"

# ==================== PANEL VERI CEKME ====================
async def fetch_site_data(session, reports_url, api_csrf, site_id, site_name, today):
    try:
        async with session.post(
            reports_url,
            headers={"X-CSRF-TOKEN": api_csrf},
            json={
                "site": site_id,
                "dateone": today,
                "datetwo": today,
                "bank": "",
                "user": "",
            },
        ) as r:
            data = await r.json()

            dep = data.get("deposit", [0, 0, 0])
            wth = data.get("withdraw", [0, 0, 0])

            return site_name, {
                "yat": dep[0],
                "yat_adet": int(float(dep[2])) if len(dep) > 2 and dep[2] else 0,
                "cek": wth[0],
                "cek_adet": int(float(wth[2])) if len(wth) > 2 and wth[2] else 0,
            }
    except Exception as e:
        print(f"[HATA] {site_name}: {e}")
        return site_name, {"yat": 0, "yat_adet": 0, "cek": 0, "cek_adet": 0}


async def fetch_panel_data(panel_url, username, password, sites):
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    login_url = f"{panel_url}/login"
    reports_url = f"{panel_url}/reports/quickly"  # ✅ DOĞRU ENDPOINT

    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        # Login CSRF
        async with session.get(login_url) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            csrf_token = soup.find("input", {"name": "_token"})["value"]

        await session.post(
            login_url,
            data={"_token": csrf_token, "email": username, "password": password},
        )

        # API CSRF
        async with session.get(reports_url) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            api_csrf = soup.find("meta", {"name": "csrf-token"})["content"]

        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")

        tasks = [
            fetch_site_data(session, reports_url, api_csrf, v["id"], k, today)
            for k, v in sites.items()
        ]

        results = await asyncio.gather(*tasks)
        return dict(results)


async def fetch_all_data():
    panel1, panel2 = await asyncio.gather(
        fetch_panel_data(PANEL1_URL, PANEL1_USERNAME, PANEL1_PASSWORD, PANEL1_SITES),
        fetch_panel_data(PANEL2_URL, PANEL2_USERNAME, PANEL2_PASSWORD, PANEL2_SITES),
    )

    today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
    return today, panel1, panel2

# ==================== TELEGRAM KOMUTLAR ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Veri Bot\n\n"
        "/veri - Günlük TL verileri\n"
        "/tether - TRX & USDT bakiye"
    )

async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Veriler çekiliyor...")
    try:
        date, panel1, panel2 = await fetch_all_data()

        text = f"*{date}*\n\n"

        text += "📊 *PANEL 1*\n\n"
        for k, v in panel1.items():
            text += (
                f"*{k}*\n"
                f"Yat: {format_number(v['yat'])} ({v['yat_adet']} adet)\n"
                f"Çek: {format_number(v['cek'])} ({v['cek_adet']} adet)\n\n"
            )

        text += "📊 *PANEL 2*\n\n"
        for k, v in panel2.items():
            text += (
                f"*{k}*\n"
                f"Yat: {format_number(v['yat'])} ({v['yat_adet']} adet)\n"
                f"Çek: {format_number(v['cek'])} ({v['cek_adet']} adet)\n\n"
            )

        await msg.edit_text(text, parse_mode="Markdown")

    except Exception as e:
        print("GENEL HATA:", e)
        await msg.edit_text("❌ Veriler alınamadı")

async def tether(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import requests

        msg = await update.message.reply_text("⏳ Hesaplanıyor...")
        r = requests.get(TRON_API_URL, params={"address": TRX_ADDRESS}, timeout=10)
        data = r.json()

        trx = data.get("balance", 0) / 1_000_000
        usdt = 0.0

        for t in data.get("trc20token_balances", []):
            if t.get("tokenId") == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
                usdt = int(t.get("balance", 0)) / 1_000_000
                break

        await msg.edit_text(
            f"📍 `{TRX_ADDRESS}`\n"
            f"⭐ TRX: {trx:,.2f}\n"
            f"⭐ USDT: ${usdt:,.2f}",
            parse_mode="Markdown",
        )
    except:
        await update.message.reply_text("❌ TRX verisi okunamadı")

# ==================== MAIN ====================
def main():
    print("🤖 Bot başlatılıyor...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.add_handler(CommandHandler("tether", tether))

    app.run_polling()

if __name__ == "__main__":
    main()
