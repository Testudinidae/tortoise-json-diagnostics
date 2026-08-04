from os import PathLike


type Json = None | bool | int | float | str | list[Json] | dict[str, Json]
type StrPath = str | PathLike[str]
