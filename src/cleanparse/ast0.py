"""
HIR 

The richest AST representation containing all the high level features in the language represented as distinct AST nodes

TODO: 
Features (i.e. each should probably get an AST node)
(a lot of stuff could probably be pulled from syntax.py)
- strings
- string interpolations
- numbers
- arrays/dicts/objects
- ranges
- complex ranges, multiple spans, etc.
- iterators
- logically combined iterators
- type system stuff? I think type-checking should be complete at this point
- 


perhaps after this phase theres a second typechecking phase making use of all the rich type information built at this phase?
"""