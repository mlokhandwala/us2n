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

def getTemp():
	return tempsensor.getAvTemp()