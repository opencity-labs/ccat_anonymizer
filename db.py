from sqlalchemy import String, create_engine, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import List

class Base(DeclarativeBase):
    pass

class AllowedEntity(Base):
    __tablename__ = 'allowed_entity'
    text: Mapped[str] = mapped_column(String(256), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    sources: Mapped[List["EntitySource"]] = relationship(back_populates="entity", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f'AllowedEntity(text={self.text!r}, entity_type={self.entity_type!r})'

class EntitySource(Base):
    __tablename__ = 'entity_source'
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_text: Mapped[str] = mapped_column(ForeignKey("allowed_entity.text"))
    source: Mapped[str] = mapped_column(String(512))
    
    entity: Mapped["AllowedEntity"] = relationship(back_populates="sources")

    def __repr__(self) -> str:
        return f'EntitySource(entity_text={self.entity_text!r}, source={self.source!r})'

def get_engine(db_path: str):
    return create_engine(f"sqlite:///{db_path}")
