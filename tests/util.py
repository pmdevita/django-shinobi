import pydantic


def pydantic_ref_fix(data: dict):
    "In pydantic 1.7 $ref was changed to allOf: [{'$ref': ...}] but in 2.9 it was changed back"
    v = tuple(map(int, pydantic.version.version_short().split(".")))
    if v < (1, 7) or v >= (2, 9):
        return data

    result = data.copy()
    if "$ref" in data:
        result["allOf"] = [{"$ref": result.pop("$ref")}]
    return result


def pydantic_arbitrary_dict_fix(data: dict):
    """
    In Pydantic 2.11, arbitrary dictionaries now contain "additionalProperties": True in the schema
    https://github.com/pydantic/pydantic/pull/11392

    :param data: A pre-Pydantic 2.11 arbitrary dictionary schema
    """
    v = tuple(map(int, pydantic.version.version_short().split(".")))
    if v < (2, 11):
        return data

    data["additionalProperties"] = True
    return data
