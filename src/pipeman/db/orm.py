import sqlalchemy as sa
import sqlalchemy.orm as orm
from sqlalchemy.ext.declarative import declared_attr
import json

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

user_organization = sa.Table(
    "user_organization",
    Base.metadata,
    sa.Column("user_id", sa.ForeignKey("user.id"), index=True),
    sa.Column("organization_id", sa.ForeignKey("organization.id"), index=True)
)


class _BaseModel(object):

    @declared_attr
    def __tablename__(cls):
        cls_name = cls.__name__
        table_name = cls_name[0].lower()
        for x in cls_name[1:]:
            if x.isupper():
                table_name += "_"
            table_name += x.lower()
        return table_name

    id = sa.Column(sa.Integer, primary_key=True, nullable=False)


class _DisplayNameModel(_BaseModel):

    short_name = sa.Column(sa.String(255), unique=True, nullable=False)
    display_names = sa.Column(sa.Text, default=None, nullable=True)

    def set_display_name(self, language, display_name):
        dns = {}
        if self.display_names:
            dns = json.loads(self.display_names)
        dns[language] = display_name
        self.display_names = json.dumps(dns)

    def display_name(self, language, fallback_language='en'):
        dns = {}
        if self.display_names:
            dns = json.loads(self.display_names)
        if language in self.display_names:
            return dns[language]
        if fallback_language in self.display_names:
            return dns[fallback_language]
        return self.short_name


class Organization(_DisplayNameModel, Base):

    users = orm.relationship("User", secondary=user_organization, back_populates="organizations")


class User(_BaseModel, Base):

    username = sa.Column(sa.String(255), unique=True, nullable=False)
    display = sa.Column(sa.String(255), nullable=False)
    salt = sa.Column(sa.String(64), nullable=True)
    phash = sa.Column(sa.String(128), nullable=True)
    email = sa.Column(sa.String(1024), nullable=False, index=True)

    groups = orm.relationship("Group", secondary=user_group, back_populates="users")
    organizations = orm.relationship("Organization", secondary=user_organization, back_populates="users")


class Group(_DisplayNameModel, Base):

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


class Entity(_BaseModel, Base):

    entity_type = sa.Column(sa.String(255), nullable=False, index=True)
    data = sa.Column(sa.Text)
    created_date = sa.Column(sa.DateTime)
    modified_date = sa.Column(sa.DateTime)
    display_names = sa.Column(sa.Text, default=None, nullable=True)

    def set_display_name(self, language, display_name):
        dns = {}
        if self.display_names:
            dns = json.loads(self.display_names)
        dns[language] = display_name
        self.display_names = json.dumps(dns)

    def display_name(self, language, fallback_language='en'):
        dns = {}
        if self.display_names:
            dns = json.loads(self.display_names)
        if language in self.display_names:
            return dns[language]
        if fallback_language in self.display_names:
            return dns[fallback_language]
        return f"{self.entity_type}_{self.id}"


class VocabularyTerm(_BaseModel, Base):

    vocabulary_name = sa.Column(sa.String(255), nullable=False, index=True)
    short_name = sa.Column(sa.String(255), nullable=False)
    display_names = sa.Column(sa.Text, default=None, nullable=True)
    descriptions = sa.Column(sa.Text, default=None, nullable=True)
    __table_args__ = (sa.UniqueConstraint("vocabulary_name", "short_name", name="unique_vocab_short_term"),)

    def set_display_name(self, language, display_name):
        dns = {}
        if self.display_names:
            dns = json.loads(self.display_names)
        dns[language] = display_name
        self.display_names = json.dumps(dns)

    def display_name(self, language, fallback_language='en'):
        dns = {}
        if self.display_names:
            dns = json.loads(self.display_names)
        if language in self.display_names:
            return dns[language]
        if fallback_language in self.display_names:
            return dns[fallback_language]
        return self.short_name



