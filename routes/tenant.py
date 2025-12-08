from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import get_db
from models import Tenant, Channel
from auth.dependencies import get_current_tenant
from schemas.tenant import TenantSetupRequest, TenantSetupResponse
from typing import List, Dict
import json

router = APIRouter(tags=["Tenant"])


def _format_faqs_for_prompt(faqs: List[Dict]) -> str:
    if not faqs:
        return "No FAQs provided."
    lines = []
    for i, faq in enumerate(faqs, start=1):
        q = faq.get("question", "").strip()
        a = faq.get("answer", "").strip()
        if q or a:
            lines.append(f"{i}. Q: {q}\n   A: {a}")
    return "\n".join(lines) if lines else "No FAQs provided."


def _format_services_for_prompt(services: List[Dict]) -> str:
    if not services:
        return "No services listed."
    lines = []
    for svc in services:
        name = svc.get("service", "").strip()
        price = svc.get("price", "").strip()
        if price:
            lines.append(f"- {name} — {price}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def generate_ai_system_prompt(
    business_name: str,
    industry: str,
    tone_of_voice: str,
    greeting_message: str,
    phone_number: str,
    open_time: str,
    close_time: str,
    timezone: str,
    faqs: List[Dict],
    services: List[Dict],
) -> str:
    """
    Create a robust, human-readable system prompt suitable for a multi-tenant AI receptionist.
    This prompt is intentionally explicit about behavior, limits, and required fields to make AI
    responses consistent across different businesses and industries.
    """

    # Normalize inputs to avoid None issues
    business_name = (business_name or "").strip()
    industry = (industry or "general").strip()
    tone_of_voice = (tone_of_voice or "professional and friendly").strip()
    greeting_message = (greeting_message or f"Hello, thank you for contacting {business_name}.").strip()
    phone_number = (phone_number or "").strip()
    open_time = (open_time or "").strip()
    close_time = (close_time or "").strip()
    timezone = (timezone or "").strip()

    formatted_faqs = _format_faqs_for_prompt(faqs)
    formatted_services = _format_services_for_prompt(services)

    prompt = f"""
You are the AI receptionist for "{business_name}", a business in the "{industry}" industry.
Act as a friendly, professional, and helpful customer-facing assistant. Adopt the tone: {tone_of_voice}.

PRIMARY GOALS
1. Route and answer inbound calls and messages.
2. Book, confirm, reschedule, or cancel appointments.
3. Provide accurate, concise answers about services, pricing, and policies using the information below.
4. Capture required contact details and any special requests and store them in the appointment record.

BUSINESS CONTEXT
- Business name: {business_name}
- Industry: {industry}
- Phone number: {phone_number}
- Business hours: {open_time} — {close_time} ({timezone})

GREETING
- Use this greeting when a customer first contacts: "{greeting_message}"

SERVICES OFFERED
{formatted_services}

FREQUENTLY ASKED QUESTIONS
{formatted_faqs}

BEHAVIORAL RULES (must follow)
1. Always greet the customer naturally and warmly on first contact.
2. Ask the customer the purpose of their visit and which service they want.
3. Request a preferred date and time for the appointment. If they give vague info (e.g. "next Wednesday"), ask for a specific date and preferred time range.
4. Check business hours and confirm availability. If requested time is outside hours, propose the next available slots within business hours.
5. Confirm appointment details before scheduling (service, date, time, customer name, phone, email, special requests).
6. Capture and store the customer's name, contact info, service selected, and any special requests in a structured form.
7. If the customer asks about pricing, use the services list above. If price is missing, say: "I'll confirm the price and get back to you."
8. If the customer asks for medical advice, diagnosis, or anything beyond the business services, politely refuse and recommend they consult a qualified professional. Example: "I'm not able to provide medical advice. For medical questions please consult your provider."
9. Escalate to a human agent when:
   - The customer explicitly requests a human.
   - The request is a complaint that cannot be handled by the assistant.
   - The conversation becomes confused or the customer is unhappy.
10. Keep responses concise, professional, polite, and helpful. Use short sentences and confirm next steps clearly.

SAMPLE INTERACTIONS
- Booking:
  AI: "{greeting_message} How can I help you today?"
  Customer: "I'd like to book a facial."
  AI: "Great — which facial would you like from our services list? We offer: {', '.join([s.get('service','') for s in services if s.get('service')])}."
  (Proceed to ask date/time, confirm, and save.)

- Rescheduling:
  AI: "I can help reschedule. What date and time would you prefer?"
  (Check availability; confirm new appointment and send confirmation.)

ERROR HANDLING & POLICIES
- If you do not know an answer, say: "Let me confirm that for you and I'll get back to you shortly."
- Never invent prices, medical details, or legal statements.
- Never share internal notes with the customer.
- Always confirm the final appointment details and tell the customer they will receive SMS/email confirmation if contact details are provided.

OUTPUT REQUIREMENTS
When saving appointment records or returning structured data, ensure you output (or store) the following fields:
- customer_name
- customer_phone
- customer_email (if provided)
- requested_service
- requested_date (ISO format YYYY-MM-DD if possible)
- requested_time (HH:MM)
- timezone
- special_requests
- source_channel (phone / sms / chat / email)

Always ensure the conversation flows naturally while guiding the customer toward confirming an appointment or resolving their inquiry.
"""

    # Strip redundant blank lines/leading/trailing whitespace
    return "\n".join([line.rstrip() for line in prompt.strip().splitlines() if line.strip() != ""])


