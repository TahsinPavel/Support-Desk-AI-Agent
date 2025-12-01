from fastapi import FastAPI
from routes import email, sms, chat, voice

app = FastAPI()
app.include_router(email.router, prefix="/email")
app.include_router(sms.router, prefix="/sms", tags=["SMS"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(voice.router, prefix="/voice", tags=["Voice"])

@app.get("/")
def home():
    return {"message": "AI Support Desk Running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)



