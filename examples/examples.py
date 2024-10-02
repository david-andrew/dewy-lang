#TODO: imports...


def hello(root:Scope) -> AST:
    """printl('Hello, World!')"""
    return Call('printl', Array([String('Hello, World!')]))


def hello_func(root:Scope) -> AST:
    """
    {
        main = () => {printl('Hello, World!')}
        main
    }
    """
    return Block([
        Bind(
            'main',
            Function(
                [],
                Call('printl', Array([String('Hello, World!')])),
                root
            )
        ),
        Call('main'),
    ])
   

def anonymous_func(root:Scope) -> AST:
    """
    {
        (() => printl('Hello, World!'))()
    }
    """
    return Block([
        Call(
            Function(
                [],
                Call('printl', Array([String('Hello, World!')])),
                root
            )
        ),
    ])

def hello_name(root:Scope) -> AST:
    """
    {
        print("What's your name? ")
        name = readl()
        printl('Hello {name}!')
    }
    """
    return Block([
        Call('print', Array([String("What's your name? ")])),
        Bind('name', Call('readl')),
        Call('printl', Array([IString([String('Hello '), Call('name'), String('!')])])),
    ])


def if_else(root:Scope) -> AST:
    """
    {
        print("What's your name? ")
        name = readl()
        if name =? 'Alice' printl('Hello Alice!')
        else printl('Hello stranger!')
    }
    """
    return Block([
        Call('print', Array([String("What's your name? ")])),
        Bind('name', Call('readl')),
        Flow([
            If(
                Equal(Call('name'), String('Alice')),
                Call('printl', Array([String('Hello Alice!')]))
            ),
            Call('printl', Array([String('Hello Stranger!')])),
        ])
    ])


def if_else_if(root:Scope) -> AST:
    """
    {
        print("What's your name? ")
        name = readl()
        if name =? 'Alice' printl('Hello Alice!')
        else if name =? 'Bob' printl('Hello Bob!')
        else printl('Hello stranger!')
    }
    """
    return Block([
        Call('print', Array([String("What's your name? ")])),
        Bind('name', Call('readl')),
        Flow([
            If(
                Equal(Call('name'), String('Alice')),
                Call('printl', Array([String('Hello Alice!')]))
            ),
            If(
                Equal(Call('name'), String('Bob')),
                Call('printl', Array([String('Hello Bob!')]))
            ),
            Call('printl', Array([String('Hello Stranger!')])),
        ])
    ])


def hello_loop(root:Scope) -> AST:
    """
    {
        print("What's your name? ")
        name = readl()
        i = 0
        loop i <? 10 {
            printl('Hello {name}!')
            i = i + 1
        }
    }
    """
    return Block([
        Call('print', Array([String("What's your name? ")])),
        Bind('name', Call('readl')),
        Bind('i', Number(0)),
        Loop(
            Less(Call('i'), Number(10)),
            Block([
                Call('printl', Array([IString([String('Hello '), Call('name'), String('!')])])),
                Bind('i', Add(Call('i'), Number(1), Number)),
            ])
        )
    ])


