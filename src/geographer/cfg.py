"""Explicit basic blocks and monotone reaching-binding fixed-point analysis."""
from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass, field

UNBOUND = "!unbound"
Env = dict[str, frozenset[str]]


def join(states: list[Env]) -> Env:
    if not states:
        return {}
    return {name: frozenset().union(*(s.get(name, frozenset({UNBOUND})) for s in states))
            for name in set().union(*(s.keys() for s in states))}


def target_names(node):
    return [n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))]


@dataclass
class Block:
    events: list[tuple[str, object]] = field(default_factory=list)
    successors: set[int] = field(default_factory=set)


class CFG:
    def __init__(self, body: list[ast.stmt], binding_ids: dict[tuple[int, str], str]):
        self.blocks = [Block()]
        self.binding_ids = binding_ids
        self.exit = self.new()
        ends = self.sequence(body, {0})
        self.connect(ends, self.exit)

    def new(self, events=()):
        self.blocks.append(Block(list(events)))
        return len(self.blocks) - 1

    def connect(self, ends, to):
        for b in ends:
            self.blocks[b].successors.add(to)

    def eval(self, expression):
        return [("eval", expression)] if expression is not None else []

    def bind(self, node, names):
        return [("bind", (name, self.binding_ids.get((id(node), name), UNBOUND))) for name in names]

    def sequence(self, body, ends, loop=None):
        for stmt in body:
            # Still create unreachable blocks, but fixed point will not visit them.
            events = []
            b = self.new()
            self.connect(ends, b)
            if isinstance(stmt, ast.If):
                self.blocks[b].events = self.eval(stmt.test)
                ends = self.sequence(stmt.body, {b}, loop) | self.sequence(stmt.orelse, {b}, loop)
            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                exit_block = self.new()
                header = self.new(self.eval(stmt.test) if isinstance(stmt, ast.While) else [])
                self.blocks[b].events = [] if isinstance(stmt, ast.While) else self.eval(stmt.iter)
                self.connect({b}, header)
                enter = self.new([] if isinstance(stmt, ast.While) else self.bind(stmt, target_names(stmt.target)))
                self.connect({header}, enter)
                self.connect({header}, exit_block)
                body_ends = self.sequence(stmt.body, {enter}, (header, exit_block))
                self.connect(body_ends, header)
                # Break bypasses else; false exit passes through else.
                false_exit = self.new()
                self.blocks[header].successors.discard(exit_block)
                self.connect({header}, false_exit)
                normal = self.sequence(stmt.orelse, {false_exit}, loop)
                self.connect(normal, exit_block)
                ends = {exit_block}
            elif isinstance(stmt, (ast.Try, ast.TryStar)):
                before = len(self.blocks)
                body_ends = self.sequence(stmt.body, {b}, loop)
                try_blocks = set(range(before, len(self.blocks))) | {b}
                normal = self.sequence(stmt.orelse, body_ends, loop)
                alternatives = set(normal)
                for handler in stmt.handlers:
                    hb = self.new(self.eval(handler.type) + self.bind(handler, [handler.name] if handler.name else []))
                    # Every try-block state can reach a handler; certainty is downgraded for this scope.
                    self.connect(try_blocks, hb)
                    handler_ends = self.sequence(handler.body, {hb}, loop)
                    if handler.name:
                        cleanup=self.new([('bind',(handler.name,UNBOUND))])
                        self.connect(handler_ends,cleanup);handler_ends={cleanup}
                    alternatives |= handler_ends
                if stmt.finalbody:
                    # Also visit finally for exceptional/returning paths; conservative join.
                    alternatives |= try_blocks
                ends = self.sequence(stmt.finalbody, alternatives, loop)
            elif isinstance(stmt, ast.Match):
                self.blocks[b].events = self.eval(stmt.subject)
                ends = {b}
                for case in stmt.cases:
                    names = [n.name for n in ast.walk(case.pattern) if isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name]
                    names += [n.rest for n in ast.walk(case.pattern) if isinstance(n, ast.MatchMapping) and n.rest]
                    cb = self.new(self.eval(case.pattern) + self.bind(case.pattern, names) + self.eval(case.guard))
                    self.connect({b}, cb)
                    ends |= self.sequence(case.body, {cb}, loop)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    events += self.eval(item.context_expr)
                    if item.optional_vars:
                        events += self.bind(stmt, target_names(item.optional_vars))
                self.blocks[b].events = events
                ends = self.sequence(stmt.body, {b}, loop)
            else:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    for expr in [*getattr(stmt, "decorator_list", []), *getattr(stmt, "bases", []), *getattr(stmt, "keywords", [])]:
                        events += self.eval(expr)
                    if hasattr(stmt, "args"):
                        args = stmt.args
                        for expr in [*args.defaults, *(x for x in args.kw_defaults if x is not None), *[a.annotation for a in [*args.posonlyargs, *args.args, *args.kwonlyargs] if a.annotation], getattr(stmt, "returns", None)]:
                            events += self.eval(expr)
                    events += self.bind(stmt, [stmt.name])
                elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    events += self.eval(getattr(stmt, "annotation", None)) + self.eval(stmt.value)
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    for target in targets:
                        events += self.eval(target) + self.bind(stmt, target_names(target))
                elif isinstance(stmt, ast.Delete):
                    for target in stmt.targets:
                        events += self.eval(target)
                        events += [("bind", (name, UNBOUND)) for name in target_names(target)]
                elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    names = [a.asname or (a.name.split(".")[0] if isinstance(stmt, ast.Import) else a.name) for a in stmt.names if a.name != "*"]
                    events += self.bind(stmt, names)
                    events.append(("import", stmt))
                else:
                    events += self.eval(stmt)
                self.blocks[b].events = events
                if isinstance(stmt, (ast.Return, ast.Raise)):
                    ends = set()
                elif isinstance(stmt, ast.Break) and loop:
                    self.connect({b}, loop[1]); ends = set()
                elif isinstance(stmt, ast.Continue) and loop:
                    self.connect({b}, loop[0]); ends = set()
                else:
                    ends = {b}
        return ends

    @staticmethod
    def expression_writes(node, state):
        # Short-circuit branches and comprehension evaluation are overapproximated.
        # Unknown is joined, never discarded, when an expression can write a cell.
        for n in ast.walk(node):
            if isinstance(n,ast.NamedExpr):
                for name in target_names(n.target):
                    state[name]=state.get(name,frozenset({UNBOUND})) | {UNBOUND}

    @staticmethod
    def transfer(block, incoming):
        state = dict(incoming)
        for kind, value in block.events:
            if kind == "bind":
                name, binding = value
                state[name] = frozenset({binding})
            elif kind=='eval':
                CFG.expression_writes(value,state)
        return state

    def solve(self, initial: Env | None = None):
        inputs = {0: initial or {}}
        outputs = {}
        predecessors = {i: set() for i in range(len(self.blocks))}
        for i, b in enumerate(self.blocks):
            for succ in b.successors:
                predecessors[succ].add(i)
        work = deque([0])
        self.iterations = 0
        while work:
            i = work.popleft()
            self.iterations += 1
            incoming = inputs[i]
            outgoing = self.transfer(self.blocks[i], incoming)
            if outputs.get(i) == outgoing:
                continue
            outputs[i] = outgoing
            for succ in sorted(self.blocks[i].successors):
                states = [outputs[p] for p in sorted(predecessors[succ]) if p in outputs]
                new = join(states)
                if succ not in inputs or inputs[succ] != new:
                    inputs[succ] = new
                    work.append(succ)
        return inputs, outputs

    def event_states(self, initial=None):
        inputs, outputs = self.solve(initial)
        for i in sorted(inputs):
            state = dict(inputs[i])
            for kind, value in self.blocks[i].events:
                if kind == "bind":
                    name, binding = value
                    state[name] = frozenset({binding})
                else:
                    yield kind, value, dict(state)
                    if kind=='eval':self.expression_writes(value,state)

    def definition_states(self, initial=None):
        inputs,_=self.solve(initial)
        result={}
        for i,state_in in inputs.items():
            state=dict(state_in)
            for kind,value in self.blocks[i].events:
                if kind=='bind':
                    name,binding=value;result[binding]=dict(state);state[name]=frozenset({binding})
                elif kind=='eval':self.expression_writes(value,state)
        return result
