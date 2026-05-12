#!/usr/bin/env python3
# Telegram Bot - Admin Kontrollü Full Versiyon

import json
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

# Aynı anda yalnızca bir /veri akışı (panel yükü ve oturum çakışmasını azaltır)
VERI_FETCH_LOCK = asyncio.Lock()

# Tek bir fetch_panel içinde aynı panele giden POST sayısı (sunucu limiti için)
PANEL_SITE_CONCURRENCY = 4

# ==================== ADMIN ====================

def is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_IDS

async def deny(update: Update):
    await update.message.reply_text("hahhahaha yetkin yok.")

# ==================== TRX ====================

TRX_ADDRESS = "TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H"
TRON_API_URL = "https://apilist.tronscan.org/api/account"
OKX_TICKER_URL = "https://www.okx.com/api/v5/market/ticker"


def fetch_okx_spot_rates():
    """OKX spot: USDT/TRY, TRX/USDT ve bunlardan türetilen TRX/TRY (TL)."""
    out = {"usdt_try": None, "trx_usdt": None, "trx_try": None}
    try:
        r_u = requests.get(
            OKX_TICKER_URL,
            params={"instId": "USDT-TRY"},
            timeout=10,
        )
        r_t = requests.get(
            OKX_TICKER_URL,
            params={"instId": "TRX-USDT"},
            timeout=10,
        )
        ju = r_u.json()
        jt = r_t.json()
        if ju.get("code") == "0" and ju.get("data"):
            out["usdt_try"] = float(ju["data"][0]["last"])
        if jt.get("code") == "0" and jt.get("data"):
            out["trx_usdt"] = float(jt["data"][0]["last"])
        if out["usdt_try"] is not None and out["trx_usdt"] is not None:
            out["trx_try"] = out["trx_usdt"] * out["usdt_try"]
    except Exception:
        pass
    return out


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

def _panel_label_from_url(panel_url: str) -> str:
    if not panel_url:
        return "panel"
    return panel_url.rstrip("/").split("/")[-1] or panel_url


async def parse_json_http_response(resp: aiohttp.ClientResponse, what: str) -> dict:
    """HTML/hata gövdesinde r.json() patlamasın diye metin + tip kontrolü."""
    text = await resp.text()
    ctype = resp.headers.get("Content-Type", "")

    if resp.status >= 400:
        raise RuntimeError(
            f"{what}: HTTP {resp.status} ct={ctype!r} url={resp.url} gövde={text[:400]!r}"
        )

    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"{what}: JSON ayrıştırılamadı url={resp.url} örnek={text[:300]!r}"
            ) from e

    raise RuntimeError(
        f"{what}: JSON bekleniyordu, HTML veya metin geldi "
        f"(status={resp.status}, ct={ctype!r}, url={resp.url}, örnek={text[:400]!r})"
    )


async def fetch_site_data(session, reports_url, csrf, site_id, today, what: str):
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
        data = await parse_json_http_response(r, what)

        dep = data.get("deposit") or [0, 0, 0]
        wth = data.get("withdraw") or [0, 0, 0]

        return {
            "yat": safe(dep[0] if len(dep) > 0 else 0),
            "yat_adet": int(dep[2] or 0) if len(dep) > 2 else 0,
            "cek": safe(wth[0] if len(wth) > 0 else 0),
            "cek_adet": int(wth[2] or 0) if len(wth) > 2 else 0
        }

async def fetch_total_delivery(session, reports_url, csrf, today, what: str):
    """Site boş bırakılarak toplam teslimat verisini çeker."""
    async with session.post(
        reports_url,
        headers={"X-CSRF-TOKEN": csrf},
        json={
            "site": "",
            "dateone": today,
            "datetwo": today,
            "bank": "",
            "user": ""
        }
    ) as r:
        data = await parse_json_http_response(r, what)
        # delivery formatı: [adet, tutar]
        dlv = data.get("delivery") or ["0", "0.00"]
        return {
            "teslimat": safe(dlv[1] if len(dlv) > 1 else 0),
            "teslimat_adet": int(safe(dlv[0])) if len(dlv) > 0 else 0
        }

