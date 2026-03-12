"""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   ██╗███╗   ██╗███████╗██╗███╗   ██╗██╗████████╗   ║
║   ██║████╗  ██║██╔════╝██║████╗  ██║██║╚══██╔══╝   ║
║   ██║██╔██╗ ██║█████╗  ██║██╔██╗ ██║██║   ██║      ║
║   ██║██║╚██╗██║██╔══╝  ██║██║╚██╗██║██║   ██║      ║
║   ██║██║ ╚████║██║     ██║██║ ╚████║██║   ██║      ║
║   ╚═╝╚═╝  ╚═══╝╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝   ╚═╝      ║
║                                                      ║
║      ◆ GROUP MANAGEMENT + YOUTUBE MUSIC ◆           ║
║              Infinity GC Bot V1                      ║
╚══════════════════════════════════════════════════════╝
"""

import os, re, sys, asyncio, json, time, traceback
from datetime import datetime, timedelta
from pathlib import Path

from telethon import TelegramClient, events, functions, types
from telethon.errors import (
    FloodWaitError, UserAdminInvalidError,
    ChatAdminRequiredError, UserNotParticipantError,
    SessionPasswordNeededError, PhoneCodeInvalidError
)
from telethon.tl.functions.channels import (
    EditBannedRequest, EditAdminRequest,
    GetParticipantsRequest, EditTitleRequest
)
from telethon.tl.functions.messages import (
    UpdatePinnedMessageRequest, DeleteMessagesRequest
)
from telethon.tl.types import (
    ChatBannedRights, ChatAdminRights,
    ChannelParticipantsAdmins, ChannelParticipantsSearch,
    InputPeerChannel
)

import yt_dlp

# ══════════════════════════════════════════════════════
#  DATA STORAGE
# ══════════════════════════════════════════════════════
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

def load_json(f, default):
    try:
        p = Path(f)
        return json.loads(p.read_text()) if p.exists() else default
    except:
        return default

def save_json(f, data):
    try:
        Path(f).write_text(json.dumps(data, indent=2))
    except:
        pass

WARNS_FILE    = DATA_DIR / "warns.json"
WELCOME_FILE  = DATA_DIR / "welcome.json"
ANTILINK_FILE = DATA_DIR / "antilink.json"
ANTIWORD_FILE = DATA_DIR / "antiwords.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
SUDO_FILE     = DATA_DIR / "sudo.json"
KING_FILE     = DATA_DIR / "king.json"

warns        = load_json(WARNS_FILE,    {})
welcome_cfg  = load_json(WELCOME_FILE,  {})
antilink     = load_json(ANTILINK_FILE, {})
antiwords    = load_json(ANTIWORD_FILE, {})
settings     = load_json(SETTINGS_FILE, {"prefix": ".", "nc_delay": 0.5})
sudo_users   = set(load_json(SUDO_FILE, []))
king_chats   = set(load_json(KING_FILE, []))   # chats where king mode is active

PREFIX    = settings.get("prefix", ".")
NC_DELAY  = settings.get("nc_delay", 0.5)

# ── ADMIN ID — set your admin chat/user ID here ──
ADMIN_ID  = 8494250384

def save_all():
    save_json(WARNS_FILE,    warns)
    save_json(WELCOME_FILE,  welcome_cfg)
    save_json(ANTILINK_FILE, antilink)
    save_json(ANTIWORD_FILE, antiwords)
    save_json(SETTINGS_FILE, settings)
    save_json(SUDO_FILE,     list(sudo_users))
    save_json(KING_FILE,     list(king_chats))

# ══════════════════════════════════════════════════════
#  MUSIC / NC STATE
# ══════════════════════════════════════════════════════
yts_cache      = {}    # chat_id → track info
music_queues   = {}    # chat_id → [tracks]
now_playing    = {}    # chat_id → track

TMP_DIR = Path("./tmp")
TMP_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════
#  CONFIG — fill your credentials here
# ══════════════════════════════════════════════════════
API_ID   = 123456          # ← your api_id from my.telegram.org
API_HASH = "your_api_hash" # ← your api_hash from my.telegram.org

client = TelegramClient("infinity_session", API_ID, API_HASH)

ME = None   # will be set after login

# ══════════════════════════════════════════════════════
#  BANNER
# ══════════════════════════════════════════════════════
BANNER = """
\033[1;34m
██╗███╗   ██╗███████╗██╗███╗   ██╗██╗████████╗██╗   ██╗
██║████╗  ██║██╔════╝██║████╗  ██║██║╚══██╔══╝╚██╗ ██╔╝
██║██╔██╗ ██║█████╗  ██║██╔██╗ ██║██║   ██║    ╚████╔╝ 
██║██║╚██╗██║██╔══╝  ██║██║╚██╗██║██║   ██║     ╚██╔╝  
██║██║ ╚████║██║     ██║██║ ╚████║██║   ██║      ██║   
╚═╝╚═╝  ╚═══╝╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝   ╚═╝      ╚═╝   
\033[0m
\033[1;36m     ◆ GROUP MANAGEMENT + YOUTUBE MUSIC ◆\033[0m
\033[0;37m             Infinity GC Bot V1\033[0m
\033[1;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m

\033[1;32mCommands:\033[0m
  \033[0;37m{p}yts <query>    →  Search YouTube\033[0m
  \033[0;37m{p}song           →  Download MP3\033[0m
  \033[0;37m{p}kick/ban/mute  →  GC Management\033[0m
  \033[0;37m{p}menu           →  Full command list\033[0m

\033[1;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
"""

