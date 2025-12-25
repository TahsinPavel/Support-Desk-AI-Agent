import json
import re
from html.parser import HTMLParser
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from auth.dependencies import get_current_tenant
from config import settings
from models import Tenant
from schemas.scraper import ScraperRequest, ScraperResponse

import google.genai as genai
from google.genai import types

router = APIRouter(tags=["Scraper"])


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        if data and data.strip():
            self._chunks.append(data.strip())

    def get_text(self) -> str:
        return "\n".join(self._chunks)


def _strip_html_to_text(html: str) -> str:
    # Remove script/style blocks first to reduce noise.
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)

    parser = _HTMLTextExtractor()
    parser.feed(html)
    text = parser.get_text()

    # Normalize whitespace a bit.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_json_object(text: str) -> Any:
    """Best-effort extraction of JSON from model output (object or array)."""
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to find the first JSON object/array in the response.
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if not match:
        raise ValueError("No JSON found")

    candidate = match.group(1)
    return json.loads(candidate)


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return str(value).strip() or None


def _pick_first(d: dict, keys: list[str]) -> Optional[str]:
    for k in keys:
        if k in d:
            v = _coerce_str(d.get(k))
            if v:
                return v
    return None


def _normalize_faqs(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []

    cleaned: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        question = _pick_first(item, ["question", "q", "prompt"]) or ""
        answer = _pick_first(item, ["answer", "a", "response"]) or ""
        question = question.strip()
        answer = answer.strip()
        if question and answer:
            cleaned.append({"question": question, "answer": answer})
    return cleaned


def _normalize_services(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []

    cleaned: list[dict] = []
    for item in raw:
        if isinstance(item, str):
            name = item.strip()
            if name:
                cleaned.append({"service": name, "price": None})
            continue

        if not isinstance(item, dict):
            continue

        service = _pick_first(item, ["service", "name", "title", "service_name"]) or ""
        price = _pick_first(item, ["price", "cost", "rate", "starting_price", "from"])  # may be None
        service = service.strip()
        if service:
            cleaned.append({"service": service, "price": price})
    return cleaned


def _get_gemini_client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GEMINI_API_KEY is not configured",
        )
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _build_generate_config(system_instruction: str) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2,
        # Give enough budget to avoid truncating JSON while still bounded.
        max_output_tokens=2000,
        response_mime_type="application/json",
    )


def _gemini_extract_json(
    client: genai.Client,
    model: str,
    system_instruction: str,
    prompt_obj: dict,
) -> tuple[dict, str]:
    """Call Gemini and return (json_object, raw_text). Retries once with a repair prompt."""

    def _call(prompt_text: str) -> str:
        result = client.models.generate_content(
            model=model,
            contents=[prompt_text],
            config=_build_generate_config(system_instruction),
        )
        return (result.text or "").strip()

    raw_text = _call(json.dumps(prompt_obj, ensure_ascii=False))
    try:
        parsed = _extract_json_object(raw_text)
    except Exception:
        # Repair pass: ask the model to output valid JSON only.
        repair_instruction = (
            "You fix malformed JSON. Return ONLY valid, minified JSON. "
            "Do not add any commentary or markdown. Do not invent new fields. "
            "Escape all newlines as \\n inside string values."
        )
        repair_prompt = {
            "task": "Repair the following content into valid JSON.",
            "malformed_json": raw_text[:12000],
        }
        repaired_text = _call(json.dumps(repair_prompt, ensure_ascii=False))
        try:
            parsed = _extract_json_object(repaired_text)
            raw_text = repaired_text
        except Exception as e2:
            raise ValueError(str(e2))

    # Some models may return a top-level array; pick first object if so.
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        parsed = parsed[0]
    if not isinstance(parsed, dict):
        raise ValueError("JSON was not an object")
    return parsed, raw_text


@router.post("", response_model=ScraperResponse)
async def scrape_business_info(
    payload: ScraperRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Scrape a public Google Maps link or website URL and extract structured onboarding data.

    Returns: opening/closing time, timezone, FAQs, and services.
    """
    # Auth is required to avoid turning this into an open proxy.
    _ = current_tenant

    url = str(payload.url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch URL: {e}",
        )

    # Keep prompt size bounded.
    html = html[:250_000]
    page_text = _strip_html_to_text(html)
    page_text = page_text[:80_000]

    business_hint = (payload.business_name or "").strip()

    system_instruction = (
        "You extract business onboarding data from messy web page text. "
        "Return ONLY valid JSON (no markdown, no code fences). "
        "Return MINIFIED JSON (single line). "
        "Do not include raw newlines inside string values; use \\n escapes if needed. "
        "Keep FAQ answers concise (<= 240 chars). Return at most 10 FAQs and 20 services."
    )

    user_prompt = {
        "source_url": url,
        "business_name_hint": business_hint or None,
        "task": "Extract business timezone, opening time, closing time, FAQs, and services.",
        "output_requirements": {
            "timezone": "IANA timezone if confidently determinable (e.g. 'America/New_York'), else null",
            "open_time": "HH:MM 24-hour format if there is a single daily opening time, else null",
            "close_time": "HH:MM 24-hour format if there is a single daily closing time, else null",
            "faqs": "Array of {question, answer}. If none, empty array.",
            "services": "Array of {service, price}. price can be null if not available. If none, empty array.",
            "notes": "Short string if the data is ambiguous or incomplete, else null",
        },
        "page_text": page_text,
    }

    client = _get_gemini_client()

    try:
        data, raw_text = _gemini_extract_json(
            client=client,
            model="gemini-2.5-flash",
            system_instruction=system_instruction,
            prompt_obj=user_prompt,
        )
    except Exception as e:
        print(
            "[scraper] Gemini output was not parseable JSON after repair:",
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to parse Gemini JSON output: {str(e)}",
        )

    # Normalize and validate with Pydantic.
    response_payload = {
        "source_url": url,
        "extracted_business_name": _coerce_str(data.get("extracted_business_name") or data.get("business_name")),
        "timezone": _coerce_str(data.get("timezone")),
        "open_time": _coerce_str(data.get("open_time")),
        "close_time": _coerce_str(data.get("close_time")),
        "faqs": _normalize_faqs(data.get("faqs")),
        "services": _normalize_services(data.get("services")),
        "notes": _coerce_str(data.get("notes")),
    }

    # Print extracted JSON so you can see it in the server terminal.
    try:
        pretty = json.dumps(response_payload, ensure_ascii=False)
        print("[scraper] extracted_json:", pretty)
    except Exception as _e:
        print("[scraper] extracted_json: <failed to serialize>")

    try:
        return ScraperResponse.model_validate(response_payload)
    except Exception as e:
        # Best-effort fallback: return minimal valid structure rather than failing onboarding.
        print("[scraper] Gemini returned invalid shape after normalization:", str(e))
        print("[scraper] Gemini raw_output_snippet:", (raw_text or "")[:2000])
        response_payload["notes"] = (response_payload.get("notes") or "").strip() or "Extraction returned incomplete/invalid fields; returning best-effort result."
        response_payload["faqs"] = response_payload.get("faqs") or []
        response_payload["services"] = response_payload.get("services") or []
        return ScraperResponse(
            source_url=payload.url,
            extracted_business_name=response_payload.get("extracted_business_name"),
            timezone=response_payload.get("timezone"),
            open_time=response_payload.get("open_time"),
            close_time=response_payload.get("close_time"),
            faqs=response_payload.get("faqs"),
            services=response_payload.get("services"),
            notes=response_payload.get("notes"),
        )
