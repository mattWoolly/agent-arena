"""Reference solution: a tiny spreadsheet formula engine."""


class CycleError(Exception):
    pass


_OPS = {"+": (1, lambda a, b: a + b), "-": (1, lambda a, b: a - b),
        "*": (2, lambda a, b: a * b), "/": (2, lambda a, b: a / b),
        "^": (3, lambda a, b: a ** b)}


def _tokenize(s):
    toks = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c in "+-*/^()":
            toks.append(c)
            i += 1
        elif c.isalpha():
            j = i
            while j < len(s) and s[j].isalpha():
                j += 1
            k = j
            while k < len(s) and s[k].isdigit():
                k += 1
            toks.append(("ref", s[i:k]))
            i = k
        elif c.isdigit() or c == ".":
            j = i
            while j < len(s) and (s[j].isdigit() or s[j] == "."):
                j += 1
            toks.append(("num", float(s[i:j])))
            i = j
        else:
            raise ValueError(f"bad char {c!r}")
    return toks


def _parse(toks):
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def eat():
        nonlocal pos
        t = toks[pos]
        pos += 1
        return t

    def atom():
        nonlocal pos
        t = peek()
        if t == "(":
            eat()
            node = expr(0)
            if peek() != ")":
                raise ValueError("missing )")
            eat()
            return node
        if t == "-":
            eat()
            return ("neg", power())
        if isinstance(t, tuple):
            eat()
            return t
        raise ValueError(f"unexpected {t!r}")

    def power():
        return expr(3)

    def expr(min_prec):
        left = atom()
        while True:
            t = peek()
            if t in _OPS and _OPS[t][0] >= min_prec:
                prec = _OPS[t][0]
                eat()
                # ^ is right-associative (recurse at same prec); others left.
                right = expr(prec if t == "^" else prec + 1)
                left = ("op", t, left, right)
            else:
                return left

    node = expr(0)
    if pos != len(toks):
        raise ValueError("trailing tokens")
    return node


def evaluate(cells):
    """cells: {name: formula-string beginning with '=' or a bare number string}.
    Returns {name: float}. Raises CycleError on any dependency cycle."""
    asts = {}
    for name, raw in cells.items():
        s = raw.strip()
        if s.startswith("="):
            asts[name] = _parse(_tokenize(s[1:]))
        else:
            asts[name] = ("num", float(s))

    cache = {}
    visiting = set()

    def resolve(name):
        if name in cache:
            return cache[name]
        if name in visiting:
            raise CycleError(name)
        if name not in asts:
            raise ValueError(f"unknown cell {name}")
        visiting.add(name)
        val = walk(asts[name])
        visiting.discard(name)
        cache[name] = val
        return val

    def walk(node):
        tag = node[0]
        if tag == "num":
            return node[1]
        if tag == "ref":
            return resolve(node[1])
        if tag == "neg":
            return -walk(node[1])
        if tag == "op":
            _, oper, a, b = node
            return _OPS[oper][1](walk(a), walk(b))
        raise ValueError("bad node")

    return {name: resolve(name) for name in cells}
