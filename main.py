"""
TELEGRAM VC IP EXTRACTOR BOT - CRASH PROOF
Session validation + error handling
"""

import os
import sys
import asyncio
import re
import json
import ipaddress
import logging
import traceback
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.raw import functions, types
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait, UserAlreadyParticipant

# ============= LOGGING =============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= CONFIG =============
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Get sessions - handle multiple formats
SESSION_STRINGS = []

# Try SESSION_STRINGS (comma separated)
sessions_env = os.getenv("SESSION_STRINGS", "")
if sessions_env:
    SESSION_STRINGS = [s.strip() for s in sessions_env.split(",") if s.strip()]

# Try SESSION_STRING (single)
if not SESSION_STRINGS:
    single = os.getenv("SESSION_STRING", "")
    if single:
        SESSION_STRINGS = [single]

logger.info(f"📱 Loaded {len(SESSION_STRINGS)} session(s)")

# ============= BOT CLASS =============

class IPExtractorBot:
    def __init__(self):
        logger.info("🚀 Starting IP Extractor Bot...")
        self.bot = None
        self.user_clients = []
        self.ip_pattern = re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        )
        self.processing = {}
        self.running = True
        
    async def start_clients(self):
        """Start all clients safely"""
        try:
            # Start bot
            self.bot = Client(
                "bot",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                workers=4
            )
            await self.bot.start()
            logger.info("✅ Bot started")
            
            # Start user accounts with validation
            for i, session in enumerate(SESSION_STRINGS):
                if not session or len(session) < 10:
                    logger.warning(f"⚠️ Session {i+1} is invalid (too short)")
                    continue
                    
                try:
                    client = Client(
                        f"user_{i}",
                        api_id=API_ID,
                        api_hash=API_HASH,
                        session_string=session,
                        workers=2
                    )
                    await client.start()
                    
                    # Verify account
                    try:
                        me = await client.get_me()
                        logger.info(f"✅ Account {i+1}: @{me.username or me.first_name} (ID: {me.id})")
                        self.user_clients.append(client)
                    except Exception as e:
                        logger.error(f"❌ Account {i+1} verification failed: {e}")
                        await client.stop()
                        
                except Exception as e:
                    logger.error(f"❌ Account {i+1} failed: {e}")
                    continue
            
            if not self.user_clients:
                logger.error("❌ No working accounts!")
                return False
            
            logger.info(f"✅ {len(self.user_clients)} account(s) working")
            return True
            
        except Exception as e:
            logger.error(f"❌ Start error: {e}")
            traceback.print_exc()
            return False
    
    async def run(self):
        """Main run loop"""
        try:
            if not await self.start_clients():
                logger.error("Failed to start clients")
                return
            
            await self.setup_commands()
            
            logger.info(f"✅ Bot Ready! Accounts: {len(self.user_clients)}")
            
            # Keep running
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            traceback.print_exc()
        finally:
            await self.cleanup()
    
    async def setup_commands(self):
        """Setup bot commands"""
        
        @self.bot.on_message(filters.command(["start", "help"]))
        async def start_cmd(client, message):
            try:
                await message.reply(
                    "🤖 **IP Extractor Bot**\n\n"
                    f"👥 Accounts: {len(self.user_clients)}\n"
                    "📝 Send group link/ID to extract IPs\n\n"
                    "**Usage:**\n"
                    "`/getip https://t.me/group`\n"
                    "`/getip @username`\n"
                    "`/getip -100123456789`\n\n"
                    "**Commands:**\n"
                    "/getip - Extract IPs\n"
                    "/accounts - Show accounts\n"
                    "/stats - Show stats"
                )
            except Exception as e:
                logger.error(f"Start cmd error: {e}")
        
        @self.bot.on_message(filters.command("accounts"))
        async def accounts_cmd(client, message):
            try:
                msg = "👥 **Active Accounts:**\n\n"
                for i, c in enumerate(self.user_clients):
                    try:
                        me = await c.get_me()
                        msg += f"✅ {i+1}. @{me.username or me.first_name}\n"
                    except:
                        msg += f"❌ {i+1}. Inactive\n"
                await message.reply(msg)
            except Exception as e:
                logger.error(f"Accounts cmd error: {e}")
        
        @self.bot.on_message(filters.command("stats"))
        async def stats_cmd(client, message):
            try:
                msg = f"📊 **Bot Stats**\n\n"
                msg += f"👥 Accounts: {len(self.user_clients)}\n"
                msg += f"⚡ Status: Running\n"
                msg += f"🔄 Processing: {len(self.processing)}\n"
                await message.reply(msg)
            except Exception as e:
                logger.error(f"Stats cmd error: {e}")
        
        @self.bot.on_message(filters.command("getip"))
        async def get_ip_cmd(client, message):
            chat_id = message.chat.id
            
            try:
                if chat_id in self.processing and self.processing[chat_id]:
                    await message.reply("⏳ Already processing...")
                    return
                
                args = message.text.split(maxsplit=1)
                if len(args) < 2:
                    await message.reply(
                        "❌ Please provide group link/ID!\n"
                        "Example: `/getip https://t.me/group`"
                    )
                    return
                
                identifier = args[1].strip()
                self.processing[chat_id] = True
                
                status = await message.reply("🔍 Finding group...")
                
                group = await self.resolve_group(identifier)
                if not group:
                    await status.edit("❌ Group not found!")
                    self.processing[chat_id] = False
                    return
                
                await status.edit(f"📂 Group: {group['title']}\n🔄 Extracting...")
                
                ips = await self.extract_ips(group)
                
                if ips:
                    msg = f"✅ **IPs Extracted!**\n\n"
                    msg += f"📂 {group['title']}\n"
                    msg += f"🆔 `{group['chat_id']}`\n"
                    msg += f"🎯 {len(ips)} IPs\n\n"
                    
                    for i, ip in enumerate(ips[:10], 1):
                        msg += f"`{ip['ip']}:{ip['port']}`\n"
                    
                    if len(ips) > 10:
                        msg += f"\n... and {len(ips)-10} more"
                    
                    await status.edit(msg)
                else:
                    await status.edit(
                        f"❌ **No IPs Found!**\n\n"
                        f"📂 {group['title']}\n"
                        f"🆔 `{group['chat_id']}`\n\n"
                        "💡 Make sure:\n"
                        "• Voice chat is active\n"
                        "• Someone is in the VC\n"
                        "• Account is in the group"
                    )
                    
            except FloodWait as e:
                await message.reply(f"⏳ Rate limited! Wait {e.value}s")
            except Exception as e:
                logger.error(f"GetIP error: {e}")
                await message.reply(f"❌ Error: {str(e)[:100]}")
            finally:
                self.processing[chat_id] = False
    
    async def resolve_group(self, identifier):
        """Resolve group"""
        try:
            identifier = identifier.strip()
            
            if "t.me/" in identifier:
                username = identifier.split("t.me/")[-1].split("/")[0]
                identifier = f"@{username}"
            
            # Try bot
            try:
                chat = await self.bot.get_chat(identifier)
                if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                    return {"chat_id": chat.id, "title": chat.title or "Unknown"}
            except:
                pass
            
            # Try user accounts
            for client in self.user_clients:
                try:
                    chat = await client.get_chat(identifier)
                    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                        return {"chat_id": chat.id, "title": chat.title or "Unknown"}
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Resolve error: {e}")
            return None
    
    async def extract_ips(self, group):
        """Extract IPs"""
        all_ips = []
        seen = set()
        
        for client in self.user_clients:
            try:
                ips = await self.extract_single(client, group)
                for ip in ips:
                    if ip["ip"] not in seen:
                        seen.add(ip["ip"])
                        all_ips.append(ip)
            except Exception as e:
                logger.error(f"Extract error: {e}")
                continue
        
        return all_ips
    
    async def extract_single(self, client, group):
        """Extract with single account"""
        ips = []
        chat_id = group["chat_id"]
        
        try:
            peer = await client.resolve_peer(chat_id)
            call = await self.get_call(client, peer)
            if not call:
                return ips
            
            # Join VC
            try:
                me = await client.resolve_peer('me')
                params = types.DataJSON(
                    data=json.dumps({
                        "ufrag": "x",
                        "pwd": "y",
                        "fingerprints": [],
                        "ssrc": 1
                    })
                )
                await client.invoke(
                    functions.phone.JoinGroupCall(
                        call=types.InputGroupCall(call.id, call.access_hash),
                        join_as=me,
                        params=params,
                        muted=True,
                        video_stopped=True
                    )
                )
                await asyncio.sleep(0.5)
            except UserAlreadyParticipant:
                pass
            except Exception as e:
                logger.error(f"Join error: {e}")
            
            # Extract IPs
            call_str = str(call)
            found_ips = self.ip_pattern.findall(call_str)
            
            if hasattr(call, "params"):
                params_data = getattr(call.params, "data", "{}")
                found_ips.extend(self.ip_pattern.findall(params_data))
                
                try:
                    params = json.loads(params_data)
                    for key in ["servers", "endpoints", "relays"]:
                        if key in params:
                            data = params[key]
                            if isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict):
                                        for k in ["ip", "host", "address"]:
                                            if k in item:
                                                found_ips.extend(self.ip_pattern.findall(str(item[k])))
                except:
                    pass
            
            # Leave VC
            try:
                await client.invoke(
                    functions.phone.LeaveGroupCall(
                        call=types.InputGroupCall(call.id, call.access_hash),
                        source=0
                    )
                )
            except:
                pass
            
            # Filter
            for ip in found_ips:
                if self.is_public(ip):
                    ips.append({"ip": ip, "port": 10001})
                    
        except Exception as e:
            logger.error(f"Extract single error: {e}")
        
        return ips[:15]
    
    async def get_call(self, client, peer):
        """Get active call"""
        try:
            if isinstance(peer, types.InputPeerChannel):
                full = await client.invoke(
                    functions.channels.GetFullChannel(
                        channel=types.InputChannel(peer.channel_id, peer.access_hash)
                    )
                )
                return getattr(full.full_chat, "call", None)
            elif isinstance(peer, types.InputPeerChat):
                full = await client.invoke(
                    functions.messages.GetFullChat(chat_id=peer.chat_id)
                )
                return getattr(full.full_chat, "call", None)
        except:
            pass
        return None
    
    def is_public(self, ip):
        """Check public IP"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            return not (ip_obj.is_private or ip_obj.is_loopback or 
                       ip_obj.is_link_local or ip_obj.is_reserved)
        except:
            return False
    
    async def cleanup(self):
        """Cleanup"""
        try:
            if self.bot:
                await self.bot.stop()
            for client in self.user_clients:
                try:
                    await client.stop()
                except:
                    pass
            logger.info("✅ Cleanup done")
        except:
            pass

# ============= MAIN =============

async def main():
    bot = None
    try:
        bot = IPExtractorBot()
        await bot.run()
    except Exception as e:
        logger.error(f"Main error: {e}")
        traceback.print_exc()
    finally:
        if bot:
            await bot.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Fatal: {e}")
        traceback.print_exc()
