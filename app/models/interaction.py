from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base
import uuid


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id"))
    interaction_type: Mapped[str] = mapped_column(String(50))  # call, email, whatsapp, meeting
    notes: Mapped[str] = mapped_column(String(2000), nullable=True)
    outcome: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="interactions")