# ══════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════
def seconds_to_min(sec):
    if not sec:
        return "N/A"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def is_cmd(text: str, cmd: str) -> bool:
    t = text.strip()
    return t == f"{PREFIX}{cmd}" or t.startswith(f"{PREFIX}{cmd} ")

def get_arg(text: str) -> str:
    parts = text.strip().split(None, 1)
    return parts[1] if len(parts) > 1 else ""

async def get_target(event):
    """Return target user from reply."""
    if event.is_reply:
        replied = await event.get_reply_message()
        if replied and replied.sender_id:
            return await client.get_entity(replied.sender_id)
    return None

async def is_admin(chat_id, user_id) -> bool:
    # Hardcoded admin always has full access
    if user_id == ADMIN_ID:
        return True
    try:
        p = await client.get_permissions(chat_id, user_id)
        return p.is_admin or p.is_creator
    except:
        return False

def is_authorized(user_id: int) -> bool:
    return user_id == ADMIN_ID or user_id in sudo_users

async def safe_reply(event, text, **kwargs):
    try:
        return await event.reply(text, **kwargs)
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
        return await event.reply(text, **kwargs)

def yt_search_list(query: str, n=5):
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
        if info and "entries" in info:
            return [e for e in info["entries"] if e][:n]
    return []

def yt_download_mp3(url: str, out: str) -> bool:
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "outtmpl": out.replace(".mp3","") + ".%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        return True
    except:
        return False

# ══════════════════════════════════════════════════════
#  MENU / HELP
# ══════════════════════════════════════════════════════
HELP_TEXT = """
♾️ **INFINITY USERBOT** ♾️

━━━━━━━━━━━━━━━━━━━━━━━━
🎵 **YOUTUBE / MUSIC**
`{p}yts <query>` — Search YouTube (top 5)
`{p}song` — Download MP3 of last yts result
`{p}song <query>` — Search + download directly
`{p}play <song>` — Join VC & play music
`{p}skip` — Skip current song
`{p}stop` — Stop & leave VC
`{p}pause` — Pause
`{p}resume` — Resume
`{p}queue` — Show queue
`{p}np` — Now playing

━━━━━━━━━━━━━━━━━━━━━━━━
👥 **GROUP MANAGEMENT**
`{p}kick` — Kick (reply)
`{p}ban` — Ban (reply)
`{p}unban` — Unban (reply)
`{p}mute 10m` — Mute user (s/m/h/d)
`{p}unmute` — Unmute (reply)
`{p}warn` — Warn (3 warns = auto ban)
`{p}unwarn` — Remove warning
`{p}warns` — Check warnings
`{p}promote` — Make admin (reply)
`{p}demote` — Remove admin (reply)
`{p}pin` — Pin message (reply)
`{p}unpin` — Unpin
`{p}del` — Delete message (reply)
`{p}purge` — Purge from reply to now

━━━━━━━━━━━━━━━━━━━━━━━━
📋 **GROUP INFO**
`{p}gcinfo` — Group details
`{p}adminlist` — List admins
`{p}tagall` — Tag all members
`{p}id` — Get ID
`{p}invite` — Get invite link
`{p}lock` — Lock group
`{p}unlock` — Unlock group

━━━━━━━━━━━━━━━━━━━━━━━━
🔧 **GROUP SETTINGS**
`{p}welcome on/off` — Toggle welcome
`{p}setwelcome <text>` — Set welcome msg
`{p}antilink on/off` — Anti-invite-link
`{p}addword <word>` — Ban a word
`{p}delword <word>` — Unban a word
`{p}wordlist` — Banned words

━━━━━━━━━━━━━━━━━━━━━━━━
👑 **KING MODE**
`{p}kingmode on/off` — Toggle in this chat
  └ Mentions @admin → auto reply

━━━━━━━━━━━━━━━━━━━━━━━━
🤖 **BOT**
`{p}ping` — Latency
`{p}prefix <new>` — Change prefix
`{p}menu` — This menu

♾️ _Infinity V1 — Userbot_
"""

# ══════════════════════════════════════════════════════
#  EVENT HANDLERS
# ══════════════════════════════════════════════════════

# ── PING ──
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ping$"))
async def cmd_ping(event):
    t = time.time()
    m = await event.edit("🏓 Pinging...")
    ms = round((time.time() - t) * 1000)
    await m.edit(f"🏓 **Pong!** `{ms}ms`")

# ── MENU / HELP ──
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.(menu|help|start)$"))
async def cmd_menu(event):
    await event.edit(HELP_TEXT.format(p=PREFIX), parse_mode="markdown")

# ── ID ──
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.id$"))
async def cmd_id(event):
    if event.is_reply:
        r = await event.get_reply_message()
        uid = r.sender_id
        name = getattr(r.sender, "first_name", str(uid)) if r.sender else str(uid)
        await event.edit(f"👤 **User:** {name}\n🆔 **ID:** `{uid}`")
    else:
        chat = await event.get_chat()
        await event.edit(f"💬 **Chat ID:** `{event.chat_id}`\n👤 **Your ID:** `{ME.id}`")

