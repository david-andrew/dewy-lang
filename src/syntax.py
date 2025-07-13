from abc import ABC, abstractmethod, ABCMeta
from typing import get_args, get_origin, Generator, Any, Literal, Union, dataclass_transform, Callable as TypingCallable, TypeVar
from types import UnionType
from dataclasses import dataclass, field, fields
from enum import Enum, auto
# from fractions import Fraction

from .tokenizer import Operator_t, escape_whitespace  # TODO: move into utils

import pdb


@dataclass_transform()
class AST(ABC):
    def __init_subclass__(cls: type['AST'], **kwargs):
        """
        - automatically applies the dataclass decorator with repr=False to AST subclasses
        """
        super().__init_subclass__(**kwargs)

        # Apply the dataclass decorator with repr=False to the subclass
        dataclass(repr=False)(cls)

    # TODO: add property to all ASTs for function complete/locked/etc. meaning it and all children are settled
    @abstractmethod
    def __str__(self) -> str:
        """Return a string representation of the AST in a canonical dewy code format"""

    def __repr__(self) -> str:
        """
        Returns a string representation of the AST tree with correct indentation for each sub-component

        e.g.
        SomeAST(prop0=..., prop1=...)
        ├── child0=SomeSubAST(...)
        ├── child1=SomeOtherAST(...)
        │   ├── a=ThisAST(...)
        │   └── b=ThatAST(...)
        └── child2=AST2(...)
            └── something=ThisLastAST(...)

        Where all non-ast attributes of a node are printed on the same line as the node itself
        and all children are recursively indented a level and printed on their own line
        """
        return '\n'.join(self._gentree())

    def _gentree(self, prefix: str = '') -> Generator[str, None, None]:
        """
        a recursive generator helper function for __repr__

        Args:
            prefix: str - the string to prepend to each child line (root line already has prefix)
            name: str - the name of the current node in the tree
            # draw_branches: bool - whether each item should be drawn with branches or only use whitespace

        Returns:
            str: the string representation of the AST tree
        """
        # prefix components:
        space = '    '
        branch = '│   '
        # pointers:
        tee = '├── '
        last = '└── '

        attrs_str = ', '.join(f'{k}={v}' for k, v in self.__iter_non_ast_props__())
        yield f'{self.__class__.__name__}({attrs_str})'
        children: tuple[tuple[str, AST], ...] = tuple((k, v) for k, v in self.__iter_ast_props__())
        pointers = [tee] * (len(children) - 1) + [last]
        for (k, v), pointer in zip(children, pointers):
            extension = branch if pointer == tee else space
            gen = v._gentree(f'{prefix}{extension}')
            name = f'{k}=' if k else ''
            yield f'{prefix}{pointer}{name}{next(gen)}'     # first line gets name and pointer
            yield from gen                                  # rest of lines already have a prefix


    def __iter_ast_props__(self, *, visit_replacement:bool=True) -> Generator[tuple[str, 'AST'], 'AST', None]:
        """
        Iterate over all children ASTs of this AST (including those in containers, e.g. list[AST])
        Allows for in place replacement of the current AST via .send()

        Arguments:
            visit_replacement (bool): if True, then anytime .send(ast) is called, the iterator will visit that ast on the next step

        Sends:
            replacement (AST): an AST to replace the current AST with in the parent/container

        Yields:
            ast (AST): The current child AST
        """
        for key, value in self.__dict__.items():
            # catch cases of something: AST | None
            if value is None:
                continue

            if isinstance(value, AST):
                while True:
                    replacement = yield key, value
                    if replacement is not None:
                        value = replacement
                        setattr(self, key, value)
                        assert (yield) is None, 'ILLEGAL: Cannot .send() multiple times in a row. must allow next() (e.g. from loop iter) to be called first'
                        if visit_replacement:
                            continue
                    break
                continue

            if is_ast_container(self.__class__.__annotations__.get(key)):
                if isinstance(value, list):
                    for i, vi in enumerate(value):
                        while True:
                            replacement = yield '', vi
                            if replacement is not None:
                                vi = replacement
                                value[i] = vi
                                assert (yield) is None, 'ILLEGAL: Cannot .send() multiple times in a row. must allow next() (e.g. from loop iter) to be called first'
                                if visit_replacement:
                                    continue
                            break
                    continue
                # elif isinstance(value, some_other_container_type)
                else:
                    pdb.set_trace()
                    raise NotImplementedError(f'__iter_ast_props__ over {type(value)} (from member "{key}") of {self} is not yet implemented')



    def __iter_non_ast_props__(self) -> Generator[tuple[str, Any], None, None]:
        """Iterate over the non-AST members of the AST, returning the key and value of each prop"""
        for key, value in self.__dict__.items():
            if isinstance(value, AST):
                continue
            if key.startswith('_'):
                continue
            yield key, value

    def __iter_asts__(self, *, visit_replacement:bool=True) -> Generator['AST', 'AST', None]:
        """Return a generator of the direct children ASTs of the AST"""
        yield from map_generator(lambda x: x[1], self.__iter_ast_props__(visit_replacement=visit_replacement))


    def __iter_asts_full_traversal__(self, *, visit_replacement:bool=True):
        """
        Recursively pre-order traversal of all child ASTs of the current AST
        Allows for in place replacement of the current AST via .send()
        """
        for child in (gen:= self.__iter_asts__(visit_replacement=visit_replacement)):
            replacement = yield child
            if replacement is not None:
                child = replacement
                gen.send(child)
                assert (yield) is None, 'ILLEGAL: Cannot .send() multiple times in a row. must allow next() (e.g. from loop iter) to be called first'

            yield from child.__iter_asts_full_traversal__(visit_replacement=visit_replacement)


    def is_settled(self) -> bool:
        """Return True if the neither the AST, nor any of its descendants, are prototypes"""
        for child in self.__iter_asts__():
            if not child.is_settled():
                return False
        return True



