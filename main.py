import machine
import time

def start_us2n():
    import us2n
    server = us2n.server()
    #server.serve()
    #server.serve_forever() #commented out as we want to boot with WLAN but not start the server loop. 


if __name__ == '__main__':
    start_us2n()