# ══════════════════════════════════════════════════════
#  YTS — YouTube Search
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.yts (.+)"))
async def cmd_yts(event):
    query = event.pattern_match.group(1).strip()
    await event.edit(f"🔍 Searching YouTube for: `{query}`...")

    results = await asyncio.get_event_loop().run_in_executor(
        None, yt_search_list, query, 5
    )
    if not results:
        await event.edit("❌ No results found.")
        return

    top = results[0]
    yts_cache[event.chat_id] = {
        "title":    top.get("title", "Unknown"),
        "url":      top.get("url") or f"https://youtube.com/watch?v={top.get('id','')}",
        "id":       top.get("id",""),
        "duration": top.get("duration"),
        "channel":  top.get("channel") or top.get("uploader",""),
    }

    lines = []
    for i, r in enumerate(results, 1):
        title = (r.get("title") or "Unknown")[:55]
        dur   = seconds_to_min(r.get("duration"))
        vid   = r.get("id","")
        lines.append(f"{i}️⃣ [{title}](https://youtu.be/{vid}) — `{dur}`")

    text = (
        f"🎵 **YouTube: `{query}`**\n\n"
        + "\n".join(lines)
        + f"\n\n✅ Top result saved — use `.song` to download MP3"
    )
    await event.edit(text, parse_mode="markdown", link_preview=False)

# ══════════════════════════════════════════════════════
#  SONG — Download & send MP3
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.song(.*)"))
async def cmd_song(event):
    extra = (event.pattern_match.group(1) or "").strip()
    chat_id = event.chat_id

    if extra:
        await event.edit(f"🔍 Searching `{extra}`...")
        results = await asyncio.get_event_loop().run_in_executor(
            None, yt_search_list, extra, 1
        )
        if not results:
            await event.edit("❌ Not found.")
            return
        r = results[0]
        track = {
            "title":    r.get("title","Unknown"),
            "url":      r.get("url") or f"https://youtube.com/watch?v={r.get('id','')}",
            "duration": r.get("duration"),
        }
    else:
        track = yts_cache.get(chat_id)
        if not track:
            await event.edit("❌ Use `.yts <song>` first, then `.song`.")
            return

    safe = re.sub(r'[\\/:*?"<>|]', "", track["title"])[:50]
    out  = TMP_DIR / f"{safe}_{chat_id}.mp3"

    await event.edit(f"⏬ Downloading **{track['title']}**...")

    ok = await asyncio.get_event_loop().run_in_executor(
        None, yt_download_mp3, track["url"], str(out)
    )

    # yt-dlp may rename extension
    final = out
    if not final.exists():
        candidates = list(TMP_DIR.glob(f"{safe}_{chat_id}.*"))
        if candidates:
            final = candidates[0]

    if not ok or not final.exists():
        await event.edit("❌ Download failed. Is `ffmpeg` installed?")
        return

    await event.edit(f"📤 Uploading **{track['title']}**...")
    dur = seconds_to_min(track.get("duration"))
    await client.send_file(
        chat_id,
        str(final),
        attributes=[
            types.DocumentAttributeAudio(
                duration=track.get("duration") or 0,
                title=track["title"],
                performer="Infinity Bot",
            )
        ],
        caption=f"🎵 **{track['title']}**\n⏱ `{dur}`",
        reply_to=event.id,
    )
    final.unlink(missing_ok=True)
    yts_cache.pop(chat_id, None)
    await event.delete()


# ══════════════════════════════════════════════════════
#  VOICE CHAT MUSIC — inline controls
# ══════════════════════════════════════════════════════
from pytgcalls import PyTgCalls
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from telethon import Button

calls = PyTgCalls(client)

vc_queue      = {}   # chat_id → [track, ...]
vc_playing    = {}   # chat_id → track
vc_paused     = set()  # chat_ids currently paused
vc_player_msg = {}   # chat_id → player message id (for editing)

def music_buttons(paused=False):
    pause_btn = Button.inline("▶️ Resume", data="vc_resume") if paused else Button.inline("⏸ Pause", data="vc_pause")
    return [
        [pause_btn, Button.inline("⏭ Skip", data="vc_skip"), Button.inline("⏹ Stop", data="vc_stop")],
        [Button.inline("📋 Queue", data="vc_queue"), Button.inline("🔄 Refresh", data="vc_refresh")],
    ]

def now_playing_text(track, paused=False):
    status = "⏸ Paused" if paused else "🔊 Playing in Voice Chat"
    q = vc_queue.get(track.get("_chat_id"), [])
    queue_line = f"📋 **{len(q)} song(s) in queue**" if q else "📋 Queue empty"
    return (
        f"🎵 **Now Playing**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 **{track['title']}**\n"
        f"⏱ `{seconds_to_min(track.get('duration'))}`\n"
        f"🎙 {status}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{queue_line}"
    )

def vc_ydl_download(url: str, out: str) -> bool:
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "outtmpl": out,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        return True
    except:
        return False

