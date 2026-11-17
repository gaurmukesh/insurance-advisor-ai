import enum
import uuid

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class ClaimStatus(str, enum.Enum):
    approved = "approved"
    partially_approved = "partially_approved"
    rejected = "rejected"
    pending = "pending"


class Claimant(Base):
    """Background profile of the person who filed one or more claims. These
    are the attributes rejection outcomes get correlated against, so they are
    kept as low-cardinality, analysable columns rather than free text."""

    __tablename__ = "claimants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    external_ref: Mapped[str] = mapped_column(String(64), unique=True)
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    gender: Mapped[str] = mapped_column(String(10), nullable=True)
    occupation: Mapped[str] = mapped_column(String(50), nullable=True)
    annual_income: Mapped[float] = mapped_column(Float, nullable=True)
    city_tier: Mapped[str] = mapped_column(String(10), nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=True)
    pre_existing_conditions: Mapped[bool] = mapped_column(Boolean, nullable=True)
    policy_tenure_years: Mapped[float] = mapped_column(Float, nullable=True)
    prior_claims_count: Mapped[int] = mapped_column(Integer, nullable=True)
    purchase_channel: Mapped[str] = mapped_column(String(30), nullable=True)  # agent, online, bancassurance, broker
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    claims: Mapped[list["Claim"]] = relationship(back_populates="claimant")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_no: Mapped[str] = mapped_column(String(64), unique=True)
    claimant_id: Mapped[str] = mapped_column(String, ForeignKey("claimants.id"), index=True)
    insurer_name: Mapped[str] = mapped_column(String(100), nullable=True)
    policy_type: Mapped[str] = mapped_column(String(50), nullable=True)  # health, term, motor, personal_accident
    claim_type: Mapped[str] = mapped_column(String(30), nullable=True)  # cashless, reimbursement, death, accident
    claim_amount: Mapped[float] = mapped_column(Float)
    settled_amount: Mapped[float] = mapped_column(Float, nullable=True)
    filed_date: Mapped[Date] = mapped_column(Date, index=True)
    decision_date: Mapped[Date] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    # The insurer's own remark, as recorded. reason_category is the normalised
    # bucket from app.core.claim_reasons, which is what the analysis groups by.
    decision_reason_text: Mapped[str] = mapped_column(String(1000), nullable=True)
    reason_category: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    reason_classified_by: Mapped[str] = mapped_column(String(10), nullable=True)  # rule, llm, source
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    claimant: Mapped["Claimant"] = relationship(back_populates="claims")
