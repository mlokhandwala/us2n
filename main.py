import machine
import time

def cat(fname):
    with open(fname, 'r') as f:
        print(f.read())


def start_us2n():
    import us2n
    server = us2n.server()
    #server.serve_forever() #commented out as we want to boot with WLAN but not start the server loop. 


if __name__ == '__main__':
    start_us2n()
