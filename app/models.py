from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Text, ForeignKey


class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    SQLAlchemy uses this to keep track of tables and mappings.
    """
    pass


class Pokemon(Base):
    """
    ORM model for the 'pokemon' table.

    Mirrors the required schema :
    - pokemon_id (Primary Key)
    - name
    - base_experience
    - height
    - order
    - weight
    - location_area_encounters
    """
    __tablename__ = "pokemon"

    pokemon_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    base_experience: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    # 'order' is a reserved word in SQL, so we specify the column name explicitly
    order: Mapped[int | None] = mapped_column("order", Integer)
    weight: Mapped[int | None] = mapped_column(Integer)
    location_area_encounters: Mapped[str | None] = mapped_column(Text)
    # Relationship: one Pokemon → many types
    location_name: Mapped[str | None] = mapped_column(Text)
    
    nature: Mapped[str | None] = mapped_column(Text)
    types: Mapped[list["PokemonType"]] = relationship(
        back_populates="pokemon",
        cascade="all, delete-orphan",
    )
    
class PokemonType(Base):
    """
    ORM model for the 'pokemon_types' table.

    Each row represents one type belonging to one Pokemon.
    Composite Primary Key ensures we don't store duplicates.
    """
    __tablename__ = "pokemon_types"

    pokemon_id: Mapped[int] = mapped_column(
        ForeignKey("pokemon.pokemon_id", ondelete="CASCADE"),
        primary_key=True,
    )
    type_name: Mapped[str] = mapped_column(String, primary_key=True)
    type_url: Mapped[str] = mapped_column(Text, nullable=False)

    pokemon: Mapped[Pokemon] = relationship(
        back_populates="types",
    )