T = TypeVar('T')
U = TypeVar('U')
V = TypeVar('V')
def map_generator(f: TypingCallable[[T], U], gen: Generator[T, V, None]) -> Generator[U, V, None]:
    """Map a sendable generator to a new generator using the given function"""
    gen = iter(gen)
    try:
        val = next(gen)
        while True:
            to_send = yield f(val) if val is not None else None
            val = gen.send(to_send)
    except StopIteration:
        return


def is_ast_container(type_hint: type | None) -> bool:
    """
    Determine if the type hint is a container of ASTs.
    e.g. list[AST], set[SomeSubclassOfAST|OtherSubclassOfAST], etc.

    Args:
        type_hint: type | None - the type hint to check. If None, returns False

    Returns:
        bool: True if any of the contained types are subclasses of AST, False otherwise
    """
    if type_hint is None:
        return False

    # class constructors are not containers
    if get_origin(type_hint) is type:
        return False

    # python callables are not containers regardless of if they take in or return ASTs
    if get_origin(type_hint) == get_origin(TypingCallable):
        return False


    # Iterate over all contained types
    args = get_args(type_hint)
    for arg in args:
        # Handle Union types (e.g., Union[B, C] or B | C)
        if get_origin(arg) is Union:
            if any(issubclass(sub_arg, AST) for sub_arg in get_args(arg) if isinstance(sub_arg, type)):
                return True
        elif isinstance(arg, UnionType):
            if any(issubclass(sub_arg, AST) for sub_arg in arg.__args__ if isinstance(sub_arg, type)):
                return True
        # Check if the argument itself is a subclass of the base class
        elif isinstance(arg, type) and issubclass(arg, AST):
            return True

    # no AST subclasses found
    return False


class PrototypeAST(AST, ABC):
    """Used to represent AST nodes that are not complete, and must be removed before the whole AST is evaluated"""

    def is_settled(self) -> bool:
        """By definition, prototypes are not settled"""
        return False


class Delimited(ABC):
    """used to track which ASTs are printed with their own delimiter so they can be juxtaposed without extra parentheses"""

class TypeParam(AST, Delimited):
    items: list[AST]

    def __str__(self):
        return f'<{" ".join(map(str, self.items))}>'
class Type(AST):
    t: type[AST]
    parameters: TypeParam | None = None

    def __str__(self) -> str:
        if self.parameters:
            return f'{self.t.__name__}{self.parameters}'
        return self.t.__name__

    # strictly for hashing
    def __eq__(self, other):
        return isinstance(other, Type) and self.t == other.t and self.parameters == other.parameters

    def __hash__(self):
        return hash((self.t, self.parameters))




# TODO: turn into a singleton...
# untyped type for when a declaration doesn't specify a type
class Untyped(AST):
    def __str__(self) -> str:
        return 'untyped'
untyped = Type(Untyped)


class Undefined(AST):
    """undefined singleton"""
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Undefined, cls).__new__(cls)
        return cls.instance

    def __str__(self) -> str:
        return 'undefined'


# undefined shorthand, for convenience
undefined = Undefined()


class Void(AST):
    """void singleton"""
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Void, cls).__new__(cls)
        return cls.instance

    def __str__(self) -> str:
        return 'void'


# void shorthand, for convenience
void = Void()


