from sqlalchemy import String, Float, DateTime, ForeignKey, func, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base
import uuid


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id"))
    insurer_name: Mapped[str] = mapped_column(String(100))
    product_name: Mapped[str] = mapped_column(String(150))
    policy_no: Mapped[str] = mapped_column(String(50), unique=True)
    policy_type: Mapped[str] = mapped_column(String(50))  # term, health, motor, ulip
    premium_amount: Mapped[float] = mapped_column(Float)
    sum_assured: Mapped[float] = mapped_column(Float, nullable=True)
    next_due_date: Mapped[Date] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Date] = mapped_column(Date, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="policies")
    email_logs: Mapped[list] = relationship("EmailLog", back_populates="policy")
    whatsapp_logs: Mapped[list] = relationship("WhatsAppLog", back_populates="policy")