def unpack_test(root:Scope) -> AST:
    """
    {
        s = ['Hello' ['World' '!'] 5 10]
        printl('s={s}')
        a, b, c, d = s
        printl('a={a} b={b} c={c} d={d}')
        a, ...b = s
        printl('a={a} b={b}')
        ...a, b = s
        printl('a={a} b={b}')
        a, [b, c], ...d = s
        printl('a={a} b={b} c={c} d={d}')

        //error tests
        //a, b, c, d, e = s         //error: not enough values to unpack
        //a, b = s                  //error: too many values to unpack
        //a, ...b, c, d, e, f = s   //error: too many values to unpack

        //TBD how unpack would handle `a, ...b, c, d, e = s`. Probably b would be empty?
    }
    """

    return Block([
        Bind('s', Array([String('Hello'), Array([String('World'), String('!')]), Number(5), Number(10)])),
        Call('printl', Array([IString([String('s='), Call('s')])])),
        Unpack(['a', 'b', 'c', 'd'], Call('s')),
        Call('printl', Array([IString([String('a='), Call('a'), String(' b='), Call('b'), String(' c='), Call('c'), String(' d='), Call('d')])])),
        Unpack(['a', '...b'], Call('s')),
        Call('printl', Array([IString([String('a='), Call('a'), String(' b='), Call('b')])])),
        Unpack(['...a', 'b'], Call('s')),
        Call('printl', Array([IString([String('a='), Call('a'), String(' b='), Call('b')])])),
        Unpack(['a', ['b', 'c'], '...d'], Call('s')),
        Call('printl', Array([IString([String('a='), Call('a'), String(' b='), Call('b'), String(' c='), Call('c'), String(' d='), Call('d')])])),

        # Test unpacking too few/many values
        # Unpack(['a', 'b', 'c', 'd', 'e'], Call('s')),         # error: not enough values to unpack
        # Unpack(['a', 'b'], Call('s')),                        # error: too many values to unpack
        # Unpack(['a', '...b', 'c', 'd', 'e', 'f'], Call('s')), # error: too many values to unpack
    ])


def range_iter_test(root:Scope) -> AST:
    """
    {
        r = [0,2..20]
        it = iter(r)
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it)) //last iteration. should return [true, 20]
        printl(next(it)) //should return [false, undefined]
        printl(next(it))
        printl(next(it))
    }
    """
    return Block([
        Bind('r', Range(Number(0), Number(2), Number(20))),
        Bind('it', RangeIter(Call('r'))),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])), #should print [False, None] since the iterator is exhausted
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
    ])


def loop_iter_manual(root:Scope) -> AST:
    """
    {
        it = iter([0,2..10])
        [cond, i] = next(it)
        loop cond {
            printl(i)
            [cond, i] = next(it)
        }
    }
    """
    return Block([
        Bind('it', RangeIter(Range(Number(0), Number(2), Number(10)))),
        Unpack(['cond', 'i'], Next(Call('it'))),

        Loop(
            Call('cond'),
            Block([
                Call('printl', Array([Call('i')])),
                Unpack(['cond', 'i'], Next(Call('it'))),
            ])
        )
    ])



def loop_in_iter(root:Scope) -> AST:
    """
    {
        loop i in [0,2..10] printl(i)
    }
    """
    return Loop(
        In('i', Range(Number(0), Number(2), Number(10))),
        Call('printl', Array([Call('i')])),
    )
   

def nested_loop(root:Scope) -> AST:
    """    
    loop i in [0,2..10]
        loop j in [0,2..10]
            printl('{i},{j}')
    """
    return Loop(
        In('i', Range(Number(0), Number(2), Number(10))),
        Loop(
            In('j', Range(Number(0), Number(2), Number(10))),
            Call('printl', Array([IString([Call('i'), String(','), Call('j')])])),
        )
    )



def block_printing(root:Scope) -> AST:
    """
    {
        loop i in [0,2..5] {
            loop j in [0,2..5] {
                loop k in [0,2..5] {
                    loop l in [0,2..5] {
                        loop m in [0,2..5] {
                            printl('{i},{j},{k},{l},{m}')
                        }
                    }
                }
            }
        }
    }
    """
    return Block([
        Loop(
            In('i', Range(Number(0), Number(2), Number(5))),
            Block([
                Loop(
                    In('j', Range(Number(0), Number(2), Number(5))),
                    Block([
                        Loop(
                            In('k', Range(Number(0), Number(2), Number(5))),
                            Block([
                                Loop(
                                    In('l', Range(Number(0), Number(2), Number(5))),
                                    Block([
                                        Loop(
                                            In('m', Range(Number(0), Number(2), Number(5))),
                                            Block([
                                                Call('printl', Array([IString([Call('i'), String(','), Call('j'), String(','), Call('k'), String(','), Call('l'), String(','), Call('m')])])),
                                            ])
                                        )
                                    ])
                                )
                            ])
                        )
                    ])
                )
            ])
        )
    ])

