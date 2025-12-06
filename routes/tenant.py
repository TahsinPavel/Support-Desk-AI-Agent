from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import get_db
from models import Tenant, Channel
from auth.dependencies import get_current_tenant
from schemas.tenant import TenantSetupRequest, TenantSetupResponse
from typing import List
import json

router = APIRouter(tags=["Tenant"])


def generate_ai_system_prompt(business_name: str, industry: str, tone_of_voice: str, 
                            greeting_message: str, website: str, phone_number: str,
                            open_time: str, close_time: str, timezone: str, faqs: List[dict]) -> str:
    """Generate a structured AI system prompt based on tenant information."""
    
    # Format FAQs
    formatted_faqs = "\n".join([f"Q: {faq['question']}\nA: {faq['answer']}" for faq in faqs])
    
    prompt = f"""You are the AI receptionist for {business_name}, a business in the {industry} sector.

Your tone of voice should be: {tone_of_voice}
Your greeting message is: "{greeting_message}"

Business information:
- Website: {website}
- Phone: {phone_number}
- Business hours: {open_time} - {close_time} ({timezone})

Frequently Asked Questions:
{formatted_faqs if formatted_faqs else "No FAQs provided."}

Your role:
- Respond politely and professionally
- Follow the greeting message
- Stay within business hours rules
- If user asks about services you don't know, say "Let me confirm that for you."
- Escalate to a human when appropriate
- Be helpful and concise in your responses"""

    return prompt


@router.post("/setup", response_model=TenantSetupResponse)
def setup_tenant(
    setup_data: TenantSetupRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Receive onboarding data after signup and store in database tables."""
    
    try:
        # 1. Update Tenant Table
        updated_fields = {}
        
        if current_tenant.business_name != setup_data.business_name:
            current_tenant.business_name = setup_data.business_name
            updated_fields["business_name"] = setup_data.business_name
            
        if current_tenant.primary_phone != setup_data.phone_number:
            current_tenant.primary_phone = setup_data.phone_number
            updated_fields["primary_phone"] = setup_data.phone_number
            
        if current_tenant.timezone != setup_data.business_hours.timezone:
            current_tenant.timezone = setup_data.business_hours.timezone
            updated_fields["timezone"] = setup_data.business_hours.timezone
            
        if current_tenant.open_time != setup_data.business_hours.open_time:
            current_tenant.open_time = setup_data.business_hours.open_time
            updated_fields["open_time"] = setup_data.business_hours.open_time
            
        if current_tenant.close_time != setup_data.business_hours.close_time:
            current_tenant.close_time = setup_data.business_hours.close_time
            updated_fields["close_time"] = setup_data.business_hours.close_time
            
        # Update FAQs
        faq_list = [{"question": faq.question, "answer": faq.answer} for faq in setup_data.faq]
        if current_tenant.faqs != faq_list:
            current_tenant.faqs = faq_list
            updated_fields["faqs"] = faq_list
            
        # Generate and update AI system prompt
        ai_prompt = generate_ai_system_prompt(
            business_name=setup_data.business_name,
            industry=setup_data.industry,
            tone_of_voice=setup_data.tone_of_voice,
            greeting_message=setup_data.greeting_message,
            website=setup_data.website,
            phone_number=setup_data.phone_number,
            open_time=setup_data.business_hours.open_time,
            close_time=setup_data.business_hours.close_time,
            timezone=setup_data.business_hours.timezone,
            faqs=faq_list
        )
        
        if current_tenant.ai_system_prompt != ai_prompt:
            current_tenant.ai_system_prompt = ai_prompt
            updated_fields["ai_system_prompt"] = "Generated system prompt"
            
        # Update tenant in database
        db.add(current_tenant)
        
        # 2. Insert Channel Records
        created_channels = []
        for channel_input in setup_data.channels:
            # Check if channel already exists
            existing_channel = db.query(Channel).filter(
                Channel.tenant_id == current_tenant.id,
                Channel.type == channel_input.type,
                Channel.identifier == channel_input.identifier
            ).first()
            
            if not existing_channel:
                # Create new channel
                new_channel = Channel(
                    tenant_id=current_tenant.id,
                    type=channel_input.type,
                    identifier=channel_input.identifier
                )
                db.add(new_channel)
                created_channels.append(new_channel)
        
        # Commit all changes
        db.commit()
        
        # Refresh objects to get IDs
        db.refresh(current_tenant)
        for channel in created_channels:
            db.refresh(channel)
            
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