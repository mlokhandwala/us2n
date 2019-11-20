# us2n.py

import json
import time
import select
import socket
import machine
import network
import re
from machine import Timer
from machine import ADC, Pin
import machine
import ntptime
import sys


print_ = print
VERBOSE = 1

gEnterCommandMode = 'XXXXXXXXXXX'

class RingBuffer:
    def __init__(self, size):
        self.size = size
        self.data = [0 for i in range(self.size)]

    def initialize(self, initfn):
        for i in range(self.size):
            self.append(initfn())

    def append(self, x):
        self.data.pop(0)
        self.data.append(x)

    def get(self):
        return self.data

class Temperature:
    
    
    def __init__(self):
        self.adcP1 = ADC(Pin(33))          # create ADC object on ADC pin
        self.adcP1.atten(ADC.ATTN_11DB)    # set 11dB input attenuation (voltage range roughly 0.0v - 3.6v)
        self.adcP1.width(ADC.WIDTH_12BIT)   # set 9 bit return values (returned range 0-511)
        
        self.several = RingBuffer(10)
        self.several.initialize(self.getTemperature)

    def getTemperature(self):
        raw = self.adcP1.read()
        voltage = (raw / 1.13) # from observation & calculation. 290mV gives 240 reading but 1.5V gives 1700 reading. 4096 / 3600 also = 1.13 so using that
        tempC = voltage * 0.1
        
        #if 'several' in vars(Temperature):
        self.several.append(tempC)
        
        return tempC
        
    def getAvTemp(self):
        return sum(self.several.get()) / len(self.several.get())
        
        

tempsensor = Temperature()


