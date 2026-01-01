from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from routes import email, sms, chat, voice, voice_logs, analytics, appointments, subscription, tenant, pricing, settings as settings_routes, scraper, twilio as twilio_routes
from auth import routes as auth_routes

app = FastAPI()

# Add CORS middleware
# Use frontend URL from environment variable
frontend_url = os.getenv("FRONTEND_URL")
allowed_origins = [frontend_url]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers with /api prefix
app.include_router(auth_routes.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(email.router, prefix="/api/email", tags=["Email"])
app.include_router(sms.router, prefix="/api/sms", tags=["SMS"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
app.include_router(voice_logs.router, prefix="/api/voice_logs", tags=["Voice Logs"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["Settings"])
app.include_router(appointments.router, prefix="/api/appointments", tags=["Appointments"])
app.include_router(subscription.router, prefix="/api/subscription", tags=["Subscription"])
app.include_router(tenant.router, prefix="/api/tenant", tags=["Tenant"])
app.include_router(pricing.router, prefix="/api/pricing", tags=["Pricing"])
app.include_router(scraper.router, prefix="/api/scraper", tags=["Scraper"])
app.include_router(twilio_routes.router, prefix="/api/twilio", tags=["Twilio"])

@app.get("/")
def home():
    return {"message": "AI Support Desk Running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)