class Extern(AST):
    """extern singleton"""
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Extern, cls).__new__(cls)
        return cls.instance

    def __str__(self) -> str:
        return 'extern'


# extern shorthand, for convenience
extern = Extern()


class New(AST):
    """new singleton"""
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(New, cls).__new__(cls)
        return cls.instance

    def __str__(self) -> str:
        return 'new'


# new shorthand, for convenience
new = New()

class End(AST):
    """end singleton"""
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(End, cls).__new__(cls)
        return cls.instance

    def __str__(self) -> str:
        return 'end'


# end shorthand, for convenience
end = End()


class EmptyObjLiteral(AST):
    def __str__(self): return '[]'

class ListOfASTs(PrototypeAST):
    """Intermediate step for holding a list of ASTs that are probably captured by a container"""
    asts: list[AST]

    def __str__(self):
        return f'{", ".join(map(str, self.asts))}'


class PrototypeTuple(PrototypeAST):
    """
    A comma separated list of expressions (not wrapped in parentheses) e.g. 1, 2, 3
    There is no special in-memory representation of a tuple, it is literally just a const list
    """
    items: list[AST]

    def __str__(self):
        return f'{", ".join(map(str, self.items))}'


class Group(AST, Delimited):
    items: list[AST]

    def __str__(self):
        return f'({" ".join(map(str, self.items))})'


class Block(AST, Delimited):
    items: list[AST]

    def __str__(self):
        return f'{{{" ".join(map(str, self.items))}}}'


# class Number(AST):
#     val: int | float | Fraction

class Bool(AST):
    val: bool

    def __str__(self) -> str:
        return str(self.val).lower()


class Int(AST):
    val: int

    def __str__(self) -> str:
        return str(self.val)


class String(AST, Delimited):
    val: str

    def __str__(self) -> str:
        return f'"{escape_whitespace(self.val)}"'


class IString(AST, Delimited):
    parts: list[AST]

    def __str__(self):
        s = ''
        for part in self.parts:
            if isinstance(part, String):
                s += part.val
            else:
                s += f'{part}'
        return f'"{s}"'


class Flowable(AST, ABC):
    ...
    # def was_entered(self) -> bool:
    #     """Determine if the flowable branch was entered. Should reset before performing calls to flow and checking this."""
    #     raise NotImplementedError(f'flowables must implement `was_entered()`. No implementation found for {self.__class__}')

    # def reset_was_entered(self) -> None:
    #     """reset the state of was_entered, in preparation for executing branches in a flow"""
    #     raise NotImplementedError(f'flowables must implement `reset_was_entered()`. No implementation found for {self.__class__}')


class Flow(AST):
    branches: list[Flowable]

    def __str__(self):
        return ' else '.join(map(str, self.branches))


class If(Flowable):
    condition: AST
    body: AST

    def __str__(self):
        return f'if {self.condition} {self.body}'


class Loop(Flowable):
    condition: AST
    body: AST

    def __str__(self):
        return f'loop {self.condition} {self.body}'


class Default(Flowable):
    body: AST

    def __str__(self):
        return f'{self.body}'


class PrototypeFunctionLiteral(PrototypeAST):
    args: AST
    body: AST

    def __str__(self):
        if isinstance(self.args, Delimited):
            return f'{self.args} => {self.body}'
        return f'({self.args}) => {self.body}'


class PrototypeBuiltin(PrototypeAST):
    args: Group
    return_type: AST

    def __str__(self):
        return f'({self.args}):> {self.return_type} => ...'


class Call(AST):
    f: AST
    args: None | AST = None

    def __str__(self):
        if self.args is None:
            return f'{self.f}()'
        if isinstance(self.args, Delimited):
            return f'{self.f}{self.args}'
        return f'{self.f}({self.args})'

from typing import cast
class BinOp(AST, ABC):
    left: AST
    right: AST

    def __post_init__(self):
        self._space = cast(bool, getattr(self, '_space', True))
        self._op = cast(str, getattr(self, '_op', None))
        assert isinstance(self._op, str), f'BinOp subclass "{self.__class__.__name__}" must define an `_op` attribute'

    def __str__(self) -> str:
        if self._space:
            return f'{self.left} {self._op} {self.right}'
        return f'{self.left}{self._op}{self.right}'

class Assign(BinOp):
    _op = '='
class CompiletimeAssign(BinOp):
    _op = '::'
class PointsTo(BinOp):
    _op = '->'
class BidirPointsTo(BinOp):
    _op = '<->'
class Access(BinOp):
    _op = '.'
    _space = False

class Index(BinOp):
    _op = ''
    _space = False

