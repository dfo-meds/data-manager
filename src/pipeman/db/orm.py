import sqlalchemy as sa
import sqlalchemy.orm as orm

meta = sa.MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_`%(constraint_name)s`",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

Base = orm.declarative_base(metadata=meta)


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
    permissions = sa.Column(sa.Text)

    users = orm.relationship("User", back_populates="groups", secondary=user_group)

    def add_permission(self, new_perm):
        p = set(self.permissions.split(";"))
        p.add(new_perm)
        self.permissions = ";".join(p)

    def remove_permission(self, perm_name):
        p = set(self.permissions.split(';'))
        if perm_name in p:
            p.remove(perm_name)
        self.permissions = ";".join(p)
