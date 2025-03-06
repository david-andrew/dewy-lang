from .qbe import QbeArg, QbeType, QbeModule, QbeBlock, QbeFunction


m = QbeModule()
m.global_data.append(r'data $str = { b "helldajgdjahgsdo world\0" }')
m.functions.append(
    QbeFunction(
        name='$main',
        export=True,
        args=[QbeArg(r'%argc', 'w'), QbeArg(r'%argv', 'l')],
        ret='w',
        blocks=[
            QbeBlock(
                label='@apple',
                lines=[
                    # debug get and print argv[0]
                    '%.0 =l loadl %argv',
                    # '%stdout = global stdout',
                    'call $printf(l %.0)',
                    'call $putchar(w 10)',
                    'call $printf(l $str)',
                    'call $putchar(w 10)',
                    'ret 0'
                ]
            )
        ]
    )
)


print(m)