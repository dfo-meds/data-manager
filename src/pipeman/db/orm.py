import sqlalchemy as sa
import sqlalchemy.orm as orm

Base = orm.declarative_base()


# Relational table between users and groups
user_group = sa.Table(
    "user_group",
    Base.metadata,
    sa.Column("user_id", sa.ForeignKey("user.id"), index=True),
    sa.Column("group_id", sa.ForeignKey("group.id"), index=True),
)


class User(Base):

    __tablename__ = "user"

    id = sa.Column(sa.Integer, primary_key=True, nullable=False)
    username = sa.Column(sa.String(255), unique=True, nullable=False)
    display = sa.Column(sa.String(255), nullable=False)
    salt = sa.Column(sa.String(64), nullable=False)
    phash = sa.Column(sa.String(128), nullable=False)
    email = sa.Column(sa.String(1024), nullable=False, index=True)

    groups = orm.relationship("Group", secondary=user_group, back_populates="users")


class Group(Base):

    __tablename__ = "group"

    id = sa.Column(sa.Integer, primary_key=True, nullable=False)
    short_name = sa.Column(sa.String(255), unique=True, nullable=False)
    name_en = sa.Column(sa.Unicode(255), unique=True, nullable=False)
    name_fr = sa.Column(sa.Unicode(255), unique=True, nullable=False)
    permissions = sa.Column(sa.Text)

    users = orm.relationship("User", back_populates="groups", secondary=user_group)

