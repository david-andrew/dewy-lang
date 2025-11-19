from abc import ABC, abstractmethod
from typing import Generic, TypeVar

class Phase(ABC): ...
    # def __init_subclass__(cls) -> None:
    #     """ensure that each subclass of Phase, itself can only have one at most one subclass, all in one single inheritance chain"""
    #     super().__init_subclass__()
    #     for base in cls.__bases__:
    #         if not issubclass(base, Phase): continue
    #         existing = getattr(base, "_single_child", None)
    #         if existing is not None and existing is not cls:
    #             raise TypeError(f"{base.__name__} already has a direct subclass {existing.__name__}; cannot subclass it again with {cls.__name__}")
    #         base._single_child = cls


class Tokenized(Phase): ...
class Chained(Tokenized): ...
class Parsed(Chained): ...
class Resolved(Parsed): ...
class Typechecked(Resolved): ...




T = TypeVar('T', bound=Phase)
class AST(Generic[T], ABC): ...
