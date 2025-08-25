from typing import ClassVar, List, Optional, Union
from unittest.mock import Mock

import pytest
from django.db.models import Manager, QuerySet
from django.db.models.fields.files import FileField, ImageFieldFile
from pydantic import AliasPath
from pydantic import __version__ as pydantic_version_str
from pydantic_core import ValidationError

from ninja import Schema
from ninja.files import FileFieldType
from ninja.schema import DjangoGetter, Field, ObjectPatcher

pydantic_version = [int(i) for i in pydantic_version_str.split(".")[:2]]


class FakeManager(Manager):
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def __str__(self):
        return "FakeManager"


class FakeQS(QuerySet):
    def __init__(self, items):
        self._result_cache = items
        self._prefetch_related_lookups = False

    def __str__(self):
        return "FakeQS"


class Tag:
    def __init__(self, id, title):
        self.id = id
        self.title = title


# mocking some users:
class Boss:
    name = "Jane Jackson"
    title = "CEO"


class MockFile:
    def __init__(self):
        self.name = "asdf"


class MockStorage:
    def __init__(self):
        pass

    def url(self, name: str) -> str:
        return name


file_field = FileField(storage=MockStorage())
null_file = ImageFieldFile(None, Mock(), name=None)
non_null_file = ImageFieldFile(MockFile(), file_field, name="mockfile")


class User:
    name = "John Smith"
    group_set = FakeManager([1, 2, 3])
    avatar = null_file
    boss: Optional[Boss] = Boss()

    @property
    def tags(self):
        return FakeQS([Tag(1, "foo"), Tag(2, "bar")])

    def get_boss_title(self):
        return self.boss and self.boss.title


class TagSchema(Schema):
    id: int
    title: str


class UserSchema(Schema):
    name: str
    groups: List[int] = Field(..., alias="group_set")
    tags: List[TagSchema]
    avatar: Optional[FileFieldType] = None


# Tests for new schema without resolvers or aliases
class NewUserSchema(Schema):
    _compatibility = False
    _class_var: bool = False  # Tests ClassVar skipping on Manager validation attachment
    name: str
    groups: List[int] = Field(..., alias="group_set")
    tags: List[TagSchema]
    avatar: Optional[FileFieldType] = None


class UserWithBossSchema(UserSchema):
    _compatibility = True
    boss: Optional[str] = Field(None, alias="boss.name")
    has_boss: bool
    boss_title: Optional[str] = Field(None, alias="get_boss_title")

    @staticmethod
    def resolve_has_boss(obj):
        return bool(obj.boss)


class NewUserWithBossSchema(NewUserSchema):
    _compatibility = False
    boss: Optional[str] = Field(None, alias="boss.name")
    has_boss: bool
    boss_title: Optional[str] = Field(None)

    @staticmethod
    def resolve_has_boss(obj):
        return bool(obj.boss)

    @staticmethod
    def resolve_boss_title(obj):
        return obj.get_boss_title()


class UserWithInitialsSchema(UserWithBossSchema):
    initials: str

    def resolve_initials(self, obj):
        return "".join(n[:1] for n in self.name.split())


class ResolveAttrSchema(Schema):
    "The goal is to test that the resolve_xxx is not callable it should be a regular attribute"

    id: str
    resolve_attr: str


class ClassVarSchema(Schema):
    value: ClassVar[List[int]]


class CompatibleFileSchema(Schema):
    non_null_file: FileFieldType
    null_file: Optional[FileFieldType]


class NewFileSchema(Schema):
    _compatibility = False
    non_null_file: FileFieldType
    null_file: Optional[FileFieldType]


def test_schema():
    user = User()
    schema = UserSchema.from_orm(user)
    assert schema.dict() == {
        "name": "John Smith",
        "groups": [1, 2, 3],
        "tags": [{"id": 1, "title": "foo"}, {"id": 2, "title": "bar"}],
        "avatar": None,
    }


def test_schema_with_image():
    user = User()
    field = Mock()
    field.storage.url = Mock(return_value="/smile.jpg")
    user.avatar = ImageFieldFile(None, field, name="smile.jpg")
    schema = UserSchema.from_orm(user)
    assert schema.dict() == {
        "name": "John Smith",
        "groups": [1, 2, 3],
        "tags": [{"id": 1, "title": "foo"}, {"id": 2, "title": "bar"}],
        "avatar": "/smile.jpg",
    }


@pytest.mark.parametrize(["Schema"], [[UserWithBossSchema], [NewUserWithBossSchema]])
def test_with_boss_schema(Schema):
    user = User()
    schema = Schema.from_orm(user)
    assert schema.dict() == {
        "name": "John Smith",
        "boss": "Jane Jackson",
        "has_boss": True,
        "groups": [1, 2, 3],
        "tags": [{"id": 1, "title": "foo"}, {"id": 2, "title": "bar"}],
        "avatar": None,
        "boss_title": "CEO",
    }

    user_without_boss = User()
    user_without_boss.boss = None
    schema = Schema.from_orm(user_without_boss)
    assert schema.dict() == {
        "name": "John Smith",
        "boss": None,
        "has_boss": False,
        "boss_title": None,
        "groups": [1, 2, 3],
        "tags": [{"id": 1, "title": "foo"}, {"id": 2, "title": "bar"}],
        "avatar": None,
    }

    user = User()
    schema = Schema.from_orm(user)
    assert schema.dict() == {
        "name": "John Smith",
        "boss": "Jane Jackson",
        "boss_title": "CEO",
        "has_boss": True,
        "groups": [1, 2, 3],
        "tags": [{"id": 1, "title": "foo"}, {"id": 2, "title": "bar"}],
        "avatar": None,
    }


