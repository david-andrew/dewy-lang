from __future__ import annotations

class Grammar:
    def __init__(self):
        # Initialize grammar rules, nonterminals, and terminals
        ...

    def transform(self):
        # Apply grammar transformations: eliminate ε-productions and unit productions
        ...

class GLLParser:
    def __init__(self, grammar: Grammar, input_string: str):
        # Initialize parser with the grammar and input string
        ...

    def parse(self):
        # Main parsing function, implementing the optimized GLL algorithm
        ...

    def create_descriptor(self, label: str, position: int, sppf_node: SPPFNode) -> Descriptor:
        # Create a descriptor for processing
        ...

    def process_descriptor(self, descriptor: Descriptor):
        # Process a descriptor, updating the parsing state
        ...

    def schedule(self, descriptor: Descriptor):
        # Schedule a descriptor for processing, following the improved scheduling strategy
        ...

    def construct_sppf(self) -> SPPFNode:
        # Efficiently construct the SPPF during parsing, merging identical nodes on-the-fly
        ...

    def extract_parse_trees(self, sppf: SPPFNode) -> list[list[str]]:
        # Extract parse trees from the SPPF using the faster extraction algorithm
        ...

class SPPFNode:
    def __init__(self, label: str, start_position: int, end_position: int):
        # Initialize an SPPF node with a label and start/end positions
        ...

    def merge(self, other_node: SPPFNode) -> SPPFNode:
        # Merge two SPPF nodes if they have the same label, start, and end positions
        ...

class Descriptor:
    def __init__(self, label: str, position: int, sppf_node: SPPFNode):
        # Initialize a descriptor with a label, position, and SPPF node
        ...

def main():
    # Load grammar and input string
    grammar = Grammar()
    input_string = "your_input_string_here"

    # Transform the grammar
    grammar.transform()

    # Create GLL parser and parse input string
    parser = GLLParser(grammar, input_string)
    parser.parse()

    # Construct SPPF
    sppf = parser.construct_sppf()

    # Extract parse trees from SPPF
    parse_trees = parser.extract_parse_trees(sppf)

if __name__ == "__main__":
    main()
