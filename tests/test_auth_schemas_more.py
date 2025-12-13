import pytest
from pydantic import ValidationError


def test_phone_model_validation_edge_cases():
    """Тест: PhoneModel валидация граничных случаев"""
    from app.auth.schemas import PhoneModel

    # Валидные номера
    assert PhoneModel(phone_number="+12345").phone_number == "+12345"  # Минимум 5 цифр
    assert (
        PhoneModel(phone_number="+123456789012345").phone_number == "+123456789012345"
    )  # Максимум 15 цифр

    # Невалидные номера
    with pytest.raises(ValidationError):
        PhoneModel(phone_number="12345")  # Нет плюса

    with pytest.raises(ValidationError):
        PhoneModel(phone_number="+1234")  # Меньше 5 цифр

    with pytest.raises(ValidationError):
        PhoneModel(phone_number="+1234567890123456")  # Больше 15 цифр

    with pytest.raises(ValidationError):
        PhoneModel(phone_number="+12abc")  # Нецифровые символы


def test_user_base_phone_validation():
    """Тест: UserBase валидация телефона"""
    from app.auth.schemas import UserBase

    with pytest.raises(ValidationError):
        UserBase(
            email="test@example.com",
            phone_number="invalid",
            first_name="Test",
            last_name="User",
        )

    valid = UserBase(
        email="test@example.com",
        phone_number="+70000000001",
        first_name="Test",
        last_name="User",
    )
    assert valid.phone_number == "+70000000001"


def test_suser_update_phone_none_allowed():
    """Тест: SUserUpdate phone_number может быть None"""
    from app.auth.schemas import SUserUpdate

    # None разрешён
    upd = SUserUpdate(phone_number=None)
    assert upd.phone_number is None

    # Валидный номер
    upd2 = SUserUpdate(phone_number="+70000000001")
    assert upd2.phone_number == "+70000000001"

    # Невалидный номер
    with pytest.raises(ValidationError):
        SUserUpdate(phone_number="invalid")


def test_suser_update_password_without_confirm():
    """Тест: SUserUpdate password без confirm_password -> не хешируется"""
    from app.auth.schemas import SUserUpdate

    # Если password задан, но confirm_password не задан -> ошибка валидации
    with pytest.raises(ValidationError):
        SUserUpdate(password="secret123")

    # Если password не задан -> всё ок
    upd = SUserUpdate()
    assert upd.password is None


def test_suser_update_password_hash_when_provided():
    """Тест: SUserUpdate password хешируется когда задан"""
    from app.auth.schemas import SUserUpdate

    upd = SUserUpdate(password="secret123", confirm_password="secret123")
    assert upd.password != "secret123"  # Должен быть захеширован
    assert upd.password.startswith("$2b$") or upd.password.startswith(
        "$2a$"
    )  # bcrypt hash


def test_suser_info_computed_fields():
    """Тест: SUserInfo computed fields role_name и role_id"""
    from app.auth.models import Role, User
    from app.auth.schemas import SUserInfo

    # Создаём объект с ролью
    role = Role(id=3, name="Admin")
    user = User(
        id=1,
        email="test@example.com",
        phone_number="+70000000001",
        first_name="Test",
        last_name="User",
        role=role,
    )

    info = SUserInfo.model_validate(user)
    assert info.role_id == 3
    assert info.role_name == "Admin"


def test_suser_register_password_mismatch():
    """Тест: SUserRegister несовпадающие пароли -> ValidationError"""
    from app.auth.schemas import SUserRegister

    with pytest.raises(ValidationError) as exc_info:
        SUserRegister(
            email="test@example.com",
            phone_number="+70000000001",
            first_name="Test",
            last_name="User",
            password="secret123",
            confirm_password="different",
        )
    # Проверяем, что ошибка содержит информацию о несовпадении паролей
    errors = exc_info.value.errors()
    assert any(
        "парол" in str(err).lower() or "password" in str(err).lower() for err in errors
    )


def test_suser_register_password_hash():
    """Тест: SUserRegister password хешируется"""
    from app.auth.schemas import SUserRegister

    user = SUserRegister(
        email="test@example.com",
        phone_number="+70000000001",
        first_name="Test",
        last_name="User",
        password="secret123",
        confirm_password="secret123",
    )
    assert user.password != "secret123"  # Должен быть захеширован
    assert user.password.startswith("$2b$") or user.password.startswith(
        "$2a$"
    )  # bcrypt hash
