from dataclasses import dataclass
from typing import Any


class BError(Exception): ...
class BSyntaxError(BError): ...
class BSemanticError(BError): ...


class Type:
    def check_cp(self, to: "Type") -> bool:
        ...


class UncheckedType(Type):
    ...


@dataclass
class BasicType(Type):
    name: str

    def check_cp(self, to: Type):
        if isinstance(to, BasicType) and self.name in ('int', 'float') and to.name in ('int', 'float'):
            return True
        return False


@dataclass
class FuncType(Type):
    ret: Type
    args: list[Type]

    def check_cp(self, to: Type) -> bool:
        if not isinstance(to, FuncType):
            return False
        if len(self.args) != len(to.args) or not self.ret.check_cp(to.ret):
            return False
        for f, t in zip(self.args, to.args):
            if not f.check_cp(t):
                return False
        return True


@dataclass
class ListType(Type):
    item: Type

    def check_cp(self, to: Type) -> bool:
        return isinstance(to, ListType) and self.item.check_cp(to.item)


class ComplexType(Type):
    id = 0

    def __init__(self, name: str, parents: "list[ComplexType]", attrs: dict[str, Type], methods: dict[str, FuncType]):
        self.name, self.parents, self.attrs, self.methods = name, parents, attrs, methods
        self.id = ComplexType.id
        self.all_cp = self.get_all_cp()
        ComplexType.id += 1

    def __hash__(self) -> int:
        return self.id

    def get_all_cp(self) -> "set[int]":
        res = {self.id}
        for i in self.parents:
            for j in i.get_all_cp():
                res.add(j)
        return res

    def check_cp(self, to: Type) -> bool:
        return isinstance(to, ComplexType) and to.id in self.all_cp

    def find_attr(self, name: str):
        if name in self.attrs:
            return self.attrs[name]
        elif self.parents:
            for parent in self.parents:
                try:
                    return parent.find_attr(name)
                except BSemanticError:
                    pass
        raise BSemanticError(f"attribute '{name}' is not defined")

    def find_method(self, name: str):
        if name in self.methods:
            return self.methods[name]
        elif self.parents:
            for parent in self.parents:
                try:
                    return parent.find_method(name)
                except BSemanticError:
                    pass
        raise BSemanticError(f"method '{name}' is not defined")


Unchecked = UncheckedType()
del UncheckedType


type ExpandedGeneric = list[tuple[list[Type], Type]]


class Env:
    def __init__(self, parent: "Env | None" = None):
        self.parent = parent
        self.vars: dict[str, Type] = {}
        self.types: dict[str, Type] = {}
        self.generic_funcs: dict[str, FuncDecl] = {}
        self.generic_types: dict[str, TypeDecl] = {}
        self.expand_funcs: dict[str, ExpandedGeneric] = {}
        self.expand_types: dict[str, ExpandedGeneric] = {}
        if parent:
            self.expected_ret: Type | None = parent.expected_ret
        else:
            self.expected_ret = None

    def find_var(self, name: str):
        if name in self.vars:
            return self.vars[name]
        elif self.parent is not None:
            return self.parent.find_var(name)
        else:
            raise BSemanticError(f"variable '{name}' is not defined")

    def find_type(self, name: str):
        if name in self.types:
            return self.types[name]
        elif self.parent is not None:
            return self.parent.find_type(name)
        else:
            raise BSemanticError(f"type '{name}' is not defined")

    def find_generic_func(self, name: str):
        if name in self.generic_funcs:
            return self.generic_funcs[name]
        elif self.parent is not None:
            return self.parent.find_generic_func(name)
        else:
            raise BSemanticError(f"function '{name}' is not defined")

    def find_generic_type(self, name: str):
        if name in self.generic_types:
            return self.generic_types[name]
        elif self.parent is not None:
            return self.parent.find_generic_type(name)
        else:
            raise BSemanticError(f"type '{name}' is not defined")

    def find_expand_func(self, name: str):
        if name in self.expand_funcs:
            return self.expand_funcs[name]
        elif self.parent is not None:
            return self.parent.find_expand_func(name)
        else:
            raise BSemanticError(f"function '{name}' is not defined")

    def find_expand_type(self, name: str):
        if name in self.expand_types:
            return self.expand_types[name]
        elif self.parent is not None:
            return self.parent.find_expand_type(name)
        else:
            raise BSemanticError(f"type '{name}' is not defined")


    def add_var(self, name: str, type: Type):
        if name in self.vars:
            raise BSemanticError(f"variable '{name}' is already defined")
        self.vars[name] = type

    def add_type(self, name: str, type: Type):
        if name in self.types:
            raise BSemanticError(f"type '{name}' is already defined")
        self.types[name] = type

    def add_generic_func(self, name: str, func: "FuncDecl"):
        if name in self.generic_funcs:
            raise BSemanticError(f"function '{name}' is already defined")
        self.generic_funcs[name] = func

    def add_generic_type(self, name: str, type: "TypeDecl"):
        if name in self.generic_types:
            raise BSemanticError(f"type '{name}' is already defined")
        self.generic_types[name] = type