@router.post("/setup", response_model=TenantSetupResponse)
def setup_tenant(
    setup_data: TenantSetupRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Receive onboarding data after signup and store in database tables.
    Also generate a high-quality AI system prompt for this tenant and persist it.
    """
    try:
        updated_fields = {}

        # Defensive updates: only update if attribute exists on model
        def _set_if_changed(obj, attr_name, new_value, friendly_name=None):
            friendly_name = friendly_name or attr_name
            if hasattr(obj, attr_name):
                old_value = getattr(obj, attr_name)
                if old_value != new_value:
                    setattr(obj, attr_name, new_value)
                    updated_fields[friendly_name] = new_value

        _set_if_changed(current_tenant, "business_name", setup_data.business_name, "business_name")
        _set_if_changed(current_tenant, "primary_phone", setup_data.phone_number, "primary_phone")

        # Business hours
        bh = setup_data.business_hours
        _set_if_changed(current_tenant, "timezone", bh.timezone, "timezone")
        _set_if_changed(current_tenant, "open_time", bh.open_time, "open_time")
        _set_if_changed(current_tenant, "close_time", bh.close_time, "close_time")

        # Update FAQs (store as list of dicts)
        faq_list = [{"question": f.question, "answer": f.answer} for f in setup_data.faq]
        if hasattr(current_tenant, "faqs"):
            if getattr(current_tenant, "faqs") != faq_list:
                setattr(current_tenant, "faqs", faq_list)
                updated_fields["faqs"] = faq_list

        # Update Services (store as list of dicts)
        services_list = [{"service": s.service, "price": s.price} for s in setup_data.services]
        if hasattr(current_tenant, "services"):
            if getattr(current_tenant, "services") != services_list:
                setattr(current_tenant, "services", services_list)
                updated_fields["services"] = services_list

        # Generate AI system prompt
        ai_prompt = generate_ai_system_prompt(
            business_name=setup_data.business_name,
            industry=setup_data.industry,
            tone_of_voice=setup_data.tone_of_voice,
            greeting_message=setup_data.greeting_message,
            phone_number=setup_data.phone_number,
            open_time=bh.open_time,
            close_time=bh.close_time,
            timezone=bh.timezone,
            faqs=faq_list,
            services=services_list,
        )

        if hasattr(current_tenant, "ai_system_prompt"):
            if getattr(current_tenant, "ai_system_prompt") != ai_prompt:
                setattr(current_tenant, "ai_system_prompt", ai_prompt)
                updated_fields["ai_system_prompt"] = "Generated system prompt"

        # Persist tenant updates
        db.add(current_tenant)

        # Insert Channel Records (avoid duplicates)
        created_channels = []
        for channel_input in setup_data.channels:
            existing_channel = db.query(Channel).filter(
                Channel.tenant_id == current_tenant.id,
                Channel.type == channel_input.type,
                Channel.identifier == channel_input.identifier
            ).first()

            if not existing_channel:
                new_channel = Channel(
                    tenant_id=current_tenant.id,
                    type=channel_input.type,
                    identifier=channel_input.identifier
                )
                db.add(new_channel)
                created_channels.append(new_channel)

        # Commit all changes
        db.commit()

        # Refresh to load DB-generated fields like IDs
        db.refresh(current_tenant)
        for ch in created_channels:
            db.refresh(ch)

        return TenantSetupResponse(
            success=True,
            message="Tenant setup completed",
            tenant_id=current_tenant.id,
            updated_fields=updated_fields
        )

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error: " + str(e.orig)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup tenant: " + str(e)
        )
