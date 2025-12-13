from app.auth.models import Role, User
from app.dao.base import BaseDAO


class UsersDAO(BaseDAO):
    model = User


class RoleDAO(BaseDAO):
    model = Role
