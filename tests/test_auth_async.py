import asyncio
from time import sleep
from typing import Any, Optional
from django.conf import settings
from django.http import HttpRequest
from django.contrib.auth import get_user_model
import pytest

from ninja import NinjaAPI
from ninja.decorators import asyncable
from ninja.security import APIKeyQuery, HttpBearer
from ninja.security.apikey import APIKeyCookie
from ninja.testing import TestAsyncClient, TestClient


@pytest.mark.asyncio
async def test_async_view_handles_async_auth_func():
    api = NinjaAPI()

    async def auth(request):
        key = request.GET.get("key")
        if key == "secret":
            return key

    @api.get("/async", auth=auth)
    async def view(request):
        await asyncio.sleep(0)
        return {"key": request.auth}

    client = TestAsyncClient(api)

    # Actual tests --------------------------------------------------

    # without auth:
    res = await client.get("/async")
    assert res.status_code == 401

    # async successful
    res = await client.get("/async?key=secret")
    assert res.json() == {"key": "secret"}


@pytest.mark.asyncio
async def test_async_view_handles_async_auth_cls():
    api = NinjaAPI()

    class Auth:
        async def __call__(self, request):
            key = request.GET.get("key")
            if key == "secret":
                return key

    @api.get("/async", auth=Auth())
    async def view(request):
        await asyncio.sleep(0)
        return {"key": request.auth}

    client = TestAsyncClient(api)

    # Actual tests --------------------------------------------------

    # without auth:
    res = await client.get("/async")
    assert res.status_code == 401

    # async successful
    res = await client.get("/async?key=secret")
    assert res.json() == {"key": "secret"}


@pytest.mark.asyncio
async def test_async_view_handles_multi_auth():
    api = NinjaAPI()

    def auth_1(request):
        return None

    async def auth_2(request):
        return None

    async def auth_3(request):
        key = request.GET.get("key")
        if key == "secret":
            return key

    @api.get("/async", auth=[auth_1, auth_2, auth_3])
    async def view(request):
        await asyncio.sleep(0)
        return {"key": request.auth}

    client = TestAsyncClient(api)

    res = await client.get("/async?key=secret")
    assert res.json() == {"key": "secret"}


@pytest.mark.asyncio
async def test_async_view_handles_auth_errors():
    api = NinjaAPI()

    async def auth(request):
        raise Exception("boom")

    @api.get("/async", auth=auth)
    async def view(request):
        await asyncio.sleep(0)
        return {"key": request.auth}

    @api.exception_handler(Exception)
    def on_custom_error(request, exc):
        return api.create_response(request, {"custom": True}, status=401)

    client = TestAsyncClient(api)

    res = await client.get("/async?key=secret")
    assert res.json() == {"custom": True}


@pytest.mark.asyncio
async def test_sync_authenticate_method():
    class KeyAuth(APIKeyQuery):
        async def authenticate(self, request, key):
            await asyncio.sleep(0)
            if key == "secret":
                return key

    api = NinjaAPI(auth=KeyAuth())

    @api.get("/async")
    async def async_view(request):
        return {"auth": request.auth}

    client = TestAsyncClient(api)

    res = await client.get("/async")  # NO key
    assert res.json() == {"detail": "Unauthorized"}

    res = await client.get("/async?key=secret")
    assert res.json() == {"auth": "secret"}


def test_async_authenticate_method_in_sync_context():
    class KeyAuth(APIKeyQuery):
        async def authenticate(self, request, key):
            await asyncio.sleep(0)
            if key == "secret":
                return key

    api = NinjaAPI(auth=KeyAuth())

    @api.get("/sync")
    def sync_view(request):
        return {"auth": request.auth}

    client = TestClient(api)

    res = client.get("/sync")  # NO key
    assert res.json() == {"detail": "Unauthorized"}

    res = client.get("/sync?key=secret")
    assert res.json() == {"auth": "secret"}


@pytest.mark.asyncio
async def test_async_with_bearer():
    class BearerAuth(HttpBearer):
        async def authenticate(self, request, key):
            await asyncio.sleep(0)
            if key == "secret":
                return key

    api = NinjaAPI(auth=BearerAuth())

    @api.get("/async")
    async def async_view(request):
        return {"auth": request.auth}

    client = TestAsyncClient(api)

    res = await client.get("/async")  # NO key
    assert res.json() == {"detail": "Unauthorized"}

    res = await client.get("/async", headers={"Authorization": "Bearer secret"})
    assert res.json() == {"auth": "secret"}


@pytest.mark.asyncio
async def test_hybrid_auth_async_with_bearer():
    class BearerAuth(HttpBearer):
        @asyncable
        def authenticate(self, request, key):
            raise Exception("This should not be called")

        @authenticate.asynchronous
        async def authenticate(self, request, key):
            await asyncio.sleep(0)
            if key == "secret":
                return key

    api = NinjaAPI(auth=BearerAuth())

    @api.get("/async")
    async def async_view(request):
        return {"auth": request.auth}

    client = TestAsyncClient(api)

    res = await client.get("/async")  # NO key
    assert res.json() == {"detail": "Unauthorized"}

    res = await client.get("/async", headers={"Authorization": "Bearer secret"})
    assert res.json() == {"auth": "secret"}


def test_hyrbid_auth_sync_with_bearer():
    class BearerAuth(HttpBearer):
        @asyncable
        def authenticate(self, request, key):
            sleep(0)
            if key == "secret":
                return key

        @authenticate.asynchronous
        async def authenticate(self, request, key):
            raise Exception("This should not be called")

    api = NinjaAPI(auth=BearerAuth())

    @api.get("/sync")
    def sync_view(request):
        return {"auth": request.auth}

    client = TestClient(api)

    res = client.get("/sync")  # NO key
    assert res.json() == {"detail": "Unauthorized"}

    res = client.get("/sync", headers={"Authorization": "Bearer secret"})
    assert res.json() == {"auth": "secret"}


@pytest.mark.asyncio
async def test_asyncable_handle_sync_with_bearer(db):

    User = get_user_model()
    class SessionAuth(APIKeyCookie):
        param_name: str = settings.SESSION_COOKIE_NAME

        def authenticate(self, request: HttpRequest, key: Optional[str]) -> Optional[Any]:
            user = User.objects.get(username="test")
            if user.is_authenticated:
                request.user = user
                return request.user

            return None

    user = await User.objects.acreate(username="test")
    api = NinjaAPI(auth=SessionAuth())

    @api.get("/async")
    async def async_view(request):
        return {"user": request.user.username}

    client = TestAsyncClient(api)

    res = await client.get("/async")  # NO key
    assert res.json() == {"user": "test"}
