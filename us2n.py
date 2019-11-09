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

print_ = print
VERBOSE = 1

gEnterCommandMode = 'XXXXXXXXXXX'


class Temperature:
    
    def __init__(self):
        self.adcP1 = ADC(Pin(33))          # create ADC object on ADC pin
        self.adcP1.atten(ADC.ATTN_11DB)    # set 11dB input attenuation (voltage range roughly 0.0v - 3.6v)
        self.adcP1.width(ADC.WIDTH_12BIT)   # set 9 bit return values (returned range 0-511)

    def getTemperature(self):
        raw = self.adcP1.read()
        voltage = (raw / 1.13) # from observation & calculation. 290mV gives 240 reading but 1.5V gives 1700 reading. 4096 / 3600 also = 1.13 so using that
        tempC = voltage * 0.1
        
        return tempC

tempsensor = Temperature()


class Simulator:

    flagSendData = 0
    flagExit = 0
    inFile = None
    timer = None
    expr = None
    inFileName = None

    bridge = None

    simrun = 0
    linecount = 0
    logfile = None

    flagSimRun = 0

    server = None
    flagCommandMode = 0
    BrakePinNo = 0
    BrakePin = None
    
    keepAwakeCommand = '\\' # \ = Invalid commnand, Just to keep awake
    

    def log(self, message):
        try:
            if self.logfile is None:
                self.logfile = open('/log.txt', 'a+')

            if self.logfile is None:
                return

            self.logfile.write(str(time.ticks_ms() / 60000) + ':' + message + '\r\n')
        except Exception:
            print('Failed to open log file')

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

    def __init__(self, config):
        self.server = server
        self.inFileName = config.setdefault('simdata', 'ecu.data')
        # self.BrakePinNo = int(config.setdefault('brakepin', '0'))
        # if self.BrakePinNo != 0:
            # self.BrakePin = Pin(self.BrakePinNo, Pin.OUT, Pin.PULL_UP) # Set it high as grounding will activate it.
            # self.BrakePin.off()
        print("Simulation File Name: {0}", self.inFileName)

    def setSendData(self, timer):
        if self.flagSimRun == 1:
            self.flagSendData = 1
        elif self.bridge.uart is not None:
            if self.flagCommandMode == 1:
                self.bridge.uart.write(self.keepAwakeCommand)

    def startSimulator(self, bridge):
        if(self.inFileName == None):
            print("Simulation data file name not found")
            return

        self.bridge = bridge

        self.inFile = open(self.inFileName, 'r')
        if(self.inFile is None):
            print("Simulation data file not found")

        self.expr = re.compile(',')

        if(self.timer == None):
            self.timer = Timer(-1)

        self.simrun += 1

        if self.bridge.client is not None:
            self.bridge.client.sendall('Simulation Run Started: ' + str(self.simrun))

        self.log('Simulation Run Started: ' + str(self.simrun))

        self.timer.init(period=50, mode=Timer.PERIODIC, callback=self.setSendData)

    def stopSimulator(self):
        if(self.timer != None):
            self.timer.deinit()

        self.timer = None


    def reRunSimulator(self):
        self.inFile.seek(0, 0)

        self.log('Simulation Run End, Line Count: ' + str(self.linecount))
        self.simrun += 1
        self.linecount = 0

        if self.bridge.client is not None:
            self.bridge.client.sendall('Simulation Run Started: ' + str(self.simrun) + '\r\n')
        self.log('Simulation Run Started: ' + str(self.simrun))

    def slowSendData(self, text):
        for c in text:
            self.bridge.uart.write(c)
            time.sleep_ms(1) # Delay 1 ms to avoid overrun


    def sendData(self):
        try:
            if self.flagSendData == 0:
                return

            if(self.inFile is None):
                return

            line = self.inFile.readline(100)

            #print('X:' + line) #debug

            if(line == ''):
                self.reRunSimulator()
                return

            self.linecount += 1
            data = self.expr.split(line)

            if(data):
                nRpm = int(data[0])
                nSpeed = int(data[1])
                nBreak = int(data[2])
                
                if nRpm < 0 or nRpm > 7000 or nSpeed < 0 or nSpeed > 200 or nBreak < 0 or nBreak > 1:
                    return # Bad data, try again since we are not resetting the flag.
                    
                print("{:04d}:{:03d}:{:01d}:{}".format(nRpm, nSpeed, nBreak, str(time.ticks_ms())))
                
                if self.BrakePin is None:
                    command = ("`{:04d} {:03d} {:01d} ".format(nRpm, nSpeed, nBreak)) # space between fields to allow placing null to split string in recieving code. 
                #else:
                    # command = ("`{:04d} {:03d} {:01d} ".format(nRpm, nSpeed, 0)) # if externally controlling brake, do not send brake flag to device. 
                    # if nBreak == 0:
                        # self.BrakePin = Pin(self.BrakePinNo, Pin.OUT, Pin.PULL_UP) # Set it high as grounding will activate it.
                        # self.BrakePin.off()
                    # else:
                        # self.BrakePin = Pin(self.BrakePinNo, Pin.IN, Pin.PULL_DOWN) # Set it high as grounding will activate it.
                        # self.BrakePin.On()                
                print(command)                
                self.slowSendData(command)

            self.flagSendData = 0
        except Exception as e: # most likely due to conversion error in data
            print(str(e))
            self.log(str(e)) 
        


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
                self.simulator.slowSendData(gEnterCommandMode)
                self.simulator.flagCommandMode = 1
                self.simulator.flagSimRun = 1
                print("flagSimRun, flagCommandMode = 1")
                return True
            if data.find('|C') != -1: # Command mode, just enter it on device
                self.simulator.slowSendData(gEnterCommandMode)
                self.simulator.flagCommandMode = 1 if self.simulator.flagCommandMode == 0 else 0
                print("flagCommandMode = " + str(self.simulator.flagCommandMode))
                return True
            elif data.find('|T') != -1: # sTop
                print("flagSimRun = 0")
                self.simulator.flagSimRun = 0
                return True
            elif data.find('|E') != -1: #Exit
                print("flagExit = 1")
                self.simulator.flagExit = 1
                return True
            elif data.find('|ViewLog') != -1: #View Log file 
                self.simulator.viewLog()
                return True
            elif data.find('|DelLog') != -1: #Delete Log file 
                self.simulator.delLog()
                return True
        except Exception as e:
            print(str(e))
            self.client.sendall(str(e))
            self.simulator.log(str(e))
           
        
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
                self.client.sendall("{}[{:3.2f}]\n\r".format(data, tempsensor.getTemperature()))
                #self.client.sendall(data)
        except Exception as e:
            print(str(e))
            self.client.sendall(str(e))
            self.simulator.log(str(e))
            
             
    def close_client(self):
        if self.client is not None:
            print('Closing client ', self.client_address)
            self.client.close()
            self.client = None
            self.client_address = None
        if self.uart is not None:
#            self.uart.deinit()
            self.uart = None

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
                    print('Errors. bailing out')
                    continue
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