async def vc_play_next(chat_id: int):
    q = vc_queue.get(chat_id, [])
    if not q:
        vc_playing.pop(chat_id, None)
        vc_paused.discard(chat_id)
        try:
            await calls.leave_group_call(chat_id)
        except:
            pass
        (TMP_DIR / f"vc_{chat_id}.raw").unlink(missing_ok=True)
        # Update player message to show stopped
        msg_id = vc_player_msg.pop(chat_id, None)
        if msg_id:
            try:
                await client.edit_message(chat_id, msg_id, "⏹ **Playback finished.** Queue is empty.")
            except:
                pass
        return

    track = q.pop(0)
    vc_queue[chat_id] = q
    track["_chat_id"] = chat_id
    vc_playing[chat_id] = track

    out = str(TMP_DIR / f"vc_{chat_id}.raw")
    ok = await asyncio.get_event_loop().run_in_executor(
        None, vc_ydl_download, track["url"], out
    )
    if not ok:
        await vc_play_next(chat_id)
        return

    try:
        await calls.join_group_call(chat_id, AudioPiped(out, HighQualityAudio()))
    except Exception:
        try:
            await calls.change_stream(chat_id, AudioPiped(out, HighQualityAudio()))
        except:
            pass

    # Delete old player card and send new one with updated thumbnail
    msg_id = vc_player_msg.pop(chat_id, None)
    if msg_id:
        try:
            await client.delete_messages(chat_id, msg_id)
        except:
            pass
    thumb = track.get("thumbnail", "")
    try:
        import urllib.request, os as _os
        tmp_thumb = str(TMP_DIR / f"thumb_{chat_id}.jpg")
        urllib.request.urlretrieve(thumb, tmp_thumb)
        player_msg = await client.send_file(
            chat_id,
            tmp_thumb,
            caption=now_playing_text(track),
            buttons=music_buttons(False),
            parse_mode="markdown"
        )
        _os.unlink(tmp_thumb)
        vc_player_msg[chat_id] = player_msg.id
    except Exception:
        player_msg = await client.send_message(
            chat_id,
            now_playing_text(track),
            buttons=music_buttons(False),
            parse_mode="markdown"
        )
        vc_player_msg[chat_id] = player_msg.id

@calls.on_stream_end()
async def _on_stream_end(_, update: Update):
    cid = update.chat_id
    (TMP_DIR / f"vc_{cid}.raw").unlink(missing_ok=True)
    await vc_play_next(cid)

# ── .play ──
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.play(.*)"))
async def cmd_play(event):
    if not event.is_group:
        await event.edit("❌ Groups only."); return

    query = (event.pattern_match.group(1) or "").strip()
    if not query:
        await event.edit("⚠️ Usage: `.play <song name>`"); return

    chat_id = event.chat_id
    await event.edit(f"🔍 Searching: `{query}`...")

    results = await asyncio.get_event_loop().run_in_executor(None, yt_search_list, query, 1)
    if not results:
        await event.edit("❌ Not found on YouTube."); return

    r = results[0]
    vid_id = r.get("id", "")
    track = {
        "title":     r.get("title", "Unknown"),
        "url":       r.get("url") or f"https://youtube.com/watch?v={vid_id}",
        "duration":  r.get("duration"),
        "thumbnail": f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg",
        "_chat_id":  chat_id,
    }

    # Already playing → add to queue
    if vc_playing.get(chat_id):
        vc_queue.setdefault(chat_id, []).append(track)
        pos = len(vc_queue[chat_id])
        await event.edit(
            f"📋 **Added to Queue** #{pos}\n"
            f"🎵 **{track['title']}**\n"
            f"⏱ `{seconds_to_min(track.get('duration'))}`"
        )
        return

    await event.edit(f"⏬ Downloading **{track['title']}**...")

    out = str(TMP_DIR / f"vc_{chat_id}.raw")
    ok = await asyncio.get_event_loop().run_in_executor(None, vc_ydl_download, track["url"], out)
    if not ok:
        await event.edit("❌ Download failed. Is `yt-dlp` installed?"); return

    vc_playing[chat_id] = track
    vc_queue.setdefault(chat_id, [])

    try:
        await calls.join_group_call(chat_id, AudioPiped(out, HighQualityAudio()))
        await event.delete()
        # Send player card with thumbnail + inline buttons
        thumb = track.get("thumbnail", "")
        try:
            import urllib.request, tempfile, os as _os
            tmp_thumb = str(TMP_DIR / f"thumb_{chat_id}.jpg")
            urllib.request.urlretrieve(thumb, tmp_thumb)
            player_msg = await client.send_file(
                chat_id,
                tmp_thumb,
                caption=now_playing_text(track),
                buttons=music_buttons(False),
                parse_mode="markdown"
            )
            _os.unlink(tmp_thumb)
        except Exception:
            player_msg = await client.send_message(
                chat_id,
                now_playing_text(track),
                buttons=music_buttons(False),
                parse_mode="markdown"
            )
        vc_player_msg[chat_id] = player_msg.id
    except Exception as e:
        vc_playing.pop(chat_id, None)
        await event.edit(f"❌ Could not join VC: `{e}`\nMake sure a Voice Chat is active.")

# ══════════════════════════════════════════════════════
#  INLINE BUTTON CALLBACKS
# ══════════════════════════════════════════════════════
@client.on(events.CallbackQuery(data=b"vc_pause"))
async def cb_pause(event):
    chat_id = event.chat_id
    if not vc_playing.get(chat_id):
        await event.answer("❌ Nothing playing.", alert=True); return
    try:
        await calls.pause_stream(chat_id)
        vc_paused.add(chat_id)
        track = vc_playing[chat_id]
        await event.edit(now_playing_text(track, paused=True), buttons=music_buttons(paused=True), parse_mode="markdown")
        await event.answer("⏸ Paused")
    except Exception as e:
        await event.answer(f"Error: {e}", alert=True)

@client.on(events.CallbackQuery(data=b"vc_resume"))
async def cb_resume(event):
    chat_id = event.chat_id
    if not vc_playing.get(chat_id):
        await event.answer("❌ Nothing playing.", alert=True); return
    try:
        await calls.resume_stream(chat_id)
        vc_paused.discard(chat_id)
        track = vc_playing[chat_id]
        await event.edit(now_playing_text(track, paused=False), buttons=music_buttons(paused=False), parse_mode="markdown")
        await event.answer("▶️ Resumed")
    except Exception as e:
        await event.answer(f"Error: {e}", alert=True)