async def fetch_panel(panel_url, username, password, sites, use_reports_plural=True):

    label = _panel_label_from_url(panel_url)

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    login_url = f"{panel_url}/login"
    reports_url = f"{panel_url}/{'reports' if use_reports_plural else 'report'}/quickly"

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    async with aiohttp.ClientSession(connector=connector) as session:

        async with session.get(login_url) as r:
            login_html = await r.text()
            if r.status >= 400:
                raise RuntimeError(
                    f"[{label}] Giriş sayfası HTTP {r.status}: {login_html[:300]!r}"
                )
            soup = BeautifulSoup(login_html, "html.parser")
            token = soup.find("input", {"name": "_token"})
            token = token["value"] if token else ""

        if not token:
            raise RuntimeError(f"[{label}] Login formunda _token bulunamadı")

        async with session.post(
            login_url,
            data={
                "_token": token,
                "email": username,
                "password": password,
            },
            allow_redirects=True,
        ) as login_resp:
            if login_resp.status >= 400:
                body = await login_resp.text()
                raise RuntimeError(
                    f"[{label}] Login POST HTTP {login_resp.status}: {body[:400]!r}"
                )

        async with session.get(reports_url) as r:
            if r.status >= 400:
                body = await r.text()
                raise RuntimeError(
                    f"[{label}] Rapor sayfası HTTP {r.status}: {body[:400]!r}"
                )
            html = await r.text()
            soup = BeautifulSoup(html, "html.parser")
            meta = soup.find("meta", {"name": "csrf-token"})
            csrf = meta["content"] if meta else ""

        if not csrf:
            raise RuntimeError(
                f"[{label}] CSRF alınamadı (şifre hatalı, oturum yok veya sayfa girişe düşüyor)"
            )

        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")

        sem = asyncio.Semaphore(PANEL_SITE_CONCURRENCY)

        async def fetch_one_site(key, info):
            async with sem:
                return key, await fetch_site_data(
                    session,
                    reports_url,
                    csrf,
                    info["id"],
                    today,
                    what=f"[{label}] site={key}",
                )

        pairs = await asyncio.gather(
            *[fetch_one_site(k, info) for k, info in sites.items()]
        )
        site_data = {k: v for k, v in pairs}

        delivery = await fetch_total_delivery(
            session, reports_url, csrf, today, what=f"[{label}] teslimat"
        )

        return site_data, delivery

# ==================== BOT ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    await update.message.reply_text(
        "🤖 Veri Bot\n\n"
        "/veri — Günlük rapor\n"
        "/tether — USDT bakiye"
    )


