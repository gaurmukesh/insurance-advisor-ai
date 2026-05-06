from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base
import uuid


class EmailLog(Base):
    __tablename__ = "email_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id"))
    policy_id: Mapped[str] = mapped_column(String, ForeignKey("policies.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(String(5000))
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent, failed, opened
    sent_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    opened_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)

    policy: Mapped["Policy"] = relationship("Policy", back_populates="email_logs")
