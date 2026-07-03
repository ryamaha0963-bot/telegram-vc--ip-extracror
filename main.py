"""
TELEGRAM AUTO IP EXTRACTOR BOT - COMPLETE AUTOMATIC
Har group mein join karega, IPs nikalega, auto leave karega
Private/Public sab groups mein kaam karega
"""

import os
import asyncio
import re
import json
import ipaddress
import logging
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

# Multiple accounts
SESSION_STRINGS = os.getenv("SESSION_STRINGS", "").split(",")
SESSION_STRINGS = [s.strip() for s in SESSION_STRINGS if s.strip()]

if not SESSION_STRINGS:
    single = os.getenv("SESSION_STRING", "")
    if single:
        SESSION_STRINGS = [single]

logger.info(f"📱 Loaded {len(SESSION_STRINGS)} account(s)")

# ============= BOT CLASS =============

class AutoIPExtractor:
    def __init__(self):
        logger.info("🚀 Starting Auto IP Extractor Bot...")
        self.bot = None
        self.user_clients = []
        self.ip_pattern = re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        )
        self.all_ips = {}
        self.scanning = False
        self.running = True
        
    async def start(self):
        """Start all clients"""
        # Start bot
        self.bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4)
        await self.bot.start()
        logger.info("✅ Bot started")
        
        # Start user accounts
        for i, session in enumerate(SESSION_STRINGS):
            try:
                client = Client(f"user_{i}", api_id=API_ID, api_hash=API_HASH, session_string=session, workers=2)
                await client.start()
                me = await client.get_me()
                logger.info(f"✅ Account {i+1}: @{me.username or me.first_name}")
                self.user_clients.append(client)
            except Exception as e:
                logger.error(f"❌ Account {i+1} failed: {e}")
        
        if not self.user_clients:
            logger.error("❌ No working accounts!")
            return
        
        # Setup commands
        @self.bot.on_message(filters.command(["start", "help"]))
        async def start_cmd(client, message):
            total = sum(len(ips) for ips in self.all_ips.values())
            await message.reply(
                f"🤖 **Auto IP Extractor Bot**\n\n"
                f"👥 Accounts: {len(self.user_clients)}\n"
                f"🎯 Total IPs: {total}\n"
                f"📊 Groups: {len(self.all_ips)}\n\n"
                "**Commands:**\n"
                "/scan - Scan ALL groups\n"
                "/stats - Show stats\n"
                "/ips - Show all IPs\n"
                "/clear - Clear IPs\n"
                "/stop - Stop bot"
            )
        
        @self.bot.on_message(filters.command("scan"))
        async def scan_cmd(client, message):
            if self.scanning:
                await message.reply("⏳ Scan already running...")
                return
            
            status = await message.reply("🔍 Scanning ALL groups for VCs...")
            await self.scan_all_groups(status, message.chat.id)
        
        @self.bot.on_message(filters.command("stats"))
        async def stats_cmd(client, message):
            total = sum(len(ips) for ips in self.all_ips.values())
            msg = f"📊 **Stats**\n\n"
            msg += f"👥 Accounts: {len(self.user_clients)}\n"
            msg += f"📊 Groups: {len(self.all_ips)}\n"
            msg += f"🎯 Total IPs: {total}\n"
            msg += f"🔄 Status: {'Scanning' if self.scanning else 'Idle'}"
            await message.reply(msg)
        
        @self.bot.on_message(filters.command("ips"))
        async def ips_cmd(client, message):
            total = sum(len(ips) for ips in self.all_ips.values())
            if total == 0:
                await message.reply("📭 No IPs found yet. Run /scan first.")
                return
            
            msg = "🎯 **All Extracted IPs**\n\n"
            count = 0
            for group, ips in list(self.all_ips.items())[:10]:
                if ips:
                    msg += f"**{group[:30]}** ({len(ips)} IPs):\n"
                    for ip in ips[:5]:
                        msg += f"  → `{ip}`\n"
                    if len(ips) > 5:
                        msg += f"  ... and {len(ips)-5} more\n"
                    msg += "\n"
                    count += 1
                    if count >= 5:
                        break
            
            await message.reply(msg)
        
        @self.bot.on_message(filters.command("clear"))
        async def clear_cmd(client, message):
            self.all_ips = {}
            await message.reply("🗑️ All IPs cleared!")
        
        @self.bot.on_message(filters.command("stop"))
        async def stop_cmd(client, message):
            self.running = False
            await message.reply("🛑 Stopping bot...")
            await asyncio.sleep(2)
            os._exit(0)
        
        # Auto scan on startup
        logger.info("🔄 Running initial auto scan...")
        await self.scan_all_groups()
        
        # Auto scan loop - every 5 minutes
        while self.running:
            await asyncio.sleep(300)  # 5 minutes
            if self.running and not self.scanning:
                logger.info("🔄 Auto scan triggered...")
                await self.scan_all_groups()
    
    async def scan_all_groups(self, status_msg=None, chat_id=None):
        """Scan ALL groups - automatic join + extract"""
        if self.scanning:
            return
        
        self.scanning = True
        
        try:
            if status_msg:
                await status_msg.edit("🔍 Scanning all groups...")
            
            all_groups = []
            
            # Get all groups from all accounts
            for client in self.user_clients:
                try:
                    async for dialog in client.get_dialogs(limit=100):
                        if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                            all_groups.append({
                                "chat_id": dialog.chat.id,
                                "title": dialog.chat.title or "Unknown",
                                "client": client,
                                "peer": await client.resolve_peer(dialog.chat.id)
                            })
                except Exception as e:
                    logger.error(f"Error getting groups: {e}")
            
            # Remove duplicates
            seen = set()
            unique_groups = []
            for g in all_groups:
                if g["chat_id"] not in seen:
                    seen.add(g["chat_id"])
                    unique_groups.append(g)
            
            logger.info(f"📊 Found {len(unique_groups)} unique groups")
            
            if status_msg:
                await status_msg.edit(f"📊 Found {len(unique_groups)} groups\n🔄 Extracting IPs...")
            
            total_ips = 0
            processed = 0
            
            # Process each group
            for group in unique_groups:
                if not self.running:
                    break
                
                processed += 1
                title = group["title"][:30]
                
                try:
                    # Get active call
                    call = await self.get_call(group["client"], group["peer"])
                    if call:
                        # Try to join and extract
                        ips = await self.extract_ips_from_call(group["client"], group["chat_id"], call)
                        
                        if ips:
                            self.all_ips[title] = ips
                            total_ips += len(ips)
                            logger.info(f"✅ {title}: {len(ips)} IPs")
                            
                            if status_msg and chat_id:
                                await status_msg.edit(
                                    f"🔄 Scanning... {processed}/{len(unique_groups)}\n"
                                    f"✅ Found IPs in {len(self.all_ips)} groups\n"
                                    f"🎯 Total IPs: {total_ips}"
                                )
                    else:
                        logger.info(f"⏭️ {title}: No active VC")
                        
                except Exception as e:
                    logger.error(f"❌ {title}: {e}")
                
                # Small delay to avoid flood
                await asyncio.sleep(0.5)
            
            # Final message
            if status_msg and chat_id:
                msg = f"✅ **Scan Complete!**\n\n"
                msg += f"📊 Groups scanned: {processed}\n"
                msg += f"🎯 Groups with IPs: {len(self.all_ips)}\n"
                msg += f"📋 Total IPs: {total_ips}\n\n"
                msg += f"📝 Use /ips to see all IPs"
                await status_msg.edit(msg)
            
            logger.info(f"✅ Scan complete! Total IPs: {total_ips}")
            
        except Exception as e:
            logger.error(f"Scan error: {e}")
            if status_msg:
                await status_msg.edit(f"❌ Scan error: {e}")
        finally:
            self.scanning = False
    
    async def get_call(self, client, peer):
        """Get active call object"""
        try:
            if isinstance(peer, types.InputPeerChannel):
                full = await client.invoke(
                    functions.channels.GetFullChannel(
                        channel=types.InputChannel(peer.channel_id, peer.access_hash)
                    )
                )
            else:
                full = await client.invoke(
                    functions.messages.GetFullChat(chat_id=peer.chat_id)
                )
            return getattr(full.full_chat, "call", None)
        except:
            return None
    
    async def extract_ips_from_call(self, client, chat_id, call):
        """Extract IPs from call - automatic join"""
        ips = []
        
        try:
            # Join VC - AUTOMATIC
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
                await asyncio.sleep(0.5)  # Wait for connection
            except UserAlreadyParticipant:
                pass
            except Exception as e:
                logger.debug(f"Join error: {e}")
            
            # Extract IPs from call data
            call_str = str(call)
            found_ips = self.ip_pattern.findall(call_str)
            
            # Extract from params
            if hasattr(call, "params"):
                params_data = getattr(call.params, "data", "{}")
                found_ips.extend(self.ip_pattern.findall(params_data))
                
                try:
                    params = json.loads(params_data)
                    for key in ["servers", "endpoints", "relays", "candidates"]:
                        if key in params:
                            data = params[key]
                            if isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict):
                                        for k in ["ip", "host", "address", "relay_ip"]:
                                            if k in item:
                                                found_ips.extend(self.ip_pattern.findall(str(item[k])))
                                    elif isinstance(item, str):
                                        found_ips.extend(self.ip_pattern.findall(item))
                except:
                    pass
            
            # Leave VC - AUTOMATIC
            try:
                await client.invoke(
                    functions.phone.LeaveGroupCall(
                        call=types.InputGroupCall(call.id, call.access_hash),
                        source=0
                    )
                )
            except:
                pass
            
            # Filter IPs
            seen = set()
            for ip in found_ips:
                if ip not in seen and self.is_public(ip):
                    seen.add(ip)
                    ips.append(ip)
                    
        except Exception as e:
            logger.error(f"Extract error: {e}")
        
        return ips[:20]  # Max 20 IPs per group
    
    def is_public(self, ip):
        """Check if IP is public"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            return not (ip_obj.is_private or ip_obj.is_loopback or 
                       ip_obj.is_link_local or ip_obj.is_reserved)
        except:
            return False

# ============= RUN =============

async def main():
    try:
        bot = AutoIPExtractor()
        await bot.start()
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
    except Exception as e:
        logger.error(f"❌ Fatal: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
