# Tutorial - First Steps

This tutorial shows you how to use **Django Shinobi** with most of its features.

This tutorial assumes that you know at least some basics of the <a href="https://www.djangoproject.com/" target="_blank">Django Framework</a>, like how to create a project and run it.

## Installation

```console
pip install django-shinobi
```

!!! note

    It is not required, but you can also put `ninja` to `INSTALLED_APPS`.
    In that case the OpenAPI/Swagger UI (or Redoc) will be loaded (faster) from the included JavaScript bundle (otherwise the JavaScript bundle comes from a CDN).

## Create a Django project

Start a new Django project (or if you already have an existing Django project, skip to the next step).

```
django-admin startproject myproject
```

If you're starting a new project, it's recommended to set `NINJA_COMPATIBILITY` to `False` to get the 
performance improvements.

```python
# myproject/settings.py

NINJA_COMPATIBILITY = False
```

## Create the API

Let's create a module for our API. Create an `api.py` file in the same directory location as your Django project's root `urls.py`:

!!! note

    For the sake of backwards compatibility, Shinobi still uses the `ninja` package name.

```python
from ninja import NinjaAPI

api = NinjaAPI()
```

Now go to `urls.py` and add the following:

```python hl_lines="3 7"
from django.contrib import admin
from django.urls import path
from .api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
```

## Our first operation

**Django Shinobi** comes with a decorator for each HTTP method (`GET`, `POST`,
`PUT`, etc). In our `api.py` file, let's add in a simple "hello world"
operation.

```python hl_lines="5-7"
from ninja import NinjaAPI

api = NinjaAPI()

@api.get("/hello")
def hello(request):
    return "Hello world"
```

Now browsing to <a href="http://localhost:8000/api/hello"
target="_blank">localhost:8000/api/hello</a> will return a simple JSON
response:
```json
"Hello world"
```

!!! success

    Continue on to **[Parsing input](step2.md)**.