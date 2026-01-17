#!/usr/bin/env python3
"""
Telegram Bot - Berlin Panel + TronPanel + TRX Bot
Railway uyumlu - TL formatlı
Webhook ile çalışır
"""

import os
import ssl
import asyncio
from datetime import datetime
import aiohttp
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== ENV AYARLARI ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Railway HTTPS endpoint (https://yourapp.up.railway.app)
PORT = int(os.getenv("PORT", 8443))    # Railway PORT

# Panel 1 - Paypanel
PANEL1_URL = os.getenv("PANEL_URL")
PANEL1_USERNAME = os.getenv("USERNAME")
PANEL1_PASSWORD = os.getenv("PASSWORD")

# Panel 2 - TronPanel
PANEL2_URL = "https://win.tronpanel.com"
PANEL2_USERNAME = "ALFİ@123"
PANEL2_PASSWORD = "102030++"

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN veya WEBHOOK_URL eksik! (Railway Variables)")

# ==================== TRX AYARLARI ====================
TRX_ADDRESS = "TSjQYavgJBGPr8iV3zH7qo1bx927qKVMwA"
TRON_API_URL = "https://apilist.tronscan.org/api/account"

# ==================== PANEL 1 SITE ID'LERI (Paypanel) ====================
PANEL1_SITES = {
    "Berlin": {"id": "f0db5b93-f3b0-4026-a8a9-6d62fa810e10"},
    "7Finans": {"id": "fa2f40e9-b4ff-478f-9831-639e7551322a"},
    "WinPanel": {"id": "2f271e79-7386-4af9-7cf2-e699904c2d0d"},
    "777Havale": {"id": "b8576d7f-fc11-47d3-9e6f-07e052308221"},
}

# ==================== PANEL 2 SITE ID'LERI (TronPanel) ====================
PANEL2_SITES = {
    "BahisCasino": {"id": "9c69c72a-5f88-4130-bf9b-cef6755ffb78"},
    "Casinowon": {"id": "7af7e276-7dea-4fe2-8762-636e324917ac"},
    "Lehavale": {"id": "d3ae4fcc-8224-48a4-936b-7f424ea8b26c"},
    "TLCasino": {"id": "d36896e8-8500-4905-bc7c-c0988214b213"},
    "Wbahis": {"id": "b724ae8c-bd4b-4147-acb6-dfb72656c5d5"},
}

# ==================== TL FORMAT ====================
def format_number(value):
    try:
        num = int(float(str(value).replace(',', '').replace(' ', '')))
        return f"{num:,}".replace(",", ".") + " TL"
    except:
        return f"{value} TL"

# ==================== PANEL VERI CEKME (GENEL) ====================
async def fetch_site_data(session, reports_url, api_csrf, site_info, today):
    try:
        async with session.post(
            reports_url,
            headers={"X-CSRF-TOKEN": api_csrf},
            json={"site": site_info["id"], "dateone": today, "datetwo": today, "bank": "", "user": ""}
        ) as r:
            data = await r.json()
            dep = data.get("deposit", [0, 0, 0, 0])
            wth = data.get("withdraw", [0, 0, 0, 0])
            return site_info["id"], {
                "yat": float(dep[0]) if dep[0] is not None else 0,
                "yat_adet": int(float(dep[2])) if len(dep) > 2 and dep[2] is not None else 0,
                "cek": float(wth[0]) if wth[0] is not None else 0,
                "cek_adet": int(float(wth[2])) if len(wth) > 2 and wth[2] is not None else 0,
            }
    except Exception as e:
        print(f"Site verisi çekilemedi ({site_info['id']}): {e}")
        return site_info["id"], {"yat": 0, "yat_adet": 0, "cek": 0, "cek_adet": 0}

async def fetch_panel_data(panel_url, username, password, sites, use_plural=False):
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    login_url = f"{panel_url}/login"
    reports_url = f"{panel_url}/{'reports' if use_plural else 'report'}/quickly"
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(login_url) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            csrf = soup.find("input", {"name": "_token"})
            csrf_token = csrf["value"] if csrf else ""
        await session.post(login_url, data={"_token": csrf_token, "email": username, "password": password})
        async with session.get(reports_url) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            meta = soup.find("meta", {"name": "csrf-token"})
            api_csrf = meta["content"] if meta else ""
        today = datetime.now().strftime("%Y-%m-%d")
        tasks = [fetch_site_data(session, reports_url, api_csrf, s, today) for s in sites.values()]
        results = await asyncio.gather(*tasks)
        return {sites[k]["id"] if "id" in sites[k] else k: v for k, v in results}

async def fetch_all_data():
    async def get_panel1():
        try:
            return await fetch_panel_data(PANEL1_URL, PANEL1_USERNAME, PANEL1_PASSWORD, PANEL1_SITES, True)
        except: return {}
    async def get_panel2():
        try:
            return await fetch_panel_data(PANEL2_URL, PANEL2_USERNAME, PANEL2_PASSWORD, PANEL2_SITES, False)
        except: return {}
    date = datetime.now().strftime("%Y-%m-%d")
    panel1, panel2 = await asyncio.gather(get_panel1(), get_panel2())
    return date, panel1, panel2

# ==================== TELEGRAM COMMANDS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎰 Veri Bot\n/veri - Günlük TL verileri\n/tether - TRX & USDT bakiyesi")

async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Veriler çekiliyor...")
    try:
        date, panel1_data, panel2_data = await fetch_all_data()
        text = f"📊 *{date}*\n\n"
        for k, v in panel1_data.items():
            text += f"{k}\nYat: `{format_number(v['yat'])}` ({v['yat_adet']} adet)\nÇek: `{format_number(v['cek'])}` ({v['cek_adet']} adet)\n\n"
        for k, v in panel2_data.items():
            text += f"{k}\nYat: `{format_number(v['yat'])}` ({v['yat_adet']} adet)\nÇek: `{format_number(v['cek'])}` ({v['cek_adet']} adet)\n\n"
        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as e:
        print(f"Genel hata: {e}")
        await msg.edit_text("❌ Veriler alınırken hata oluştu")

async def tether(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Hesaplanıyor...")
    try:
        r = requests.get(TRON_API_URL, params={"address": TRX_ADDRESS}, timeout=10).json()
        trx_balance = r.get("balance", 0) / 1_000_000
        usdt_balance = 0.0
        for t in r.get("trc20token_balances", []):
            if t.get("tokenId") == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
                usdt_balance = int(t.get("balance", 0)) / 1_000_000
                break
        await msg.edit_text(f"📍 {TRX_ADDRESS}\n⭐️ TRX: {trx_balance:,.2f} TRX\n⭐️ USDT: ${usdt_balance:,.2f}")
    except Exception as e:
        print(e)
        await msg.edit_text("❌ Veri okunamadı")

# ==================== MAIN ====================
def main():
    print("🤖 Veri Bot başlatılıyor...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.add_handler(CommandHandler("tether", tether))

    # 🚀 Webhook ayarları
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/bot{BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()