class Simulator:

    flagSendData = 0
    flagExit = 0
    inFile = None
    timer = None
    expr = None
    inFileName = None

    bridge = None

    logfile = None

    flagSimRun = 0

    server = None
    flagCommandMode = 0
    BrakePinNo = 0
    BrakePin = None

    TIMER_INTERVAL = 50 #ms
    TIMER_MINUTE = 60 * 1000 / TIMER_INTERVAL
    
    keepAwakeCommand = '\\' # \ = Invalid commnand, Just to keep awake
    

    def log(self, message):
        try:
            if self.logfile is None:
                self.logfile = open('/log.txt', 'a+')

            if self.logfile is None:
                return

            t = machine.RTC().datetime()
            self.logfile.write("[{}:{}:{}:{}:{}:{}:{}] {}".format(t[0],t[1],t[2],t[3],t[4],t[4],t[6], message))
        except Exception as e:
            print('Failed to open log file')
            sys.print_exception(e)

    def record(self, field3 = None, field4 = None, field5 = None):
        import urequests as requests

        try:
            if self.recorderurl is None:
                return

            url = self.recorderurl
            url += "&field1={}".format(tempsensor.getAvTemp())
            url += "&field2={}".format(time.time() - self.simrecordedtime)

            url += "&field6={}".format(self.linecount)
            url += "&field7={}".format(self.parsesys()) # Get system info
            self.simrecordedtime = time.time() # We record time difference only so that we can add them in summary

            if field3 is not None:
                url += "&field3={}".format(field3)

            if field4 is not None:
                url += "&field4={}".format(field4)

            if field5 is not None:
                url += "&field5={}".format(field5)


            #print(url)
            attempt = 0

            while attempt < 5:
                response = requests.get(url)

                if response.status_code == 200:
                    response.close()
                    break
                else:
                    attempt += 1
                    print("ERecFailed:".format(response.status_code))
                    time.sleep_ms(100)  # wait a bit before retrying. server may be throttling or busy
                    response.close()

            import gc
            gc.collect()

        except Exception as e:
            self.logConsoles(str(e))
            self.log(str(e))
            sys.print_exception(e)

    def notify(self):    
        import urequests as requests

        try:
            if self.notifyurl is None:
                return

            response = requests.get(self.notifyurl)
            print(response.status_code)
            response.close()
        except Exception as e:
            self.log(str(e))
            sys.print_exception(e)

    def viewLog(self):
        if self.logfile is not None:
            self.logfile.seek(0,0)
            self.bridge.client.sendall(self.logfile.read())
        else:
            self.bridge.client.sendall('Log file does not exist')
        
    def delLog(self):
        self.logfile.close()
        import os
        os.remove('/log.txt')
        self.logfile = None
        
    def wakeup(self):
        if self.BrakePin is None: # set during init so if config present should be not None
            self.logConsoles('Wakeup not possible, no break pin')
            return

        self.BrakePin.off()
        time.sleep_ms(10)
        self.BrakePin.on()
        time.sleep_ms(10)
        self.BrakePin.off()

        self.logConsoles('Wakeup exeuted on BrakePin')

    def logConsoles(self, text):
        try:
            print(str(text))
            if self.bridge is not None and self.bridge.client is not None:
                self.bridge.client.sendall(str(text))
        except Exception as e:
            print(str(e))
            sys.print_exception(e)


    def __init__(self, config):
        self.simrun = 0
        self.linecount = 0
        self.recordtickcounter = 0
        self.simrecordedtime = time.time()
        self.server = server
        self.isCommandMode = False
        self.inFileName = config.setdefault('simdata', 'ecu.data')
        self.BrakePinNo = int(config.setdefault('brakepin', 0))
        if self.BrakePinNo != 0:
            self.BrakePin = Pin(self.BrakePinNo, Pin.OUT) # pull up to avoid float
            self.BrakePin.off()
            self.logConsoles("BreakPin:" + str(self.BrakePin))

        self.notifyurl = config.setdefault('notifyurl', None)
        self.recorderurl = config.setdefault('recorderurl', None)
        self.autostartsim = config.setdefault('autostartsim', 0)
        self.recordinterval = config.setdefault('recordinterval', 5)

        try:
            ntptime.settime()
        except Exception as e:
            self.logConsoles(str(e))
            self.log(str(e))
            sys.print_exception(e)

        self.logConsoles("Simulation File Name: {0}".format(self.inFileName))

    def timerTickHandler(self, timer):
        if self.flagSimRun == 1:
            self.flagSendData = 1
        elif self.bridge.uart is not None:
            if self.flagCommandMode == 1:
                self.bridge.uart.write(self.keepAwakeCommand)
                
        self.recordtickcounter += 1
        if self.recordtickcounter >= (self.TIMER_MINUTE * self.recordinterval) and self.flagSimRun == 1:
            self.record()
            self.recordtickcounter = 0 # Reset for next trigger

    def startSimulation(self):
        if self.bridge.uart is None: # for autostart without client
            self.bridge.open_uart()

        self.slowSendData(gEnterCommandMode)
        self.flagCommandMode = 1
        self.flagSimRun = 1
        self.recordtickcounter = 0
        print("flagSimRun, flagCommandMode = 1")
        self.simstarttime = time.time()
        self.record(field3='SimStarted')

    def startSimulator(self, bridge):
        if(self.inFile is None):
            if(self.inFileName == None):
                self.logConsoles("Simulation data file name not found")
                return

            self.inFile = open(self.inFileName, 'r')
            if(self.inFile is None):
                self.logConsoles("Simulation data file not found")
                return
        else:
            self.logConsoles("Resuming Simulation") # won't get called as this function is not called twice.

        self.bridge = bridge
        self.expr = re.compile(',')

        if(self.timer == None):
            self.timer = Timer(-1)
            self.timer.init(period=50, mode=Timer.PERIODIC, callback=self.timerTickHandler)

        self.simrun += 1

        if self.bridge.client is not None:
            self.bridge.client.sendall('Simulation Run Started: ' + str(self.simrun))

        self.log('Simulation Run Started:{}'.format(self.simrun))
        self.notify()
        self.record(field3='Server Started')

        if self.autostartsim == 1:
            self.startSimulation()

    def stopSimulator(self):
        if(self.timer != None):
            self.timer.deinit()

        self.timer = None


    def reRunSimulator(self):
        self.inFile.seek(0, 0)

#        self.log('Simulation Run End, Line Count: ' + str(self.linecount))
        self.simrun += 1
        self.linecount = 0

        if self.bridge.client is not None:
            self.bridge.client.sendall('Simulation Run Started:{}'.format(self.simrun))
