"""Response schema for the tenant Owner/Admin WhatsApp test-send endpoint.

No request body fields exist for the recipient — the endpoint takes no
caller-supplied phone number at all (see whatsapp_test_send_service.py).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class WhatsAppTestSendResponse(BaseModel):
    delivery_id: uuid.UUID | None = None
    masked_recipient: str | None = None
    status: str
    provider: str
    template_key: str
    provider_message_id: str | None = None
    safe_error: str | None = None
