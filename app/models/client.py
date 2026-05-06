from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base
import uuid
import enum


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    interested = "interested"
    converted = "converted"
    lost = "lost"


class RiskAppetite(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    advisor_id: Mapped[str] = mapped_column(String, ForeignKey("advisors.id"))
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), nullable=True)
    phone: Mapped[str] = mapped_column(String(15), nullable=True)
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    income: Mapped[float] = mapped_column(Float, nullable=True)
    family_size: Mapped[int] = mapped_column(Integer, nullable=True)
    risk_appetite: Mapped[str] = mapped_column(String(10), nullable=True)
    goals: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=LeadStatus.new)
    notes: Mapped[str] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    advisor: Mapped["Advisor"] = relationship("Advisor", back_populates="clients")
    policies: Mapped[list] = relationship("Policy", back_populates="client")
    interactions: Mapped[list] = relationship("Interaction", back_populates="client")
