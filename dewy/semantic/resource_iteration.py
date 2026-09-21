"""Give resource iterators ordinary lexical owners and borrowed targets.

Owning declarations deliberately reuse normal copy/move/view proofs. A loop
needs no separate policy for snapshotting a mutable source or keeping a fresh
factory result alive. The read-only loop target borrows an element; ordinary
value boundaries inside the body perform any necessary logical copy.
"""
from dataclasses import replace
from . import hir, ty


def prepare(root, registry, resource):
    loans = set()
    memo = {}

    def declare(value, loc):
        name = f'__dewy_iter_owner_{registry.next_id}'
        binding = registry.allocate(object(), name, 'value', loc)
        binding.type = value.type
        binding_id = binding.id
        declaration = hir.Declare(loc, ty.VOID_TYPE, 'let', name, value.type, value, binding_id=binding_id)
        registry.by_id[binding_id].declaration = declaration
        return declaration, hir.ExpressedIdentifier(loc, value.type, name, binding_id=binding_id)

    def mapped(value):
        if isinstance(value, hir.AST):
            return visit(value)
        if isinstance(value, list):
            return [mapped(item) for item in value]
        if isinstance(value, tuple):
            return tuple(mapped(item) for item in value)
        if isinstance(value, dict):
            return {key: mapped(item) for key, item in value.items()}
        if isinstance(value, (hir.ObjectField, hir.Param)):
            return replace(value, **{name: mapped(getattr(value, name)) for name in hir.child_fields(type(value))})
        return value

    def leaves(condition):
        return [condition] if isinstance(condition, hir.IteratorExpression) else condition.iterators if isinstance(condition, hir.MultiIteratorExpression) else []

    def needs_owner(iterator):
        source = iterator.iterable
        return resource(source.dictionary.type if isinstance(source, hir.DictEntries) else source.type) is not None

    def visit(node):
        key = id(node)
        if key not in memo:
            memo[key] = rewrite(node)
        return memo[key]

    def rewrite(node):
        if isinstance(node, hir.FunctionLiteral):
            return node  # each lexical function is transformed separately
        node = replace(node, **{name: mapped(getattr(node, name)) for name in hir.child_fields(type(node))})
        if not isinstance(node, hir.Flow) or not any(needs_owner(it) for arm in node.arms for it in leaves(arm.condition)):
            return node
        tail = node.default
        for arm in reversed(node.arms):
            iterators = leaves(arm.condition)
            prefix, transformed, dictionaries = [], [], {}
            arm_needs_owner = any(needs_owner(iterator) for iterator in iterators)
            for iterator in iterators:
                # Capture all value-producing sources in order. Hoisting
                # only the resource source would reorder it ahead of an
                # earlier ordinary factory in a multi-iterator condition.
                if not arm_needs_owner or isinstance(iterator.iterable, hir.Range):
                    transformed.append(iterator)
                    continue
                source = iterator.iterable
                if isinstance(source, hir.DictEntries):
                    held = dictionaries.get(id(source.dictionary))
                    if held is None:
                        declaration, held = declare(source.dictionary, source.loc)
                        prefix.append(declaration)
                        dictionaries[id(source.dictionary)] = held
                    source = replace(source, dictionary=held)
                else:
                    declaration, source = declare(source, source.loc)
                    prefix.append(declaration)
                target = iterator.target
                if resource(target.type) is not None:
                    # Loop bindings are already read-only element loans. Keep
                    # their identity; ordinary value boundaries in the body
                    # perform any needed logical copy.
                    loans.add(target.binding_id)
                transformed.append(replace(iterator, iterable=source, target=target))
            if prefix:
                condition = transformed[0] if isinstance(arm.condition, hir.IteratorExpression) else replace(arm.condition, iterators=transformed)
                body = arm.body
                items = body.items if isinstance(body, hir.Block) else [body]
                body = hir.Block(body.loc, body.type, items, True)
                arm = replace(arm, condition=condition, body=body)
                inner = hir.Flow(node.loc, node.type, [arm], tail)
                tail = hir.Block(node.loc, node.type, [*prefix, inner], True)
            else:
                tail = hir.Flow(node.loc, node.type, [arm], tail)
        return tail

    # Preserve callable identity while replacing its body. Effect summaries
    # run after this pass and see all introduced ownership boundaries.
    prepared = set()
    for literal in list(hir.walk(root)):
        if isinstance(literal, hir.FunctionLiteral) and not literal.proof and id(literal) not in prepared:
            prepared.add(id(literal))
            memo.clear()
            literal.body = visit(literal.body)
    return loans