@client.on(events.CallbackQuery(data=b"vc_skip"))
async def cb_skip(event):
    chat_id = event.chat_id
    current = vc_playing.get(chat_id)
    if not current:
        await event.answer("❌ Nothing playing.", alert=True); return
    await event.answer("⏭ Skipping...")
    (TMP_DIR / f"vc_{chat_id}.raw").unlink(missing_ok=True)
    await vc_play_next(chat_id)
    nxt = vc_playing.get(chat_id)
    if not nxt:
        try:
            await event.edit(f"⏹ Skipped **{current['title']}** — queue empty.")
        except:
            pass

@client.on(events.CallbackQuery(data=b"vc_stop"))
async def cb_stop(event):
    chat_id = event.chat_id
    vc_queue.pop(chat_id, None)
    vc_playing.pop(chat_id, None)
    vc_paused.discard(chat_id)
    vc_player_msg.pop(chat_id, None)
    (TMP_DIR / f"vc_{chat_id}.raw").unlink(missing_ok=True)
    try:
        await calls.leave_group_call(chat_id)
    except:
        pass
    await event.edit("⏹ **Stopped** — Left Voice Chat.")
    await event.answer("⏹ Stopped")

@client.on(events.CallbackQuery(data=b"vc_queue"))
async def cb_queue(event):
    chat_id = event.chat_id
    current = vc_playing.get(chat_id)
    q       = vc_queue.get(chat_id, [])
    if not current and not q:
        await event.answer("📋 Queue is empty.", alert=True); return
    lines = []
    if current:
        lines.append(f"▶️ **Now:** {current['title']} `{seconds_to_min(current.get('duration'))}`")
    for i, t in enumerate(q, 1):
        lines.append(f"{i}. {t['title']} `{seconds_to_min(t.get('duration'))}`")
    await event.answer("\n".join(lines)[:200], alert=True)

@client.on(events.CallbackQuery(data=b"vc_refresh"))
async def cb_refresh(event):
    chat_id = event.chat_id
    track   = vc_playing.get(chat_id)
    if not track:
        await event.answer("❌ Nothing playing.", alert=True); return
    paused = chat_id in vc_paused
    await event.edit(now_playing_text(track, paused=paused), buttons=music_buttons(paused=paused), parse_mode="markdown")
    await event.answer("🔄 Refreshed")

# ══════════════════════════════════════════════════════
#  GC INFO / ADMINLIST / TAGALL / INVITE
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.gcinfo$"))
async def cmd_gcinfo(event):
    if not event.is_group:
        await event.edit("❌ Groups only.")
        return
    chat  = await event.get_chat()
    admins = []
    async for p in client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins()):
        tag = "🌟" if getattr(p.participant, "is_creator", False) else "👑"
        admins.append(f"{tag} {p.first_name}")
    count = 0
    async for _ in client.iter_participants(event.chat_id):
        count += 1
    desc = getattr(chat, "about", None) or "(none)"
    text = (
        f"🏘️ **GROUP INFO**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📛 **Name:** {chat.title}\n"
        f"🆔 **ID:** `{event.chat_id}`\n"
        f"👥 **Members:** {count}\n"
        f"📝 **Desc:** {desc}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👑 **Admins:**\n" + "\n".join(admins)
    )
    await event.edit(text, parse_mode="markdown")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.adminlist$"))
async def cmd_adminlist(event):
    if not event.is_group:
        await event.edit("❌ Groups only."); return
    lines = []
    async for p in client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins()):
        tag = "🌟" if getattr(p.participant, "is_creator", False) else "👑"
        lines.append(f"{tag} [{p.first_name}](tg://user?id={p.id})")
    await event.edit("👑 **Admins:**\n\n" + "\n".join(lines), parse_mode="markdown", link_preview=False)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.tagall(.*)"))
async def cmd_tagall(event):
    if not event.is_group:
        await event.edit("❌ Groups only."); return
    extra = (event.pattern_match.group(1) or "").strip() or "Attention everyone!"
    users = []
    async for p in client.iter_participants(event.chat_id):
        if not p.bot:
            users.append(f"[{p.first_name}](tg://user?id={p.id})")
    # Send in chunks of 20
    for i in range(0, len(users), 20):
        chunk = users[i:i+20]
        await client.send_message(
            event.chat_id,
            f"📢 **{extra}**\n\n" + " ".join(chunk),
            parse_mode="markdown",
            link_preview=False
        )
        await asyncio.sleep(1.5)
    await event.delete()

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.invite$"))
async def cmd_invite(event):
    if not event.is_group:
        await event.edit("❌ Groups only."); return
    try:
        result = await client(functions.messages.ExportChatInviteRequest(peer=event.chat_id))
        await event.edit(f"🔗 **Invite Link:**\n{result.link}")
    except:
        await event.edit("❌ Need admin rights for invite link.")