#        self.log('Simulation Run Started: ' + str(self.simrun))

    def slowSendData(self, text):
        for c in text:
            self.bridge.uart.write(c)
            time.sleep_ms(1) # Delay 1 ms to avoid overrun


    def isSystemInCommandMode(self, s):
        s = str(s)
        if s.find('Press') != -1 and s.find('X') != -1:
            return True
        else:
            return False

    def sendData(self):
        try:
            if self.flagSendData == 0:
                return

            if(self.inFile is None):
                return

            if self.isCommandMode == False:         # Redundant for safety
                self.slowSendData(gEnterCommandMode)

            line = self.inFile.readline(100)
            self.linecount += 1

            #self.logConsoles('X:' + line) #debug

            if(line == ''):
                self.reRunSimulator()
                return

            data = self.expr.split(line)

            if(data):
                nRpm = int(data[0])
                nSpeed = int(data[1])
                nBreak = int(data[2])
                
                if nRpm < 0 or nRpm > 7000 or nSpeed < 0 or nSpeed > 200 or nBreak < 0 or nBreak > 1:
                    return # Bad data, try again since we are not resetting the flag.
                    
                #print("{:04d}:{:03d}:{:01d}:{}".format(nRpm, nSpeed, nBreak, str(time.ticks_ms())))
                
                if self.BrakePin is None:
                    command = ("`{:04d} {:03d} {:01d} ".format(nRpm, nSpeed, nBreak)) # space between fields to allow placing null to split string in recieving code. 
                else:
                    command = ("`{:04d} {:03d} {:01d} ".format(nRpm, nSpeed, 2 if nBreak == 0 else 3)) # if externally controlling brake, set brake not (0,1) so 2,3. 
                    if nBreak == 0:
                        self.BrakePin.off()
                    else:
                        self.BrakePin.on()                
                print("[{}] {}".format(self.linecount, command))                
                self.slowSendData(command)
                
#                if self.linecount == 0 or self.linecount % 1000 == 0:
#                    self.log('Run:{} Line:{}'.format(self.simrun, self.linecount))

            self.flagSendData = 0
        except Exception as e: # most likely due to conversion error in data
            self.logConsoles(str(e))
            self.log(str(e))
            sys.print_exception(e)

    def parsesys(self):
        import re
        try:
            if self.bridge.uart is None: # for autostart without client
                self.bridge.open_uart()

            self.bridge.uart.read() # just cleanup
            self.bridge.uart.write('S')
            time.sleep_ms(20)
            s = self.bridge.uart.read()
            if s is None:
                return ' '

            st = str(s)

            temp = re.search(r'T\d* T(\d*)', st); temp = None if temp is None else temp.group(1)
            pt = re.search(r'PT:(\d*)',st); pt = None if pt is None else pt.group(1)
            rt = re.search(r'RT:(\d*)',st); rt = None if rt is None else rt.group(1)
            bpd = re.search(r'BPD:(\d*)',st); bpd = None if bpd is None else bpd.group(1)
            bpr = re.search(r'BPR:(\d*)',st); bpr = None if bpr is None else bpr.group(1)
            ms = re.search(r'MS:(\d*)', st); ms = None if ms is None else ms.group(1)
            stl = re.search(r'ST:(\d*)', st); stl = None if stl is None else stl.group(1)
            tic = re.search(r'S\d* (\d+)', st); tic = None if tic is None else tic.group(1)

            return '{}_{}_{}_{}_{}_{}_{}_{}'.format(temp, pt, rt, bpd, bpr, ms, stl, tic)
        except Exception as e:
            self.logConsoles(str(e))
            self.log(str(e))
            sys.print_exception(e)

def print(*args, **kwargs):
    if VERBOSE:
        print_(*args, **kwargs)


def read_config(filename='us2n.json', obj=None, default=None):
    with open(filename, 'r') as f:
        config = json.load(f)
        if obj is None:
            return config
        return config.get(obj, default)


