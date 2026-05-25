import asyncio
import random
import re
import time
import json
import os
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import SessionPasswordNeeded, FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = 36331118       
API_HASH = "ed6c2b1e8e348e00c0957016dce5b58d"   
BOT_TOKEN = "8953236354:AAHN60_igIOzuBEXSkyM2ClHAqXrLnG8J4M" 
LOGGER_TOKEN = "8958059338:AAFN0VAggRO79Gk_en5JKdTr0AGGteVex5s"

MASTER_ADMIN = 8759516193
ADMIN_GROUP = -1003904012585

WALLETS = {
    "SOL": "5S73mum48Q7DenKcBmon8rT99WAH5bqHdzDtATqn4C3k",
    "TON": "UQAH10oqKGYQZKgZtuOr9oP1Po81pmdZol4F7f7bV3-_XsT3",
    "ETH": "0x12D3B35A0819661c97703260b4CC30baBA8275EB",
    "LTC": "Li7vXacDTTUfeoNJw7GFYAL1yyefyFRVwS",
    "USDT": "0xee013480A9f513d2A2827cE3817CFe7F922A2321"
}

PRICES = {
    "1": {"name": "1 Day", "price": "$1"},
    "15": {"name": "15 Days", "price": "$10"}, 
    "30": {"name": "1 Month", "price": "$20"}
}

IMAGE_URL = "https://i.ibb.co/Zz4LZqVL/a1f921a33f73f05dc795b314624eae98.jpg" 
DB_FILE = "database.json"

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f: master_db = json.load(f)
else:
    master_db = {"subs_db": {str(MASTER_ADMIN): 2000000000000}, "user_data": {}}

subs_db = {int(k): v for k, v in master_db["subs_db"].items()}
user_data = master_db["user_data"]

def save_db():
    master_db["subs_db"] = {str(k): v for k, v in subs_db.items()}
    master_db["user_data"] = user_data
    with open(DB_FILE, "w") as f: json.dump(master_db, f, indent=4)

user_states = {} 
temp_auth = {}   
group_cache = {} 
active_clients_memory = {} 

app = Client("ad_bot_ui", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
logger_app = Client("logger_bot", api_id=API_ID, api_hash=API_HASH, bot_token=LOGGER_TOKEN)

def get_udata(uid):
    uid_str = str(uid)
    if uid_str not in user_data:
        user_data[uid_str] = {
            "accounts": [], "ad_msg": None, "targets": [], "interval": 300, 
            "status": "Paused", "analytics": {"sent": 0, "failed": 0},
            "ar_on": False, "smart_ar": {"default": "I am currently away."},
            "mode": "GROUP" 
        }
        save_db()
    if uid not in active_clients_memory: active_clients_memory[uid] = {"clients": [], "task": None}
    return user_data[uid_str], active_clients_memory[uid]

def parse_spintax(text):
    if not text: return ""
    while re.search(r'\{[^{}]*\}', text):
        text = re.sub(r'\{([^{}]*)\}', lambda m: random.choice(m.group(1).split('|')), text)
    return text

def bind_auto_reply(user_client, uid):
    @user_client.on_message(filters.private & ~filters.me)
    async def auto_responder(c, m):
        ud, _ = get_udata(uid)
        if ud.get("ar_on") and ud.get("status") == "Running":
            try:
                incoming_text = (m.text or "").lower()
                response = ud["smart_ar"].get("default", "")
                for kw, resp in ud["smart_ar"].items():
                    if kw != "default" and kw in incoming_text:
                        response = resp
                        break
                if response:
                    parsed_resp = parse_spintax(response)
                    await m.reply_text(parsed_resp)
            except: pass

def get_paywall_menu():
    btns = [[InlineKeyboardButton(f"Purchase {info['name']} — {info['price']}", callback_data=f"buy_{days}")] for days, info in PRICES.items()]
    btns.append([InlineKeyboardButton("Contact Support", url="https://t.me/Claxen")])
    return InlineKeyboardMarkup(btns)

def get_crypto_menu(days):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SOL", callback_data=f"pay_{days}_SOL"), InlineKeyboardButton("TON", callback_data=f"pay_{days}_TON")],
        [InlineKeyboardButton("ETH", callback_data=f"pay_{days}_ETH"), InlineKeyboardButton("LTC", callback_data=f"pay_{days}_LTC")],
        [InlineKeyboardButton("USDT (BEP-20)", callback_data=f"pay_{days}_USDT")],
        [InlineKeyboardButton("Return", callback_data="cancel_pay")]
    ])

