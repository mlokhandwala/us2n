#from machine import UART

#u1 = UART(1)                                                                                                        
#u1.init(921600,bits=8,parity=None, stop=1)
#u1.write('Y')
#print(u1.read())

def test():
	from machine import UART; import time

	u2 = UART(2); u2.init(921000, bits=8, parity=None, stop=1)
	time.sleep_ms(100)
	print(u2.write('Y'))
	time.sleep_ms(100)
	print(u2.read())
	time.sleep_ms(100)
	print(u2)