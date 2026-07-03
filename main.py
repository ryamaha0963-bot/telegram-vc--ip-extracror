"""
TELEGRAM VC IP EXTRACTOR - RAILWAY DEPLOYMENT
With multi-account support & GitHub deployment guide
"""

import os
import asyncio
import json
import re
import ipaddress
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.raw import functions, types
from pyrogram.errors import FloodWait, UserAlreadyParticipant

# ============= RAILWAY CONFIG =============
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

# ============= MULTI-ACCOUNT SUPPORT =============
# Add multiple sessions separated by commas
# Format: session1,session2,session3
SESSION_STRINGS = os.getenv("SESSION_STRINGS", "").split(",")
# Or use single session for backward compatibility
if not SESSION_STRINGS or SESSION_STRINGS == [""]:
    SESSION_STRINGS = [os.getenv("SESSION_STRING", "")]

# Remove empty strings
SESSION_STRINGS = [s.strip() for s in SESSION_STRINGS if s.strip()]

print(f"📱 Loaded {len(SESSION_STRINGS)} accounts")

# ============= OTHER CONFIG =============
AUTO_EXTRACT_INTERVAL = int(os.getenv("AUTO_EXTRACT_INTERVAL", "60"))
MAX_GROUPS = int(os.getenv("MAX_GROUPS", "50"))
SAVE_TO_FILE = os.getenv("SAVE_TO_FILE", "True").lower() == "true"
USE_MULTI_ACCOUNT = os.getenv("USE_MULTI_ACCOUNT", "True").lower() == "true"

# ============= MAIN BOT CLASS =============

