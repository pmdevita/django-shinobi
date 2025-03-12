# Migrating from Ninja

Shinobi has made a number of changes on top of Ninja. For those migrating from 
Ninja to Shinobi, this guide exists to bring you up to speed on the fixes and 
and new features.

## Ninja 1.4.0 changes

At the time of writing, Shinobi includes development changes to Ninja that 
have not yet been released on Ninja. You can read the list of them them on the 
[1.4.0a release notes](https://github.com/pmdevita/django-shinobi/releases/tag/v1.4.0a).
A write-up will be completed for them if Shinobi releases 1.4.0 before Ninja.

## Features

### Improved Choices Enum support

[Choices and Enums](/django-shinobi/guides/response/django-pydantic/#choices-and-enums)

When you use the `.choices` option on a Model field in Django,

```python
class NumberEnum(TextChoices):
    ONE = "ONE", "One"
    TWO = "TWO", "Two"
    THREE = "THREE", "Three"

class MyModel(models.Model):
    number = models.CharField(max_length=10, choices=NumberEnum.choices)
```

Ninja will not detect the enum and map the type as just a string.

Shinobi will automatically detect you are using `.choices` and carry that over into your ModelSchema. In the 
OpenAPI schema, it will appear as an [inline enum](https://swagger.io/docs/specification/v3_0/data-models/enums/).

In some cases, it may be useful for an enum to be named and reusable between schemas or fields, particularly if you are 
working with auto-generated OpenAPI clients. Shinobi can directly carry over a `TextChoices` or `IntegerChoices` enum 
by adding the `ChoicesMixin` to it.

!!! info
    `ChoicesMixin` requires Django 5.0+ and Python 3.11+
    Note that `choices` must be set to `NumberEnum`, *not* `NumberEnum.choices`, as shown in the
    following example.

```python
from ninja.enum import ChoicesMixin

class NumberEnum(ChoicesMixin, TextChoices):
    ONE = "ONE", "One"
    TWO = "TWO", "Two"
    THREE = "THREE", "Three"

class MyModel(models.Model):
    number = models.CharField(max_length=10, choices=NumberEnum)
```

This will be published to your OpenAPI schema as a [reusable enum](https://swagger.io/docs/specification/v3_0/data-models/enums/#reusable-enums).


## Bug Fixes

### Primary keys and blanks are now opt-in nullable

A backwards-incompatible change was introduced in Ninja 1.3.0 where `ModelSchema` now 
marks primary key Model Fields and `blank` Model Fields as nullable. This enforcement is 
incorrect, `blank` is a setting that should be used exclusively by Django forms, and 
your primary key should never be null. If you are using your OpenAPI schema to autogenerate 
client libraries, this can cause additional issues as they will now need to perform an 
unnecessary null check every time they interact with a primary key.

This has been reverted to the old behavior. If you still need to mark your primary key 
fields as nullable for some reason, you can use `fields_optional` or set `null=True` 
on the Model Field.

```python
# Ninja 1.3.0

class PKNullable(ModelSchema):
   class Meta:
       model = MyModel
       fields = ["id"]

# Shinobi 1.4.0

class PKNullable(ModelSchema):
    class Meta:
        model = MyModel
        fields = ["id"]
        fields_optional = ["id"]

```


### Foreign keys now work with auto-generated aliases

[Automatic Camel Case Aliases](/django-shinobi/guides/response/config-pydantic/#automatic-camel-case-aliases)

Ninja uses Pydantic's alias feature to handle aliasing between a foreign key Field's 
normal name (`book`) and its field name (`book_id`). However, if you use automatic aliases 
such as `toCamel`, Pydantic will not rewrite the alias for the foreign key field.

Shinobi adds a `@property` field to the Schema so that the normal name can be accessed without 
using Pydantic's aliases, freeing it to be used for other manual or automatically generated aliases.
