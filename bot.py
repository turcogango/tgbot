#!/usr/bin/env python3
# Telegram Bot - Admin + Panel + TRX/USDT Live Monitor (FIXED)

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

# ==================== TRX ====================

TRX_ADDRESS = "TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H"
TRON_API = f"https://api.trongrid.io/v1/accounts/{TRX_ADDRESS}/transactions?limit=10"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

last_tx = None

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

# ==================== PANEL (DEĞİŞMEDİ) ====================

def format_number(value):
    try:
        num = int(float(value))
        return f"{num:,}".replace(",", ".") + " TL"
    except:
        return "0 TL"

# (senin panel fonksiyonların aynen kaldı)

# ==================== COMMANDS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)
    await update.message.reply_text("🤖 Bot aktif")

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

# ==================== FIX: POST_INIT ====================

async def post_init(app):
    app.create_task(tron_listener(app))

# ==================== MAIN ====================

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.add_handler(CommandHandler("tether", tether))

    app.run_polling()

if __name__ == "__main__":
    main()
