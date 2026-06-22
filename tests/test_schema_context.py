import pytest

from ninja import NinjaAPI, Schema
from ninja.testing import TestClient


class ResolveWithKWargs(Schema):
    value: int

    @staticmethod
    def resolve_value(obj, **kwargs):
        context = kwargs["context"]
        return obj["value"] + context["extra"]


class ResolveWithContext(Schema):
    value: int

    @staticmethod
    def resolve_value(obj, context):
        return obj["value"] + context["extra"]


class NewResolveWithContext(Schema):
    _compatibility = False
    value: int

    @staticmethod
    def resolve_value(obj, context):
        return obj["value"] + context["extra"]


class DataWithRequestContext(Schema):
    value: dict = None
    other: dict = None

    @staticmethod
    def resolve_value(obj, context):
        result = {k: str(v) for k, v in context.items()}
        assert "request" in result, "request not in context"
        result["request"] = "<request>"  # making it static for easier testing
        return result


api = NinjaAPI()


@api.post("/resolve_ctx", response=DataWithRequestContext)
def resolve_ctx(request, data: DataWithRequestContext):
    return {"other": data.dict()}


client = TestClient(api)


def test_schema_with_kwargs():
    obj = ResolveWithKWargs.model_validate({"value": 10}, context={"extra": 10})
    assert obj.value == 20


@pytest.mark.parametrize(["Schema"], [[ResolveWithContext], [NewResolveWithContext]])
def test_schema_with_context(Schema):
    obj = Schema.model_validate({"value": 2}, context={"extra": 2})
    assert obj.value == 4

    obj = Schema.from_orm({"value": 2}, context={"extra": 2})
    assert obj.value == 4


def test_request_context():
    resp = client.post("/resolve_ctx", json={})
    assert resp.status_code == 200, resp.content
    assert resp.json() == {
        "other": {"value": {"request": "<request>"}, "other": None},
        "value": {"request": "<request>", "response_status": "200"},
    }


# --- Response tuple (result, additional_context) + resolvers with context ---


class ResolveCombinedFromContext(Schema):
    """
    Resolver reads only from context (no obj key) to prove additional_context
    from the view tuple is merged into validation context for resolvers.
    """

    base: int
    combined: int

    @staticmethod
    def resolve_combined(obj, context):
        return obj["base"] + context["addon"]


api_tuple_ctx = NinjaAPI()


@api_tuple_ctx.get("/resolve_tuple_ctx", response=ResolveWithContext)
def resolve_tuple_ctx_resolve_with_context(request):
    # Same pattern as ResolveWithContext tests: value from obj + context["extra"]
    return ({"value": 2}, {"extra": 3})


@api_tuple_ctx.get("/resolve_tuple_ctx_new", response=NewResolveWithContext)
def resolve_tuple_ctx_new_resolve_with_context(request):
    return ({"value": 10}, {"extra": 5})


@api_tuple_ctx.get("/resolve_tuple_ctx_kwargs", response=ResolveWithKWargs)
def resolve_tuple_ctx_kwargs(request):
    return ({"value": 7}, {"extra": 8})


@api_tuple_ctx.get("/resolve_tuple_combined", response=ResolveCombinedFromContext)
def resolve_tuple_combined(request):
    return ({"base": 100}, {"addon": 25})


client_tuple_ctx = TestClient(api_tuple_ctx)


def test_response_tuple_additional_context_resolve_with_context():
    """View returns (body, ctx); staticmethod resolve_* (obj, context) sees ctx."""
    resp = client_tuple_ctx.get("/resolve_tuple_ctx")
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"value": 5}


def test_response_tuple_additional_context_new_resolve_with_context():
    """NewResolveWithContext (_compatibility = False) also receives tuple context."""
    resp = client_tuple_ctx.get("/resolve_tuple_ctx_new")
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"value": 15}


def test_response_tuple_additional_context_resolve_with_kwargs():
    """Resolver with **kwargs still gets context from tuple second element."""
    resp = client_tuple_ctx.get("/resolve_tuple_ctx_kwargs")
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"value": 15}


