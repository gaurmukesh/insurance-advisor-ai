import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class Product(Base):
    """A generic insurer product (e.g. 'HDFC Click2Protect'), extracted from
    its spec-sheet PDF at ingestion time -- distinct from a client's actual
    issued Policy row."""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("insurer_name", "product_name", name="uq_product_identity"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    insurer_name: Mapped[str] = mapped_column(String(100))
    product_name: Mapped[str] = mapped_column(String(150))
    product_type: Mapped[str] = mapped_column(String(50))
    source_pdf: Mapped[str] = mapped_column(String(255))
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending")
    extracted_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    raw_extraction_json: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    coverages: Mapped[list["CoverageItem"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    exclusions: Mapped[list["ExclusionItem"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class CoverageItem(Base):
    __tablename__ = "coverage_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(String, ForeignKey("products.id", ondelete="CASCADE"))
    benefit_name: Mapped[str] = mapped_column(String(150))
    benefit_category: Mapped[str] = mapped_column(String(50))
    coverage_amount_text: Mapped[str] = mapped_column(String(200), nullable=True)
    sub_limit_note: Mapped[str] = mapped_column(String(300), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="coverages")


class ExclusionItem(Base):
    __tablename__ = "exclusion_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(String, ForeignKey("products.id", ondelete="CASCADE"))
    exclusion_text: Mapped[str] = mapped_column(String(500))
    exclusion_category: Mapped[str] = mapped_column(String(50))

    product: Mapped["Product"] = relationship(back_populates="exclusions")


class PolicyProductLink(Base):
    """Links a client's actual owned Policy row to the Product it matches, so
    agents can join client -> policy -> product -> coverage/exclusion.
    A row always exists once a Policy is created (match_method='unmatched'
    when no Product matches yet), so "not linked" and "not yet attempted"
    are distinguishable."""

    __tablename__ = "policy_product_link"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_id: Mapped[str] = mapped_column(
        String, ForeignKey("policies.id", ondelete="CASCADE"), unique=True
    )
    product_id: Mapped[str] = mapped_column(
        String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    match_method: Mapped[str] = mapped_column(String(20))
    matched_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
