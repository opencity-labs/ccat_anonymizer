from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class AllowedEntity(Base):
    __tablename__ = 'allowed_entity'
    text: Mapped[str] = mapped_column(String(256), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64))

    def __repr__(self) -> str:
        return f'AllowedEntity(text={self.text!r}, entity_type={self.entity_type!r})'

def get_engine(db_path: str):
    return create_engine(f"sqlite:///{db_path}")
