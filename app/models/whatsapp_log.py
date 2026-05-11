from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base
import uuid


class WhatsAppLog(Base):
    __tablename__ = "whatsapp_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id"))
    policy_id: Mapped[str] = mapped_column(String, ForeignKey("policies.id"), nullable=True)
    phone: Mapped[str] = mapped_column(String(20))
    template_name: Mapped[str] = mapped_column(String(100))
    message_body: Mapped[str] = mapped_column(String(1000))
    wa_message_id: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent, failed, delivered, read
    sent_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    policy: Mapped["Policy"] = relationship("Policy", back_populates="whatsapp_logs")
