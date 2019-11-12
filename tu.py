#ts : Tools Utilities

#u1 = UART(1)                                                                                                        
#u1.init(921600,bits=8,parity=None, stop=1)
#u1.write('Y')
#print(u1.read())

config = None

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

def notify():    
    # import socket
    # #http://api.pushingbox.com/pushingbox?devid=vF76606BF68C0BFE
    # s = socket.socket()
    # ai = socket.getaddrinfo("api.pushingbox.com", 80)
    # print("Address infos:", ai)
    # addr = ai[0][-1]
    # print("Address", addr)
    # s.connect(addr)
    
    # s.send(b"GET /pushingbox?devid=vF76606BF68C0BFE HTTP/1.0\r\n\r\n")
    # print(s.recv(4096))

    # s.close()
    import urequests as requests
    
    response = requests.get('http://api.pushingbox.com/pushingbox?devid=vF76606BF68C0BFE')
    
    print(response.status_code)

def parsesys(txt):
    import re
    st = str(txt)

    temp = re.search(r'T\d* T(\d*)', st); temp = None if temp is None else temp.group(1)
    pt = re.search(r'PT:(\d*)',st); pt = None if pt is None else pt.group(1)
    rt = re.search(r'RT:(\d*)',st); rt = None if rt is None else rt.group(1)
    bpd = re.search(r'BPD:(\d*)',st); bpd = None if bpd is None else bpd.group(1)
    bpr = re.search(r'BPR:(\d*)',st); bpr = None if bpr is None else bpr.group(1)
    ms = re.search(r'MS:(\d*)', st); ms = None if ms is None else ms.group(1)
    st = re.search(r'ST:(\d*)', st); st = None if st is None else st.group(1)
    tic = re.search(r'S\d* (\d+)', st); tic = None if tic is None else tic.group(1)

    print('{},{},{},{},{},{},{},{}'.format(temp, pt, rt, bpd, bpr, ms, st, tic))


    
def sts(text = '\\'): #send to system
    from machine import UART; import time

    u2 = UART(2) 
    u2.init(921000, bits=8, parity=None, stop=1)
    time.sleep_ms(10)
    _slowSendData(u2, text)
    time.sleep_ms(10)
    print('sent:' + str(text))

    import time
    time.sleep_ms(100)

    data = u2.read()
    print(data)
    return data

    
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
        
        f.close()
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

            f.close()
            f = open('us2n.json', 'w')
            json.dump(j, f)
            f.close()

    except Exception as e:
        print(str(e))


def configset(name, value):
    try:
        import json

        with open('us2n.json') as f:  # readonly
            j = json.load(f)

            j[name] = value
            print(j)

            f.close()
            f = open('us2n.json', 'w')
            json.dump(j, f)
            f.close()

    except Exception as e:
        print(str(e))

def configget(name):
    try:
        import json

        with open('us2n.json') as f:  # readonly
            j = json.load(f)

            print(j[name])

            f.close()

    except Exception as e:
        print(str(e))

def bp(): # brake pulse
    from machine import Pin
    import json
    
    import time
    with open('us2n.json') as f: #readonly
        j = json.load(f)

    BrakePinNo = int(j.setdefault('brakepin', 0))
    if BrakePinNo != 0:
        BrakePin = Pin(BrakePinNo, Pin.OUT) # pull up to avoid float

    if BrakePin is None: # set during init so if config present should be not None
        print("Wakeup not possible, no break pin")
        return

    BrakePin.off()
    time.sleep_ms(10)
    BrakePin.on()
    time.sleep_ms(10)
    BrakePin.off()

    print("Wakeup exeuted on BrakePin")

def reset():
    import machine
    machine.reset()

def readConfig():
    import json

    global config
    
    with open('us2n.json') as f: #readonly
        config = json.load(f)

def brake(on = 1):
    global config
    
    if config is None:
        readConfig()
        
    from machine import Pin
    
    p = Pin(config['brakepin'], Pin.OUT)
    
    if on == 1:
        p.on()
    else:
        p.off()

def run():
    import us2n
    s = us2n.server()
    s.serve()
    
    

    