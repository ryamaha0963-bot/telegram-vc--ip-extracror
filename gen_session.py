from pyrogram import Client

# For each account, run this
API_ID = 12345
API_HASH = "abc123"

app = Client("session1", api_id=API_ID, api_hash=API_HASH)
app.start()
print("Session 1:", app.export_session_string())
app.stop()

# Repeat for multiple accounts
app2 = Client("session2", api_id=API_ID, api_hash=API_HASH)
app2.start()
print("Session 2:", app2.export_session_string())
app2.stop()