def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Enter Dashboard", callback_data="menu_dashboard")],
        [InlineKeyboardButton("Contact Support", url="https://t.me/Claxen")]
    ])

def get_dashboard_menu(uid):
    ud, _ = get_udata(uid)
    msg_status = "Ready" if ud["ad_msg"] else "Pending"
    grp_status = f"{len(ud['targets'])} Groups" if ud["targets"] else "Pending"
    status_toggle = "⏸ PAUSE CAMPAIGN" if ud["status"] == "Running" else "🚀 LAUNCH CAMPAIGN"
    status_cb = "stop_ads" if ud["status"] == "Running" else "start_ads"
    ar_status = "ON" if ud.get("ar_on") else "OFF"
    mode_str = "Group Broadcast" if ud.get("mode") == "GROUP" else "Scrape & DM"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Mode: {mode_str} 🔄", callback_data="switch_mode")],
        [InlineKeyboardButton(f"🔗 Connect Accounts ({len(ud['accounts'])}/5)", callback_data="add_acc")],
        [InlineKeyboardButton(f"🎯 Audience: {grp_status}", callback_data="target_menu"), InlineKeyboardButton(f"📝 Ad Msg: {msg_status}", callback_data="set_msg")],
        [InlineKeyboardButton(f"⏱ Delay: {ud['interval']}s", callback_data="set_interval"), InlineKeyboardButton(f"🤖 Auto-Reply: {ar_status}", callback_data="toggle_ar")],
        [InlineKeyboardButton("⚙️ Setup Auto-Responder", callback_data="edit_ar_msg")],
        [InlineKeyboardButton(status_toggle, callback_data=status_cb)],
        [InlineKeyboardButton("🗑 Clear Accounts", callback_data="del_acc"), InlineKeyboardButton("📊 Analytics", callback_data="analytics")],
        [InlineKeyboardButton("Back", callback_data="menu_start")]
    ])

def get_target_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Smart Audience Select", callback_data="tg_smart")],
        [InlineKeyboardButton("📋 Manual Audience List", callback_data="tg_manual")],
        [InlineKeyboardButton("Back", callback_data="menu_dashboard")]
    ])

