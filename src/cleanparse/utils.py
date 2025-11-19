def truncate(s:str, max_len:int=50) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."