import os
import logging
from typing import Tuple, Optional, Union, List, Dict
from openai import OpenAI
import google.genai as genai
from dotenv import load_dotenv
from google.genai import types
from datetime import datetime
from dateutil.parser import parse as date_parse
import re

load_dotenv(dotenv_path=os.getenv("ENV_FILE", ".env"))
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
    ai_provider: str = "gemini",
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

def extract_appointment_datetime(text: str) -> Optional[datetime]:
    """
    Extracts date and time from AI response or user text.
    """
    try:
        dt = date_parse(text, fuzzy=True)  # fuzzy=True allows ignoring extra words
        if dt > datetime.utcnow():
            return dt
        return None
    except Exception as e:
        logger.warning(f"Failed to extract datetime from text: {text}. Error: {e}")
        return None

def extract_service(text: str, services_list: Optional[Union[List[str], List[Dict[str, str]]]] = None) -> Optional[str]:
    if not text:
        return None

    text_lower = text.lower()

    # Normalize services_list to a list of strings
    normalized_services: List[str] = []
    if services_list:
        for s in services_list:
            if isinstance(s, dict) and "name" in s:
                normalized_services.append(s["name"].lower())
            elif isinstance(s, str):
                normalized_services.append(s.lower())

        for service in normalized_services:
            if service in text_lower:
                return service  # return the matched service

    # Fallback regex for common service keywords
    match = re.search(r"(facial|massage|consultation|botox|laser|spa)", text_lower)
    if match:
        return match.group(1)

    return None


def parse_appointment_from_user_message(text, tenant_settings=None):
    """
    Extract appointment datetime and service from free text.
    Returns:
        dict: {"datetime": datetime_obj, "service": service_name} or None
    """
    if not text:
        return None

    # --- Extract service name ---
    service_name = None
    if tenant_settings and tenant_settings.get("services"):
        for service in tenant_settings["services"]:
            # Case-insensitive search
            if re.search(r"\b" + re.escape(service) + r"\b", text, re.IGNORECASE):
                service_name = service
                break
    if not service_name:
        # Fallback: just take last word after 'for'
        match = re.search(r"for\s+([a-zA-Z\s]+)", text, re.IGNORECASE)
        if match:
            service_name = match.group(1).strip()

    # --- Extract datetime ---
    appointment_time = parse_date(text, settings={'PREFER_DATES_FROM': 'future'})
    if not appointment_time:
        return None

    return {"datetime": appointment_time, "service": service_name}