@app.on_message(filters.command("broadcast") & filters.private)
async def admin_broadcast(client, message):
    if message.from_user.id != MASTER_ADMIN: return
    if len(message.command) < 2:
        return await message.reply_text("📢 Syntax Error\nUse: /broadcast [message]", parse_mode=ParseMode.HTML)
    
    msg_to_send = message.text.split(None, 1)[1]
    b_text = f"📢 <b>ARCVIUM BROADCAST</b>\n\n{msg_to_send}"
    await message.reply_text("🔴 Initializing Network Broadcast...", parse_mode=ParseMode.HTML)
    
    success, fail = 0, 0
    for uid_str in user_data.keys():
        try:
            await app.send_message(int(uid_str), b_text, parse_mode=ParseMode.HTML)
            success += 1
        except: fail += 1
        await asyncio.sleep(0.1)
    
    await message.reply_text(f"✔️ <b>Broadcast Complete!</b>\n\n⭐ Delivered: {success}\n❌ Failed: {fail}", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    if message.from_user.id != MASTER_ADMIN: return
    args = message.text.split()
    if len(args) == 1:
        active, expired = 0, 0
        text = "💠 <b>ARCVIUM ADMINISTRATION</b>\n\n<b>Network Data:</b>\n"
        for uid, exp in subs_db.items():
            if uid == MASTER_ADMIN: continue
            if time.time() < exp:
                active += 1
                text += f"▪ {uid}: Active ({round((exp - time.time()) / 86400, 1)} days)\n"
            else:
                expired += 1
                text += f"▪ {uid}: Expired\n"
        text += f"\n<b>Overview:</b>\nActive Clients: {active}\nExpired Clients: {expired}\n\n<b>Operations:</b>\n▪ /admin add [uid] [days]\n▪ /admin remove [uid]\n▪ /broadcast [message]"
        return await message.reply_text(text, parse_mode=ParseMode.HTML)
    elif len(args) >= 3 and args[1].lower() == "add":
        try:
            target_uid, days = int(args[2]), int(args[3]) if len(args) > 3 else 30
            subs_db[target_uid] = time.time() + (days * 86400)
            save_db()
            await message.reply_text(f"✔️ System updated. UID {target_uid} granted {days} days.")
        except: await message.reply_text("❌ Invalid syntax.")
    elif len(args) >= 3 and args[1].lower() == "remove":
        try:
            target_uid = int(args[2])
            if target_uid in subs_db:
                subs_db[target_uid] = 0
                save_db()
                await message.reply_text(f"✔️ System updated. UID {target_uid} access revoked.")
        except: pass

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    user_states[user_id] = None 
    if user_id not in subs_db or time.time() > subs_db[user_id]:
        text = "❌ <b>ACCESS RESTRICTED</b>\n\nActive subscription required.\nSelect a tier below:"
        return await message.reply_text(text, reply_markup=get_paywall_menu(), parse_mode=ParseMode.HTML)
    
    text = "💠 <b>ARCVIUM NETWORK</b>\n\n<i>Automate your marketing, scrape clients, and broadcast safely.</i>\n\n▪ Premium Delivery\n▪ Spintax Engine\n▪ DM Scraper\n\n✈️ <b>Support:</b> @Claxen"
    try: await message.reply_photo(photo=IMAGE_URL, caption=text, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)
    except: await message.reply_text(text, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)

@app.on_callback_query(filters.regex("^(buy_|pay_|cancel_pay)"))
async def payment_gateway(client, query):
    data, user_id = query.data, query.from_user.id
    if data == "cancel_pay": 
        text = "❌ <b>ACCESS RESTRICTED</b>\n\nSelect a tier below:"
        return await query.edit_message_text(text, reply_markup=get_paywall_menu(), parse_mode=ParseMode.HTML)
    elif data.startswith("buy_"):
        days = data.split("_")[1]
        text = f"💲 <b>Transaction Setup</b>\nSelect crypto for <b>{PRICES[days]['name']}</b> access:"
        await query.edit_message_text(text, reply_markup=get_crypto_menu(days), parse_mode=ParseMode.HTML)
    elif data.startswith("pay_"):
        _, days, crypto = data.split("_")
        text = f"💲 <b>Payment Protocol</b>\n\nSend <b>{PRICES[days]['price']}</b> to <code>{WALLETS[crypto]}</code>\n\nReply with TXN ID. Type cancel to abort."
        user_states[user_id] = f"waiting_txn_{days}_{crypto}"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)

@logger_app.on_callback_query(filters.regex("^(approve_|reject_)"))
async def admin_approval(client, query):
    if query.from_user.id != MASTER_ADMIN: return await query.answer("Unauthorized.", show_alert=True)
    data = query.data
    if data.startswith("approve_"):
        _, target_uid, days = data.split("_")
        subs_db[int(target_uid)] = time.time() + (int(days) * 86400)
        save_db()
        await query.edit_message_text(f"{query.message.text}\n\n[ Status: APPROVED ]")
        try: await app.send_message(int(target_uid), "✔️ Verification Successful. Send /start")
        except: pass
    elif data.startswith("reject_"):
        _, target_uid = data.split("_")
        await query.edit_message_text(f"{query.message.text}\n\n[ Status: REJECTED ]")
        try: await app.send_message(int(target_uid), "❌ Verification Failed.")
        except: pass

