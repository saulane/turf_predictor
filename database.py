from sqlalchemy import create_engine, Column, ForeignKey, String, Integer, select
from sqlalchemy.orm import declarative_base, relationship, Session

Base = declarative_base()

class Cheval(Base):

    __tablename__ = "cheval"

    id = Column(Integer, primary_key=True)
    name = Column(String(30))

    def __repr__(self):
        return f"Cheval({self.id=!r}, {self.name=!r})"

if __name__ == "__main__":
    engine = create_engine("sqlite:///database.sqlite", echo=True, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        hautain = Cheval(name="hautain")
        mangetesmorts = Cheval(name="mangetesmorts")

        session.add_all([hautain, mangetesmorts])
        session.commit()