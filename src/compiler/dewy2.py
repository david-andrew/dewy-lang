"""
[redo of dewy runtime]
remove all reliance on .topy(). .eval() needs to be better fleshed out
--> .eval() means if atom type, return self, otherwise operate/evaluate until there is an atomic type
    --> eval(4) -> 4.  eval(1 + 2) -> 3. eval(() => {5}) -> 5 (or function handle?)  
FunctionHandle(AST)
--> .eval returns a Function (perhaps different name...)
--> Function.eval() evaluates the function


On each new binop AST, add an entry to the type table
--> any types that want to use that binop must register in the table first.
    registration is basically just how to get the result given the input types
    e.g. __add__ binop, need to register left:int, right:int => left + right
--> All of the binop outtype should be handled by looking up in the table
    ```
    def eval(self, scope):
        left = self.left.eval(scope)
        right = self.right.eval(scope)
        outtype = self.outtype
        if outtype is None:
            #lookup outtype based on the table
            outtype = types_table[self.__class__][left.typeof(), right.typeof()]
    
        return outtype(self.op(left.topy(), right.topy()))
    ```



implement .typeof() more extensively
--> .typeof() is basically saying, if you call .eval() on this, what type will the result be

nand, nor, xnor currently won't work work on integers, only booleans...

dealing with scopes, especially during parsing... handling function declarations, partial evaluation, etc.

handling case insensitive identifiers (e.g. for units)
"""


from abc import ABC, abstractmethod




class AST(ABC):
    
    #TODO: make accessing this raise better error if not overwritten by child class
    #      for now, just rely on exception for missing property
    # type:'Type' = None
    @abstractmethod
    def eval(self, scope:'Scope'=None) -> 'AST':
        """Evaluate the AST in the given scope, and return the result (as a dewy obj) if any"""
    @abstractmethod
    def comp(self, scope:'Scope'=None) -> str:
        """TODO: future handle compiling an AST to LLVM IR"""
    @abstractmethod
    def typeof(self, scope:'Scope'=None) -> 'Type':
        """Return the type of the object that would be returned by eval"""
    @abstractmethod
    def treestr(self, indent=0) -> str:
        """Return a string representation of the AST tree"""
    @abstractmethod
    def __str__(self) -> str:
        """Return a string representation of the AST as dewy code"""
    @abstractmethod
    def __repr__(self) -> str:
        """Return a string representation of the python objects making up the AST"""