@app.on_callback_query(filters.regex("^(menu_start|menu_dashboard|target_menu|tg_smart|tg_manual|switch_mode)$"))
async def navigate_menus(client, query):
    user_id = query.from_user.id
    if user_id not in subs_db or time.time() > subs_db[user_id]: return
    user_states[user_id] = None 
    ud, mem = get_udata(user_id)
    
    if query.data == "menu_start":
        text = "💠 <b>ARCVIUM NETWORK</b>\n\n<i>Automate marketing, scrape clients, and broadcast safely.</i>"
        try: await query.edit_message_caption(caption=text, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)
        except: await query.edit_message_text(text=text, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)
    
    elif query.data == "switch_mode":
        ud["mode"] = "DM" if ud.get("mode") == "GROUP" else "GROUP"
        ud["targets"] = []
        save_db()
        await navigate_menus(client, type("obj", (object,), {"data": "menu_dashboard", "from_user": query.from_user, "edit_message_caption": query.edit_message_caption, "edit_message_text": query.edit_message_text})())

    elif query.data == "menu_dashboard":
        status_icon = "🟢 ACTIVE" if ud['status'] == "Running" else "🔴 PAUSED"
        text = f"💠 <b>ARCVIUM DASHBOARD</b>\n\n▫️ Accounts: {len(ud['accounts'])}\n▫️ Delay: {ud['interval']}s\n▫️ Audience: {len(ud['targets'])}\n▫️ Status: {status_icon}"
        try: await query.edit_message_caption(caption=text, reply_markup=get_dashboard_menu(user_id), parse_mode=ParseMode.HTML)
        except: await query.edit_message_text(text=text, reply_markup=get_dashboard_menu(user_id), parse_mode=ParseMode.HTML)

    elif query.data == "target_menu":
        if ud["mode"] == "GROUP":
            text = "🎯 <b>AUDIENCE SELECTION</b>\nSelect method:"
            try: await query.edit_message_caption(caption=text, reply_markup=get_target_menu(), parse_mode=ParseMode.HTML)
            except: await query.edit_message_text(text=text, reply_markup=get_target_menu(), parse_mode=ParseMode.HTML)
        else:
            user_states[user_id] = "waiting_for_dm_group"
            await query.message.reply_text("💬 <b>Module: DM Scraper</b>\nInput @username of target group. Type cancel to abort.", parse_mode=ParseMode.HTML)

    elif query.data == "tg_smart":
        if not mem["clients"]: return await query.answer("Connect an account first.", show_alert=True)
        user_states[user_id] = "waiting_for_smart_keywords"
        await query.message.reply_text("🧠 <b>Smart Audience Select</b>\nKeywords (comma separated):", parse_mode=ParseMode.HTML)

    elif query.data == "tg_manual":
        if not mem["clients"]: return await query.answer("Connect an account first.", show_alert=True)
        await query.answer("Scanning...", show_alert=False)
        try:
            groups = []
            async for dialog in mem["clients"][0].get_dialogs(limit=1000):
                if "GROUP" in str(dialog.chat.type).upper(): groups.append({"id": dialog.chat.id, "title": dialog.chat.title[:25]})
            if not groups: return await query.message.reply_text("❌ No groups found.")
            groups = groups[:80]
            group_cache[user_id] = groups
            user_states[user_id] = "waiting_for_group_selection"
            text = f"🎯 <b>MANUAL AUDIENCE</b>\nSelect indices (1, 2) or 'all':\n\n"
            for i, g in enumerate(groups): text += f"{i+1}. <code>{g['title']}</code>\n"
            await query.message.reply_text(text, parse_mode=ParseMode.HTML)
        except Exception as e: await query.message.reply_text(f"⚠️ Error: {e}")

