from fastapi import FastAPI
from routes import email, sms, chat, voice, voice_logs, analytics, appointments, subscription, tenant
from auth import routes as auth_routes

app = FastAPI()

# Include all routers with /api prefix
app.include_router(auth_routes.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(email.router, prefix="/api/email", tags=["Email"])
app.include_router(sms.router, prefix="/api/sms", tags=["SMS"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
app.include_router(voice_logs.router, prefix="/api/voice_logs", tags=["Voice Logs"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(appointments.router, prefix="/api/appointments", tags=["Appointments"])
app.include_router(subscription.router, prefix="/api/subscription", tags=["Subscription"])
app.include_router(tenant.router, prefix="/api/tenant", tags=["Tenant"])

@app.get("/")
def home():
    return {"message": "AI Support Desk Running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)