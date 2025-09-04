# from flask_appbuilder.models.sqla import Model
# from sqlalchemy import (
#     Boolean,
#     Column,
#     DateTime,
#     ForeignKey,
#     Index,
#     Integer,
#     MetaData,
#     String,
#     Table,
#     UniqueConstraint,
#     event,
#     func,
#     select,
# )
# from sqlalchemy.orm import backref, declared_attr, registry, relationship

# class DocClass(Model):
#     """Represents an Airflow user which has roles assigned to it."""

#     __tablename__ = "ab_user"
#     id = Column(Integer, primary_key=True)
#     first_name = Column(String(256), nullable=False)
#     last_name = Column(String(256), nullable=False)
#     username = Column(
#         String(512).with_variant(String(512, collation="NOCASE"), "sqlite"), unique=True, nullable=False
#     )
#     password = Column(String(256))
#     active = Column(Boolean, default=True)
#     email = Column(String(512), unique=True, nullable=False)
#     last_login = Column(DateTime)
#     login_count = Column(Integer)
#     fail_login_count = Column(Integer)
#     roles = relationship("Role", secondary=assoc_user_role, backref="user", lazy="selectin")
#     created_on = Column(DateTime, default=datetime.datetime.now, nullable=True)
#     changed_on = Column(DateTime, default=datetime.datetime.now, nullable=True)

#     @declared_attr
#     def created_by_fk(self):
#         return Column(Integer, ForeignKey("ab_user.id"), default=self.get_user_id, nullable=True)

#     @declared_attr
#     def changed_by_fk(self):
#         return Column(Integer, ForeignKey("ab_user.id"), default=self.get_user_id, nullable=True)

#     created_by = relationship(
#         "User",
#         backref=backref("created", uselist=True),
#         remote_side=[id],
#         primaryjoin="User.created_by_fk == User.id",
#         uselist=False,
#     )
#     changed_by = relationship(
#         "User",
#         backref=backref("changed", uselist=True),
#         remote_side=[id],
#         primaryjoin="User.changed_by_fk == User.id",
#         uselist=False,
#     )

#     @classmethod
#     def get_user_id(cls):
#         try:
#             return g.user.get_id()
#         except Exception:
#             return None

#     @property
#     def is_authenticated(self):
#         return True

#     @property
#     def is_active(self):
#         return self.active

#     @property
#     def is_anonymous(self):
#         return False

#     @property
#     def perms(self):
#         if not self._perms:
#             # Using the ORM here is _slow_ (Creating lots of objects to then throw them away) since this is in
#             # the path for every request. Avoid it if we can!
#             if current_app:
#                 sm = current_app.appbuilder.sm
#                 self._perms: set[tuple[str, str]] = set(
#                     sm.get_session.execute(
#                         select(sm.action_model.name, sm.resource_model.name)
#                         .join(sm.permission_model.action)
#                         .join(sm.permission_model.resource)
#                         .join(sm.permission_model.role)
#                         .where(sm.role_model.user.contains(self))
#                     )
#                 )
#             else:
#                 self._perms = {
#                     (perm.action.name, perm.resource.name) for role in self.roles for perm in role.permissions
#                 }
#         return self._perms

#     def get_id(self):
#         return self.id

#     def get_name(self) -> str:
#         return self.username or self.email or self.user_id

#     def get_full_name(self):
#         return f"{self.first_name} {self.last_name}"

#     def __repr__(self):
#         return self.get_full_name()

#     _perms = None
