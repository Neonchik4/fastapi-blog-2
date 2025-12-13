from typing import ClassVar

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import User
from app.dao.database import Base, str_uniq


# Промежуточная таблица для связи Many-to-Many
class BlogTag(Base):
    # Base.__tablename__ объявлен через @declared_attr, mypy трактует его как Callable[..., str].
    # Для таблицы-связки задаём явное имя и игнорируем типовую несовместимость (на рантайм не влияет).
    __tablename__: ClassVar[str] = "blog_tags"  # type: ignore[assignment]

    blog_id: Mapped[int] = mapped_column(
        ForeignKey("blogs.id", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (UniqueConstraint("blog_id", "tag_id", name="uq_blog_tag"),)


class Blog(Base):
    title: Mapped[str_uniq]
    author: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="blogs")
    content: Mapped[str] = mapped_column(Text)
    short_description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="published", server_default="published")

    tags: Mapped[list["Tag"]] = relationship(
        secondary="blog_tags", back_populates="blogs"
    )


class Tag(Base):
    name: Mapped[str] = mapped_column(String(50), unique=True)

    blogs: Mapped[list["Blog"]] = relationship(
        secondary="blog_tags", back_populates="tags"
    )