# ══════════════════════════════════════════════════════
#  KICK / BAN / UNBAN
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.kick$"))
async def cmd_kick(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    target = await get_target(event)
    if not target: await event.edit("⚠️ Reply to a user."); return
    if await is_admin(event.chat_id, target.id): await event.edit("❌ Can't kick an admin."); return
    try:
        await client.kick_participant(event.chat_id, target.id)
        await event.edit(f"👢 **Kicked:** [{target.first_name}](tg://user?id={target.id})", parse_mode="markdown")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ban(.*)"))
async def cmd_ban(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    target = await get_target(event)
    if not target: await event.edit("⚠️ Reply to a user."); return
    if await is_admin(event.chat_id, target.id): await event.edit("❌ Can't ban an admin."); return
    reason = (event.pattern_match.group(1) or "").strip() or "No reason"
    try:
        rights = ChatBannedRights(until_date=None, view_messages=True)
        await client(EditBannedRequest(event.chat_id, target.id, rights))
        await event.edit(f"🔨 **Banned:** [{target.first_name}](tg://user?id={target.id})\n📋 Reason: {reason}", parse_mode="markdown")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unban$"))
async def cmd_unban(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    target = await get_target(event)
    if not target: await event.edit("⚠️ Reply to a user."); return
    try:
        rights = ChatBannedRights(until_date=None, view_messages=False)
        await client(EditBannedRequest(event.chat_id, target.id, rights))
        await event.edit(f"✅ **Unbanned:** [{target.first_name}](tg://user?id={target.id})", parse_mode="markdown")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

# ══════════════════════════════════════════════════════
#  MUTE / UNMUTE
# ══════════════════════════════════════════════════════
def parse_duration(s: str):
    m = re.match(r"(\d+)([smhd]?)", s.lower().strip())
    if not m: return None
    val, unit = int(m.group(1)), m.group(2)
    mult = {"s":1,"m":60,"h":3600,"d":86400}.get(unit, 60)
    return val * mult

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.mute(.*)"))
async def cmd_mute(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    target = await get_target(event)
    if not target: await event.edit("⚠️ Reply to a user."); return
    if await is_admin(event.chat_id, target.id): await event.edit("❌ Can't mute an admin."); return
    dur_str = (event.pattern_match.group(1) or "").strip() or "10m"
    secs = parse_duration(dur_str) or 600
    until = datetime.now() + timedelta(seconds=secs)
    try:
        rights = ChatBannedRights(until_date=until, send_messages=True)
        await client(EditBannedRequest(event.chat_id, target.id, rights))
        await event.edit(f"🔇 **Muted:** [{target.first_name}](tg://user?id={target.id})\n⏱ Duration: `{dur_str}`", parse_mode="markdown")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unmute$"))
async def cmd_unmute(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    target = await get_target(event)
    if not target: await event.edit("⚠️ Reply to a user."); return
    try:
        rights = ChatBannedRights(until_date=None, send_messages=False)
        await client(EditBannedRequest(event.chat_id, target.id, rights))
        await event.edit(f"🔔 **Unmuted:** [{target.first_name}](tg://user?id={target.id})", parse_mode="markdown")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

# ══════════════════════════════════════════════════════
#  WARN SYSTEM
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.warn(.*)"))
async def cmd_warn(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    target = await get_target(event)
    if not target: await event.edit("⚠️ Reply to a user."); return
    if await is_admin(event.chat_id, target.id): await event.edit("❌ Can't warn an admin."); return
    cid, uid = str(event.chat_id), str(target.id)
    reason = (event.pattern_match.group(1) or "").strip() or "No reason"
    warns.setdefault(cid, {})
    warns[cid][uid] = warns[cid].get(uid, 0) + 1
    count = warns[cid][uid]
    save_all()
    if count >= 3:
        try:
            rights = ChatBannedRights(until_date=None, view_messages=True)
            await client(EditBannedRequest(event.chat_id, target.id, rights))
            await event.edit(f"🔨 **{target.first_name} auto-banned!** ({count}/3 warnings)\n📋 Reason: {reason}", parse_mode="markdown")
            warns[cid][uid] = 0; save_all()
        except Exception as e:
            await event.edit(f"❌ Auto-ban failed: `{e}`")
    else:
        await event.edit(f"⚠️ **Warned:** [{target.first_name}](tg://user?id={target.id})\n📊 `{count}/3`\n📋 {reason}", parse_mode="markdown")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unwarn$"))
async def cmd_unwarn(event):
    target = await get_target(event)
    if not target: await event.edit("⚠️ Reply to a user."); return
    cid, uid = str(event.chat_id), str(target.id)
    if warns.get(cid, {}).get(uid, 0) > 0:
        warns[cid][uid] -= 1; save_all()
        await event.edit(f"✅ Warning removed from [{target.first_name}](tg://user?id={target.id})\n📊 `{warns[cid][uid]}/3`", parse_mode="markdown")
    else:
        await event.edit(f"ℹ️ [{target.first_name}](tg://user?id={target.id}) has no warnings.", parse_mode="markdown")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.warns$"))
async def cmd_warns(event):
    target = await get_target(event)
    if not target: target_id = str(ME.id); name = ME.first_name
    else: target_id = str(target.id); name = target.first_name
    cid = str(event.chat_id)
    count = warns.get(cid, {}).get(target_id, 0)
    await event.edit(f"📊 **{name}:** `{count}/3` warnings")

# ══════════════════════════════════════════════════════
#  PROMOTE / DEMOTE
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.promote$"))
async def cmd_promote(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    target = await get_target(event)
    if not target: await event.edit("⚠️ Reply to a user."); return
    try:
        rights = ChatAdminRights(
            change_info=True, post_messages=True,
            edit_messages=True, delete_messages=True,
            ban_users=True, invite_users=True,
            pin_messages=True, manage_call=True,
            other=False
        )
        await client(EditAdminRequest(event.chat_id, target.id, rights, rank="Admin"))
        await event.edit(f"👑 **Promoted:** [{target.first_name}](tg://user?id={target.id})", parse_mode="markdown")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.demote$"))
async def cmd_demote(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    target = await get_target(event)
    if not target: await event.edit("⚠️ Reply to a user."); return
    try:
        rights = ChatAdminRights()
        await client(EditAdminRequest(event.chat_id, target.id, rights, rank=""))
        await event.edit(f"📉 **Demoted:** [{target.first_name}](tg://user?id={target.id})", parse_mode="markdown")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

# ══════════════════════════════════════════════════════
#  PIN / UNPIN / DEL / PURGE
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.pin$"))
async def cmd_pin(event):
    if not event.is_reply: await event.edit("⚠️ Reply to a message to pin."); return
    r = await event.get_reply_message()
    try:
        await client.pin_message(event.chat_id, r.id)
        await event.edit("📌 **Pinned!**")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unpin$"))
async def cmd_unpin(event):
    try:
        await client.unpin_message(event.chat_id)
        await event.edit("📌 **Unpinned!**")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.del$"))
async def cmd_del(event):
    if not event.is_reply: await event.edit("⚠️ Reply to a message to delete."); return
    r = await event.get_reply_message()
    await r.delete()
    await event.delete()

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.purge$"))
async def cmd_purge(event):
    if not event.is_reply: await event.edit("⚠️ Reply to the start message."); return
    r     = await event.get_reply_message()
    from_id = r.id
    to_id   = event.id
    ids = list(range(from_id, to_id + 1))
    deleted = 0
    for chunk in [ids[i:i+100] for i in range(0, len(ids), 100)]:
        try:
            await client.delete_messages(event.chat_id, chunk)
            deleted += len(chunk)
        except:
            pass
    m = await client.send_message(event.chat_id, f"🗑 **Purged {deleted} messages.**")
    await asyncio.sleep(3)
    await m.delete()

# ══════════════════════════════════════════════════════
#  LOCK / UNLOCK
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.lock$"))
async def cmd_lock(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    try:
        await client(functions.messages.EditChatDefaultBannedRightsRequest(
            peer=event.chat_id,
            banned_rights=ChatBannedRights(until_date=None, send_messages=True)
        ))
        await event.edit("🔒 **Group Locked!** Only admins can send messages.")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unlock$"))
async def cmd_unlock(event):
    if not event.is_group: await event.edit("❌ Groups only."); return
    try:
        await client(functions.messages.EditChatDefaultBannedRightsRequest(
            peer=event.chat_id,
            banned_rights=ChatBannedRights(until_date=None, send_messages=False)
        ))
        await event.edit("🔓 **Group Unlocked!** Everyone can send messages.")
    except Exception as e:
        await event.edit(f"❌ Failed: `{e}`")

# ══════════════════════════════════════════════════════
#  WELCOME
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.welcome (.+)"))
async def cmd_welcome_toggle(event):
    arg = event.pattern_match.group(1).strip().lower()
    cid = str(event.chat_id)
    if arg == "on":
        welcome_cfg.setdefault(cid, {})["on"] = True; save_all()
        await event.edit("✅ **Welcome ON**")
    elif arg == "off":
        welcome_cfg.setdefault(cid, {})["on"] = False; save_all()
        await event.edit("❌ **Welcome OFF**")
    else:
        await event.edit("⚠️ Use `.welcome on` or `.welcome off`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.setwelcome (.+)"))
async def cmd_setwelcome(event):
    text = event.pattern_match.group(1).strip()
    cid  = str(event.chat_id)
    welcome_cfg.setdefault(cid, {})["msg"] = text; save_all()
    await event.edit(f"✅ **Welcome set!**\n\n{text}", parse_mode="markdown")

@client.on(events.ChatAction())
async def on_join(event):
    if not event.user_joined and not event.user_added:
        return
    cid = str(event.chat_id)
    cfg_w = welcome_cfg.get(cid, {})
    if not cfg_w.get("on"):
        return
    user  = await event.get_user()
    if not user:
        return
    chat  = await event.get_chat()
    count = 0
    async for _ in client.iter_participants(event.chat_id):
        count += 1
    tmpl = cfg_w.get("msg", "✦ Welcome to {chat}, {name}! You're member #{count} 🎉")
    text = tmpl.replace("{name}", user.first_name or "User")\
               .replace("{chat}", getattr(chat,"title","Group"))\
               .replace("{count}", str(count))
    try:
        await client.send_message(event.chat_id, text, parse_mode="markdown")
    except:
        pass

# ══════════════════════════════════════════════════════
#  ANTI-LINK
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.antilink (.+)"))
async def cmd_antilink_toggle(event):
    arg = event.pattern_match.group(1).strip().lower()
    cid = str(event.chat_id)
    if arg == "on":
        antilink[cid] = True; save_all()
        await event.edit("🔗 **Anti-link ON**")
    elif arg == "off":
        antilink.pop(cid, None); save_all()
        await event.edit("🔗 **Anti-link OFF**")
    else:
        await event.edit("⚠️ Use `.antilink on` or `.antilink off`")

@client.on(events.NewMessage(incoming=True))
async def auto_filter_handler(event):
    if not event.is_group or not event.text:
        return
    cid    = str(event.chat_id)
    sender = await event.get_sender()
    if not sender:
        return

    # Skip if sender is admin
    if await is_admin(event.chat_id, sender.id):
        return

    # ── Anti-link ──
    if antilink.get(cid):
        if re.search(r"(https?://|t\.me/|telegram\.me/)", event.text, re.I):
            try:
                await event.delete()
                m = await client.send_message(event.chat_id, f"🔗 Link removed — [{sender.first_name}](tg://user?id={sender.id})", parse_mode="markdown")
                await asyncio.sleep(4)
                await m.delete()
            except:
                pass
            return

    # ── Anti-word ──
    words = antiwords.get(cid, [])
    lower = event.text.lower()
    for w in words:
        if w in lower:
            try:
                await event.delete()
                m = await client.send_message(event.chat_id, "🚫 Banned word — message deleted.")
                await asyncio.sleep(4)
                await m.delete()
            except:
                pass
            return

# ══════════════════════════════════════════════════════
#  ANTI-WORD COMMANDS
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.addword (.+)"))
async def cmd_addword(event):
    word = event.pattern_match.group(1).strip().lower()
    cid  = str(event.chat_id)
    antiwords.setdefault(cid, [])
    if word in antiwords[cid]:
        await event.edit(f"⚠️ `{word}` already banned."); return
    antiwords[cid].append(word); save_all()
    await event.edit(f"✅ Banned word: `{word}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.delword (.+)"))
async def cmd_delword(event):
    word = event.pattern_match.group(1).strip().lower()
    cid  = str(event.chat_id)
    if word in antiwords.get(cid, []):
        antiwords[cid].remove(word); save_all()
        await event.edit(f"✅ Removed: `{word}`")
    else:
        await event.edit(f"⚠️ `{word}` not in list.")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.wordlist$"))
async def cmd_wordlist(event):
    cid   = str(event.chat_id)
    words = antiwords.get(cid, [])
    if not words:
        await event.edit("📋 No banned words."); return
    await event.edit("🚫 **Banned:**\n" + "\n".join(f"• `{w}`" for w in words), parse_mode="markdown")

# ══════════════════════════════════════════════════════
#  KING MODE — auto reply when admin is mentioned
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.kingmode (.+)"))
async def cmd_kingmode(event):
    arg = event.pattern_match.group(1).strip().lower()
    cid = event.chat_id
    if arg == "on":
        king_chats.add(cid); save_all()
        await event.edit("👑 **King Mode ON!**\nMentioning @admin triggers king reply.")
    elif arg == "off":
        king_chats.discard(cid); save_all()
        await event.edit("👑 **King Mode OFF**")
    else:
        status = "ON" if cid in king_chats else "OFF"
        await event.edit(f"👑 King Mode is **{status}**\nUse `.kingmode on/off`")

@client.on(events.NewMessage(incoming=True))
async def king_mode_trigger(event):
    if not event.is_group: return
    if event.chat_id not in king_chats: return
    if not event.text: return
    # Check if any admin is mentioned or text says "admin"
    if "@admin" in event.text.lower() or (event.mentioned and ME and event.mentioned):
        try:
            king_mp3 = Path("king.mp3")
            if king_mp3.exists():
                await client.send_file(
                    event.chat_id,
                    str(king_mp3),
                    reply_to=event.id,
                    caption="👑 **KING MODE ACTIVE** ♾️"
                )
            else:
                await event.reply("👑 **KING IS HERE** ♾️\n_یرادخ — Infinity_", parse_mode="markdown")
        except:
            pass

# ══════════════════════════════════════════════════════
#  PREFIX CHANGE
# ══════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.prefix (.+)"))
async def cmd_prefix(event):
    global PREFIX
    new = event.pattern_match.group(1).strip()
    if len(new) > 3:
        await event.edit("❌ Prefix must be 1-3 chars."); return
    old = PREFIX
    PREFIX = new
    settings["prefix"] = PREFIX
    save_all()
    await event.edit(f"✅ Prefix: `{old}` → `{PREFIX}`")

# ══════════════════════════════════════════════════════
#  MAIN — LOGIN FLOW (Phone + OTP, exactly like screenshot)
# ══════════════════════════════════════════════════════
async def main():
    global ME

    print(BANNER.format(p=PREFIX))
    print("\033[1;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m")

    if not API_ID or API_HASH == "your_api_hash":
        print("\n\033[1;31m❌ ERROR: Fill in API_ID and API_HASH inside main.py!\033[0m")
        print("Open main.py and edit lines with API_ID and API_HASH at the top.")
        print("Get them from: https://my.telegram.org\n")
        sys.exit(1)

    await client.connect()

    if not await client.is_user_authorized():
        phone = input("\n\033[1;33mPlease enter your phone (or bot token): \033[0m").strip()

        if ":" in phone and len(phone) > 20:
            # Looks like a bot token
            await client.sign_in(bot_token=phone)
        else:
            try:
                await client.send_code_request(phone)
                code = input("\033[1;33mPlease enter the code you received: \033[0m").strip()
                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    pw = input("\033[1;33mTwo-step verification enabled. Enter your password: \033[0m").strip()
                    await client.sign_in(password=pw)
                except PhoneCodeInvalidError:
                    print("\033[1;31m❌ Invalid code. Restarting...\033[0m")
                    sys.exit(1)
            except Exception as e:
                print(f"\033[1;31m❌ Login failed: {e}\033[0m")
                sys.exit(1)

    ME = await client.get_me()
    name = f"{ME.first_name or ''} {ME.last_name or ''}".strip()
    username = f"@{ME.username}" if ME.username else f"ID:{ME.id}"

    print(f"\n\033[1;32m  ✔ Logged in as: {name} ({username})\033[0m")
    print(f"\033[1;33m  👑 Admin ID: {ADMIN_ID}\033[0m")
    print(f"\033[1;36m  🔧 Bot will auto-detect group chats\033[0m")
    print(f"\033[1;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m")
    print(f"\033[1;32m  ✅ Infinity Userbot is ONLINE! Prefix: [{PREFIX}]\033[0m\n")

    await calls.start()
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())