def parse_bind_address(addr, default=None):
    if addr is None:
        return default
    args = addr
    if not isinstance(args, (list, tuple)):
        args = addr.rsplit(':', 1)
    host = '' if len(args) == 1 or args[0] == '0' else args[0]
    port = int(args[1])
    return host, port


def UART(config):
    config = dict(config)
    port = config.pop('port')
    uart = machine.UART(port)
    uart.init(**config)
    #uart.init(921000, bits=8, parity=None, stop=1)
    return uart


class Bridge:

    simulator = None

    def __init__(self, config, simulator):
        super().__init__()
        self.config = config
        self.uart = None
        self.uart_port = config['uart']['port']
        self.tcp = None
        self.address = parse_bind_address(config['tcp']['bind'])
        self.bind_port = self.address[1]
        self.client = None
        self.client_address = None
        self.simulator = simulator

    def bind(self):
        tcp = socket.socket()
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    #    tcp.setblocking(False)
        tcp.bind(self.address)
        tcp.listen(5)
        print('Bridge listening at TCP({0}) for UART({1})'
              .format(self.bind_port, self.uart_port))
        self.tcp = tcp
        return tcp

    def process_command(self, data):
        try:
            if data.find('|S') != -1: # Simulate
                self.simulator.startSimulation()
                return True
            if data.find('|C') != -1: # Command mode, just enter it on device
                self.simulator.slowSendData(gEnterCommandMode)
                self.simulator.flagCommandMode = 1 if self.simulator.flagCommandMode == 0 else 0
                print("flagCommandMode = " + str(self.simulator.flagCommandMode))
                return True
            elif data.find('|T') != -1: # sTop
                print("flagSimRun = 0")
                self.simulator.flagSimRun = 0
                self.simulator.record(field3='SimStopped')
                return True
            elif data.find('|E') != -1: #Exit
                print("flagExit = 1")
                self.simulator.flagExit = 1
                self.simulator.record(field3='ServerExit')
                return True
            elif data.find('|ViewLog') != -1: #View Log file 
                self.simulator.viewLog()
                return True
            elif data.find('|DelLog') != -1: #Delete Log file 
                self.simulator.delLog()
                return True
            elif data.find('|W') != -1: #Wake System file 
                self.simulator.wakeup()
                return True
            elif data.find('|M') != -1: #Mock Data
                command = data.split('|M')[1][:12] 
                self.simulator.slowSendData(command)
                return True                
        except Exception as e:
            self.simulator.logConsoles(str(e))
            self.simulator.log(str(e))
            sys.print_exception(e)
           
        
        return False

    def fill(self, fds):
        if self.uart is not None:
            fds.append(self.uart)
        if self.tcp is not None:
            fds.append(self.tcp)
        if self.client is not None:
            fds.append(self.client)
        return fds

    def handle(self, fd):
        try:
            if fd == self.tcp:
                self.close_client()
                self.open_client()
            elif fd == self.client:
                data = self.client.recv(4096)
                if data:
                    print('TCP({0})->UART({1}) {2}'.format(self.bind_port, self.uart_port, data))

                    if(self.process_command(str(data)) == False):
                            self.uart.write(data)

                else:
                    print('Client ', self.client_address, ' disconnected')
                    self.close_client()
            elif fd == self.uart:
                data = self.uart.read()
                print('UART({0})->TCP({1}) {2}'.format(self.uart_port,
                                                       self.bind_port, data))
                if self.client is not None:
                    #self.client.sendall("{}[{:3.2f}]\n\r".format(data, tempsensor.getTemperature()))
                    self.client.sendall(data)
                self.simulator.isCommandMode = self.simulator.isSystemInCommandMode(data)
                #self.client.sendall(data)
        except Exception as e:
            self.simulator.logConsoles(str(e))
            self.simulator.log(str(e))
            sys.print_exception(e)

    def xhandle(self, fd):
        print('Client ', self.client_address, ' disconnected')
        self.close_client()
             
    def close_client(self):
        if self.client is not None:
            print('Closing client ', self.client_address)
            self.client.close()
            self.client = None
            self.client_address = None
        if self.uart is not None:
            pass
