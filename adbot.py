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

# --- PREMIUM EMOJI TAGS ---
E_STAR = '<tg-emoji emoji-id="5438496463044752972">⭐</tg-emoji>'
E_TICK = '<tg-emoji emoji-id="5206607081334906820">✔️</tg-emoji>'
E_WRONG = '<tg-emoji emoji-id="5210952531676504517">❌</tg-emoji>'
E_ALERT = '<tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji>'
E_DOLLAR = '<tg-emoji emoji-id="5409048419211682843">💲</tg-emoji>'
E_LIVE = '<tg-emoji emoji-id="5264919878082509254">🔴</tg-emoji>'
E_BUBBLE = '<tg-emoji emoji-id="5443038326535759644">💬</tg-emoji>'
E_TG = '<tg-emoji emoji-id="6028346797368283073">✈️</tg-emoji>'
E_MIC = '<tg-emoji emoji-id="5424818078833715060">📢</tg-emoji>'

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
        return await message.reply_text(f"{E_ALERT} <b>Syntax Error</b>\nUse: <code>/broadcast Your message here</code>", parse_mode=ParseMode.HTML)
    
    msg_to_send = message.text.split(None, 1)[1]
    b_text = f"{E_MIC} <b>ARCVIUM BROADCAST</b>\n\n{msg_to_send}"
    await message.reply_text(f"{E_LIVE} <b>Initializing Network Broadcast...</b>", parse_mode=ParseMode.HTML)
    
    success, fail = 0, 0
    for uid_str in user_data.keys():
        try:
            await app.send_message(int(uid_str), b_text, parse_mode=ParseMode.HTML)
            success += 1
        except: fail += 1
        await asyncio.sleep(0.1)
    
    await message.reply_text(f"{E_TICK} <b>Broadcast Complete!</b>\n\n{E_STAR} Delivered: {success}\n{E_WRONG} Failed: {fail}", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    if message.from_user.id != MASTER_ADMIN: return
    args = message.text.split()
    if len(args) == 1:
        active, expired = 0, 0
        text = f"<b>{E_STAR} ARCVIUM ADMINISTRATION</b>\n\n<b>Network Data:</b>\n"
        for uid, exp in subs_db.items():
            if uid == MASTER_ADMIN: continue
            if time.time() < exp:
                active += 1
                text += f"▪ {uid}: Active ({round((exp - time.time()) / 86400, 1)} days)\n"
            else:
                expired += 1
                text += f"▪ {uid}: Expired\n"
        text += f"\n<b>Overview:</b>\nActive Clients: {active}\nExpired Clients: {expired}\n\n<b>Operations:</b>\n▪ <code>/admin add [uid] [days]</code>\n▪ <code>/admin remove [uid]</code>\n▪ <code>/broadcast [message]</code>"
        return await message.reply_text(text, parse_mode=ParseMode.HTML)
    elif len(args) >= 3 and args[1].lower() == "add":
        try:
            target_uid, days = int(args[2]), int(args[3]) if len(args) > 3 else 30
            subs_db[target_uid] = time.time() + (days * 86400)
            save_db()
            await message.reply_text(f"{E_TICK} System updated. UID {target_uid} granted {days} days.", parse_mode=ParseMode.HTML)
        except: await message.reply_text(f"{E_WRONG} Invalid syntax.", parse_mode=ParseMode.HTML)
    elif len(args) >= 3 and args[1].lower() == "remove":
        try:
            target_uid = int(args[2])
            if target_uid in subs_db:
                subs_db[target_uid] = 0
                save_db()
                await message.reply_text(f"{E_TICK} System updated. UID {target_uid} access revoked.", parse_mode=ParseMode.HTML)
        except: pass

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    user_states[user_id] = None 
    if user_id not in subs_db or time.time() > subs_db[user_id]:
        text = f"<b>{E_WRONG} ACCESS RESTRICTED</b>\n\nActive subscription is required for network access.\nSelect a tier below to proceed."
        return await message.reply_text(text, reply_markup=get_paywall_menu(), parse_mode=ParseMode.HTML)
    
    text = f"<b>{E_STAR} ARCVIUM NETWORK</b>\n\n<i>Automate your marketing, scrape potential clients, and broadcast your campaigns safely across Telegram.</i>\n\n▪ Premium Delivery\n▪ Sequential Bridging\n▪ Spintax Engine\n▪ DM Scraper Module\n\n{E_TG} <b>Contact Support:</b> @Claxen"
    try: await message.reply_photo(photo=IMAGE_URL, caption=text, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)
    except: await message.reply_text(text, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)

@app.on_callback_query(filters.regex("^(buy_|pay_|cancel_pay)"))
async def payment_gateway(client, query):
    data, user_id = query.data, query.from_user.id
    if data == "cancel_pay": 
        text = f"<b>{E_WRONG} ACCESS RESTRICTED</b>\n\nSelect a tier below to proceed."
        return await query.edit_message_text(text, reply_markup=get_paywall_menu(), parse_mode=ParseMode.HTML)
    elif data.startswith("buy_"):
        days = data.split("_")[1]
        text = f"<b>{E_DOLLAR} Transaction Setup</b>\nSelect crypto network for <b>{PRICES[days]['name']}</b> access:"
        await query.edit_message_text(text, reply_markup=get_crypto_menu(days), parse_mode=ParseMode.HTML)
    elif data.startswith("pay_"):
        _, days, crypto = data.split("_")
        text = f"<b>{E_DOLLAR} Payment Protocol</b>\n\nTransfer exactly <b>{PRICES[days]['price']}</b> to the following {crypto} address:\n\n<code>{WALLETS[crypto]}</code>\n\n<i>Awaiting verification. Reply to this message with your transaction hash (TXN ID).</i> Type <code>cancel</code> to abort."
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
        await query.edit_message_text(f"{query.message.text}\n\n[ Status: APPROVED ]", parse_mode=ParseMode.HTML)
        try: await app.send_message(int(target_uid), f"<b>{E_TICK} Verification Successful</b>\nNetwork access granted. Send /start to initialize.", parse_mode=ParseMode.HTML)
        except: pass
    elif data.startswith("reject_"):
        _, target_uid = data.split("_")
        await query.edit_message_text(f"{query.message.text}\n\n[ Status: REJECTED ]", parse_mode=ParseMode.HTML)
        try: await app.send_message(int(target_uid), f"<b>{E_WRONG} Verification Failed</b>\nTransaction rejected. Contact support for assistance.", parse_mode=ParseMode.HTML)
        except: pass

@app.on_callback_query(filters.regex("^(menu_start|menu_dashboard|target_menu|tg_smart|tg_manual|switch_mode)$"))
async def navigate_menus(client, query):
    user_id = query.from_user.id
    if user_id not in subs_db or time.time() > subs_db[user_id]: return
    user_states[user_id] = None 
    ud, mem = get_udata(user_id)
    
    if query.data == "menu_start":
        text = f"<b>{E_STAR} ARCVIUM NETWORK</b>\n\n<i>Automate your marketing, scrape potential clients, and broadcast your campaigns safely across Telegram.</i>\n\n▪ Premium Delivery\n▪ Sequential Bridging\n▪ Spintax Engine\n▪ DM Scraper Module"
        try: await query.edit_message_caption(caption=text, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)
        except: await query.edit_message_text(text=text, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)
    
    elif query.data == "switch_mode":
        ud["mode"] = "DM" if ud.get("mode") == "GROUP" else "GROUP"
        ud["targets"] = []
        save_db()
        await navigate_menus(client, type("obj", (object,), {"data": "menu_dashboard", "from_user": query.from_user, "edit_message_caption": query.edit_message_caption, "edit_message_text": query.edit_message_text})())

    elif query.data == "menu_dashboard":
        status_icon = f"{E_LIVE} ACTIVE" if ud['status'] == "Running" else f"{E_WRONG} PAUSED"
        text = f"<b>{E_STAR} ARCVIUM DASHBOARD</b>\n\n<b>Overview:</b>\n▫️ Active Accounts: {len(ud['accounts'])}\n▫️ Safety Delay: {ud['interval']}s\n▫️ Target Audience: {len(ud['targets'])}\n▫️ Broadcast Status: {status_icon}\n\n<i>Select a module below to configure your campaign:</i>"
        try: await query.edit_message_caption(caption=text, reply_markup=get_dashboard_menu(user_id), parse_mode=ParseMode.HTML)
        except: await query.edit_message_text(text=text, reply_markup=get_dashboard_menu(user_id), parse_mode=ParseMode.HTML)

    elif query.data == "target_menu":
        if ud["mode"] == "GROUP":
            text = f"<b>{E_STAR} AUDIENCE SELECTION</b>\nSelect your targeting method:"
            try: await query.edit_message_caption(caption=text, reply_markup=get_target_menu(), parse_mode=ParseMode.HTML)
            except: await query.edit_message_text(text=text, reply_markup=get_target_menu(), parse_mode=ParseMode.HTML)
        else:
            user_states[user_id] = "waiting_for_dm_group"
            await query.message.reply_text(f"{E_STAR} <b>Module: DM Scraper</b>\nInput the <code>@username</code> of the target group to scrape members from. Type <code>cancel</code> to abort.", parse_mode=ParseMode.HTML)

    elif query.data == "tg_smart":
        if not mem["clients"]: return await query.answer("Please connect an account first.", show_alert=True)
        user_states[user_id] = "waiting_for_smart_keywords"
        await query.message.reply_text(f"{E_STAR} <b>Module: Smart Audience Selection</b>\nInput keywords separated by commas (e.g., <code>crypto, airdrop, gaming</code>). The system will scan and map all matching groups. Type <code>cancel</code> to abort.", parse_mode=ParseMode.HTML)

    elif query.data == "tg_manual":
        if not mem["clients"]: return await query.answer("Please connect an account first.", show_alert=True)
        await query.answer("Running deep scan...", show_alert=False)
        try:
            groups = []
            async for dialog in mem["clients"][0].get_dialogs(limit=1000):
                if "GROUP" in str(dialog.chat.type).upper(): groups.append({"id": dialog.chat.id, "title": dialog.chat.title[:25]})
            if not groups: return await query.message.reply_text(f"{E_WRONG} Scan failed: No external groups found.", parse_mode=ParseMode.HTML)
            groups = groups[:80]
            group_cache[user_id] = groups
            user_states[user_id] = "waiting_for_group_selection"
            text = f"<b>{E_STAR} TARGET AUDIENCE</b>\nIdentified {len(groups)} reachable groups:\n\n"
            for i, g in enumerate(groups): text += f"{i+1}. <code>{g['title']}</code>\n"
            text += "\nInput indices separated by commas (e.g., <code>1, 3</code>) or type <code>all</code>. Type <code>cancel</code> to abort."
            await query.message.reply_text(text, parse_mode=ParseMode.HTML)
        except Exception as e: await query.message.reply_text(f"{E_ALERT} System error: {e}", parse_mode=ParseMode.HTML)

@app.on_callback_query(filters.regex("^(add_acc|set_msg|set_interval|toggle_ar|edit_ar_msg|start_ads|stop_ads|del_acc|analytics)$"))
async def handle_actions(client, query):
    user_id = query.from_user.id
    if user_id not in subs_db or time.time() > subs_db[user_id]: return
    action, ud, mem = query.data, *get_udata(user_id)

    if action == "toggle_ar":
        ud["ar_on"] = not ud.get("ar_on", False)
        save_db()
        await query.answer(f"Auto-Responder: {'Enabled' if ud['ar_on'] else 'Disabled'}")
        query.data = "menu_dashboard"
        await navigate_menus(client, query)

    elif action == "edit_ar_msg":
        user_states[user_id] = "waiting_for_smart_ar"
        text = f"{E_BUBBLE} <b>Module: Smart Auto-Responder</b>\nConfigure using format:\n<code>keyword: response | keyword: response | default: response</code>\n\n<i>Example:</i> <code>price: It costs $50 | default: I am away right now</code>\n\n(Spintax like <code>{Hi|Hey}</code> is supported!). Type <code>cancel</code> to abort."
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)

    elif action == "add_acc":
        if len(ud["accounts"]) >= 5: return await query.answer("Capacity reached (5 max).", show_alert=True)
        user_states[user_id] = "waiting_for_phone"
        await query.message.reply_text(f"{E_STAR} <b>Module: Connect Account</b>\nInput mobile number (+1234567890). Type <code>cancel</code> to abort.", parse_mode=ParseMode.HTML)

    elif action == "set_msg":
        user_states[user_id] = "waiting_for_ad_msg"
        await query.message.reply_text(f"{E_STAR} <b>Module: Ad Campaign Setup</b>\nSubmit your advertisement (text/media). Spintax <code>{word1|word2}</code> is supported. Type <code>cancel</code> to abort.", parse_mode=ParseMode.HTML)

    elif action == "set_interval":
        user_states[user_id] = "waiting_for_interval"
        await query.message.reply_text(f"{E_STAR} <b>Module: Delay Configuration</b>\nInput safety delay interval in seconds. Type <code>cancel</code> to abort.", parse_mode=ParseMode.HTML)

    elif action == "del_acc":
        ud["accounts"].clear()
        save_db()
        for c in mem["clients"]: await c.stop()
        mem["clients"].clear()
        await query.answer("Accounts cleared successfully.", show_alert=True)
        query.data = "menu_dashboard"
        await navigate_menus(client, query)

    elif action == "analytics":
        text = f"<b>{E_STAR} CAMPAIGN ANALYTICS</b>\n\n▪ Mode: {ud['mode']}\n▪ Packets Delivered: {ud['analytics']['sent']}\n▪ Packets Dropped: {ud['analytics']['failed']}\n▪ Target Audience: {len(ud['targets'])}\n▪ Active Accounts: {len(mem['clients'])}"
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)
        await query.answer()

    elif action == "start_ads":
        if not mem["clients"] or not ud["targets"] or not ud["ad_msg"]:
            return await query.answer("Campaign setup is incomplete.", show_alert=True)
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
        await query.answer("Campaign Paused.", show_alert=True)
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
            return await message.reply_text(f"{E_WRONG} Operation aborted.", parse_mode=ParseMode.HTML)
        txn_clean = text.strip()
        if len(txn_clean) < 30 or " " in txn_clean: return await message.reply_text(f"{E_ALERT} Validation failed: Invalid hash.", parse_mode=ParseMode.HTML)
        _, _, days, crypto = state.split("_")
        admin_text = f"<b>INBOUND TRANSACTION</b>\nUID: <code>{user_id}</code>\nTier: {PRICES[days]['name']}\nNetwork: {crypto}\nHash: <code>{txn_clean}</code>"
        admin_kb = InlineKeyboardMarkup([[InlineKeyboardButton("Approve", callback_data=f"approve_{user_id}_{days}"), InlineKeyboardButton("Reject", callback_data=f"reject_{user_id}")]])
        await logger_app.send_message(ADMIN_GROUP, admin_text, reply_markup=admin_kb, parse_mode=ParseMode.HTML)
        user_states[user_id] = None
        return await message.reply_text(f"{E_TICK} Hash submitted. Awaiting network validation.", parse_mode=ParseMode.HTML)

    if user_id not in subs_db or time.time() > subs_db[user_id]: return
    if not state: return 
    ud, mem = get_udata(user_id)

    if text.lower() == "cancel":
        user_states[user_id] = None
        return await message.reply_text(f"{E_WRONG} Operation aborted.", parse_mode=ParseMode.HTML)

    if state == "waiting_for_ad_msg":
        media_type, media_id = "text", None
        if message.photo: media_type, media_id = "photo", message.photo.file_id
        elif message.video: media_type, media_id = "video", message.video.file_id
        elif message.animation: media_type, media_id = "animation", message.animation.file_id
        elif message.document: media_type, media_id = "document", message.document.file_id
        
        raw_html = message.text.html if message.text else (message.caption.html if message.caption else "")
        ud["ad_msg"] = {"type": media_type, "media_id": media_id, "text": raw_html}
        save_db()
        user_states[user_id] = None
        return await message.reply_text(f"<b>{E_TICK} Ad Campaign Saved.</b> Formatting and Spintax preserved.\nSend /start to return.", parse_mode=ParseMode.HTML)

    elif state == "waiting_for_smart_ar":
        try:
            parts = text.split("|")
            ar_dict = {}
            for p in parts:
                k, v = p.split(":", 1)
                ar_dict[k.strip().lower()] = v.strip()
            if "default" not in ar_dict: ar_dict["default"] = "I am currently away."
            ud["smart_ar"] = ar_dict
            save_db()
            user_states[user_id] = None
            await message.reply_text(f"<b>{E_TICK} Auto-Responder updated.</b>\nSend /start to return.", parse_mode=ParseMode.HTML)
        except: await message.reply_text(f"{E_WRONG} Invalid format. Use <code>key: value | key2: value2</code>", parse_mode=ParseMode.HTML)

    elif state == "waiting_for_smart_keywords":
        keywords = [k.strip().lower() for k in text.split(",")]
        await message.reply_text("Scanning network based on keywords...", parse_mode=ParseMode.HTML)
        try:
            matched = []
            async for dialog in mem["clients"][0].get_dialogs(limit=1000):
                if "GROUP" in str(dialog.chat.type).upper():
                    title = dialog.chat.title.lower()
                    if any(kw in title for kw in keywords): matched.append(dialog.chat.id)
            ud["targets"] = matched
            save_db()
            user_states[user_id] = None
            await message.reply_text(f"<b>{E_TICK} Smart Scan Complete</b>\nMapped {len(matched)} target groups to your audience.\nSend /start to return.", parse_mode=ParseMode.HTML)
        except Exception as e: await message.reply_text(f"{E_ALERT} Scan error: {e}", parse_mode=ParseMode.HTML)

    elif state == "waiting_for_dm_group":
        grp_username = text.strip()
        await message.reply_text(f"Scraping members from <code>{grp_username}</code>... This may take a minute.", parse_mode=ParseMode.HTML)
        try:
            members = []
            async for member in mem["clients"][0].get_chat_members(grp_username, limit=1000):
                if not member.user.is_bot and not member.user.is_deleted:
                    members.append(member.user.id)
            if not members: return await message.reply_text(f"{E_WRONG} Scrape failed: No visible members or invalid group.", parse_mode=ParseMode.HTML)
            ud["targets"] = members
            save_db()
            user_states[user_id] = None
            await message.reply_text(f"<b>{E_TICK} Scrape Complete</b>\nExtracted {len(members)} direct message targets.\nSend /start to return.", parse_mode=ParseMode.HTML)
        except Exception as e: await message.reply_text(f"{E_ALERT} Scrape error (Ensure connected account is in the group): {e}", parse_mode=ParseMode.HTML)

    elif state == "waiting_for_group_selection":
        groups = group_cache.get(user_id, [])
        if not groups: return await message.reply_text(f"{E_ALERT} Session timed out.", parse_mode=ParseMode.HTML)
        if text.lower() == "all": ud["targets"] = [g["id"] for g in groups]
        else:
            selected = []
            for p in text.split(","):
                if p.strip().isdigit():
                    idx = int(p.strip()) - 1
                    if 0 <= idx < len(groups): selected.append(groups[idx]["id"])
            ud["targets"] = selected
        save_db()
        user_states[user_id] = None
        group_cache.pop(user_id, None)
        return await message.reply_text(f"<b>{E_TICK} Audience Saved:</b> {len(ud['targets'])} targets linked.\nSend /start to return.", parse_mode=ParseMode.HTML)

    elif state == "waiting_for_phone":
        temp_client = Client(f"temp_{user_id}_{len(ud['accounts'])}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        try:
            await temp_client.connect()
            sent_code = await temp_client.send_code(text)
            temp_auth[user_id] = {"client": temp_client, "phone": text, "hash": sent_code.phone_code_hash}
            user_states[user_id] = "waiting_for_otp"
            await message.reply_text(f"{E_STAR} Auth requested. Input secure OTP format: <code>Mycodeis12345</code>", parse_mode=ParseMode.HTML)
        except Exception as e: await message.reply_text(f"{E_WRONG} Auth error: {e}", parse_mode=ParseMode.HTML)

    elif state == "waiting_for_otp":
        auth_data = temp_auth.get(user_id)
        otp_code = re.sub(r'\D', '', text)
        try:
            await auth_data["client"].sign_in(auth_data["phone"], auth_data["hash"], otp_code)
            session_string = await auth_data["client"].export_session_string()
            ud["accounts"].append(session_string)
            save_db()
            c = Client(f"u_{user_id}_{len(ud['accounts'])}", session_string=session_string)
            bind_auto_reply(c, user_id)
            await c.start()
            mem["clients"].append(c)
            await message.reply_text(f"<b>{E_TICK} Account Linked Successfully.</b>\nSend /start to return.", parse_mode=ParseMode.HTML)
            await auth_data["client"].disconnect()
            user_states[user_id] = None
        except SessionPasswordNeeded:
            user_states[user_id] = "waiting_for_password"
            await message.reply_text(f"{E_ALERT} 2FA Check: Provide cloud password.", parse_mode=ParseMode.HTML)
        except Exception as e: await message.reply_text(f"{E_WRONG} Binding failed: {e}", parse_mode=ParseMode.HTML)

    elif state == "waiting_for_password":
        auth_data = temp_auth.get(user_id)
        try:
            await auth_data["client"].check_password(text) 
            session_string = await auth_data["client"].export_session_string()
            ud["accounts"].append(session_string)
            save_db()
            c = Client(f"u_{user_id}_{len(ud['accounts'])}", session_string=session_string)
            bind_auto_reply(c, user_id)
            await c.start()
            mem["clients"].append(c)
            await message.reply_text(f"<b>{E_TICK} Account Linked Successfully.</b>\nSend /start to return.", parse_mode=ParseMode.HTML)
        except Exception as e: await message.reply_text(f"{E_WRONG} Auth error: {e}", parse_mode=ParseMode.HTML)
        finally:
            await auth_data["client"].disconnect()
            user_states[user_id] = None

    elif state == "waiting_for_interval":
        if text.isdigit() and 5 <= int(text) <= 300:
            ud["interval"] = int(text)
            save_db()
            user_states[user_id] = None
            await message.reply_text(f"<b>{E_TICK} Safety delay updated.</b>\nSend /start to return.", parse_mode=ParseMode.HTML)
        else: await message.reply_text(f"{E_WRONG} Out of bounds parameter.", parse_mode=ParseMode.HTML)

async def broadcast_loop(user_id):
    ud, mem = get_udata(user_id)
    while ud["status"] == "Running":
        if not mem["clients"] or not ud["targets"] or not ud["ad_msg"]:
            ud["status"] = "Paused"
            save_db()
            await app.send_message(user_id, f"{E_ALERT} <b>System Warning:</b> Campaign paused due to missing configuration (Account, Target, or Ad Message).", parse_mode=ParseMode.HTML)
            break
            
        ad = ud["ad_msg"]
        for group in ud["targets"]:
            if ud["status"] != "Running": break 
            sender_client = random.choice(mem["clients"])
            
            try:
                target_chat = int(group) if str(group).lstrip('-').isdigit() else group
                parsed_text = parse_spintax(ad["text"])

                if ad["type"] == "text":
                    await sender_client.send_message(chat_id=target_chat, text=parsed_text, parse_mode=ParseMode.HTML)
                elif ad["type"] == "photo":
                    await sender_client.send_photo(chat_id=target_chat, photo=ad["media_id"], caption=parsed_text, parse_mode=ParseMode.HTML)
                elif ad["type"] == "video":
                    await sender_client.send_video(chat_id=target_chat, video=ad["media_id"], caption=parsed_text, parse_mode=ParseMode.HTML)
                elif ad["type"] == "animation":
                    await sender_client.send_animation(chat_id=target_chat, animation=ad["media_id"], caption=parsed_text, parse_mode=ParseMode.HTML)
                elif ad["type"] == "document":
                    await sender_client.send_document(chat_id=target_chat, document=ad["media_id"], caption=parsed_text, parse_mode=ParseMode.HTML)

                ud["analytics"]["sent"] += 1
                try: await logger_app.send_message(user_id, f"{E_TICK} Delivered -> <code>{group}</code>", parse_mode=ParseMode.HTML)
                except: pass
                
            except FloodWait as fw:
                try: await logger_app.send_message(user_id, f"{E_ALERT} Rate Limit -> Sleeping for {fw.value}s", parse_mode=ParseMode.HTML)
                except: pass
                await asyncio.sleep(fw.value)
            except Exception as e:
                ud["analytics"]["failed"] += 1
                try: await logger_app.send_message(user_id, f"{E_WRONG} Failed -> <code>{group}</code>\nTrace: <code>{e}</code>", parse_mode=ParseMode.HTML)
                except: pass
                if "PEER_ID_INVALID" in str(e).upper() or "PEERIDINVALID" in str(e).upper():
                    try:
                        async for _ in sender_client.get_dialogs(limit=10): pass
                    except: pass
                    
            save_db()
            await asyncio.sleep(ud["interval"])

async def health_check(request):
    return web.Response(text="Arcvium Network is ONLINE and Running!")

async def start_webserver():
    web_app = web.Application()
    web_app.router.add_get('/', health_check)
    runner = web.AppRunner(web_app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web Server started on port {port}")

async def main():
    await app.start()
    await logger_app.start()
    await start_webserver()
    for uid_str, data in user_data.items():
        uid = int(uid_str)
        if uid in subs_db and time.time() < subs_db[uid]:
            ud, mem = get_udata(uid)
            for session in data["accounts"]:
                try:
                    c = Client(f"u_{uid}_{random.randint(100,999)}", session_string=session)
                    bind_auto_reply(c, uid)
                    await c.start()
                    try: 
                        async for _ in c.get_dialogs(limit=5): pass
                    except: pass
                    mem["clients"].append(c)
                except Exception as e: pass
            if ud["status"] == "Running":
                mem["task"] = asyncio.create_task(broadcast_loop(uid))
    import pyrogram
    await pyrogram.idle()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