def check_wrapper(fn):
    def wrapper(self, *args, **kwargs):
        if self.type is not Unchecked:
            return self.type
        self.type = fn(self, *args, **kwargs)
        return self.type

    return wrapper


def try_func(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except:
        return


class Stmt:
    type: Type | None = Unchecked

    @check_wrapper
    def check(self, env: Env) -> Type | None: ...


class Expr:
    type: Type = Unchecked

    @check_wrapper
    def check(self, env: Env) -> Type: ...


class TypeExpr:
    type: Type = Unchecked

    @check_wrapper
    def check(self, env: Env) -> Type: ...


@dataclass
class NoOp(Stmt):
    pass


@dataclass
class ExprStmt(Stmt):
    expr: Expr

    @check_wrapper
    def check(self, env: Env) -> Type | None:
        self.expr.check(env)


@dataclass
class Block(Stmt):
    stmts: list[Stmt]

    @check_wrapper
    def check(self, env: Env) -> Type | None:
        env = Env(env)
        ret = None
        for i in self.stmts:
            tp = i.check(env)
            if tp is not None:
                if env.expected_ret is None or not tp.check_cp(env.expected_ret):
                    raise BSemanticError("unexpected return or return type")
                ret = tp
        return ret


@dataclass
class VarDecl(Stmt):
    vars: list[tuple[str, TypeExpr | None, Expr | None]]

    @check_wrapper
    def check(self, env: Env) -> Type | None:
        for name, tpe, val in self.vars:
            tp = None if tpe is None else tpe.check(env)
            if tp is None and val:
                tp = val.check(env)
            elif tp and val is not None:
                vt = val.check(env)
                if not vt.check_cp(tp):
                    raise BSemanticError("")
            else:
                raise
            env.add_var(name, tp)


@dataclass
class FuncDecl(Stmt):
    name: str
    tparams: list[str] | None
    params: list[tuple[str, TypeExpr]]
    ret: TypeExpr
    body: Block | None

    @check_wrapper
    def check(self, env: Env) -> Type | None:
        


@dataclass
class TypeDecl(Stmt):
    name: str
    targs: list[str]
    inherits: list[TypeExpr]
    attrs: list[tuple[str, TypeExpr]] | None
    methods: list[FuncDecl] | None


@dataclass
class Assign(Stmt):
    l: Expr
    r: Expr


@dataclass
class If(Stmt):
    cases: list[tuple[Expr, Block]]
    default: Block | None


@dataclass
class While(Stmt):
    cond: Expr
    body: Block


@dataclass
class Return(Stmt):
    expr: Expr | None


@dataclass
class Break(Stmt):
    ...


@dataclass
class Continue(Stmt):
    ...


@dataclass
class LitExpr(Expr):
    val: object


@dataclass
class VarExpr(Expr):
    name: str


@dataclass
class GenIdent(Expr):
    name: str
    targs: list[TypeExpr]


@dataclass
class Binary(Expr):
    op: str
    l: Expr
    r: Expr


@dataclass
class Unary(Expr):
    op: str
    e: Expr


@dataclass
class Call(Expr):
    fn: Expr
    args: list[Expr]


@dataclass
class Index(Expr):
    base: Expr
    index: Expr


@dataclass
class Attr(Expr):
    base: Expr
    attr: str


@dataclass
class GenAttr(Expr):
    base: Expr
    attr: str
    targs: list[TypeExpr]


@dataclass
class Lambda(Expr):
    args: list[tuple[str, TypeExpr]]
    ret: TypeExpr | None
    body: Block


@dataclass
class ListExpr(Expr):
    items: list[Expr]


@dataclass
class ObjNew(Expr):
    type: TypeExpr


@dataclass
class BasicTypeExpr(TypeExpr):
    name: str


@dataclass
class FuncTypeExpr(TypeExpr):
    ret: TypeExpr
    args: list[tuple[str, TypeExpr]]


@dataclass
class ListTypeExpr(TypeExpr):
    item: TypeExpr


@dataclass
class GenericTypeExpr(TypeExpr):
    name: str
    targs: list[TypeExpr]


KEYWORDS = {
    'if', 'else', 'while',
    'var', 'func', 'type',
    'return', 'break', 'continue',
    'True', 'False', 'None',
    'new',
}

OPERATORS = {
    '+', '-', '*', '/', '%',
    '==', '!=', '<', '<=', '>', '>=',
    '&', '|', '^', '<<', '>>',
    '&&', '||',
    '!', '~',
    
    '(', ')', '[', ']', '{', '}',
    ',', ';', ':', '.', '?', '=',
}

ESCAPES = {
    'r': '\r',
    't': '\t',
    'a': '\a',
    'f': '\f',
    'v': '\v',
    'b': '\b',
    'n': '\n',
    '\\': '\\',
    '"': '"',
}

PRIORITYS = {
    '*': 100, '/': 100, '%': 100,
    '+': 99, '-': 99,
    '<<': 98, '>>': 98,
    '==': 97, '!=': 97,
    '>': 96, '<': 96, '>=': 96, '<=': 96,
    '&': 95, '^': 94, '|': 93,
    '&&': 92, '||': 91,
}


def tokenize(s: str) -> list[str]:
    i = 0
    res = []

    while i < len(s):
        while i < len(s) and (s[i] == '#' or s[i] in " \n\r\t"):
            if s[i] == '#':
                while i < len(s) and s[i] != '\n':
                    i += 1
            i += 1

        if i >= len(s):
            break
        elif s[i].isalpha() or s[i] == '_':
            t = ""
            while i < len(s) and (s[i].isalnum() or s[i] == '_'):
                t += s[i]
                i += 1
            if t in KEYWORDS:
                res.append('*' + t)
            else:
                res.append(t)
        elif s[i].isdigit() or s[i] == '.':
            t = ""
            while i < len(s) and (s[i].isdigit() or s[i] == '.'):
                t += s[i]
                i += 1
            if t.count('.') > 1:
                raise BSyntaxError(f"unexpected number '{t}'")
            res.append(t)
        elif s[i] in '\'"':
            x = s[i]
            t = s[i]
            i += 1
            while i < len(s) and s[i] != x:
                if s[i] == '\\':
                    i += 1
                    if s[i] in ESCAPES:
                        t += ESCAPES[s[i]]
                        i += 1
                    elif s[i] == 'u':
                        i += 1
                        t += chr(int(s[i:i+4], 16))
                        i += 4
                    elif s[i] == 'U':
                        i += 1
                        t += chr(int(s[i:i+8], 16))
                        i += 8
                    elif s[i] == 'x':
                        i += 1
                        t += chr(int(s[i:i+2], 16))
                        i += 2
                    else:
                        raise BSyntaxError(f"unexpected escape character '{s[i]}'")
                else:
                    t += s[i]
                    i += 1
            if i >= len(s):
                raise BSyntaxError(f"unexpected EOF")
            i += 1
            res.append(t)
        elif s[i: i + 2] in OPERATORS:
            res.append(s[i: i + 2])
            i += 2
        elif s[i] in OPERATORS:
            res.append(s[i])
            i += 1
        else:
            raise BSyntaxError(f"unexpected character '{s[i]}'")

    res.append('')
    return res


def parse(tokens: list[str]) -> Block:
    i = 0
    token = tokens[i]
    parse_env: list[set[str]] = [set()]

    def is_generic_func(name: str):
        for env in reversed(parse_env):
            if name in env:
                return True
        return False

    def eat_id():
        nonlocal i, token
        if token is None or not (token[0].isalpha() or token[0] == '_'):
            raise BSyntaxError(f"unexpected token '{token}'")
        i += 1
        token = tokens[i]
        return token[i - 1]

    def eat(t=None):
        nonlocal i, token
        if t is not None and token != t:
            raise BSyntaxError(f"unexpected token '{token}'")
        i += 1
        token = tokens[i]
        return token[i - 1]

    def _in_parens(l: str | None, r: str, fn = None, sep: str = ','):
        if fn is None:
            fn = expr
        if l is not None:
            eat(l)
        res = []
        while token != r:
            res.append(fn())
            if token != r:
                eat(sep)
        eat()
        return res

    def _vardecl_single():
        name = eat_id()
        if token == ':':
            eat()
            tp = type()
        else:
            tp = None
        if token == '=':
            eat()
            val = expr()
        else:
            val = None
        if tp is None and val is None:
            raise BSyntaxError("expect type or value at variable declaration")
        return name, tp, val

    def type():
        name = eat_id()
        if token == '<':
            res = GenericTypeExpr(name, _in_parens('<', '>', type))
        else:
            res = BasicTypeExpr(name)

        while True:
            if token == '[':
                eat()
                eat(']')
                res = ListTypeExpr(res)
            elif token == '(':
                res = FuncTypeExpr(res, _in_parens('(', ')', type))
            else:
                break

        return res

    def factor() -> Expr:
        if token == '':
            raise BSyntaxError(f"unexpected EOF")
        elif token[0].isalpha() or token[0] == '_':
            res = VarExpr(eat_id())
            if token == '<' and is_generic_func(res.name):
                res = GenIdent(res.name, _in_parens('<', '>', type))
        elif token[0].isdigit() or token[0] == '.':
            if '.' in token:
                res = LitExpr(float(token))
            else:
                res = LitExpr(int(token))
        elif token[0] == '"':
            res = LitExpr(token[1:])
        elif token == '(':
            eat()
            res = expr()
            eat(')')
        elif token in '~!+-':
            op = token
            eat()
            res = Unary(op, expr())
        elif token == '[':
            res = ListExpr(_in_parens('[', ']'))
        elif token == '*new':
            eat()
            res = ObjNew(type())
        else:
            raise BSyntaxError(f"unexpected token '{token}'")

        while True:
            if token == '.':
                eat()
                res = Attr(res, eat_id())
            elif token == '[':
                eat()
                res = Index(res, expr())
                eat(']')
            elif token == '(':
                res = Call(res, _in_parens('(', ')'))
            else:
                break

        return res

    def expr() -> Expr:
        res = [factor()]
        stack = []
        while token in PRIORITYS:
            op = eat()
            while stack and PRIORITYS[stack[-1]] >= PRIORITYS[op]:
                r, l = res.pop(), res.pop()
                res.append(Binary(stack.pop(), l, r))
            stack.append(op)
            res.append(factor())
        while stack:
            r, l = res.pop(), res.pop()
            res.append(Binary(stack.pop(), l, r))
        return res[-1]

    def stmt():
        if token == ';':
            eat()
            return NoOp()
        elif token == '*var':
            return VarDecl(_in_parens('*var', ';', _vardecl_single))
        elif token == '*if':
            eat()
            cases = [(expr(), block())]
            while token == '*else':
                eat()
                if token == '*if':
                    eat()
                    cases.append((expr(), block()))
                else:
                    return If(cases, block())
            return If(cases, Block([]))
        elif token == '*while':
            eat()
            return While(expr(), block())
        elif token == '*func':
            eat()
            fname = eat_id()
            tparams = _in_parens('<', '>', eat_id) if token == '<' else None
            if tparams is not None:
                parse_env[-1].add(fname)
            params = []
            eat('(')
            while token != ')':
                name = eat_id()
                eat(':')
                tp = type()
                params.append((name, tp))
                if token != ')':
                    eat(',')
            eat(')')
            eat('->')
            ret = type()
            if token == ';':
                eat()
                return FuncDecl(fname, tparams, params, ret, None)
            body = block()
            return FuncDecl(fname, tparams, params, ret, body)
        elif token == '*type':
            eat()
            tname = eat_id()
            tparams = _in_parens('<', '>', eat_id) if token == '<' else []
            inherits = []
            if token == ':':
                eat()
                while token != ';' and token != '{':
                    inherits.append(type())
                    if token != ';' and token != '{':
                        eat(',')
            if token == ';':
                eat()
                return TypeDecl(tname, tparams, inherits, None, None)
            eat('{')
            attrs = []
            methods = []
            while token != '}':
                name = eat_id()
                if token == '(':
                    params = []
                    eat('(')
                    while token != ')':
                        name = eat_id()
                        eat(':')
                        tp = type()
                        params.append((name, tp))
                        if token != ')':
                            eat(',')
                    eat(')')
                    eat('->')
                    ret = type()
                    methods.append(FuncDecl(name, None, params, ret, None))
                else:
                    eat(':')
                    tp = type()
                    attrs.append((name, tp))
                if token != '}':
                    eat(',')
            eat()
            return TypeDecl(tname, tparams, inherits, attrs, methods)
        elif token == '*return':
            eat()
            if token == ';':
                res = LitExpr(None)
            else:
                res = expr()
            eat(';')
            return Return(res)
        elif token == '*break':
            eat()
            eat(';')
            return Break()
        elif token == '*continue':
            eat()
            eat(';')
            return Continue()
        else:
            left = expr()
            if token == '=':
                if not isinstance(left, (VarExpr, Attr, Index)):
                    raise BSyntaxError("invalid l-value in assignment")
                eat()
                right = expr()
                eat(';')
                return Assign(left, right)
            eat(';')
            return ExprStmt(left)

    def block(new_env=True):
        parse_env.append(set())
        eat('{')
        res = []
        while token != '}':
            res.append(stmt())
        eat('}')
        parse_env.pop()
        return Block(res)

    res = []
    while token != '':
        res.append(stmt())
    return Block(res)
