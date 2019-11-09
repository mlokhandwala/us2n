#from machine import UART

#u1 = UART(1)                                                                                                        
#u1.init(921600,bits=8,parity=None, stop=1)
#u1.write('Y')
#print(u1.read())

def _slowSendData(uart, text):
    import time
    for c in text:
        uart.write(c)
        time.sleep_ms(1) # Delay 1 ms to avoid overrun

def testUART():
    from machine import UART; import time

    u2 = UART(2) 
    u2.init(921000, bits=8, parity=None, stop=1)
    time.sleep_ms(100)
    print(u2.write('Y'))
    time.sleep_ms(100)
    print(u2.read())
    time.sleep_ms(100)
    print(u2)
    
def sts(text = '\\'): #send to system
    from machine import UART; import time

    u2 = UART(2) 
    u2.init(921000, bits=8, parity=None, stop=1)
    time.sleep_ms(10)
    _slowSendData(u2, text)
    time.sleep_ms(10)
    print('sent:' + str(text))
    
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
    

def brakepin(num = -1):
    try:
        import json

        with open('us2n.json') as f: #readonly
            j = json.load(f)
            
            if num == -1:
                print('Get BrakePin:' + str(j['brakepin']))
            elif num > 0:
                j['brakepin'] = num
                print('Set BrakePin:' + str(j['brakepin']))
            elif num < -1: # < -1 means delete
                del j['brakepin']
                print('Del BrakePin')
            
            f.close();
            f = open('us2n.json', 'w')
            json.dump(j, f)
            f.close()
        
    except Exception as e:
        print(str(e))

    
    
def run():
    import us2n
    s = us2n.server()
    s.serve()
    
    

    