# Bootstrap frontends

The C stage zero (`../stage0/`) implements only the implementation language.
While it builds the first compiler generation, `frontend.jo` and `dewy_fmt.jo`
replace their counterparts in `../compiler/` so that generation needs no Dewy
frontend. That compiler then builds the complete compiler, which builds itself
again.
