#BSR and SPPF implementations + convert from BSR to SPPF


"""
extractSPPF (Υ, Γ)
{
    G := empty graph
    let S be the start symbol of Γ
    let n be the extent of Υ
    if Υ has an element of the form (S ::= α, 0, k, n)
    {
        create a node labelled (S, 0, n) in G
        while G has an extendable leaf node
        {
            let w = (μ, i, j) be an extendable leaf node of G
            if (μ is a nonterminal X in Γ)
            {
                for each (X ::= γ, i, k, j) ∈ Υ 
                { 
                    mkPN(X ::= γ·, i, k, j, G) 
                } 
            }
            else
            {
                suppose μ is X ::= α·δ
                if (|α| = 1)
                {
                    mkPN(X ::= α·δ, i, i, j, G)
                }
                else for each (α, i, k, j) ∈ Υ 
                { 
                    mkPN(X ::= α·δ, i, k, j, G) 
                } 
            } 
        } 
    }
    return G
}

mkPN(X ::= α·δ, i, k, j, G)
{
    make a node y in G labelled (X ::= α·δ, k)
    if (α = ϵ)
    {
        mkN(ϵ, i, i, y, G)
    }
    if (α = βx, where |x| = 1)
    {
        mkN(x, k, j, y, G)
        if (|β| = 1)
        {
            mkN(β, i, k, y, G)
        }
        if (|β| > 1)
        {
            mkN(X ::= β·xδ, i, k, y, G) 
        }
    }
}

mkN (Ω, i, j, y, G)
{
    if there is not a node labelled (Ω, i, j) in G make one
    add an edge from y to the node (Ω, i, j) 
}
"""