@app.on_callback_query(filters.regex("^(add_acc|set_msg|set_interval|toggle_ar|edit_ar_msg|start_ads|stop_ads|del_acc|analytics)$"))
async def handle_actions(client, query):
    user_id = query.from_user.id
    if user_id not in subs_db or time.time() > subs_db[user_id]: return
    action, ud, mem = query.data, *get_udata(user_id)

    if action == "toggle_ar":
        ud["ar_on"] = not ud.get("ar_on", False)
        save_db()
        await query.answer(f"Auto-Responder: {'ON' if ud['ar_on'] else 'OFF'}")
        query.data = "menu_dashboard"
        await navigate_menus(client, query)

    elif action == "edit_ar_msg":
        user_states[user_id] = "waiting_for_smart_ar"
        await query.message.reply_text("💬 <b>Smart Auto-Responder</b>\nFormat: <code>key: value | default: value</code>", parse_mode=ParseMode.HTML)

    elif action == "add_acc":
        if len(ud["accounts"]) >= 5: return await query.answer("Max 5 accounts.", show_alert=True)
        user_states[user_id] = "waiting_for_phone"
        await query.message.reply_text("🔗 <b>Connect Account</b>\nInput phone number (+123...).", parse_mode=ParseMode.HTML)

    elif action == "set_msg":
        user_states[user_id] = "waiting_for_ad_msg"
        await query.message.reply_text("📝 <b>Ad Campaign Setup</b>\nSubmit message/media.", parse_mode=ParseMode.HTML)

    elif action == "set_interval":
        user_states[user_id] = "waiting_for_interval"
        await query.message.reply_text("⏱ <b>Delay Configuration</b>\nSeconds (5-300):", parse_mode=ParseMode.HTML)

    elif action == "del_acc":
        ud["accounts"].clear()
        save_db()
        for c in mem["clients"]: await c.stop()
        mem["clients"].clear()
        await query.answer("Accounts cleared.", show_alert=True)
        query.data = "menu_dashboard"
        await navigate_menus(client, query)

    elif action == "analytics":
        text = f"📊 <b>ANALYTICS</b>\n\nDelivered: {ud['analytics']['sent']}\nFailed: {ud['analytics']['failed']}"
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)
        await query.answer()

    elif action == "start_ads":
        if not mem["clients"] or not ud["targets"] or not ud["ad_msg"]:
            return await query.answer("Incomplete setup.", show_alert=True)
        ud["status"] = "Running"
        save_db()
        await query.answer("Campaign Launched!", show_alert=True)
        query.data = "menu_dashboard"
        await navigate_menus(client, query)
        if mem["task"] and not mem["task"].done(): mem["task"].cancel()
        mem["task"] = asyncio.create_task(broadcast_loop(user_id))

    elif action == "stop_ads":
        ud["status"] = "Paused"
        save_db()
        await query.answer("Paused.", show_alert=True)
        query.data = "menu_dashboard"
        await navigate_menus(client, query)

