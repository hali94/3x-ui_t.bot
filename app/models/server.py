from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.security.encryption import encrypt_value, decrypt_value


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    xui_url: Mapped[str] = mapped_column(String(512), nullable=False)
    xui_username: Mapped[str] = mapped_column(String(255), nullable=False)
    _xui_password_encrypted: Mapped[str] = mapped_column("xui_password_encrypted", Text, nullable=False)
    default_inbound_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="server")

    @property
    def xui_password(self) -> str:
        return decrypt_value(self._xui_password_encrypted)

    @xui_password.setter
    def xui_password(self, value: str) -> None:
        self._xui_password_encrypted = encrypt_value(value)

    def __repr__(self) -> str:
        return f"<Server id={self.id} name={self.name} url={self.xui_url}>"
