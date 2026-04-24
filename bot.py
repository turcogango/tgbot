#!/usr/bin/env python3
# Telegram Bot - Admin + Panel + TRX/USDT Live Monitor

import os
import ssl
import asyncio
import requests
from datetime import datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup

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
    await update.message.reply_text("yetkin yok.")

# ==================== TRX LIVE ====================

TRX_ADDRESS = "TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H"
TRON_API = f"https://api.trongrid.io/v1/accounts/{TRX_ADDRESS}/transactions?limit=10"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

last_tx = None

# ==================== FORMAT ====================

def format_number(value):
    try:
        num = int(float(value))
        return f"{num:,}".replace(",", ".") + " TL"
    except:
        return "0 TL"

# ==================== PANEL (AYNI KALDI) ====================

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

# ==================== TRX LISTENER ====================

async def tron_listener(app):
    global last_tx

    await asyncio.sleep(5)

    while True:
        try:
            r = requests.get(TRON_API, timeout=10)
            txs = r.json().get("data", [])

            if txs:
                latest = txs[0]["txID"]

                if last_tx is None:
                    last_tx = latest

                elif latest != last_tx:

                    for tx in txs:
                        if tx["txID"] == last_tx:
                            break

                        txid = tx["txID"]
                        raw = tx["raw_data"]["contract"][0]
                        ctype = raw["type"]

                        # TRX
                        if ctype == "TransferContract":
                            v = raw["parameter"]["value"]
                            amount = v["amount"] / 1_000_000

                            to_addr = v["to_address"]
                            from_addr = v["owner_address"]

                            if TRX_ADDRESS in to_addr:
                                for admin in ADMIN_IDS:
                                    await app.bot.send_message(
                                        chat_id=admin,
                                        text=f"""📥 TRX GELDİ
Miktar: {amount} TRX
💸 Rest gelsin paralar gelsin paralar

TxID: {txid}
https://tronscan.org/#/transaction/{txid}"""
                                    )

                            elif TRX_ADDRESS in from_addr:
                                for admin in ADMIN_IDS:
                                    await app.bot.send_message(
                                        chat_id=admin,
                                        text=f"""📤 TRX GİTTİ
Miktar: {amount} TRX

TxID: {txid}
https://tronscan.org/#/transaction/{txid}"""
                                    )

                        # USDT
                        elif ctype == "TriggerSmartContract":
                            v = raw["parameter"]["value"]
                            contract = v.get("contract_address")

                            if contract == USDT_CONTRACT:
                                data = v.get("data", "")

                                try:
                                    amount_hex = data[-64:]
                                    amount = int(amount_hex, 16) / 1_000_000
                                except:
                                    amount = 0

                                for admin in ADMIN_IDS:
                                    await app.bot.send_message(
                                        chat_id=admin,
                                        text=f"""💵 USDT GELDİ
Miktar: {amount} USDT
💸 Rest gelsin paralar gelsin paralar

TxID: {txid}
https://tronscan.org/#/transaction/{txid}"""
                                    )

                    last_tx = latest

            await asyncio.sleep(8)

        except Exception as e:
            print("TRON error:", e)
            await asyncio.sleep(5)

# ==================== BOT COMMANDS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    await update.message.reply_text("🤖 Bot aktif\n/veri\n/tether")

async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    await update.message.reply_text("⏳")

async def tether(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    r = requests.get(TRON_API, params={"address": TRX_ADDRESS}, timeout=10)
    data = r.json()

    trx = data.get("balance", 0) / 1_000_000
    usdt = 0

    for t in data.get("trc20token_balances", []):
        if t.get("tokenId") == USDT_CONTRACT:
            usdt = int(t.get("balance", 0)) / 1_000_000

    await update.message.reply_text(f"TRX: {trx}\nUSDT: {usdt}")

# ==================== MAIN ====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.add_handler(CommandHandler("tether", tether))

    # 🔥 LIVE LISTENER
    app.create_task(tron_listener(app))

    app.run_polling()

if __name__ == "__main__":
    main()