@app.on_message(filters.private & ~filters.command(["start", "admin", "broadcast"]))
async def process_states(client, message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    text = message.text or message.caption or ""

    if state and state.startswith("waiting_txn_"):
        if text.lower() == "cancel":
            user_states[user_id] = None
            return await message.reply_text("Aborted.")
        txn = text.strip()
        if len(txn) < 30: return await message.reply_text("❌ Invalid hash.")
        _, _, days, crypto = state.split("_")
        admin_text = f"<b>NEW TXN</b>\nUID: <code>{user_id}</code>\nTier: {days} days\nHash: <code>{txn}</code>"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Approve", callback_data=f"approve_{user_id}_{days}"), InlineKeyboardButton("Reject", callback_data=f"reject_{user_id}")]])
        await logger_app.send_message(ADMIN_GROUP, admin_text, reply_markup=kb, parse_mode=ParseMode.HTML)
        user_states[user_id] = None
        return await message.reply_text("Hash submitted. Awaiting approval.")

    if user_id not in subs_db or time.time() > subs_db[user_id]: return
    if not state: return 
    ud, mem = get_udata(user_id)

    if text.lower() == "cancel":
        user_states[user_id] = None
        return await message.reply_text("Aborted.")

    if state == "waiting_for_ad_msg":
        media_type = "photo" if message.photo else "video" if message.video else "animation" if message.animation else "document" if message.document else "text"
        media_id = message.photo.file_id if message.photo else message.video.file_id if message.video else message.animation.file_id if message.animation else message.document.file_id if message.document else None
        ud["ad_msg"] = {"type": media_type, "media_id": media_id, "text": message.text.html if message.text else message.caption.html if message.caption else ""}
        save_db()
        user_states[user_id] = None
        return await message.reply_text("✔️ Ad saved.")

    elif state == "waiting_for_smart_ar":
        try:
            ar_dict = {p.split(":")[0].strip().lower(): p.split(":")[1].strip() for p in text.split("|")}
            if "default" not in ar_dict: ar_dict["default"] = "I am away."
            ud["smart_ar"] = ar_dict
            save_db()
            user_states[user_id] = None
            await message.reply_text("✔️ Auto-Responder updated.")
        except: await message.reply_text("❌ Error format.")

    elif state == "waiting_for_smart_keywords":
        keywords = [k.strip().lower() for k in text.split(",")]
        matched = []
        async for d in mem["clients"][0].get_dialogs(limit=1000):
            if "GROUP" in str(d.chat.type).upper() and any(kw in d.chat.title.lower() for kw in keywords): matched.append(d.chat.id)
        ud["targets"] = matched
        save_db()
        user_states[user_id] = None
        await message.reply_text(f"✔️ {len(matched)} groups added.")

    elif state == "waiting_for_dm_group":
        members = []
        async for m in mem["clients"][0].get_chat_members(text.strip(), limit=1000):
            if not m.user.is_bot and not m.user.is_deleted: members.append(m.user.id)
        ud["targets"] = members
        save_db()
        user_states[user_id] = None
        await message.reply_text(f"✔️ {len(members)} users scraped.")

    elif state == "waiting_for_group_selection":
        groups = group_cache.get(user_id, [])
        if text.lower() == "all": ud["targets"] = [g["id"] for g in groups]
        else:
            ud["targets"] = [groups[int(p.strip())-1]["id"] for p in text.split(",") if p.strip().isdigit()]
        save_db()
        user_states[user_id] = None
        await message.reply_text(f"✔️ {len(ud['targets'])} targets saved.")

    elif state == "waiting_for_phone":
        tc = Client(f"tmp_{user_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await tc.connect()
        sent = await tc.send_code(text)
        temp_auth[user_id] = {"client": tc, "phone": text, "hash": sent.phone_code_hash}
        user_states[user_id] = "waiting_for_otp"
        await message.reply_text("Input OTP (format: Mycodeis1234):")

    elif state == "waiting_for_otp":
        auth = temp_auth.get(user_id)
        await auth["client"].sign_in(auth["phone"], auth["hash"], re.sub(r'\D', '', text))
        session = await auth["client"].export_session_string()
        ud["accounts"].append(session)
        save_db()
        c = Client(f"u_{user_id}_{len(ud['accounts'])}", session_string=session)
        bind_auto_reply(c, user_id)
        await c.start()
        mem["clients"].append(c)
        await message.reply_text("✔️ Account linked.")
        await auth["client"].disconnect()
        user_states[user_id] = None

    elif state == "waiting_for_interval":
        ud["interval"] = int(text)
        save_db()
        user_states[user_id] = None
        await message.reply_text("✔️ Delay updated.")

async def broadcast_loop(user_id):
    ud, mem = get_udata(user_id)
    while ud["status"] == "Running":
        ad = ud["ad_msg"]
        for group in ud["targets"]:
            if ud["status"] != "Running": break 
            client = random.choice(mem["clients"])
            try:
                if ad["type"] == "text": await client.send_message(group, parse_spintax(ad["text"]), parse_mode=ParseMode.HTML)
                else: await getattr(client, f"send_{ad['type']}")(group, ad["media_id"], caption=parse_spintax(ad["text"]), parse_mode=ParseMode.HTML)
                ud["analytics"]["sent"] += 1
            except: ud["analytics"]["failed"] += 1
            save_db()
            await asyncio.sleep(ud["interval"])

async def start_webserver():
    app_web = web.Application()
    app_web.router.add_get('/', lambda r: web.Response(text="Running"))
    runner = web.AppRunner(app_web)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

async def main():
    await app.start()
    await logger_app.start()
    await start_webserver()
    for uid, data in user_data.items():
        if int(uid) in subs_db and time.time() < subs_db[int(uid)]:
            ud, mem = get_udata(int(uid))
            for s in data["accounts"]:
                c = Client(f"u_{uid}_{random.randint(100,999)}", session_string=s)
                await c.start()
                mem["clients"].append(c)
            if ud["status"] == "Running": mem["task"] = asyncio.create_task(broadcast_loop(int(uid)))
    await pyrogram.idle()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
