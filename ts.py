#ts : Tools System

def un(mod_name='us2n'):
    import sys
    #mod_name = mod.__name__
    del sys.modules[mod_name]
    
    return 