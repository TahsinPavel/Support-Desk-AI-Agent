import os
import logging
from typing import Tuple
from openai import OpenAI
import google.genai as genai
from dotenv import load_dotenv
from google.genai import types


load_dotenv()
# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

gemini_client = None

# Load API keys from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize AI clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def get_ai_response(
    message_text: str,
    ai_provider: str = "openai",
    system_prompt: str = "",
    model: str = None,
    temperature: float = 0.7
) -> Tuple[str, float]:
    """
    Returns AI-generated response and confidence score.
    Supports 'openai' and 'gemini'.
    Multi-tenant ready: accepts tenant-specific system_prompt, model, and temperature.
    """
    try:
        if ai_provider.lower() == "openai":
            if not model:
                model = "gpt-4o-mini"  # default OpenAI model

            response = openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message_text}
                ],
                temperature=temperature
            )
            reply = response.choices[0].message.content
            confidence = 0.9  # placeholder, can be replaced with scoring logic

        elif ai_provider.lower() == "gemini":
            if not model:
                model = "gemini-2.5-flash"

            response = gemini_client.models.generate_content(
                model=model,
                contents=[message_text],
                config=types.GenerateContentConfig( 
                    system_instruction=system_prompt, # Use the system_prompt argument
                    temperature=temperature,
                    max_output_tokens=300
                )
            )
            reply = response.text
            confidence = 0.9

        else:
            reply = "AI provider not supported."
            confidence = 0.0

        return reply, confidence

    except Exception as e:
        logger.error(f"AI response error for provider {ai_provider}: {str(e)}")
        return f"[AI Error]: {str(e)}", 0.0
