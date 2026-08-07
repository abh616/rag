"""
IndoGulf Trading — FastAPI Webhook
====================================
Receives WhatsApp messages via Meta Cloud API
and returns Arya's reply.

Flow:
    WhatsApp message
        → Meta Cloud API
        → POST /webhook  (this file)
        → agent.py generates reply
        → reply sent back to WhatsApp

Run:
    uvicorn webhook:app --host 0.0.0.0 --port 8000 --reload

Requirements:
    pip install fastapi uvicorn requests
"""

import os
import json
import requests
from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

# Import your agent
from agent import generate_reply

load_dotenv()

app = FastAPI()

# ─────────────────────────────────────────────
# CONFIGURATION — fill these in .env
# ─────────────────────────────────────────────

VERIFY_TOKEN    = os.getenv("VERIFY_TOKEN", "indogulf_verify_123")
WA_TOKEN        = os.getenv("WA_ACCESS_TOKEN", "")   # Meta permanent token
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")   # from Meta dashboard

# In-memory conversation store
# { "phone_number": [{"role": "user/assistant", "content": "..."}] }
conversations = {}


# ─────────────────────────────────────────────
# ROUTE 1 — VERIFICATION
# Meta calls this once when you register the webhook
# It checks your verify token to confirm ownership
# ─────────────────────────────────────────────

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """
    Meta sends a GET request to verify you own this webhook.
    You confirm by echoing back the challenge if token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print(f"✅ Webhook verified by Meta")
        return PlainTextResponse(content=hub_challenge)

    print("❌ Webhook verification failed — token mismatch")
    return PlainTextResponse(content="Forbidden", status_code=403)


# ─────────────────────────────────────────────
# ROUTE 2 — RECEIVE MESSAGE
# Meta sends every incoming WhatsApp message here
# ─────────────────────────────────────────────

@app.post("/webhook")
async def receive_message(request: Request):
    """
    Receives incoming WhatsApp messages from Meta.
    Calls the agent and sends reply back.
    """
    body = await request.json()

    # ── Parse the incoming message ──
    try:
        entry    = body["entry"][0]
        changes  = entry["changes"][0]
        value    = changes["value"]

        # Ignore status updates (delivered, read receipts)
        if "messages" not in value:
            return {"status": "ignored"}

        message  = value["messages"][0]
        msg_type = message["type"]

        # Only handle text messages for now
        if msg_type != "text":
            print(f"⏭️  Ignoring non-text message: {msg_type}")
            return {"status": "ignored"}

        sender_phone = message["from"]        # e.g. "919876543210"
        msg_text     = message["text"]["body"]
        msg_id       = message["id"]

        print(f"\n📩 Message from {sender_phone}: {msg_text}")

    except (KeyError, IndexError) as e:
        print(f"⚠️  Could not parse message: {e}")
        return {"status": "parse_error"}

    # ── Get or create conversation history ──
    if sender_phone not in conversations:
        conversations[sender_phone] = []

    history = conversations[sender_phone]

    # ── Call the agent ──
    print(f"🤖 Calling agent...")
    result = generate_reply(
        user_message=msg_text,
        conversation_history=history,
    )

    reply_text  = result["reply"]
    lead_score  = result["lead_score"]
    escalate    = result["escalate"]

    print(f"💬 Reply: {reply_text}")
    print(f"📊 Score: {lead_score} | Escalate: {escalate}")

    # ── Update conversation history ──
    conversations[sender_phone].append(
        {"role": "user", "content": msg_text}
    )
    conversations[sender_phone].append(
        {"role": "assistant", "content": reply_text}
    )

    # ── Send reply back to WhatsApp ──
    send_whatsapp_message(
        to=sender_phone,
        text=reply_text,
    )

    # ── Notify team if HOT lead ──
    if escalate:
        notify_team(
            phone=sender_phone,
            message=msg_text,
            score=lead_score,
        )

    return {"status": "ok"}


# ─────────────────────────────────────────────
# HELPER: SEND WHATSAPP MESSAGE
# ─────────────────────────────────────────────

def send_whatsapp_message(to: str, text: str):
    """
    Sends a WhatsApp message via Meta Cloud API.
    """
    if not WA_TOKEN or not PHONE_NUMBER_ID:
        print("⚠️  WA_ACCESS_TOKEN or PHONE_NUMBER_ID not set — skipping send")
        return

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"✅ Reply sent to {to}")
    else:
        print(f"❌ Failed to send: {response.status_code} — {response.text}")


# ─────────────────────────────────────────────
# HELPER: NOTIFY TEAM FOR HOT LEADS
# Prints to console for now
# Later: send email / Slack / SMS to sales team
# ─────────────────────────────────────────────

def notify_team(phone: str, message: str, score: str):
    """
    Alerts the human sales team about a HOT lead.
    Currently prints to console.
    Easy to extend to email/Slack later.
    """
    print(f"""
╔══════════════════════════════════════╗
║  🔴 HOT LEAD — HUMAN NEEDED          ║
╠══════════════════════════════════════╣
║  Phone  : {phone}
║  Score  : {score}
║  Message: {message[:50]}
║  Action : Reply on WhatsApp manually
╚══════════════════════════════════════╝
""")


# ─────────────────────────────────────────────
# ROUTE 3 — HEALTH CHECK
# Simple route to confirm server is running
# ─────────────────────────────────────────────

@app.get("/")
async def health_check():
    return {
        "status": "running",
        "agent": "Arya — IndoGulf Trading",
        "active_conversations": len(conversations),
    }