async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)

    msg = await update.message.reply_text("⏳ Veriler çekiliyor...")

    try:
        was_queued = False
        if VERI_FETCH_LOCK.locked():
            await msg.edit_text("⏳ Önceki /veri isteği sürüyor; sıraya alındı, bekleniyor...")
            was_queued = True

        async with VERI_FETCH_LOCK:
            # Aynı metne tekrar edit Telegram'da "message is not modified" hatası verir
            if was_queued:
                await msg.edit_text("⏳ Veriler çekiliyor...")
            berlin, berlin_delivery = await fetch_panel(PANEL1_URL, PANEL1_USERNAME, PANEL1_PASSWORD, {
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

            venus, venus_delivery = await fetch_panel(VENUS_URL, VENUS_USERNAME, VENUS_PASSWORD, {
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
                    fark = v['yat'] - v['cek']
                    text += f"{k}\nYat: {format_number(v['yat'])} ({v['yat_adet']})\nÇek: {format_number(v['cek'])} ({v['cek_adet']})\nFark: {format_number(fark)}\n\n"

            if venus:
                text += "📊 VENUS\n\n"
                for k, v in venus.items():
                    fark = v['yat'] - v['cek']
                    text += f"{k}\nYat: {format_number(v['yat'])} ({v['yat_adet']})\nÇek: {format_number(v['cek'])} ({v['cek_adet']})\nFark: {format_number(fark)}\n\n"

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

            b_teslimat = berlin_delivery["teslimat"]
            b_teslimat_adet = berlin_delivery["teslimat_adet"]

            b_net = b_yat - b_cek - b_teslimat
            b_emoji = "🟢" if b_net >= 0 else "🔴"

            text += "\n━━━━━━━━━━━━━━\n"
            text += "💰 BERLİN GENEL TOPLAM\n\n"
            text += f"Yatırım: {format_number(b_yat)} ({b_yat_adet})\n"
            text += f"Çekim: {format_number(b_cek)} ({b_cek_adet})\n"
            text += f"Teslimat: {format_number(b_teslimat)} ({b_teslimat_adet})\n"
            text += f"Fark: {b_emoji} {format_number(b_net)}\n"

            await msg.edit_text(text, parse_mode="Markdown")

    except Exception as e:
        print(e)
        detail = str(e).strip()
        if len(detail) > 500:
            detail = detail[:500] + "…"
        out = "❌ Veri alınamadı" + (f"\n\n{detail}" if detail else "")
        if len(out) > 4096:
            out = out[:4090] + "…"
        await msg.edit_text(out)

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

        # CoinGecko'dan anlık kurlar (TRY)
        trx_try = 0.0
        usdt_try = 0.0
        try:
            cg = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "tron,tether", "vs_currencies": "try"},
                timeout=10
            )
            cg.raise_for_status()
            cg_data = cg.json()
            trx_try = float(cg_data.get("tron", {}).get("try") or 0)
            usdt_try = float(cg_data.get("tether", {}).get("try") or 0)
        except Exception:
            pass

        okx = fetch_okx_spot_rates()
        okx_ut = okx["usdt_try"]
        okx_tu = okx["trx_usdt"]
        okx_trx_try = okx["trx_try"]

        # TL karşılıkları (CoinGecko kurları)
        trx_tl = trx * trx_try
        usdt_tl = usdt * usdt_try
        toplam_tl = trx_tl + usdt_tl

        trx_tl_okx = trx * okx_trx_try if okx_trx_try is not None else None
        usdt_tl_okx = usdt * okx_ut if okx_ut is not None else None

        okx_tl_parts = []
        if trx_tl_okx is not None:
            okx_tl_parts.append(f"TRX: {trx_tl_okx:,.2f} ₺")
        if usdt_tl_okx is not None:
            okx_tl_parts.append(f"USDT: {usdt_tl_okx:,.2f} ₺")
        okx_tl_text = ""
        if okx_tl_parts:
            okx_tl_text = "\n\n━━━━━━━━━━━━━━\n"
            okx_tl_text += "💰 TL Karşılıkları (OKX kuruyla)\n\n"
            okx_tl_text += "\n".join(okx_tl_parts)
            if trx_tl_okx is not None and usdt_tl_okx is not None:
                okx_tl_text += f"\n\n🏦 Toplam: {(trx_tl_okx + usdt_tl_okx):,.2f} ₺"

        text = f"📍 {TRX_ADDRESS}\n\n"
        text += f"💎 TRX: {trx:,.2f}\n"
        text += f"💵 USDT: {usdt:,.2f}\n"
        text += "\n━━━━━━━━━━━━━━\n"
        text += "📈 Anlık Kurlar (CoinGecko)\n\n"
        text += f"TRX/TRY: {trx_try:,.4f} ₺\n"
        text += f"USDT/TRY: {usdt_try:,.2f} ₺\n"
        text += "\n━━━━━━━━━━━━━━\n"
        text += "📈 OKX (spot)\n\n"
        if okx_ut is not None:
            text += f"USDT/TRY: {okx_ut:,.2f} ₺\n"
        else:
            text += "USDT/TRY: —\n"
        if okx_tu is not None:
            text += f"TRX/USDT: {okx_tu:,.5f}\n"
        else:
            text += "TRX/USDT: —\n"
        if okx_trx_try is not None:
            text += f"TRX/TRY (≈ TRX·USDT×USDT/TRY): {okx_trx_try:,.4f} ₺\n"
        else:
            text += "TRX/TRY (≈): —\n"
        text += "\n━━━━━━━━━━━━━━\n"
        text += "💰 TL Karşılıkları (CoinGecko)\n\n"
        text += f"TRX: {trx_tl:,.2f} ₺\n"
        text += f"USDT: {usdt_tl:,.2f} ₺\n"
        text += f"\n🏦 Toplam: {toplam_tl:,.2f} ₺"
        text += okx_tl_text

        await msg.edit_text(text)

    except Exception as e:
        print(e)
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
