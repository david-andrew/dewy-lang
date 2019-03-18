//implementation of a super basic compiler/interpretor in C
//this will help me to structure how the compiler compiler will need to work in the dewy language

//probably just actually look into doing the kalidescope project from the llvm

//this toy language will have the following
//[expression] integer datatype
//[expression] addition operation (and maybe a few other simple ones)
//[statement] variable binding/update
//[statement] statement_blocks 		i.e. blocks that don't return anything
//[expression] expression_blocks	i.e. blocks that do return something
//[statement] statement_functions 	i.e. doesn't return any values
//[expression] expression_functions i.e. returns a value
//[flow control] if statements (and maybe loops)