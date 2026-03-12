# ─────────────────────────────────────────────────────
#  EDIT THESE 3 LINES ONLY
# ─────────────────────────────────────────────────────
API_ID   = 33249253
API_HASH = "dcd4638483c3da00a39393fd754872ba"
ADMIN_ID = 8494250384
# ─────────────────────────────────────────────────────

import asyncio, json, os, re, sys, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import yt_dlp
from telethon import Button, TelegramClient, events, functions, types
from telethon.errors import FloodWaitError, PhoneCodeInvalidError, SessionPasswordNeededError
from telethon.tl.functions.channels import EditAdminRequest, EditBannedRequest
from telethon.tl.types import ChannelParticipantsAdmins, ChatAdminRights, ChatBannedRights

try:
    from pytgcalls import PyTgCalls
    from pytgcalls.types import MediaStream
    VC_OK = True
except ImportError:
    VC_OK = False; PyTgCalls = None; MediaStream = None

DATA = Path("data"); DATA.mkdir(exist_ok=True)
TMP  = Path("tmp");  TMP.mkdir(exist_ok=True)

def _load(f, d):
    p = DATA / f
    try: return json.loads(p.read_text()) if p.exists() else d
    except: return d
def _save(f, d): (DATA / f).write_text(json.dumps(d, indent=2))

warns    = _load("warns.json",    {})
welcome  = _load("welcome.json",  {})
antilink = _load("antilink.json", {})
antiwords= _load("antiwords.json",{})
def save():
    _save("warns.json",warns); _save("welcome.json",welcome)
    _save("antilink.json",antilink); _save("antiwords.json",antiwords)

vc_playing = {}; vc_queue = {}; vc_paused = set(); vc_msg = {}

client = TelegramClient("infinity", API_ID, API_HASH)
calls  = PyTgCalls(client) if VC_OK else None
ME     = None
PREFIX = "."

