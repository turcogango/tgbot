#!/usr/bin/env python3
# Telegram Bot - Admin Kontrollü Full Versiyon

import os
import ssl
import json
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

# ==================== TESLİMAT KAYIT ====================

TESLIMAT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "teslimat.json")

def load_teslimat():
    """Bugünün teslimat değerini dosyadan oku."""
    today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
    try:
        with open(TESLIMAT_FILE, "r") as f:
            data = json.load(f)
        if data.get("date") == today:
            return data.get("berlin", 0), data.get("venus", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return 0, 0

def save_teslimat(berlin_val=None, venus_val=None):
    """Teslimat değerini dosyaya kaydet. Mevcut değerleri korur."""
    today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
    current_berlin, current_venus = load_teslimat()

    data = {
        "date": today,
        "berlin": berlin_val if berlin_val is not None else current_berlin,
        "venus": venus_val if venus_val is not None else current_venus,
    }
    with open(TESLIMAT_FILE, "w") as f:
        json.dump(data, f)

# ==================== FORMAT ====================

def format_number(value):
    try:
        num = int(float(value))
        return f"{num:,}".replace(",", ".") + " TL"
    except:
        return "0 TL"

def safe(v):
    try:
        return float(v if v is not None else 0)
    except:
        return 0.0

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

        dep = data.get("deposit") or [0, 0, 0]
        wth = data.get("withdraw") or [0, 0, 0]

        return {
            "yat": safe(dep[0] if len(dep) > 0 else 0),
            "yat_adet": int(dep[2] or 0) if len(dep) > 2 else 0,
            "cek": safe(wth[0] if len(wth) > 0 else 0),
            "cek_adet": int(wth[2] or 0) if len(wth) > 2 else 0
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

    await update.message.reply_text(
        "🤖 Veri Bot\n\n"
        "/veri — Günlük rapor\n"
        "/teslimat — Teslimat değerini ayarla\n"
        "/tether — USDT bakiye"
    )

async def teslimat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Kullanım:
      /teslimat berlin 150000
      /teslimat venus 80000
      /teslimat              → mevcut değerleri gösterir
    """
    if not is_admin(update):
        return await deny(update)

    args = context.args

    # Argüman yoksa mevcut değerleri göster
    if not args:
        b_tes, v_tes = load_teslimat()
        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
        await update.message.reply_text(
            f"📦 Teslimat ({today})\n\n"
            f"BERLİN: {format_number(b_tes)}\n"
            f"VENUS: {format_number(v_tes)}\n\n"
            f"Ayarlamak için:\n"
            f"/teslimat berlin 150000\n"
            f"/teslimat venus 80000"
        )
        return

    if len(args) < 2:
        await update.message.reply_text(
            "❌ Kullanım:\n/teslimat berlin 150000\n/teslimat venus 80000"
        )
        return

    panel = args[0].lower()
    try:
        amount = float(args[1].replace(".", "").replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Geçersiz miktar.")
        return

    if panel in ("berlin", "b"):
        save_teslimat(berlin_val=amount)
        await update.message.reply_text(f"✅ BERLİN teslimat: {format_number(amount)}")
    elif panel in ("venus", "v"):
        save_teslimat(venus_val=amount)
        await update.message.reply_text(f"✅ VENUS teslimat: {format_number(amount)}")
    else:
        await update.message.reply_text("❌ Panel adı: berlin veya venus")

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

        # ==================== TESLİMAT DEĞERLERİNİ OKU ====================

        berlin_teslimat, venus_teslimat = load_teslimat()

        # ==================== BERLİN GENEL TOPLAM ====================

        b_yat = 0
        b_cek = 0
        b_yat_adet = 0
        b_cek_adet = 0

        if berlin:
            for v in berlin.values():
                b_yat += v["yat"] or 0
                b_cek += v["cek"] or 0
                b_yat_adet += v["yat_adet"] or 0
                b_cek_adet += v["cek_adet"] or 0

        b_net = b_yat - b_cek - berlin_teslimat
        b_emoji = "🟢" if b_net >= 0 else "🔴"

        text += "\n━━━━━━━━━━━━━━\n"
        text += "💰 BERLİN GENEL TOPLAM\n\n"
        text += f"Yatırım: {format_number(b_yat)} ({b_yat_adet})\n"
        text += f"Çekim: {format_number(b_cek)} ({b_cek_adet})\n"
        text += f"Teslimat: {format_number(berlin_teslimat)}\n"
        text += f"Fark: {b_emoji} {format_number(b_net)}\n"

        # ==================== VENUS GENEL TOPLAM ====================

        v_yat = 0
        v_cek = 0
        v_yat_adet = 0
        v_cek_adet = 0

        if venus:
            for v in venus.values():
                v_yat += v["yat"] or 0
                v_cek += v["cek"] or 0
                v_yat_adet += v["yat_adet"] or 0
                v_cek_adet += v["cek_adet"] or 0

        v_net = v_yat - v_cek - venus_teslimat
        v_emoji = "🟢" if v_net >= 0 else "🔴"

        text += "\n━━━━━━━━━━━━━━\n"
        text += "💰 VENUS GENEL TOPLAM\n\n"
        text += f"Yatırım: {format_number(v_yat)} ({v_yat_adet})\n"
        text += f"Çekim: {format_number(v_cek)} ({v_cek_adet})\n"
        text += f"Teslimat: {format_number(venus_teslimat)}\n"
        text += f"Fark: {v_emoji} {format_number(v_net)}\n"

        # ==================== GENEL TOPLAM ====================

        g_yat = b_yat + v_yat
        g_cek = b_cek + v_cek
        g_teslimat = berlin_teslimat + venus_teslimat
        g_net = g_yat - g_cek - g_teslimat
        g_emoji = "🟢" if g_net >= 0 else "🔴"

        text += "\n━━━━━━━━━━━━━━\n"
        text += "🏦 GENEL TOPLAM\n\n"
        text += f"Yatırım: {format_number(g_yat)} ({b_yat_adet + v_yat_adet})\n"
        text += f"Çekim: {format_number(g_cek)} ({b_cek_adet + v_cek_adet})\n"
        text += f"Teslimat: {format_number(g_teslimat)}\n"
        text += f"Fark: {g_emoji} {format_number(g_net)}\n"

        await msg.edit_text(text, parse_mode="Markdown")

    except Exception as e:
        print(e)
        await msg.edit_text("❌ Veri alınamadı")

async def tether(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    msg = await update.message.reply_text("⏳ Hesaplanıyor...")

    try:
        # Cüzdan bakiyesi
        r = requests.get(TRON_API_URL, params={"address": TRX_ADDRESS}, timeout=10)
        data = r.json()

        trx = data.get("balance", 0) / 1_000_000
        usdt = 0

        for t in data.get("trc20token_balances", []):
            if t.get("tokenId") == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
                usdt = int(t.get("balance", 0)) / 1_000_000

        # Binance'den anlık TRY kurları
        trx_try = 0.0
        usdt_try = 0.0
        try:
            br = requests.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbols": '["TRXTRY","USDTTRY"]'},
                timeout=10
            )
            for item in br.json():
                if item["symbol"] == "TRXTRY":
                    trx_try = float(item["price"])
                elif item["symbol"] == "USDTTRY":
                    usdt_try = float(item["price"])
        except:
            pass

        # TL karşılıkları
        trx_tl = trx * trx_try
        usdt_tl = usdt * usdt_try
        toplam_tl = trx_tl + usdt_tl

        text = f"📍 {TRX_ADDRESS}\n\n"
        text += f"💎 TRX: {trx:,.2f}\n"
        text += f"💵 USDT: {usdt:,.2f}\n"
        text += "\n━━━━━━━━━━━━━━\n"
        text += "📈 Anlık Kurlar (Binance)\n\n"
        text += f"TRX/TRY: {trx_try:,.4f} ₺\n"
        text += f"USDT/TRY: {usdt_try:,.2f} ₺\n"
        text += "\n━━━━━━━━━━━━━━\n"
        text += "💰 TL Karşılıkları\n\n"
        text += f"TRX: {trx_tl:,.2f} ₺\n"
        text += f"USDT: {usdt_tl:,.2f} ₺\n"
        text += f"\n🏦 Toplam: {toplam_tl:,.2f} ₺"

        await msg.edit_text(text)

    except:
        await msg.edit_text("❌ Bakiye okunamadı")

# ==================== MAIN ====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.add_handler(CommandHandler("teslimat", teslimat_cmd))
    app.add_handler(CommandHandler("tether", tether))

    app.run_polling()

if __name__ == "__main__":
    main()
