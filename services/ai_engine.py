import os
import openai
from dotenv import load_dotenv

# Optional Gemini SDK
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

load_dotenv()

# OpenAI setup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Gemini setup
GEMINI_API_KEY = os.getenv("GEM_API_KEY")
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Main AI function
def get_ai_response(message: str, provider: str = "openai"):
    """
    :param message: User message
    :param provider: 'openai' or 'gemini'
    :return: ai_reply, confidence_score
    """
    if provider.lower() == "openai":
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": f"Reply as a professional support agent:\n\n{message}"}],
                max_tokens=200
            )
            ai_reply = response["choices"][0]["message"]["content"]
            confidence = 0.9
            return ai_reply, confidence
        except Exception as e:
            print(f"[OpenAI Error]: {e}")
            return f"[OpenAI Error]: {e}", 0.0

    elif provider.lower() == "gemini" and GEMINI_AVAILABLE:
        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(
                f"Reply as a professional support agent:\n\n{message}",
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=300
                )
            )
            # Check if response has valid content
            if response.candidates and response.candidates[0].content.parts:
                ai_reply = response.candidates[0].content.parts[0].text
                confidence = 0.9
                return ai_reply, confidence
            else:
                # Response was blocked or empty
                finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                return f"[Gemini blocked response: {finish_reason}]", 0.0
        except Exception as e:
            print(f"[Gemini API Error]: {e}")
            return f"[Gemini API Error]: {e}", 0.0

    else:
        return "[No valid AI provider configured]", 0.0
