from typing import Any, List, Tuple, TypeVar

import django

# Because this isn't supported with Django <5, we need to ignore coverage for
# unsupported versions.

if django.VERSION[0] < 5:  # pragma: no cover

    class NinjaChoicesType(type): ...

    class ChoicesMixin: ...

else:  # pragma: no cover
    from django.db.models.enums import ChoicesType

    class NinjaChoicesType(ChoicesType):  # type: ignore[no-redef]
        @property
        def choices(self) -> "List[Tuple[Any, str]]":
            return NinjaChoicesList(super().choices, choices_enum=self)

    class ChoicesMixin(metaclass=NinjaChoicesType):  # type: ignore[no-redef]
        pass


ListMemberType = TypeVar("ListMemberType")


class NinjaChoicesList(List[ListMemberType]):
    def __init__(
        self, *args: Any, choices_enum: NinjaChoicesType, **kwargs: Any
    ) -> None:  # pragma: no cover
        self.enum = choices_enum
        super().__init__(*args, **kwargs)
