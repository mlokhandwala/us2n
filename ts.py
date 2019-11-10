#ts : Tools System

def unload(mod):
    import sys
    mod_name = mod.__name__
    del sys.modules[mod_name]
    
    return 