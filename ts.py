#ts : Tools System

def unload(mod_name):
    import sys
    #mod_name = mod.__name__
    del sys.modules[mod_name]
    
    return 