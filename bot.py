#!/usr/bin/env python3
"""
Telegram Bot - Berlin Panel + TronPanel + TRX Bot
Railway uyumlu - TL formatlı
"""

import os
import ssl
from datetime import datetime
import aiohttp
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== ENV AYARLARI ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Panel 1 - Paypanel (Berlin Panel)
PANEL1_URL = os.getenv("PANEL_URL")
PANEL1_USERNAME = os.getenv("USERNAME")
PANEL1_PASSWORD = os.getenv("PASSWORD")

# Panel 2 - TronPanel
PANEL2_URL = "https://win.tronpanel.com"
PANEL2_USERNAME = "ALFİ@123"
PANEL2_PASSWORD = "102030++"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN bulunamadı! (Railway Variables)")

# ==================== TRX AYARLARI ====================
TRX_ADDRESS = "TSjQYavgJBGPr8iV3zH7qo1bx927qKVMwA"
TRON_API_URL = "https://apilist.tronscan.org/api/account"

# ==================== PANEL 1 SITE ID'LERI (Paypanel) ====================
PANEL1_SITES = {
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

# ==================== PANEL 2 SITE ID'LERI (TronPanel) ====================
PANEL2_SITES = {
    "bahiscasino": {
        "id": "9c69c72a-5f88-4130-bf9b-cef6755ffb78",
        "name": "BahisCasino"
    },
    "casinowon": {
        "id": "7af7e276-7dea-4fe2-8762-636e324917ac",
        "name": "Casinowon"
    },
    "lehavale": {
        "id": "d3ae4fcc-8224-48a4-936b-7f424ea8b26c",
        "name": "Lehavale"
    },
    "tlcasino": {
        "id": "d36896e8-8500-4905-bc7c-c0988214b213",
        "name": "TLCasino"
    },
    "wbahis": {
        "id": "b724ae8c-bd4b-4147-acb6-dfb72656c5d5",
        "name": "Wbahis"
    }
}

# ==================== TL FORMAT ====================
def format_number(value):
    if value is None:
        return "0 TL"
    try:
        num = int(float(str(value).replace(',', '').replace(' ', '')))
        return f"{num:,}".replace(",", ".") + " TL"
    except:
        return f"{value} TL"

# ==================== PANEL VERI CEKME (GENEL) ====================
async def fetch_panel_data(panel_url, username, password, sites, use_plural=False):
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    login_url = f"{panel_url}/login"
    # Paypanel (Panel 1) plural /reports kullanır, TronPanel (Panel 2) singular /report kullanır.
    reports_url = f"{panel_url}/{'reports' if use_plural else 'report'}/quickly"
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # Login sayfasından CSRF token al
        async with session.get(login_url) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            csrf = soup.find("input", {"name": "_token"})
            csrf_token = csrf["value"] if csrf else ""
        
        # Giriş yap
        await session.post(login_url, data={
            "_token": csrf_token,
            "email": username,
            "password": password
        })
        
        # Rapor sayfasından CSRF token al
        async with session.get(reports_url) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            meta = soup.find("meta", {"name": "csrf-token"})
            api_csrf = meta["content"] if meta else ""
        
        today = datetime.now().strftime("%Y-%m-%d")
        result = {}
        
        for s in sites.values():
            try:
                async with session.post(
                    reports_url,
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
                    # deposit/withdraw listelerinde 0: tutar, 2: günlük adet bilgisi yer alır.
                    dep = data.get("deposit", [0, 0, 0, 0])
                    wth = data.get("withdraw", [0, 0, 0, 0])
                    
                    # Kullanıcı günlük adetleri (index 2) istediği için güncellendi.
                    result[s["name"]] = {
                        "yat": dep[0],
                        "yat_adet": int(float(dep[2])) if len(dep) > 2 and dep[2] is not None else 0,
                        "cek": wth[0],
                        "cek_adet": int(float(wth[2])) if len(wth) > 2 and wth[2] is not None else 0
                    }
            except Exception as e:
                print(f"Site verisi çekilemedi ({s['name']}): {e}")
                result[s["name"]] = {"yat": 0, "yat_adet": 0, "cek": 0, "cek_adet": 0}
        
        return result

# ==================== TUM VERILERI CEK ====================
async def fetch_all_data():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Panel 1 verileri (Paypanel plural /reports kullanır)
    try:
        panel1_data = await fetch_panel_data(
            PANEL1_URL, PANEL1_USERNAME, PANEL1_PASSWORD, PANEL1_SITES, use_plural=True
        )
    except Exception as e:
        print(f"Panel 1 hatası: {e}")
        panel1_data = {}
    
    # Panel 2 verileri (TronPanel singular /report kullanır)
    try:
        panel2_data = await fetch_panel_data(
            PANEL2_URL, PANEL2_USERNAME, PANEL2_PASSWORD, PANEL2_SITES, use_plural=False
        )
    except Exception as e:
        print(f"Panel 2 hatası: {e}")
        panel2_data = {}
    
    return today, panel1_data, panel2_data

# ==================== TELEGRAM ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎰 Veri Bot\n\n"
        "/veri - Günlük TL verileri (Tüm Paneller)\n"
        "/tether - TRX & USDT bakiyesi"
    )

async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Veriler çekiliyor...")
    
    try:
        date, panel1_data, panel2_data = await fetch_all_data()
        
        text = f"📊 *{date}*\n\n"
        
        # Panel 1 Verileri
        if panel1_data:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += "🔵 *PANEL 1 (Paypanel)*\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            for k, v in panel1_data.items():
                text += (
                    f"🏷️ *{k}*\n"
                    f"Yat: `{format_number(v['yat'])}` ({v['yat_adet']} adet)\n"
                    f"Çek: `{format_number(v['cek'])}` ({v['cek_adet']} adet)\n\n"
                )
        
        # Panel 2 Verileri
        if panel2_data:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += "🟢 *PANEL 2 (TronPanel)*\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            for k, v in panel2_data.items():
                text += (
                    f"🏷️ *{k}*\n"
                    f"Yat: `{format_number(v['yat'])}` ({v['yat_adet']} adet)\n"
                    f"Çek: `{format_number(v['cek'])}` ({v['cek_adet']} adet)\n\n"
                )
        
        await msg.edit_text(text, parse_mode="Markdown")
        
    except Exception as e:
        print(f"Genel hata: {e}")
        await msg.edit_text("❌ Veriler alınırken hata oluştu")

async def tether(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg = await update.message.reply_text("⏳ Hesaplanıyor...")

        r = requests.get(TRON_API_URL, params={"address": TRX_ADDRESS}, timeout=10)
        data = r.json()

        trx_balance = data.get("balance", 0) / 1_000_000

        usdt_balance = 0.0
        for t in data.get("trc20token_balances", []):
            if t.get("tokenId") == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
                usdt_balance = int(t.get("balance", 0)) / 1_000_000
                break

        text = (
            f"📍 {TRX_ADDRESS}\n\n"
            f"⭐️ TRX: {trx_balance:,.2f} TRX\n"
            f"⭐️ USDT: ${usdt_balance:,.2f}"
        )

        await msg.edit_text(text)

    except Exception as e:
        print(e)
        await update.message.reply_text("❌ Veri okunamadı")

# ==================== MAIN ====================
def main():
    print("🤖 Veri Bot başlatılıyor...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.add_handler(CommandHandler("tether", tether))
    app.run_polling()

if __name__ == "__main__":
    main()