class Equal(BinOp):
    _op = '=?'

# covered by OpChain([Not, Equal]). but used at compile time
class NotEqual(BinOp):
    _op = 'not=?'

class Less(BinOp):
    _op = '<?'

class LessEqual(BinOp):
    _op = '<=?'

class Greater(BinOp):
    _op = '>?'

class GreaterEqual(BinOp):
    _op = '>=?'

class  LeftShift(BinOp):
    _op = '<<'

class  RightShift(BinOp):
    _op = '>>'

class LeftRotate(BinOp):
    _op = '<<<'

class RightRotate(BinOp):
    _op = '>>>'

class LeftRotateCarry(BinOp):
    _op = '<<!'

class RightRotateCarry(BinOp):
    _op = '!>>'

class Add(BinOp):
    _op = '+'

class Sub(BinOp):
    _op = '-'

class Mul(BinOp):
    _op = '*'

class Div(BinOp):
    _op = '/'

class IDiv(BinOp):
    _op = '÷'

class Mod(BinOp):
    _op = 'mod'

class Pow(BinOp):
    _op = '^'

class And(BinOp):
    _op = 'and'

class Or(BinOp):
    _op = 'or'

class Xor(BinOp):
    _op = 'xor'

class Nand(BinOp):
    _op = 'nand'

class Nor(BinOp):
    _op = 'nor'

class Xnor(BinOp):
    _op = 'xnor'

class IterIn(BinOp):
    _op = 'in'

class MemberIn(BinOp):
    _op = 'in?'

class UnaryPrefixOp(AST, ABC):
    operand: AST

    def __post_init__(self):
        self._space = cast(bool, getattr(self, '_space', False))
        self._op = cast(str, getattr(self, '_op', None))
        assert isinstance(self._op, str), f'UnaryPrefixOp subclass "{self.__class__.__name__}" must define an `_op` attribute'

    def __str__(self) -> str:
        if self._space:
            return f'{self._op} {self.operand}'
        return f'{self._op}{self.operand}'

class Not(UnaryPrefixOp):
    _op = 'not'
    _space = True

class UnaryNeg(UnaryPrefixOp):
    _op = '-'

class UnaryPos(UnaryPrefixOp):
    _op = '+'

class UnaryMul(UnaryPrefixOp):
    _op = '*'

class UnaryDiv(UnaryPrefixOp):
    _op = '/'



class AtHandle(UnaryPrefixOp):
    _op = '@'
    def __str__(self):
        if isinstance(self.operand, (Delimited, Identifier)):
            return f'@{self.operand}'
        return f'@({self.operand})'


class UnaryPostfixOp(AST, ABC):
    operand: AST

    def __post_init__(self):
        self._op = cast(str, getattr(self, '_op', None))
        assert isinstance(self._op, str), f'UnaryPostfixOp subclass "{self.__class__.__name__}" must define an `_op` attribute'

    def __str__(self) -> str:
        return f'{self.operand}{self._op}'

class Suppress(UnaryPostfixOp):
    _op = ';'


class BroadcastOp(AST):
    op: BinOp

    def __str__(self):
        return f'{self.op.left} .{self.op._op} {self.op.right}'

# TBD if need. For now, parser just does `left = left op right` for `left op= right`
#     needed if we wanted to instead actually do slightly different things when doing an update assign
#     ony case I can think of is from overloading:
#     ```
#     myfunc = () => 'first version'
#     // three possible ways overloading would work...
#     myfunc  |= (a:int b:int) => 'second version'  // myfunc  = myfunc  | (a:int b:int) => 'second version' // fails because myfunc needs to be @myfunc on the right side
#     @myfunc |= (a:int b:int) => 'second version'  // @myfunc = @myfunc | (a:int b:int) => 'second version'
#     myfunc  |= (a:int b:int) => 'second version'  // myfunc  = @myfunc | (a:int b:int) => 'second version'
#     ```
# Also note that vectorized ops might be `op: BinOp | CombinedAssign` if we implement this
# class CombinedAssign(AST):
#     op: BinOp

#     def __str__(self) -> str:
#         return f'{self.op.left} {self.op._op}= {self.op.right}'


class BareRange(PrototypeAST):
    left: AST
    right: AST

    def __str__(self) -> str:
        return f'{self.left}..{self.right}'


class Ellipsis(AST):
    def __str__(self) -> str:
        return '...'


class Backticks(PrototypeAST):
    backticks: str
    def __str__(self) -> str:
        return f'{self.backticks}'


class CycleLeft(AST):
    operand: AST
    num_steps: int

    def __str__(self):
        return f'{"`"*self.num_steps}{self.operand}'