def fmt_time(sec):
    if not sec: return "N/A"
    m,s = divmod(int(sec),60); h,m = divmod(m,60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

async def is_admin(chat_id, user_id):
    if user_id == ADMIN_ID: return True
    try: p = await client.get_permissions(chat_id,user_id); return p.is_admin or p.is_creator
    except: return False

async def get_reply_user(event):
    if event.is_reply:
        r = await event.get_reply_message()
        if r and r.sender_id: return await client.get_entity(r.sender_id)
    return None

def _yt_search(q, n=5):
    opts = {"quiet":True,"no_warnings":True,"extract_flat":True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{q}", download=False)
        return (info.get("entries") or [])[:n] if info else []

def _yt_mp3(url, path):
    opts = {"format":"bestaudio/best","quiet":True,"no_warnings":True,
        "outtmpl":path.replace(".mp3","")+ ".%(ext)s",
        "postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"128"}]}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([url])
        return True
    except: return False

def _yt_raw(url, path):
    opts = {"format":"bestaudio/best","quiet":True,"no_warnings":True,"outtmpl":path}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([url])
        return True
    except: return False

def _thumb(vid_id, path):
    try: urllib.request.urlretrieve(f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg", path); return True
    except: return False

def player_text(track, paused=False):
    status = "⏸ Paused" if paused else "🔊 In Voice Chat"
    q = vc_queue.get(track.get("_cid"),[])
    return (f"🎵 **Now Playing**\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **{track['title']}**\n⏱ `{fmt_time(track.get('duration'))}`\n"
            f"🎙 {status}\n━━━━━━━━━━━━━━━━━━━━\n"
            f"{'📋 '+str(len(q))+' in queue' if q else '📋 Queue empty'}")

def player_btns(paused=False):
    pp = Button.inline("▶️ Resume",b"vc_resume") if paused else Button.inline("⏸ Pause",b"vc_pause")
    return [[pp, Button.inline("⏭ Skip",b"vc_skip"), Button.inline("⏹ Stop",b"vc_stop")],
            [Button.inline("📋 Queue",b"vc_queue"), Button.inline("🔄 Refresh",b"vc_refresh")]]

async def send_player(chat_id, track):
    thumb = TMP / f"thumb_{chat_id}.jpg"
    if _thumb(track.get("vid_id",""), str(thumb)):
        try:
            msg = await client.send_file(chat_id, str(thumb), caption=player_text(track),
                                         buttons=player_btns(), parse_mode="markdown")
            thumb.unlink(missing_ok=True); return msg
        except: thumb.unlink(missing_ok=True)
    return await client.send_message(chat_id, player_text(track), buttons=player_btns(), parse_mode="markdown")

async def update_player(chat_id, paused=False):
    track = vc_playing.get(chat_id); mid = vc_msg.get(chat_id)
    if not track or not mid: return
    try: await client.edit_message(chat_id, mid, player_text(track,paused), buttons=player_btns(paused), parse_mode="markdown")
    except: pass

async def vc_start(chat_id, track):
    if not VC_OK or not calls: return False
    raw = str(TMP / f"vc_{chat_id}.raw")
    ok  = await asyncio.get_event_loop().run_in_executor(None, _yt_raw, track["url"], raw)
    if not ok: return False
    track["_cid"] = chat_id; vc_playing[chat_id] = track
    try: await calls.play(chat_id, MediaStream(raw))
    except:
        try: await calls.change_stream(chat_id, MediaStream(raw))
        except: return False
    return True

async def vc_next(chat_id):
    TMP.joinpath(f"vc_{chat_id}.raw").unlink(missing_ok=True)
    q = vc_queue.get(chat_id, [])
    if not q:
        vc_playing.pop(chat_id,None); vc_paused.discard(chat_id)
        try:
            if calls: await calls.leave_group_call(chat_id)
        except: pass
        mid = vc_msg.pop(chat_id,None)
        if mid:
            try: await client.edit_message(chat_id, mid, "⏹ **Queue finished.** Left VC.")
            except: pass
        return
    track = q.pop(0); vc_queue[chat_id] = q
    ok = await vc_start(chat_id, track)
    if not ok: await vc_next(chat_id); return
    mid = vc_msg.pop(chat_id, None)
    if mid:
        try: await client.delete_messages(chat_id, mid)
        except: pass
    msg = await send_player(chat_id, track); vc_msg[chat_id] = msg.id

if VC_OK and calls:
    @calls.on_stream_end()
    async def _on_end(chat_id, update):
        await vc_next(chat_id)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.yts (.+)"))
async def cmd_yts(event):
    q = event.pattern_match.group(1).strip()
    await event.edit(f"🔍 Searching `{q}`...")
    res = await asyncio.get_event_loop().run_in_executor(None, _yt_search, q, 5)
    if not res: await event.edit("❌ No results."); return
    lines = [f"{i}️⃣ [{(r.get('title') or '?')[:55]}](https://youtu.be/{r.get('id','')}) — `{fmt_time(r.get('duration'))}`"
             for i,r in enumerate(res,1)]
    await event.edit(f"🎵 **YouTube: `{q}`**\n\n" + "\n".join(lines) +
                     f"\n\n▶️ `.play {q}`  |  📥 `.song {q}`",
                     parse_mode="markdown", link_preview=False)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.song (.+)"))
async def cmd_song(event):
    q = event.pattern_match.group(1).strip()
    await event.edit(f"🔍 Searching `{q}`...")
    res = await asyncio.get_event_loop().run_in_executor(None, _yt_search, q, 1)
    if not res: await event.edit("❌ Not found."); return
    r = res[0]; title = r.get("title","Unknown")
    url  = r.get("url") or f"https://youtube.com/watch?v={r.get('id','')}"
    safe = re.sub(r'[\\/:*?"<>|]',"",title)[:50]
    out  = str(TMP / f"{safe}_{event.chat_id}.mp3")
    await event.edit(f"⏬ Downloading **{title}**...")
    ok = await asyncio.get_event_loop().run_in_executor(None, _yt_mp3, url, out)
    final = Path(out)
    if not final.exists():
        matches = list(TMP.glob(f"{safe}_{event.chat_id}.*"))
        final = matches[0] if matches else final
    if not ok or not final.exists(): await event.edit("❌ Download failed. Is `ffmpeg` installed?"); return
    await event.edit(f"📤 Uploading **{title}**...")
    await client.send_file(event.chat_id, str(final),
        attributes=[types.DocumentAttributeAudio(duration=r.get("duration") or 0, title=title, performer="Infinity")],
        caption=f"🎵 **{title}**\n⏱ `{fmt_time(r.get('duration'))}`", parse_mode="markdown")
    final.unlink(missing_ok=True); await event.delete()

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.play (.+)"))
async def cmd_play(event):
    if not VC_OK or not calls:
        await event.edit("❌ **pytgcalls not installed.**\nRun: `pip install py-tgcalls`\nUse `.song` for MP3."); return
    if not event.is_group: await event.edit("❌ Groups only."); return
    q = event.pattern_match.group(1).strip(); chat_id = event.chat_id
    await event.edit(f"🔍 Searching `{q}`...")
    res = await asyncio.get_event_loop().run_in_executor(None, _yt_search, q, 1)
    if not res: await event.edit("❌ Not found."); return
    r = res[0]
    track = {"title":r.get("title","Unknown"), "url":r.get("url") or f"https://youtube.com/watch?v={r.get('id','')}",
             "duration":r.get("duration"), "vid_id":r.get("id",""), "_cid":chat_id}
    if vc_playing.get(chat_id):
        vc_queue.setdefault(chat_id,[]).append(track); pos = len(vc_queue[chat_id])
        await event.edit(f"📋 **Queued #{pos}**\n🎵 **{track['title']}**\n⏱ `{fmt_time(track.get('duration'))}`",
                         parse_mode="markdown"); return
    await event.edit(f"⏬ Downloading **{track['title']}**...")
    vc_queue.setdefault(chat_id, [])
    ok = await vc_start(chat_id, track)
    if not ok: vc_playing.pop(chat_id,None); await event.edit("❌ Failed. Start a Voice Chat first."); return
    await event.delete()
    msg = await send_player(chat_id, track); vc_msg[chat_id] = msg.id

@client.on(events.CallbackQuery(data=b"vc_pause"))
async def cb_pause(event):
    cid = event.chat_id
    if not vc_playing.get(cid): await event.answer("❌ Nothing playing.",alert=True); return
    try: await calls.pause_stream(cid); vc_paused.add(cid); await update_player(cid,True); await event.answer("⏸ Paused")
    except Exception as e: await event.answer(str(e),alert=True)

@client.on(events.CallbackQuery(data=b"vc_resume"))
async def cb_resume(event):
    cid = event.chat_id
    if not vc_playing.get(cid): await event.answer("❌ Nothing playing.",alert=True); return
    try: await calls.resume_stream(cid); vc_paused.discard(cid); await update_player(cid,False); await event.answer("▶️ Resumed")
    except Exception as e: await event.answer(str(e),alert=True)

@client.on(events.CallbackQuery(data=b"vc_skip"))
async def cb_skip(event):
    cid = event.chat_id
    if not vc_playing.get(cid): await event.answer("❌ Nothing playing.",alert=True); return
    await event.answer("⏭ Skipping..."); await vc_next(cid)

@client.on(events.CallbackQuery(data=b"vc_stop"))
async def cb_stop(event):
    cid = event.chat_id
    vc_queue.pop(cid,None); vc_playing.pop(cid,None); vc_paused.discard(cid); vc_msg.pop(cid,None)
    TMP.joinpath(f"vc_{cid}.raw").unlink(missing_ok=True)
    try:
        if calls: await calls.leave_group_call(cid)
    except: pass
    await event.edit("⏹ **Stopped.** Left Voice Chat."); await event.answer("⏹ Stopped")

@client.on(events.CallbackQuery(data=b"vc_queue"))
async def cb_queue(event):
    cid = event.chat_id; cur = vc_playing.get(cid); q = vc_queue.get(cid,[])
    if not cur and not q: await event.answer("📋 Empty.",alert=True); return
    lines = []
    if cur: lines.append(f"▶️ {cur['title']} [{fmt_time(cur.get('duration'))}]")
    for i,t in enumerate(q,1): lines.append(f"{i}. {t['title']} [{fmt_time(t.get('duration'))}]")
    await event.answer("\n".join(lines)[:190], alert=True)

@client.on(events.CallbackQuery(data=b"vc_refresh"))
async def cb_refresh(event):
    cid = event.chat_id
    if not vc_playing.get(cid): await event.answer("❌ Nothing playing.",alert=True); return
    await update_player(cid, cid in vc_paused); await event.answer("🔄 Refreshed")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.kick$"))
async def cmd_kick(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    user = await get_reply_user(event)
    if not user: await event.edit("⚠️ Reply to a user."); return
    if await is_admin(event.chat_id,user.id): await event.edit("❌ Can't kick an admin."); return
    try: await client.kick_participant(event.chat_id,user.id); await event.edit(f"👢 **Kicked:** [{user.first_name}](tg://user?id={user.id})", parse_mode="markdown")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ban(.*)"))
async def cmd_ban(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    user = await get_reply_user(event)
    if not user: await event.edit("⚠️ Reply to a user."); return
    if await is_admin(event.chat_id,user.id): await event.edit("❌ Can't ban an admin."); return
    reason = (event.pattern_match.group(1) or "").strip() or "No reason"
    try:
        await client(EditBannedRequest(event.chat_id,user.id,ChatBannedRights(until_date=None,view_messages=True)))
        await event.edit(f"🔨 **Banned:** [{user.first_name}](tg://user?id={user.id})\n📋 {reason}", parse_mode="markdown")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unban$"))
async def cmd_unban(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    user = await get_reply_user(event)
    if not user: await event.edit("⚠️ Reply to a user."); return
    try:
        await client(EditBannedRequest(event.chat_id,user.id,ChatBannedRights(until_date=None,view_messages=False)))
        await event.edit(f"✅ **Unbanned:** [{user.first_name}](tg://user?id={user.id})", parse_mode="markdown")
    except Exception as e: await event.edit(f"❌ `{e}`")

def _parse_time(s):
    m = re.fullmatch(r"(\d+)([smhd]?)", s.strip().lower())
    if not m: return None
    v,u = int(m.group(1)),m.group(2)
    return v * {"s":1,"m":60,"h":3600,"d":86400}.get(u,60)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.mute(.*)"))
async def cmd_mute(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    user = await get_reply_user(event)
    if not user: await event.edit("⚠️ Reply to a user."); return
    if await is_admin(event.chat_id,user.id): await event.edit("❌ Can't mute an admin."); return
    raw = (event.pattern_match.group(1) or "").strip() or "10m"; secs = _parse_time(raw) or 600
    until = datetime.now() + timedelta(seconds=secs)
    try:
        await client(EditBannedRequest(event.chat_id,user.id,ChatBannedRights(until_date=until,send_messages=True)))
        await event.edit(f"🔇 **Muted:** [{user.first_name}](tg://user?id={user.id}) for `{raw}`", parse_mode="markdown")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unmute$"))
async def cmd_unmute(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    user = await get_reply_user(event)
    if not user: await event.edit("⚠️ Reply to a user."); return
    try:
        await client(EditBannedRequest(event.chat_id,user.id,ChatBannedRights(until_date=None,send_messages=False)))
        await event.edit(f"🔔 **Unmuted:** [{user.first_name}](tg://user?id={user.id})", parse_mode="markdown")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.warn(.*)"))
async def cmd_warn(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    user = await get_reply_user(event)
    if not user: await event.edit("⚠️ Reply to a user."); return
    if await is_admin(event.chat_id,user.id): await event.edit("❌ Can't warn an admin."); return
    reason = (event.pattern_match.group(1) or "").strip() or "No reason"
    cid,uid = str(event.chat_id),str(user.id)
    warns.setdefault(cid,{}); warns[cid][uid] = warns[cid].get(uid,0)+1; count = warns[cid][uid]; save()
    if count >= 3:
        try:
            await client(EditBannedRequest(event.chat_id,user.id,ChatBannedRights(until_date=None,view_messages=True)))
            warns[cid][uid]=0; save()
            await event.edit(f"🔨 **Auto-banned** [{user.first_name}](tg://user?id={user.id}) — 3/3\n📋 {reason}", parse_mode="markdown")
        except Exception as e: await event.edit(f"❌ `{e}`")
    else: await event.edit(f"⚠️ **Warned** [{user.first_name}](tg://user?id={user.id}) `{count}/3`\n📋 {reason}", parse_mode="markdown")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unwarn$"))
async def cmd_unwarn(event):
    user = await get_reply_user(event)
    if not user: await event.edit("⚠️ Reply to a user."); return
    cid,uid = str(event.chat_id),str(user.id)
    if warns.get(cid,{}).get(uid,0) > 0:
        warns[cid][uid]-=1; save(); await event.edit(f"✅ Warning removed — [{user.first_name}](tg://user?id={user.id}) `{warns[cid][uid]}/3`", parse_mode="markdown")
    else: await event.edit("ℹ️ No warnings.")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.warns$"))
async def cmd_warns(event):
    user = await get_reply_user(event)
    if not user: await event.edit("⚠️ Reply to a user."); return
    count = warns.get(str(event.chat_id),{}).get(str(user.id),0)
    await event.edit(f"📊 [{user.first_name}](tg://user?id={user.id}) — `{count}/3`", parse_mode="markdown")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.promote$"))
async def cmd_promote(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    user = await get_reply_user(event)
    if not user: await event.edit("⚠️ Reply to a user."); return
    try:
        rights = ChatAdminRights(change_info=True,post_messages=True,edit_messages=True,
            delete_messages=True,ban_users=True,invite_users=True,pin_messages=True,manage_call=True)
        await client(EditAdminRequest(event.chat_id,user.id,rights,rank="Admin"))
        await event.edit(f"👑 **Promoted:** [{user.first_name}](tg://user?id={user.id})", parse_mode="markdown")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.demote$"))
async def cmd_demote(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    user = await get_reply_user(event)
    if not user: await event.edit("⚠️ Reply to a user."); return
    try:
        await client(EditAdminRequest(event.chat_id,user.id,ChatAdminRights(),rank=""))
        await event.edit(f"📉 **Demoted:** [{user.first_name}](tg://user?id={user.id})", parse_mode="markdown")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.pin$"))
async def cmd_pin(event):
    if not event.is_reply: await event.edit("⚠️ Reply to a message."); return
    r = await event.get_reply_message()
    try: await client.pin_message(event.chat_id,r.id); await event.edit("📌 **Pinned!**")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unpin$"))
async def cmd_unpin(event):
    try: await client.unpin_message(event.chat_id); await event.edit("📌 **Unpinned!**")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.del$"))
async def cmd_del(event):
    if not event.is_reply: await event.edit("⚠️ Reply to a message."); return
    r = await event.get_reply_message(); await r.delete(); await event.delete()

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.purge$"))
async def cmd_purge(event):
    if not event.is_reply: await event.edit("⚠️ Reply to start message."); return
    r = await event.get_reply_message(); ids = list(range(r.id, event.id+1)); deleted = 0
    for chunk in [ids[i:i+100] for i in range(0,len(ids),100)]:
        try: await client.delete_messages(event.chat_id,chunk); deleted+=len(chunk)
        except: pass
    m = await client.send_message(event.chat_id, f"🗑 Purged **{deleted}** messages.")
    await asyncio.sleep(3); await m.delete()

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.lock$"))
async def cmd_lock(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    try:
        await client(functions.messages.EditChatDefaultBannedRightsRequest(event.chat_id, ChatBannedRights(until_date=None,send_messages=True)))
        await event.edit("🔒 **Group locked.**")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unlock$"))
async def cmd_unlock(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    try:
        await client(functions.messages.EditChatDefaultBannedRightsRequest(event.chat_id, ChatBannedRights(until_date=None,send_messages=False)))
        await event.edit("🔓 **Group unlocked.**")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.gcinfo$"))
async def cmd_gcinfo(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    chat = await event.get_chat(); admins = []
    async for p in client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins()):
        tag = "🌟" if getattr(p.participant,"is_creator",False) else "👑"
        admins.append(f"{tag} {p.first_name}")
    parts = await client.get_participants(event.chat_id, limit=0)
    await event.edit(f"🏘️ **Group Info**\n━━━━━━━━━━━━━━━━━━\n"
                     f"📛 **Name:** {chat.title}\n🆔 **ID:** `{event.chat_id}`\n"
                     f"👥 **Members:** {parts.total}\n📝 **Desc:** {getattr(chat,'about','') or '(none)'}\n"
                     f"━━━━━━━━━━━━━━━━━━\n👑 **Admins:**\n" + "\n".join(admins), parse_mode="markdown")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.adminlist$"))
async def cmd_adminlist(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    lines = []
    async for p in client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins()):
        tag = "🌟" if getattr(p.participant,"is_creator",False) else "👑"
        lines.append(f"{tag} [{p.first_name}](tg://user?id={p.id})")
    await event.edit("👑 **Admins:**\n\n" + "\n".join(lines), parse_mode="markdown", link_preview=False)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.tagall(.*)"))
async def cmd_tagall(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    text = (event.pattern_match.group(1) or "").strip() or "Attention!"; users = []
    async for p in client.iter_participants(event.chat_id):
        if not p.bot: users.append(f"[{p.first_name}](tg://user?id={p.id})")
    for i in range(0,len(users),20):
        await client.send_message(event.chat_id, f"📢 **{text}**\n\n"+" ".join(users[i:i+20]),
                                  parse_mode="markdown", link_preview=False)
        await asyncio.sleep(1.5)
    await event.delete()

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.invite$"))
async def cmd_invite(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    try:
        r = await client(functions.messages.ExportChatInviteRequest(peer=event.chat_id))
        await event.edit(f"🔗 **Invite Link:**\n{r.link}")
    except Exception as e: await event.edit(f"❌ `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.id$"))
async def cmd_id(event):
    if event.is_reply:
        r = await event.get_reply_message(); u = await client.get_entity(r.sender_id)
        await event.edit(f"👤 **{u.first_name}**\n🆔 `{u.id}`")
    else: await event.edit(f"💬 Chat: `{event.chat_id}`\n👤 You: `{ME.id}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.welcome (.+)"))
async def cmd_welcome(event):
    arg = event.pattern_match.group(1).strip().lower(); cid = str(event.chat_id)
    if arg=="on": welcome.setdefault(cid,{})["on"]=True; save(); await event.edit("✅ **Welcome ON**")
    elif arg=="off": welcome.setdefault(cid,{})["on"]=False; save(); await event.edit("❌ **Welcome OFF**")
    else: await event.edit("⚠️ `.welcome on` or `.welcome off`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.setwelcome (.+)"))
async def cmd_setwelcome(event):
    text=event.pattern_match.group(1).strip(); cid=str(event.chat_id)
    welcome.setdefault(cid,{})["msg"]=text; save()
    await event.edit(f"✅ **Welcome set:**\n{text}", parse_mode="markdown")

@client.on(events.ChatAction())
async def on_join(event):
    if not event.user_joined and not event.user_added: return
    cid=str(event.chat_id); cfg=welcome.get(cid,{})
    if not cfg.get("on"): return
    user=await event.get_user()
    if not user: return
    chat=await event.get_chat(); parts=await client.get_participants(event.chat_id,limit=0)
    tmpl=cfg.get("msg","✦ Welcome {name} to **{chat}**! You're member #{count} 🎉")
    text=tmpl.replace("{name}",user.first_name or "User").replace("{chat}",getattr(chat,"title","")).replace("{count}",str(parts.total))
    try: await client.send_message(event.chat_id,text,parse_mode="markdown")
    except: pass

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.antilink (.+)"))
async def cmd_antilink(event):
    arg=event.pattern_match.group(1).strip().lower(); cid=str(event.chat_id)
    if arg=="on": antilink[cid]=True; save(); await event.edit("🔗 **Anti-link ON**")
    elif arg=="off": antilink.pop(cid,None); save(); await event.edit("🔗 **Anti-link OFF**")
    else: await event.edit("⚠️ `.antilink on` or `.antilink off`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.addword (.+)"))
async def cmd_addword(event):
    word=event.pattern_match.group(1).strip().lower(); cid=str(event.chat_id)
    antiwords.setdefault(cid,[])
    if word in antiwords[cid]: await event.edit(f"⚠️ `{word}` already banned."); return
    antiwords[cid].append(word); save(); await event.edit(f"✅ Banned: `{word}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.delword (.+)"))
async def cmd_delword(event):
    word=event.pattern_match.group(1).strip().lower(); cid=str(event.chat_id)
    if word in antiwords.get(cid,[]):
        antiwords[cid].remove(word); save(); await event.edit(f"✅ Removed: `{word}`")
    else: await event.edit(f"⚠️ `{word}` not found.")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.wordlist$"))
async def cmd_wordlist(event):
    words=antiwords.get(str(event.chat_id),[])
    if not words: await event.edit("📋 No banned words."); return
    await event.edit("🚫 **Banned words:**\n"+"\n".join(f"• `{w}`" for w in words), parse_mode="markdown")

@client.on(events.NewMessage(incoming=True))
async def auto_filter(event):
    if not event.is_group or not event.text: return
    sender=await event.get_sender()
    if not sender or await is_admin(event.chat_id,sender.id): return
    cid=str(event.chat_id)
    if antilink.get(cid) and re.search(r"(https?://|t\.me/|telegram\.me/)",event.text,re.I):
        try:
            await event.delete()
            m=await client.send_message(event.chat_id,f"🔗 Link removed — [{sender.first_name}](tg://user?id={sender.id})",parse_mode="markdown")
            await asyncio.sleep(4); await m.delete()
        except: pass
        return
    for word in antiwords.get(cid,[]):
        if word in event.text.lower():
            try:
                await event.delete()
                m=await client.send_message(event.chat_id,"🚫 Banned word — message deleted.")
                await asyncio.sleep(4); await m.delete()
            except: pass
            return

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ping$"))
async def cmd_ping(event):
    t=time.time(); await event.edit("🏓 Pinging...")
    await event.edit(f"🏓 **Pong!** `{round((time.time()-t)*1000)}ms`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.menu$"))
async def cmd_menu(event):
    vc = "✅ Ready" if VC_OK else "❌ Run: pip install py-tgcalls"
    await event.edit(
        f"♾️ **INFINITY GC BOT**\n\n"
        f"🎵 **MUSIC** — VC: {vc}\n"
        f"`.yts` `.song` `.play` `.skip` `.stop` `.pause` `.resume` `.queue`\n\n"
        f"👥 **GC MANAGEMENT**\n"
        f"`.kick` `.ban` `.unban` `.mute` `.unmute`\n"
        f"`.warn` `.unwarn` `.warns` `.promote` `.demote`\n"
        f"`.pin` `.unpin` `.del` `.purge` `.lock` `.unlock`\n\n"
        f"📋 **INFO**\n"
        f"`.gcinfo` `.adminlist` `.tagall` `.invite` `.id`\n\n"
        f"🔧 **SETTINGS**\n"
        f"`.welcome on/off` `.setwelcome` `.antilink on/off`\n"
        f"`.addword` `.delword` `.wordlist`\n\n"
        f"🤖 `.ping` `.menu`", parse_mode="markdown")

async def main():
    global ME
    print("\033[1;34m")
    print("██╗███╗  ██╗███████╗██╗███╗  ██╗██╗████████╗")
    print("██║████╗ ██║██╔════╝██║████╗ ██║██║╚══██╔══╝")
    print("██║██╔██╗██║█████╗  ██║██╔██╗██║██║   ██║   ")
    print("██║██║╚████║██╔══╝  ██║██║╚████║██║   ██║   ")
    print("╚═╝╚═╝ ╚═══╝╚═╝     ╚═╝╚═╝ ╚═══╝╚═╝   ╚═╝   ")
    print(f"\033[0m\033[1;36m  ◆ GC MANAGEMENT + YOUTUBE MUSIC ◆\033[0m")
    print(f"\033[1;33m  VC Music: {'✅ Ready' if VC_OK else '❌ pip install py-tgcalls'}\033[0m")
    print("\033[1;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m\n")

    if API_ID == 123456 or API_HASH == "your_api_hash":
        print("\033[1;31m❌ Fill in API_ID and API_HASH at the top of main.py!\033[0m")
        print("   Get them from: https://my.telegram.org\n"); sys.exit(1)

    await client.connect()
    if not await client.is_user_authorized():
        phone = input("\033[1;33mPlease enter your phone (or bot token): \033[0m").strip()
        if ":" in phone and len(phone) > 20:
            await client.sign_in(bot_token=phone)
        else:
            await client.send_code_request(phone)
            code = input("\033[1;33mPlease enter the code you received: \033[0m").strip()
            try: await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                pw = input("\033[1;33m2FA Password: \033[0m").strip()
                await client.sign_in(password=pw)
            except PhoneCodeInvalidError:
                print("\033[1;31m❌ Wrong code.\033[0m"); sys.exit(1)

    ME = await client.get_me()
    name = f"{ME.first_name or ''} {ME.last_name or ''}".strip()
    user = f"@{ME.username}" if ME.username else f"ID:{ME.id}"
    print(f"\n\033[1;32m  ✔ Logged in as: {name} ({user})\033[0m")
    print(f"\033[1;33m  👑 Admin ID: {ADMIN_ID}\033[0m")
    print(f"\033[1;32m  ✅ ONLINE! Prefix: [{PREFIX}]\033[0m\n")

    if VC_OK and calls: await calls.start()
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())
