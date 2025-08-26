# Django Shinobi - Fast Django REST Framework

![Django Shinobi](img/hero.png)

Django Shinobi is a web framework for building APIs with Django and Python 3.6+ type hints.

It's a fork of the fantastic **[Django Ninja](https://github.com/vitalik/django-ninja)** library focused on
community-desired features and fixes. Check out the list of [differences](https://pmdevita.github.io/django-shinobi/differences/)
if you're coming from Ninja, as well as the [roadmap](https://github.com/pmdevita/django-shinobi/discussions/6)!


Key features:

 - **Easy**: Designed to be easy to use and intuitive.
 - **FAST execution**: Very high performance thanks to **<a href="https://pydantic-docs.helpmanual.io" target="_blank">Pydantic</a>** and **<a href="guides/async-support/">async support</a>**. 
 - **Fast to code**: Type hints and automatic docs lets you focus only on business logic.
 - **Standards-based**: Based on the open standards for APIs: **OpenAPI** (previously known as Swagger) and **JSON Schema**.
 - **Django friendly**: (obviously) has good integration with the Django core and ORM.
 - **Production ready**: The original Ninja project is used by multiple companies on live projects.

<a href="https://github.com/vitalik/django-ninja-benchmarks" target="_blank">Benchmarks</a>:

![Django Shinobi REST Framework](img/benchmark.png)

## Installation

In your Django project, add Django Shinobi.

```
pip install django-shinobi
```

or start a new project.

```shell
pip install django django-shinobi
django-admin startproject apidemo
```

## Usage


In your Django project, next to urls.py, create a new file called `api.py`.


```python hl_lines="3 5 8 9 10 15"
{!./src/index001.py!}
```


Now go to `urls.py` and add the following:


```Python hl_lines="3 7"
...
from .api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),  # <---------- !
]
```

**That's it !**

Now you've just created an API that:

 - receives an HTTP GET request at `/api/add`
 - takes, validates and type-casts GET parameters `a` and `b`
 - decodes the result to JSON
 - generates an OpenAPI schema for defined operation

### Interactive API docs

Run your Django project

```shell
python manage.py runsever
```

Now go to <a href="http://127.0.0.1:8000/api/docs" target="_blank">http://127.0.0.1:8000/api/docs</a>

You will see the automatic interactive API documentation (provided by <a href="https://github.com/swagger-api/swagger-ui" target="_blank">Swagger UI</a> or <a href="https://github.com/Redocly/redoc" target="_blank">Redoc</a>):


![Swagger UI](docs/docs/img/index-swagger-ui.png)


## Recap

In summary, you declare the types of parameters, body, etc. **once only**, as function parameters.

You do that with standard modern Python types.

You don't have to learn a new syntax, the methods or classes of a specific library, etc.

Just standard **Python 3.6+**.

For example, for an `int`:

```python
a: int
```

or, for a more complex `Item` model:

```python
class Item(Schema):
    foo: str
    bar: float

def operation(a: Item):
    ...
```

... and with that single declaration you get:

* Editor support, including:
    * Completion
    * Type checks
* Validation of data:
    * Automatic and clear errors when the data is invalid
    * Validation, even for deeply nested JSON objects
* <abbr title="also known as: serialization, parsing, marshalling">Conversion</abbr> of input data coming from the network, to Python data and types, and reading from:
    * JSON
    * Path parameters
    * Query parameters
    * Cookies
    * Headers
    * Forms
    * Files
* Automatic, interactive API documentation

## What next?

 - Read the full documentation here - https://pmdevita.github.io/django-shinobi
 - To support this project, please give star it on Github. ![github star](docs/docs/img/github-star.png)
 - Share it [via Twitter](https://twitter.com/intent/tweet?text=Check%20out%20Django%20Shinobi%20-%20Fast%20Django%20REST%20Framework%20-%20https%3A%2F%2Fpmdevita.github.io/django-shinobi)
 - Share your feedback and discuss development on Discord https://discord.gg/ntFTXu7NNv
