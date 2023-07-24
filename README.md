# flask-msgspec
[msgspec](https://github.com/jcrist/msgspec) integration for [Flask](https://github.com/pallets/flask)

This project was inspired by the [flask-pydantic](https://github.com/bauerji/flask-pydantic) package created by [bauerji](https://github.com/bauerji) and the [Litestar](https://github.com/litestar-org/litestar) framework, however while the `validate` decorator appears similar to the one found in `flask-pydantic` there are many differences.

## Installation
```shell
pip install flask-msgspec
```

## Usage
Consider this simple example:
```py
class BodyStructWithConstraints(msgspec.Struct):
    foo: Annotated[int, msgspec.Meta(gt=0, le=100)]
    bar: Annotated[list[str | int], msgspec.Meta(min_length=1)]


@app.post(rule="/test/<uuid:uuid_value>")
@validate()
def test_handler(
    uuid_value: UUID,
    query1: float,
    body: BodyStructWithConstraints,
    optional_query: str = "default_value",
) -> dict:
    return locals()
```
Here we have a UUID path parameter, a required query parameter of `float` type, a body of type `BodyStructWithConstraints`, and an optional query parameter which is a `string`, the endpoint will return a `dictionary` of unknown types.

Currently there is only one reserved keyword; `body`. This tries to convert either `request.data` or `request.form` to the specified type.

Similar to how `Litestar` works, keywords that are neither path parameters or reserved keywords are considered query parameters.

The return type can be set either:
- via the `return_model` keyword in `validate` decorator, or
- by annotating the function return type. (`return_model` keyword takes priority)

Sequences/iterables can also be used for return type, e.g.; `list[ResponseModel]`.

The successful response status code can also be changed in two ways:
- via setting the `status_code` keyword in `validate` decorator, or
- by using the standard Flask syntax of returning a tuple.

Returning a tuple with a status code will override the value set by the `status_code` keyword.

As you might have noticed mixing these together most likely will cause issues or just going to be annoying to annotate.\
***Avoid using the standard Flask tuple return syntax to change the status code if you are also using the function return type to annotate the return model. This will cause issues; first with a static type checker, then with the code handling return values and conversion.***\
In my opinion the response model should be set via annotating the return type of the function and if the status code needs to be changed use the `status_code` keyword. Additionally, if you need to set headers, then set both, the return type and status code using the keywords of the `validate` decorator.

You can use `msgspec.Struct`, `dataclass`, and most built-in types natively supported by `msgspec`.

*More examples and others stuff will be added soon:tm:.*
