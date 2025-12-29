# AI Multi‑Channel Support Desk

A production‑ready **AI Customer Support System** that handles **Voice Calls, SMS, and Email** using a single unified backend. The system uses powerful LLMs (Gemini or OpenAI) to generate dynamic multi‑turn responses, log all conversation data in a database, and handle multiple simultaneous conversations.

---

## 📌 Project Summary

This project is a fully functional AI-driven support solution built for real businesses such as **dental clinics, car services, medical spas, and eCommerce stores**. It integrates with **Twilio** to process phone calls and SMS, and can also respond to incoming **emails**.

The system includes:

* **AI Voice Receptionist** (handles voice calls with speech recognition)
* **AI SMS Assistant** (two-way SMS automation)
* **AI Email Assistant** (incoming email parsing + AI-generated replies)
* **Unified Conversation Engine** (one logic for all channels)
* **Database logging** for messages, sessions, and providers
* **Multi-run support** (multiple simultaneous calls/chats)
* **Fallback & escalation logic**

The entire project is designed for **scalability, modularity, and production stability**.

---
## 📌 Overview

This project is a **full AI receptionist system** for businesses. It handles:

- **AI Voice Calls** (Twilio Voice → AI → Voice Response)  
- **AI SMS Conversations** (Twilio SMS → AI → Reply)  
- **Multi-AI Providers** (OpenAI, Gemini, DeepSeek, Groq, etc.)  
- **Conversation Storage** in PostgreSQL  
- **Webhook-Based Real-Time Processing**  
- **Business-specific AI personality** (dental clinic, auto shop, med spa, e-commerce, etc.)

Each business/user can configure:

- AI model provider  
- Phone number  
- Reception workflow  
- Conversation logs  
- Custom system prompt (optional)

---

## 🛠 Tech Stack

| Component | Technology |
|----------|------------|
| Backend Framework | **FastAPI** |
| Database | **PostgreSQL(Neon DB)** + SQLAlchemy ORM |
| AI Providers | **OpenAI, Gemini** (extensible) |
| Telephony | **Twilio Voice + Twilio SMS** |
| Response Voice | **Amazon Polly Voices via Twilio** |
| Server Tunneling | ngrok (development only) |
| Deployment | Docker / Railway / Render / VPS |

---

# For Neon Database
Key points:
- Tenant / Client model (called Tenant) is the owner of channels, KB, messages, etc.
- User model exists for tenant admins/operators (separate from tenant record).
- All channel/message/knowledge/escalation/etc. tables reference tenant_id.
- Use Alembic to generate migrations against Neon. Do NOT run create_all() blindly in prod.

# For Running migration 

- alembic revision -m "migration_commit_message" (in the created file, write the migration code)
- alembic upgrade head

# Run Fast Api 
- uvicorn main:app --reload       

---

## Google Signup/Login (OAuth)

Set these environment variables:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET` (required only for the redirect-based code exchange flow)
- `FRONTEND_URL` (for CORS)

Backend endpoints:

- `GET /api/auth/google/authorize?redirect_uri=...`
- `POST /api/auth/google/exchange`

Secretless alternative (Google Identity Services):

- `POST /api/auth/google/credential` (send the Google ID token as `credential`)
