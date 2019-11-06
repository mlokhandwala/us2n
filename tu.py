#from machine import UART

#u1 = UART(1)                                                                                                        
#u1.init(921600,bits=8,parity=None, stop=1)
#u1.write('Y')
#print(u1.read())

def testUART():
    from machine import UART; import time

    u2 = UART(2); 
    u2.init(921000, bits=8, parity=None, stop=1)
    time.sleep_ms(100)
    print(u2.write('Y'))
    time.sleep_ms(100)
    print(u2.read())
    time.sleep_ms(100)
    print(u2)
    
    
def sds(src): # switch data source
    if src is None:
        print('Provide source name as parameter')
        return
    try:
        import json
        d = open(src) # check if src file exists
        d.close()

        f = open('us2n.json') #readonly
        j = json.load(f)
        j['simdata'] = src
        
        f.close();
        f = open('us2n.json', 'w')
        json.dump(j, f)
        f.close()
        
        
    except Exception as e:
        print(str(e))
    
def ls(src = '/'): # ls dir
    import os
    l = os.listdir(src)
    for n in l:
        stat = os.stat(n)
        print("{} {}".format(str(n), stat[6])) # print name 

def cat(fname = 'us2n.json'):
    with open(fname, 'r') as f:
        print(f.read())

def rm(src):
    import os
    os.remove(src)
    

    