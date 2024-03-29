import sqlalchemy as sa
import sqlalchemy.orm as orm
from sqlalchemy.ext.declarative import declared_attr
import json
from pipeman.i18n import MultiLanguageString
import enum


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

user_dataset = sa.Table(
    "user_dataset",
    Base.metadata,
    sa.Column("user_id", sa.ForeignKey("user.id"), index=True),
    sa.Column("dataset_id", sa.ForeignKey("dataset.id"), index=True)
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


class _AuditableDateModel:

    created_date = sa.Column(sa.DateTime(timezone=True), default=sa.func.now())
    modified_date = sa.Column(sa.DateTime(timezone=True), default=sa.func.now(), onupdate=sa.func.now())


class _AuditableModel(_AuditableDateModel):

    created_by = sa.Column(sa.ForeignKey("user.id"), nullable=True)


class _DisplayNameModel(_BaseModel):

    short_name = sa.Column(sa.String(255), unique=True, nullable=False)
    display_names = sa.Column(sa.Text, default=None, nullable=True)

    def display(self):
        return MultiLanguageString(json.loads(self.display_names) if self.display_names else {"und": self.short_name})

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


class KeyValue(_BaseModel, Base):

    key = sa.Column(sa.String(256), unique=True, nullable=False)
    value = sa.Column(sa.Text, nullable=True)


class Organization(_DisplayNameModel, _AuditableModel, Base):

    users = orm.relationship("User", secondary=user_organization, back_populates="organizations")
    entities = orm.relationship("Entity", back_populates="organization")
    datasets = orm.relationship("Dataset", back_populates="organization")


class User(_AuditableModel, _BaseModel, Base):

    username = sa.Column(sa.String(255), unique=True, nullable=False)
    display = sa.Column(sa.String(255), nullable=False)
    salt = sa.Column(sa.String(64), nullable=True)
    phash = sa.Column(sa.String(128), nullable=True)
    email = sa.Column(sa.String(1024), nullable=False, index=True)
    allowed_api_access = sa.Column(sa.Boolean, nullable=False, default=False)
    locked_until = sa.Column(sa.DateTime, nullable=True)
    properties = sa.Column(sa.Text, nullable=True)
    language_preference = sa.Column(sa.String, nullable=False, default="en")

    groups = orm.relationship("Group", secondary=user_group, back_populates="users")
    organizations = orm.relationship("Organization", secondary=user_organization, back_populates="users")
    datasets = orm.relationship("Dataset", secondary=user_dataset, back_populates="users")


class UserLoginRecord(_BaseModel, Base):

    username = sa.Column(sa.String(255), nullable=True, index=True)
    attempt_time = sa.Column(sa.DateTime, nullable=False)
    remote_ip = sa.Column(sa.String(16), nullable=False)
    from_api = sa.Column(sa.Boolean, nullable=False)
    error_message = sa.Column(sa.String(255), nullable=True)
    was_success = sa.Column(sa.Boolean, nullable=False)
    was_since_last_clear = sa.Column(sa.Boolean, nullable=False)
    lockable = sa.Column(sa.Boolean, nullable=False)


class APIKey(_BaseModel, _AuditableModel, Base):

    user_id = sa.Column(sa.ForeignKey("user.id"), nullable=False, index=True)
    display = sa.Column(sa.String(1024), nullable=True)
    prefix = sa.Column(sa.String(64), nullable=False, index=True)
    key_hash = sa.Column(sa.String(128), nullable=True)
    key_salt = sa.Column(sa.String(64), nullable=True)
    expiry = sa.Column(sa.DateTime, nullable=True)
    old_key_hash = sa.Column(sa.String(128), nullable=True)
    old_key_salt = sa.Column(sa.String(64), nullable=True)
    old_expiry = sa.Column(sa.DateTime, nullable=True)
    is_active = sa.Column(sa.Boolean, default=True)


class Group(_DisplayNameModel, _AuditableModel, Base):

    permissions = sa.Column(sa.Text)
    restricted_access = sa.Column(sa.Boolean)

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

    def clear_permissions(self):
        self.permissions = ""


class Entity(_BaseModel, _AuditableModel, Base):

    entity_type = sa.Column(sa.String(255), nullable=False, index=True)

    is_deprecated = sa.Column(sa.Boolean)
    organization_id = sa.Column(sa.ForeignKey("organization.id"), nullable=True, index=True)
    display_names = sa.Column(sa.Text, default=None, nullable=True)
    parent_id = sa.Column(sa.Integer, nullable=True, index=True)
    parent_type = sa.Column(sa.String(255), nullable=True, index=True)

    data = orm.relationship("EntityData", back_populates="entity")
    organization = orm.relationship("Organization", back_populates="entities")

    def latest_revision(self):
        latest = None
        for ed in self.data:
            if latest is None or latest.revision_no < ed.revision_no:
                latest = ed
        return latest

    def specific_revision(self, rev_no):
        rev_no = int(rev_no)
        for ed in self.data:
            if ed.revision_no == rev_no:
                return ed

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


class EntityData(_BaseModel, _AuditableModel, Base):

    __table_args__ = (
        sa.UniqueConstraint("entity_id", "revision_no", name="unique_entity_revision_data"),
    )

    entity_id = sa.Column(sa.ForeignKey("entity.id"), nullable=False, index=True)
    revision_no = sa.Column(sa.Integer, nullable=False, index=True)
    data = sa.Column(sa.Text)

    entity = orm.relationship("Entity", back_populates="data")


class VocabularyTerm(_BaseModel, _AuditableModel, Base):

    vocabulary_name = sa.Column(sa.String(255), nullable=False, index=True)
    short_name = sa.Column(sa.String(255), nullable=False)
    display_names = sa.Column(sa.Text, default=None, nullable=True)
    descriptions = sa.Column(sa.Text, default=None, nullable=True)
    __table_args__ = (
        sa.UniqueConstraint("vocabulary_name", "short_name", name="unique_vocab_short_term"),
    )

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


class Dataset(_BaseModel, _AuditableModel, Base):

    is_deprecated = sa.Column(sa.Boolean)
    organization_id = sa.Column(sa.ForeignKey("organization.id"), nullable=True, index=True)
    display_names = sa.Column(sa.Text, default=None, nullable=True)
    profiles = sa.Column(sa.Text)
    pub_workflow = sa.Column(sa.String(255), nullable=False)
    act_workflow = sa.Column(sa.String(255), nullable=False)
    status = sa.Column(sa.String(255), nullable=False)
    security_level = sa.Column(sa.String(255), nullable=False)
    guid = sa.Column(sa.String(255), nullable=False, unique=True)
    activated_item_id = sa.Column(sa.ForeignKey("workflow_item.id"), nullable=True)

    attachments = orm.relationship("Attachment", back_populates="dataset")
    organization = orm.relationship("Organization", back_populates="datasets")
    data = orm.relationship("MetadataEdition", back_populates="dataset")
    users = orm.relationship("User", secondary=user_dataset, back_populates="datasets")

    def latest_revision(self):
        latest = None
        for ed in self.data:
            if latest is None or latest.revision_no < ed.revision_no:
                latest = ed
        return latest

    def latest_published_revision(self):
        latest = None
        for ed in self.data:
            if not ed.is_published:
                continue
            if latest is None or latest.revision_no < ed.revision_no:
                latest = ed
        return latest

    def specific_revision(self, rev_no):
        rev_no = int(rev_no)
        for ed in self.data:
            if ed.revision_no == rev_no:
                return ed

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


class MetadataEdition(_BaseModel, _AuditableModel, Base):

    __table_args__ = (
        sa.UniqueConstraint("dataset_id", "revision_no", name="unique_dataset_revision_data"),
    )

    dataset_id = sa.Column(sa.ForeignKey("dataset.id"), nullable=False, index=True)
    revision_no = sa.Column(sa.Integer, nullable=False, index=True)
    data = sa.Column(sa.Text)
    is_published = sa.Column(sa.Boolean, default=False, nullable=False)
    published_date = sa.Column(sa.DateTime, nullable=True, default=None)
    approval_item_id = sa.Column(sa.ForeignKey("workflow_item.id"), nullable=True)

    dataset = orm.relationship("Dataset", back_populates="data")
    approval_item = orm.relationship("WorkflowItem")


class ConfigRegistry(_BaseModel, _AuditableModel, Base):

    __table_args__ = (
        sa.UniqueConstraint("obj_type", "obj_name", name="unique_registry_name_type"),
    )
    obj_type = sa.Column(sa.String(255), index=True)
    obj_name = sa.Column(sa.String(255), index=True)
    config = sa.Column(sa.Text)


class WorkflowItem(_BaseModel, _AuditableModel, Base):

    context = sa.Column(sa.Text)
    workflow_type = sa.Column(sa.String(255), index=True)
    workflow_name = sa.Column(sa.String(255), index=True)
    object_type = sa.Column(sa.String(255), default="dataset", nullable=True)
    object_id = sa.Column(sa.Integer)
    step_list = sa.Column(sa.Text)
    completed_index = sa.Column(sa.Integer, default=None, nullable=True)
    status = sa.Column(sa.String(255))
    locked_by = sa.Column(sa.String(36))
    locked_since = sa.Column(sa.DateTime)
    step_output = sa.Column(sa.Text)

    decisions = orm.relationship("WorkflowDecision", back_populates="workflow_item")

    created_by_user = orm.relationship("User")


class Attachment(_BaseModel, _AuditableModel, Base):

    file_name = sa.Column(sa.String(1024), nullable=False)
    storage_path = sa.Column(sa.String(1024), nullable=False)
    dataset_id = sa.Column(sa.ForeignKey("dataset.id"), nullable=True, index=True)
    storage_name = sa.Column(sa.String(1024), nullable=True)

    dataset = orm.relationship("Dataset", back_populates="attachments")


class WorkflowDecision(_BaseModel, _AuditableModel, Base):

    workflow_item_id = sa.Column(sa.ForeignKey("workflow_item.id"), nullable=False, index=True)
    step_name = sa.Column(sa.String(255))
    decider_id = sa.Column(sa.String(1024), nullable=False)
    decision = sa.Column(sa.Boolean)
    decision_date = sa.Column(sa.DateTime)
    comments = sa.Column(sa.Text, nullable=True)
    attachment_id = sa.Column(sa.ForeignKey("attachment.id"), nullable=True)

    workflow_item = orm.relationship("WorkflowItem", back_populates="decisions")
    attachment = orm.relationship("Attachment")


class ServerSession(_BaseModel, Base):

    guid = sa.Column(sa.String(1024), nullable=False, unique=True)
    valid_until = sa.Column(sa.DateTime, nullable=False)
    is_valid = sa.Column(sa.Boolean, nullable=False)


class TranslationState(enum.Enum):

    IN_PROGRESS = 0
    SUCCESS = 1
    FAILURE = 2
    DELAYED = 9


class TranslationRequest(_BaseModel, _AuditableDateModel, Base):

    guid = sa.Column(sa.String(1024), nullable=False, index=True)
    lang_key = sa.Column(sa.String(16), nullable=False, index=True)
    source_hash = sa.Column(sa.String(128), nullable=False)
    source_info = sa.Column(sa.Text)
    translation = sa.Column(sa.Text, nullable=True, default=None)
    state = sa.Column(sa.Enum(TranslationState), nullable=False, default=TranslationState.IN_PROGRESS)
    handler_info = sa.Column(sa.Text)
    allow_reuse = sa.Column(sa.Boolean, default=True)
    error_text = sa.Column(sa.Text)

    def set_translation(self, translation_text: str, allow_reuse: bool = True):
        self.translation = translation_text
        self.allow_reuse = allow_reuse
        self.state = TranslationState.SUCCESS

    def mark_failed(self, failed_reason: str):
        self.error_text = failed_reason
        self.allow_reuse = False
        self.state = TranslationState.FAILURE

    def delay(self):
        self.state = TranslationState.DELAYED
