"""
TELEGRAM VC IP EXTRACTOR BOT
Sirf group ID ya link do, IP extract karke dega
1 second mein join + leave + IP extract
"""

import os
import asyncio
import re
import json
import ipaddress
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.raw import functions, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType

# ============= CONFIG =============
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# ============= BOT CLASS =============

class IPExtractorBot:
    def __init__(self):
        print("🚀 Starting IP Extractor Bot...")
        
        self.bot = Client(
            "bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
        
        self.user = Client(
            "user",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING
        )
        
        self.ip_pattern = re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        )
        
        self.processing = {}
        
    async def start(self):
        """Start bot and user client"""
        await self.bot.start()
        await self.user.start()
        print("✅ Bot Started!")
        
        # ============ COMMANDS ============
        
        @self.bot.on_message(filters.command("start"))
        async def start_cmd(client, message):
            await message.reply(
                "🤖 **VC IP Extractor Bot**\n\n"
                "Mujhe group ID ya link do, main 1 second mein IP nikalunga!\n\n"
                "**Usage:**\n"
                "`/getip @username` - Group username\n"
                "`/getip https://t.me/group` - Group link\n"
                "`/getip -100123456789` - Group ID\n\n"
                "**Example:**\n"
                "`/getip https://t.me/TestGroup`"
            )
        
        @self.bot.on_message(filters.command("getip"))
        async def get_ip_cmd(client, message):
            # Check if already processing
            chat_id = message.chat.id
            if chat_id in self.processing and self.processing[chat_id]:
                await message.reply("⏳ Already processing! Please wait...")
                return
            
            # Get group identifier
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.reply(
                    "❌ Please provide group ID or link!\n\n"
                    "Example: `/getip https://t.me/group`"
                )
                return
            
            identifier = args[1].strip()
            self.processing[chat_id] = True
            
            status = await message.reply("🔍 Finding group...")
            
            try:
                # Resolve group
                group = await self.resolve_group(identifier)
                if not group:
                    await status.edit("❌ Group not found! Check the link/ID.")
                    self.processing[chat_id] = False
                    return
                
                await status.edit(f"📂 Group: {group['title']}\n🔄 Joining VC...")
                
                # Extract IPs
                ips = await self.extract_ips(group)
                
                if ips:
                    # Format response
                    msg = f"✅ **IPs Extracted!**\n\n"
                    msg += f"📂 **Group:** {group['title']}\n"
                    msg += f"🆔 **ID:** `{group['chat_id']}`\n"
                    msg += f"🎯 **Total IPs:** {len(ips)}\n\n"
                    
                    msg += "**IPs:**\n"
                    for i, ip_data in enumerate(ips[:20], 1):
                        msg += f"`{ip_data['ip']}:{ip_data['port']}`\n"
                    
                    if len(ips) > 20:
                        msg += f"\n... and {len(ips)-20} more"
                    
                    # Send response
                    await status.edit(msg)
                    
                    # Also send as file if many IPs
                    if len(ips) > 50:
                        file_text = "\n".join([f"{ip['ip']}:{ip['port']}" for ip in ips])
                        with open("ips.txt", "w") as f:
                            f.write(file_text)
                        await message.reply_document("ips.txt", caption="📄 All IPs")
                        os.remove("ips.txt")
                
                else:
                    await status.edit(
                        f"❌ **No IPs Found!**\n\n"
                        f"📂 **Group:** {group['title']}\n"
                        f"🆔 **ID:** `{group['chat_id']}`\n\n"
                        "💡 Make sure:\n"
                        "• Voice chat is active\n"
                        "• Bot has joined the VC\n"
                        "• Someone is in the VC"
                    )
                    
            except Exception as e:
                await status.edit(f"❌ Error: {str(e)[:200]}")
            
            self.processing[chat_id] = False
        
        @self.bot.on_message(filters.command("help"))
        async def help_cmd(client, message):
            await message.reply(
                "📖 **How to use:**\n\n"
                "1️⃣ Copy group link or ID\n"
                "2️⃣ Send: `/getip group_link`\n"
                "3️⃣ Bot will extract IPs\n\n"
                "**Supported formats:**\n"
                "• `https://t.me/groupname`\n"
                "• `@groupusername`\n"
                "• `-100123456789` (ID)\n\n"
                "**Commands:**\n"
                "/getip - Extract IPs\n"
                "/start - Show info\n"
                "/help - This message"
            )
        
        # ============ KEEP RUNNING ============
        print("✅ Bot is ready!")
        print("Send /getip [group_id/link] to extract IPs")
        await asyncio.Event().wait()
    
    async def resolve_group(self, identifier):
        """Resolve group from ID, username, or link"""
        try:
            # Clean identifier
            identifier = identifier.strip()
            
            # Extract username from link
            if "t.me/" in identifier:
                username = identifier.split("t.me/")[-1].split("/")[0]
                identifier = f"@{username}"
            
            # Get chat
            try:
                chat = await self.bot.get_chat(identifier)
            except:
                # Try with user client
                chat = await self.user.get_chat(identifier)
            
            # Check if it's a group
            if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
                return None
            
            return {
                "chat_id": chat.id,
                "title": chat.title or "Unknown",
                "username": chat.username,
                "invite_link": chat.invite_link
            }
            
        except Exception as e:
            print(f"Resolve error: {e}")
            return None
    
    async def extract_ips(self, group):
        """Extract IPs from group VC - 1 SECOND"""
        ips = []
        chat_id = group["chat_id"]
        
        try:
            # Get peer
            peer = await self.user.resolve_peer(chat_id)
            
            # Get call object
            call = await self.get_call(peer)
            if not call:
                return ips
            
            # Join VC instantly
            try:
                me = await self.user.resolve_peer('me')
                params = types.DataJSON(
                    data=json.dumps({
                        "ufrag": "x",
                        "pwd": "y",
                        "fingerprints": [],
                        "ssrc": 1
                    })
                )
                
                await self.user.invoke(
                    functions.phone.JoinGroupCall(
                        call=types.InputGroupCall(call.id, call.access_hash),
                        join_as=me,
                        params=params,
                        muted=True,
                        video_stopped=True
                    )
                )
                
                # Wait 0.5 seconds for connection
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"Join error: {e}")
            
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
            
            # Leave VC immediately
            try:
                await self.user.invoke(
                    functions.phone.LeaveGroupCall(
                        call=types.InputGroupCall(call.id, call.access_hash),
                        source=0
                    )
                )
            except:
                pass
            
            # Filter and deduplicate
            seen = set()
            for ip in found_ips:
                if ip not in seen and self.is_public(ip):
                    seen.add(ip)
                    ips.append({
                        "ip": ip,
                        "port": 10001,
                        "type": "auto"
                    })
                    
        except Exception as e:
            print(f"Extract error: {e}")
        
        return ips[:20]  # Max 20 IPs
    
    async def get_call(self, peer):
        """Get active call object"""
        try:
            if isinstance(peer, types.InputPeerChannel):
                full = await self.user.invoke(
                    functions.channels.GetFullChannel(
                        channel=types.InputChannel(peer.channel_id, peer.access_hash)
                    )
                )
                return getattr(full.full_chat, "call", None)
            elif isinstance(peer, types.InputPeerChat):
                full = await self.user.invoke(
                    functions.messages.GetFullChat(chat_id=peer.chat_id)
                )
                return getattr(full.full_chat, "call", None)
        except:
            pass
        return None
    
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
    bot = IPExtractorBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