class MultiAccountIPExtractor:
    def __init__(self):
        print("🚀 Initializing Multi-Account IP Extractor Bot...")
        
        # Validate config
        if not all([API_ID, API_HASH, BOT_TOKEN]):
            raise ValueError("Missing required environment variables!")
        
        if not SESSION_STRINGS:
            raise ValueError("No session strings provided!")
        
        # Initialize bot client
        self.bot = Client(
            "ip_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=4
        )
        
        # Initialize multiple user clients
        self.user_clients = []
        for i, session_string in enumerate(SESSION_STRINGS):
            client = Client(
                f"user_{i}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_string,
                workers=2
            )
            self.user_clients.append(client)
            print(f"✅ Account {i+1} initialized")
        
        self.ip_pattern = re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        )
        
        self.extracted_ips = {}
        self.running = True
        self.is_scanning = False
        
        # Create data directory for Railway volume
        os.makedirs("data", exist_ok=True)
        self.data_file = "data/ips.json"
        
        # Load existing data
        self.load_ips()
        
    def load_ips(self):
        """Load IPs from file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r") as f:
                    self.extracted_ips = json.load(f)
                total = sum(len(data.get("ips", [])) for data in self.extracted_ips.values())
                print(f"📂 Loaded {total} IPs from {len(self.extracted_ips)} groups")
        except Exception as e:
            print(f"⚠️ Could not load IPs: {e}")
            self.extracted_ips = {}
    
    def save_ips(self):
        """Save IPs to file"""
        try:
            with open(self.data_file, "w") as f:
                json.dump(self.extracted_ips, f, indent=2, default=str)
            print(f"💾 Saved {len(self.extracted_ips)} entries to {self.data_file}")
        except Exception as e:
            print(f"❌ Save error: {e}")
    
    async def start(self):
        """Start all clients and setup bot"""
        print("🔄 Starting clients...")
        
        # Start bot
        await self.bot.start()
        print("✅ Bot started")
        
        # Start all user accounts
        for i, client in enumerate(self.user_clients):
            try:
                await client.start()
                me = await client.get_me()
                print(f"✅ Account {i+1} started: @{me.username or me.first_name}")
            except Exception as e:
                print(f"❌ Failed to start account {i+1}: {e}")
        
        print(f"✅ Bot running! Auto-extract every {AUTO_EXTRACT_INTERVAL}s")
        print(f"📊 Scanning {MAX_GROUPS} groups with {len(self.user_clients)} accounts")
        print(f"👤 Owner ID: {OWNER_ID}")
        
        # Setup bot commands
        @self.bot.on_message(filters.command(["start", "help"]))
        async def start_cmd(client, message):
            total_ips = sum(len(data.get("ips", [])) for data in self.extracted_ips.values())
            await message.reply(
                f"🤖 **Multi-Account IP Extractor Bot**\n\n"
                f"🔄 Auto scan: Every {AUTO_EXTRACT_INTERVAL}s\n"
                f"📊 Groups scanned: {MAX_GROUPS}\n"
                f"👥 Accounts: {len(self.user_clients)}\n"
                f"🎯 Total IPs: {total_ips}\n"
                f"📁 Storage: {'Enabled' if SAVE_TO_FILE else 'Disabled'}\n\n"
                "**Commands:**\n"
                "/stats - Show extraction stats\n"
                "/scan - Manual scan\n"
                "/ips - List all IPs\n"
                "/accounts - Show active accounts\n"
                "/clear - Clear IP storage (owner only)\n"
                "/stop - Stop auto extraction (owner only)"
            )
        
        @self.bot.on_message(filters.command("accounts"))
        async def accounts_cmd(client, message):
            msg = "👥 **Active Accounts:**\n\n"
            for i, client_obj in enumerate(self.user_clients):
                try:
                    me = await client_obj.get_me()
                    status = "✅ Active"
                    msg += f"**Account {i+1}:** @{me.username or me.first_name} ({status})\n"
                except:
                    msg += f"**Account {i+1}:** ❌ Inactive\n"
            await message.reply(msg)
        
        @self.bot.on_message(filters.command("stats"))
        async def stats_cmd(client, message):
            total_ips = sum(len(data.get("ips", [])) for data in self.extracted_ips.values())
            
            msg = f"📊 **Extraction Stats**\n"
            msg += f"Total Groups: {len(self.extracted_ips)}\n"
            msg += f"Total IPs: {total_ips}\n"
            msg += f"Active Accounts: {len(self.user_clients)}\n"
            msg += f"Last Scan: {self.extracted_ips.get('last_scan', 'Never')}\n\n"
            
            if total_ips > 0:
                msg += "**Latest Groups:**\n"
                for chat_id, data in list(self.extracted_ips.items())[:5]:
                    if chat_id != "last_scan":
                        msg += f"• {data.get('title', 'Unknown')}: {len(data.get('ips', []))} IPs\n"
            
            await message.reply(msg)
        
        @self.bot.on_message(filters.command("scan"))
        async def scan_cmd(client, message):
            if self.is_scanning:
                await message.reply("⏳ Scan already in progress...")
                return
            
            status = await message.reply("🔍 Starting manual scan...")
            results = await self.extract_all_ips()
            total = sum(len(data.get("ips", [])) for data in results.values())
            await status.edit(f"✅ Scan complete! Found {total} IPs from {len(results)} groups")
        
        @self.bot.on_message(filters.command("ips"))
        async def ips_cmd(client, message):
            total_ips = sum(len(data.get("ips", [])) for data in self.extracted_ips.values())
            
            if total_ips == 0:
                await message.reply("📭 No IPs found yet.")
                return
            
            msg = "🎯 **All Extracted IPs**\n\n"
            count = 0
            for chat_id, data in self.extracted_ips.items():
                if chat_id == "last_scan":
                    continue
                title = data.get("title", "Unknown")
                ips = data.get("ips", [])
                if ips:
                    msg += f"**{title}** ({len(ips)} IPs):\n"
                    for ip_data in ips[:5]:
                        msg += f"  → `{ip_data['ip']}:{ip_data['port']}`\n"
                    if len(ips) > 5:
                        msg += f"  ... and {len(ips)-5} more\n"
                    msg += "\n"
                    count += 1
                    if count >= 10:
                        msg += "*(Showing first 10 groups)*"
                        break
            
            await message.reply(msg)
        
        @self.bot.on_message(filters.command("clear"))
        async def clear_cmd(client, message):
            if message.from_user.id != OWNER_ID:
                await message.reply("❌ Only owner can clear IPs!")
                return
            
            self.extracted_ips = {}
            self.save_ips()
            await message.reply("🗑️ All IPs cleared!")
        
        @self.bot.on_message(filters.command("stop"))
        async def stop_cmd(client, message):
            if message.from_user.id != OWNER_ID:
                await message.reply("❌ Only owner can stop the bot!")
                return
            
            self.running = False
            await message.reply("🛑 Auto extraction stopped!")
            await asyncio.sleep(2)
            os._exit(0)
        
        # Start auto extraction
        asyncio.create_task(self.auto_extract_loop())
        
        # Keep bot running
        while True:
            await asyncio.sleep(1)
    
    async def auto_extract_loop(self):
        """Auto extraction loop"""
        while self.running:
            try:
                if not self.is_scanning:
                    print(f"\n⏰ Auto scan at {datetime.now().strftime('%H:%M:%S')}")
                    await self.extract_all_ips()
            except Exception as e:
                print(f"❌ Auto scan error: {e}")
            
            for _ in range(AUTO_EXTRACT_INTERVAL):
                if not self.running:
                    break
                await asyncio.sleep(1)
    
    async def extract_all_ips(self):
        """Extract IPs using all accounts"""
        if self.is_scanning:
            return {}
        
        self.is_scanning = True
        results = {}
        
        try:
            # Use all accounts to scan
            all_vc_chats = []
            
            for client in self.user_clients:
                try:
                    print(f"🔍 Scanning with account...")
                    vc_chats = await self.get_active_vc_chats(client)
                    all_vc_chats.extend(vc_chats)
                    print(f"📊 Found {len(vc_chats)} active VCs with this account")
                except Exception as e:
                    print(f"❌ Account scan error: {e}")
            
            # Remove duplicates
            seen_chats = set()
            unique_chats = []
            for chat in all_vc_chats:
                if chat["chat_id"] not in seen_chats:
                    seen_chats.add(chat["chat_id"])
                    unique_chats.append(chat)
            
            print(f"📊 Total unique VCs: {len(unique_chats)}")
            
            if not unique_chats:
                print("ℹ️ No active voice chats found")
                self.is_scanning = False
                return results
            
            # Process each chat
            for chat_data in unique_chats:
                try:
                    print(f"🔎 Processing: {chat_data.get('title', 'Unknown')}")
                    ips = await self.extract_ips_from_call(chat_data)
                    
                    if ips:
                        chat_id = str(chat_data["chat_id"])
                        results[chat_id] = {
                            "title": chat_data["title"],
                            "ips": ips,
                            "timestamp": datetime.now().isoformat()
                        }
                        self.extracted_ips[chat_id] = results[chat_id]
                        print(f"✅ Found {len(ips)} IPs from {chat_data['title']}")
                        
                        # Send notification to owner
                        if OWNER_ID:
                            try:
                                await self.bot.send_message(
                                    OWNER_ID,
                                    f"🎯 New IPs from {chat_data['title']}:\n" +
                                    "\n".join([f"`{ip['ip']}:{ip['port']}`" for ip in ips[:5]])
                                )
                            except:
                                pass
                    else:
                        print(f"❌ No IPs from {chat_data.get('title', 'Unknown')}")
                        
                except Exception as e:
                    print(f"❌ Error processing {chat_data.get('title', 'Unknown')}: {e}")
            
            # Update last scan time
            self.extracted_ips["last_scan"] = datetime.now().isoformat()
            
            # Save to file
            if SAVE_TO_FILE:
                self.save_ips()
                
        except Exception as e:
            print(f"❌ Extraction error: {e}")
        finally:
            self.is_scanning = False
            
        return results
    
    async def get_active_vc_chats(self, client):
        """Get all groups with active voice chats using specific client"""
        vc_chats = []
        try:
            async for dialog in client.get_dialogs(limit=MAX_GROUPS):
                if dialog.chat.type in ["group", "supergroup"]:
                    try:
                        peer = await client.resolve_peer(dialog.chat.id)
                        call = await self._get_active_call(client, peer)
                        if call:
                            vc_chats.append({
                                "chat_id": dialog.chat.id,
                                "title": dialog.chat.title or "Unknown",
                                "peer": peer,
                                "call": call
                            })
                    except Exception:
                        continue
        except Exception as e:
            print(f"Error getting VCs: {e}")
        return vc_chats
    
    async def _get_active_call(self, client, peer):
        """Check if VC is active"""
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
    
    async def extract_ips_from_call(self, vc_data):
        """Extract IPs from VC call data"""
        ips = []
        call = vc_data["call"]
        
        try:
            # Try to join VC with first available account
            joined = False
            for client in self.user_clients:
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
                    await asyncio.sleep(1.5)
                    joined = True
                    
                    # Leave immediately
                    try:
                        await client.invoke(
                            functions.phone.LeaveGroupCall(
                                call=types.InputGroupCall(call.id, call.access_hash),
                                source=0
                            )
                        )
                    except:
                        pass
                    break
                except UserAlreadyParticipant:
                    joined = True
                    break
                except:
                    continue
            
            # Extract IPs from call data
            call_str = str(call)
            found_ips = self.ip_pattern.findall(call_str)
            
            # Also check call params
            if hasattr(call, "params"):
                params_data = getattr(call.params, "data", "{}")
                found_ips.extend(self.ip_pattern.findall(params_data))
                
                try:
                    params = json.loads(params_data)
                    for key in ["servers", "endpoints", "relays"]:
                        if key in params:
                            if isinstance(params[key], list):
                                for item in params[key]:
                                    if isinstance(item, dict):
                                        for k in ["ip", "host", "address"]:
                                            if k in item:
                                                found_ips.extend(self.ip_pattern.findall(str(item[k])))
                except:
                    pass
            
            # Filter and format IPs
            seen = set()
            for ip in found_ips:
                if ip not in seen and self._is_valid_public_ip(ip):
                    seen.add(ip)
                    ips.append({
                        "ip": ip,
                        "port": 10001,
                        "type": "auto"
                    })
                    
        except Exception as e:
            print(f"IP extraction error: {e}")
            
        return ips[:10]
    
    def _is_valid_public_ip(self, ip):
        """Check if IP is valid public IP"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            return not (ip_obj.is_private or 
                       ip_obj.is_loopback or 
                       ip_obj.is_link_local or
                       ip_obj.is_reserved)
        except:
            return False

# ============= RUN =============

async def main():
    print("""
    ╔═══════════════════════════════════════════╗
    ║    MULTI-ACCOUNT IP EXTRACTOR BOT        ║
    ║    Auto-extracts Telegram VC IPs         ║
    ╚═══════════════════════════════════════════╝
    """)
    
    try:
        bot = MultiAccountIPExtractor()
        await bot.start()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