def rule110(root:Scope) -> AST:
    """
    progress = world:vector<bit> => {
        update:bit = 0
        loop i in 0..world.length
        {
            if i >? 0 world[i-1] = update //TODO: #notfirst handled by compiler unrolling the loop into prelude, interludes, and postlude
            update = 0b01110110 << (world[i-1..i+1] .?? 0 .<< [2 1 0])
        }
        world.push(update)
    }

    world: vector<bit> = [1]
    loop true
    {
        printl(world)
        progress(world)
    }
    """

    #rule 110
    #TODO: handle type annotations in AST
    return Block([
        Bind(
            'progress', 
            Function(
                [Arg('world', Type('vector', [Type('bit')]))], 
                Block([
                    Bind('cell_update', Number(0)),
                    # loop i in 0..world.length
                    #     if i >? 0 world[i-1] = cell_update
                    #     update = (0b01110110 << (((world[i-1] ?? 0) << 2) or ((world[i] ?? 0) << 1) or (world[i+1] ?? 0)))
                    # world.push(update)
                    #etc....
                ]), 
                root
            ),
            # Type('function', [Type('vector', [Type('bit')]), Type('vector', [Type('bit')])]),
        ),
        Let('world', Type('vector', [Type('bit')])),
        Bind(
            'world',
            Array([Number(1)]),
        ),
        # loop true
        #     printl(world)
        #     update(world)
    ])




if __name__ == '__main__':
    show = True
    show_verbose = True
    run = True

    progs = [
        hello,
        hello_func,
        anonymous_func,
        hello_name,
        if_else,
        if_else_if,
        hello_loop,
        unpack_test,
        range_iter_test,
        loop_iter_manual,
        loop_in_iter,
        nested_loop,
        block_printing,
        # rule110,
    ]

    for prog in progs:
        #set up root scope with some functions
        root = Scope.default()

        # get the program AST
        ast = prog(root)

        # display and or run the program
        if show:
            print(ast)
        if show_verbose:
            print(repr(ast))
        if run:
            ast.eval(root)

        print('----------------------------------------')




###############################################################################



# TODO: broken. probably set up scope with some default values
def test_many_lines():
    """
    Parse each line of syntax3.dewy one at a time for testing
    """
    # load the syntax3 file and split the lines
    with open('../../examples/syntax3.dewyl') as f:
        lines = f.read().splitlines()

    # set up a scope with declarations for all of the variables used in the example file
    root = Scope.default()
    root.let('x', Number.type)
    root.let('y', Number.type)
    root.let('z', Number.type)

    for line in lines:
        tokens = tokenize(line)
        post_process(tokens)

        # skip empty lines
        if len(tokens) == 0:
            continue

        # print the line, and run it
        print('-'*80)
        print(tokens)

        ast = top_level_parse(tokens)
        print(ast)

        # TODO: maybe later we can run the file. potentially declare all the values used at the top?
        # res = ast.eval(root)
        # if res: print(res)


def test_hello():
    # line = "'Hello, World!'"
    line = r"""
print'What is your name? '
name = readl
printl'Hello {name}'
a = 4(5)
b = -5
c = /4
d = 1,2,3,4,5
printl'a={a}, b={b}, c={c} d={d}'
"""

    tokens = tokenize(line)
    post_process(tokens)

    # DEBUG
    # tokens = [Identifier_t('printl'), Juxtapose_t(''), Identifier_t('readl')]

    ast = top_level_parse(tokens)
    root = Scope.default()
    ast.eval(root)


def test_example_progs():

    funcs = [hello, hello_func, anonymous_func, hello_name, if_else, if_else_if, hello_loop,
             unpack_test, range_iter_test, loop_iter_manual, loop_in_iter, nested_loop, block_printing]

    for func in funcs:
        src = func.__doc__
        print(f'Parsing source:\n{src}\n')
        tokens = tokenize(src)
        post_process(tokens)

        ast = top_level_parse(tokens)
        root = Scope.default()
        ast.eval(root)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_file(sys.argv[1])
    else:
        # test_hello()
        # test_example_progs()
        test_many_lines()

    # print("Usage: `python parser.py [path/to/file.dewy>]`")
