from fastapi import FastAPI
from routes import email, sms, chat, voice, voice_logs, analytics, appointments
from auth import routes as auth_routes

app = FastAPI()
app.include_router(auth_routes.router)
app.include_router(email.router, prefix="/email", tags=["Email"])
app.include_router(sms.router, prefix="/sms", tags=["SMS"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(voice.router, prefix="/voice", tags=["Voice"])
app.include_router(voice_logs.router, prefix="/voice", tags=["Voice Logs"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])

@app.get("/")
def home():
    return {"message": "AI Support Desk Running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)