def test_response_tuple_additional_context_resolver_uses_only_context_keys():
    """additional_context keys are available alongside request/response_status."""
    resp = client_tuple_ctx.get("/resolve_tuple_combined")
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"base": 100, "combined": 125}


# --- 3-tuple (status, body, additional_context) from last commit ---


class NoContextSchema(Schema):
    """Plain schema; no resolver needing context — safe for (status, body) only."""

    value: int


api_three_tuple = NinjaAPI()


@api_three_tuple.get("/three_tuple", response={201: ResolveCombinedFromContext})
def three_tuple_created(request):
    """Explicit status + body + context for model_validate/model_dump."""
    return (201, {"base": 10}, {"addon": 90})


@api_three_tuple.get("/three_tuple_json_only", response={202: ResolveWithContext})
def three_tuple_body_not_polluted(request):
    """Third element must not appear in JSON; only merged into validation context."""
    return (202, {"value": 1}, {"extra": 99})


@api_three_tuple.get(
    "/two_tuple_int_still_status_body", response={203: NoContextSchema}
)
def two_tuple_int_is_status_not_context(request):
    """
    (int, body) must remain status + body only — second element is never
    interpreted as additional_context (no merge into validate context).
    Using a plain schema avoids needing context; if (203, {"value": 5}) were
    misread as (body, context), validation would fail or behave wrongly.
    """
    return (203, {"value": 5})


@api_three_tuple.get("/two_tuple_int_plain", response={204: NoContextSchema})
def two_tuple_int_plain_body(request):
    return (204, {"value": 42})


@api_three_tuple.get(
    "/three_tuple_combined_status", response={205: ResolveCombinedFromContext}
)
def three_tuple_combined_status(request):
    """3-tuple with explicit status; same resolver pattern as ResolveCombinedFromContext."""
    return (205, {"base": 2}, {"addon": 3})


@api_three_tuple.get("/four_tuple", response=list)
def four_tuple_fallthrough(request):
    """4-tuple: neither len==2 nor len==3 branch taken; tuple passed as-is."""
    return (1, 2, 3, 4)


client_three_tuple = TestClient(api_three_tuple)


def test_response_three_tuple_status_and_context_for_validate():
    """(status, body, ctx) applies status and merges ctx for pydantic validate/dump."""
    resp = client_three_tuple.get("/three_tuple")
    assert resp.status_code == 201, resp.content
    assert resp.json() == {"base": 10, "combined": 100}


def test_response_three_tuple_additional_context_not_in_json():
    """HTTP body is only serialized body; context keys stay out of JSON."""
    resp = client_three_tuple.get("/three_tuple_json_only")
    assert resp.status_code == 202, resp.content
    assert resp.json() == {"value": 100}


def test_response_two_tuple_int_first_no_additional_context():
    """(int, body) keeps backward compat: no context merge, body only."""
    resp = client_three_tuple.get("/two_tuple_int_still_status_body")
    assert resp.status_code == 203, resp.content
    assert resp.json() == {"value": 5}


def test_response_two_tuple_int_first_plain():
    """(status, body) with plain schema returns correct status and JSON."""
    resp = client_three_tuple.get("/two_tuple_int_plain")
    assert resp.status_code == 204, resp.content
    assert resp.json() == {"value": 42}


def test_three_tuple_additional_context_merged_into_validate():
    """3-tuple third element is merged into model_validate context (resolver uses addon)."""
    resp = client_three_tuple.get("/three_tuple_combined_status")
    assert resp.status_code == 205, resp.content
    assert resp.json() == {"base": 2, "combined": 5}


def test_four_tuple_falls_through_both_branches():
    """
    4-tuple: neither len==2 nor len==3 branch taken (covers 270->275 branch).
    Tuple is passed through as-is to serialization.
    """
    resp = client_three_tuple.get("/four_tuple")
    assert resp.status_code == 200, resp.content
    assert resp.json() == [1, 2, 3, 4]