@pytest.mark.parametrize(["schema"], [[CompatibleFileSchema], [NewFileSchema]])
def test_file_field_schema(schema):
    first = schema(non_null_file=non_null_file, null_file=null_file)
    assert first.non_null_file is not None and first.null_file is None

    second = schema(non_null_file=non_null_file, null_file=non_null_file)
    assert second.non_null_file is not None and second.null_file is not None

    # FileField validation only works on Pydantic 2.7+
    if pydantic_version[1] >= 7:
        with pytest.raises(ValidationError):
            schema(non_null_file=null_file, null_file=null_file)

    fourth = schema(non_null_file="asdf", null_file=None)
    assert fourth.non_null_file == "asdf" and fourth.null_file is None

    data = {
        "properties": {
            "non_null_file": {"title": "Non Null File", "type": "string"},
            "null_file": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "title": "Null File",
            },
        },
        "required": ["non_null_file", "null_file"],
        "title": schema.__name__,
        "type": "object",
    }
    if pydantic_version[1] <= 6:
        data["properties"]["non_null_file"]["anyOf"] = [
            {"type": "string"},
            {"type": "null"},
        ]
        data["properties"]["non_null_file"].pop("type")

    assert first.json_schema() == data


SKIP_NON_STATIC_RESOLVES = True


@pytest.mark.skipif(SKIP_NON_STATIC_RESOLVES, reason="Lets deal with this later")
def test_with_initials_schema():
    user = User()
    schema = UserWithInitialsSchema.from_orm(user)
    assert schema.dict() == {
        "name": "John Smith",
        "initials": "JS",
        "boss": "Jane Jackson",
        "has_boss": True,
        "groups": [1, 2, 3],
        "tags": [{"id": 1, "title": "foo"}, {"id": 2, "title": "bar"}],
        "avatar": None,
        "boss_title": "CEO",
    }


@pytest.mark.parametrize(
    ["compatibility", "alias_type"],
    [
        [True, "validation_alias"],
        [False, "validation_alias"],
        [True, "alias"],
        [False, "alias"],
    ],
)
def test_complex_template_alias_resolve(compatibility, alias_type):
    class Top:
        class Midddle:
            @property
            def call(self):
                return {"dict": [1, 10]}

        m = Midddle()

    two = {"m.call.dict.1": 10}

    class Three:
        pass

    three = Three()
    setattr(three, "m.call.dict.1", 10)

    four = {"another_value": 10}

    x = Top()

    class AliasSchema(Schema):
        _compatibility = compatibility
        value: int = Field(..., **{alias_type: "m.call.dict.1"})

    assert AliasSchema.from_orm(x).dict() == {"value": 10}
    assert AliasSchema.from_orm(two).dict() == {"value": 10}
    assert AliasSchema.from_orm(three).dict() == {"value": 10}
    with pytest.raises(ValidationError):
        AliasSchema.from_orm(four)


def test_complex_aliaspath_resolve():
    class Top:
        class Midddle:
            @property
            def call(self):
                return {"dict": [1, 10]}

        m = Midddle()

    class AliasSchema(Schema):
        value: int = Field(..., validation_alias=AliasPath("m", "call", "dict", 1))

    x = Top()

    assert AliasSchema.from_orm(x).dict() == {"value": 10}


def test_with_attr_that_has_resolve():
    class Obj:
        id = "1"
        resolve_attr = "2"

    assert ResolveAttrSchema.from_orm(Obj()).dict() == {"id": "1", "resolve_attr": "2"}


def test_django_getter():
    "Coverage for DjangoGetter __repr__ method"

    class Somechema(Schema):
        i: int

    dg = DjangoGetter({"i": 1}, Somechema)
    assert repr(dg) == "<DjangoGetter: {'i': 1}>"


def test_object_patcher():
    """Coverage for ObjectPatcher __repr__ method"""

    op = ObjectPatcher({"i": 1})
    op["i"] = 5
    assert repr(op) == "<ObjectPatcher: {'i': 1} + {'i': 5}>"


def test_schema_validates_assignment_and_reassigns_the_value():
    class ValidateAssignmentSchema(Schema):
        str_var: str
        model_config = {"validate_assignment": True}

    schema_inst = ValidateAssignmentSchema(str_var="test_value")
    schema_inst.str_var = "reassigned_value"
    assert schema_inst.str_var == "reassigned_value"
    try:
        schema_inst.str_var = 5
        raise AssertionError()
    except ValidationError:
        # We expect this error, all is okay
        pass


@pytest.mark.parametrize("test_validate_assignment", [False, None])
def test_schema_skips_validation_when_validate_assignment_False(
    test_validate_assignment: Union[bool, None],
):
    class ValidateAssignmentSchema(Schema):
        str_var: str
        model_config = {"validate_assignment": test_validate_assignment}

    schema_inst = ValidateAssignmentSchema(str_var="test_value")
    try:
        schema_inst.str_var = 5
        assert schema_inst.str_var == 5
    except ValidationError as ve:
        raise AssertionError() from ve
