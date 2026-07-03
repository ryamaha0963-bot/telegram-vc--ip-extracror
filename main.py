"""
SIMPLE IP EXTRACTOR - SIRF 1 GROUP SCAN
FloodWait nahi aayega
"""

import os
import asyncio
import re
import json
import ipaddress
import logging
from pyrogram import Client, filters
from pyrogram.raw import functions, types
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ============= CONFIG =============
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# ============= BOT =============

class SimpleBot:
    def __init__(self):
        self.bot = None
        self.user = None
        self.ip_pattern = re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        )
        self.ips = []
        
    async def start(self):
        # Bot
        self.bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
        await self.bot.start()
        logger.info("✅ Bot started")
        
        # User
        self.user = Client("user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
        await self.user.start()
        me = await self.user.get_me()
        logger.info(f"✅ User: @{me.username or me.first_name}")
        
        # Commands
        @self.bot.on_message(filters.command("start"))
        async def start_cmd(client, message):
            await message.reply(
                "🤖 **IP Extractor Bot**\n\n"
                "`/getip @username` - Group username\n"
                "`/getip -100123456789` - Group ID\n\n"
                "**Commands:**\n"
                "/scan - Scan current group"
            )
        
        @self.bot.on_message(filters.command("scan"))
        async def scan_cmd(client, message):
            status = await message.reply("🔍 Scanning current group...")
            
            try:
                chat_id = message.chat.id
                ips = await self.extract_ips(chat_id)
                
                if ips:
                    msg = f"✅ **{len(ips)} IPs Found!**\n\n"
                    for ip in ips[:10]:
                        msg += f"`{ip}`\n"
                    await status.edit(msg)
                else:
                    await status.edit("❌ No IPs found! Start VC first.")
                    
            except FloodWait as e:
                await status.edit(f"⏳ Rate limited! Wait {e.value}s")
            except Exception as e:
                await status.edit(f"❌ Error: {e}")
        
        @self.bot.on_message(filters.command("getip"))
        async def getip_cmd(client, message):
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.reply("❌ Provide group ID or username")
                return
            
            status = await message.reply("🔍 Finding group...")
            
            try:
                identifier = args[1].strip()
                
                # Resolve group
                if "t.me/" in identifier:
                    identifier = "@" + identifier.split("t.me/")[-1].split("/")[0]
                
                try:
                    chat = await self.bot.get_chat(identifier)
                except:
                    chat = await self.user.get_chat(identifier)
                
                if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
                    await status.edit("❌ Not a group")
                    return
                
                await status.edit(f"📂 {chat.title}\n🔄 Extracting IPs...")
                
                ips = await self.extract_ips(chat.id)
                
                if ips:
                    msg = f"✅ **{len(ips)} IPs Found!**\n\n"
                    for ip in ips[:10]:
                        msg += f"`{ip}`\n"
                    await status.edit(msg)
                else:
                    await status.edit("❌ No IPs found! Start VC first.")
                    
            except FloodWait as e:
                await status.edit(f"⏳ Rate limited! Wait {e.value}s")
            except Exception as e:
                await status.edit(f"❌ Error: {e}")
        
        logger.info("✅ Bot ready!")
        await asyncio.Event().wait()
    
    async def extract_ips(self, chat_id):
        """Extract IPs from VC"""
        ips = []
        
        try:
            peer = await self.user.resolve_peer(chat_id)
            
            # Get call
            if isinstance(peer, types.InputPeerChannel):
                full = await self.user.invoke(
                    functions.channels.GetFullChannel(
                        channel=types.InputChannel(peer.channel_id, peer.access_hash)
                    )
                )
            else:
                full = await self.user.invoke(
                    functions.messages.GetFullChat(chat_id=peer.chat_id)
                )
            
            call = getattr(full.full_chat, "call", None)
            if not call:
                return ips
            
            # Join
            try:
                me = await self.user.resolve_peer('me')
                params = types.DataJSON(data=json.dumps({"ufrag":"x","pwd":"y","fingerprints":[],"ssrc":1}))
                await self.user.invoke(
                    functions.phone.JoinGroupCall(
                        call=types.InputGroupCall(call.id, call.access_hash),
                        join_as=me,
                        params=params,
                        muted=True,
                        video_stopped=True
                    )
                )
                await asyncio.sleep(0.5)
            except:
                pass
            
            # Extract
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
            
            # Leave
            try:
                await self.user.invoke(
                    functions.phone.LeaveGroupCall(
                        call=types.InputGroupCall(call.id, call.access_hash),
                        source=0
                    )
                )
            except:
                pass
            
            # Filter
            seen = set()
            for ip in found_ips:
                if ip not in seen and self.is_public(ip):
                    seen.add(ip)
                    ips.append(ip)
                    
        except FloodWait as e:
            raise
        except Exception as e:
            logger.error(f"Extract error: {e}")
        
        return ips[:15]
    
    def is_public(self, ip):
        try:
            ip_obj = ipaddress.ip_address(ip)
            return not (ip_obj.is_private or ip_obj.is_loopback)
        except:
            return False

# ============= RUN =============

async def main():
    bot = SimpleBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