class CycleRight(AST):
    operand: AST
    num_steps: int

    def __str__(self):
        return f'{self.operand}{"`"*self.num_steps}'


class DotDotDot(PrototypeAST):
    def __str__(self) -> str:
        return f'...'

class CollectInto(AST):
    right: AST

    def __str__(self):
        return f'...{self.right}'

class SpreadOutFrom(AST):
    left: AST

    def __str__(self):
        return f'{self.left}...'



class Range(AST):
    left: AST
    right: AST
    brackets: Literal['[]', '[)', '(]', '()']

    def __str__(self) -> str:
        return f'{self.brackets[0]}{self.left}..{self.right}{self.brackets[1]}'


class Array(AST, Delimited):
    items: list[AST] # list[T] where T is not PointsTo or BidirPointsTo. Might have Declare or Assign. Must have at least 1 expression!

    def __str__(self):
        return f'[{" ".join(map(str, self.items))}]'


class Dict(AST, Delimited):
    items: list[PointsTo]

    def __str__(self):
        return f'[{" ".join(map(str, self.items))}]'


class BidirDict(AST, Delimited):
    items: list[BidirPointsTo]

    def __str__(self):
        return f'[{" ".join(map(str, self.items))}]'


class ObjectLiteral(AST, Delimited):
    items: list[AST] # list[Declare|Assign|AST] has to have at least 1 declare or assignment, and no expressions!

    def __str__(self):
        return f'[{" ".join(map(str, self.items))}]'




class MakeGeneric(AST):
    # e.g. you are creating something that is generic: myfn = <T>(a:T, b:T) => a + b
    left: TypeParam
    right: AST

    def __str__(self):
        return f'{self.left}{self.right}'


class Parameterize(AST):
    # e.g. you are applying a type to an existing generic object: res = myfn<int64>(1 2)
    left: AST
    right: TypeParam

    def __str__(self):
        return f'{self.left}{self.right}'


class PrototypeIdentifier(PrototypeAST):
    name: str
    def __str__(self) -> str:
        return f'ProtoId<{self.name}>'

class Identifier(AST):
    name: str
    def __str__(self) -> str:
        return f'{self.name}'


class Express(AST):
    id: Identifier

    def __str__(self) -> str:
        return f'{self.id}'

class TypedIdentifier(AST):
    id: Identifier
    type: AST

    def __str__(self) -> str:
        return f'{self.id}:{self.type}'


class ReturnTyped(BinOp):
    _op = ':>'

class SubTyped(BinOp):
    _op = 'of'
    _space = True


class UnpackTarget(AST):
    target: 'list[Identifier | TypedIdentifier | UnpackTarget | Assign | CollectInto]'
    def __str__(self) -> str:
        return f'[{" ".join(map(str, self.target))}]'

class DeclarationType(Enum):
    LET = auto()
    CONST = auto()
    # LOCAL_CONST = auto()
    # FIXED_TYPE = auto()

    # default for binding without declaring
    # DEFAULT = LET


class Declare(AST):
    decltype: DeclarationType
    target: Identifier | TypedIdentifier | ReturnTyped | UnpackTarget | Assign | CompiletimeAssign #| CollectInto #TBD if can declare with collect into

    def __str__(self):
        return f'{self.decltype.name.lower()} {self.target}'


class Return(AST):
    item: AST

    def __str__(self):
        return f'return {self.item}'


if __name__ == '__main__':
    # DEBUG testing tree string printing
    class _Add(AST):
        l: AST
        r: AST

        def __str__(self) -> str:
            return f'{self.l} + {self.r}'

    class _Mul(AST):
        l: AST
        r: AST

        def __str__(self) -> str:
            return f'{self.l} * {self.r}'

    class _List(AST):
        items: list[AST]

        def __str__(self) -> str:
            return f'[{", ".join(map(str, self.items))}]'

    class _Int(AST):
        value: int

        def __str__(self) -> str:
            return str(self.value)

    # big long test ast
    test = _Add(
        _Add(
            _Int(1),
            _List([_Int(2), _Int(3), _Int(4), _Int(5)])
        ),
        _Mul(
            _Int(2),
            _Add(
                _Mul(
                    _Int(3),
                    _Int(4)
                ),
                _Mul(
                    _Int(5),
                    _Int(6)
                )
            )
        )
    )

    print(repr(test))
    print(str(test))
    # class Broken(AST):
    #     num: int
    #     def __str__(self) -> str:
    #         return f'{self.num}'
    #     def __iter__(self) -> Generator['AST', None, None]:
    #         yield Int(self.num)