#            self.uart.deinit()
#            self.uart = None

    def open_uart(self):
        self.uart = UART(self.config['uart'])
        print(self.uart)

    def open_client(self):
        self.uart = UART(self.config['uart'])
        print(self.uart)
        self.client, self.client_address = self.tcp.accept()
        print('Accepted connection from ', self.client_address)

    def close(self):
        self.close_client()
        if self.tcp is not None:
            print('Closing TCP server {0}...'.format(self.address))
            self.tcp.close()
            self.tcp = None



class S2NServer:

    simulator = None

    def __init__(self, config):
        self.config = config
        self.simulator = Simulator(config)

    def serve(self):
        try:
            self._serve_forever()
        except KeyboardInterrupt:
            print('Ctrl-C pressed or Exit Command Recieved.')

    def bind(self):
        bridges = []
        for config in self.config['bridges']:
            bridge = Bridge(config, self.simulator)
            bridge.bind()
            bridges.append(bridge)
        return bridges

    def _serve_forever(self):
        bridges = self.bind()

        self.simulator.startSimulator(bridges[0])

        try:
            while True:
                fds = []
                for bridge in bridges:
                    bridge.fill(fds)
                rlist, _, xlist = select.select(fds, (), fds, 0.005)

                if self.simulator.flagSimRun == 1:
                    self.simulator.sendData()

                if self.simulator.flagExit == 1:
                    return

                if xlist:
                    print('xlist')
                    for fd in xlist:
                        for bridge in bridges:
                            bridge.xhandle(fd)
                if rlist:
                    for fd in rlist:
                        for bridge in bridges:
                            bridge.handle(fd)
        finally:
            for bridge in bridges:
                bridge.close()

            self.simulator.stopSimulator()


def config_lan(config, name):
    # For a board which has LAN
    pass


def config_wlan(config, name):
    if config is None:
        return None, None
    return (WLANStation(config.get('sta'), name),
            WLANAccessPoint(config.get('ap'), name))


def WLANStation(config, name):
    if config is None:
        return
    essid = config['essid']
    password = config['password']
    sta = network.WLAN(network.STA_IF)

    if not sta.isconnected():
        sta.active(True)
        sta.connect(essid, password)
        n, ms = 20, 250
        t = n*ms
        while not sta.isconnected() and n > 0:
            time.sleep_ms(ms)
            n -= 1
        if not sta.isconnected():
            print('Failed to connect wifi station after {0}ms. I give up'
                  .format(t))
            return sta
    print('Wifi station connected as {0}'.format(sta.ifconfig()))
    return sta


def WLANAccessPoint(config, name):
    if config is None:
        return
    config.setdefault('essid', name)
    config.setdefault('channel', 11)
    config.setdefault('authmode',
                      getattr(network,'AUTH_' +
                              config.get('authmode', 'OPEN').upper()))
    config.setdefault('hidden', False)
#    config.setdefault('dhcp_hostname', name)
    ap = network.WLAN(network.AP_IF)
    if not ap.isconnected():
        ap.active(True)
        n, ms = 20, 250
        t = n * ms
        while not ap.active() and n > 0:
            time.sleep_ms(ms)
            n -= 1
        if not ap.active():
            print('Failed to activate wifi access point after {0}ms. ' \
                  'I give up'.format(t))
            return ap

#    ap.config(**config)
    print('Wifi {0!r} connected as {1}'.format(ap.config('essid'),
                                               ap.ifconfig()))
    return ap


def config_network(config, name):
    config_lan(config, name)
    config_wlan(config, name)


def config_verbosity(config):
    global VERBOSE
    VERBOSE = config.setdefault('verbose', 1)
    for bridge in config.get('bridges'):
        if bridge.get('uart', {}).get('port', None) == 0:
            VERBOSE = 0


def server(config_filename='us2n.json'):
    config = read_config(config_filename)
    VERBOSE = config.setdefault('verbose', 1)
    name = config.setdefault('name', 'Tiago-ESP32')
    config_verbosity(config)
    print(50*'=')
    print('Welcome to ESP8266/32 serial <-> tcp bridge\n')
    config_network(config.get('wlan'), name)
    return S2NServer(config)
