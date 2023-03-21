from socket import *
import time
import sys
import logging
from packet import Packet
from pathlib import Path

loggerseq = logging.getLogger('logger1')
loggerack = logging.getLogger('logger2')
loggerN = logging.getLogger('logger3')

loggerseq.setLevel(logging.DEBUG)
loggerack.setLevel(logging.DEBUG)
loggerN.setLevel(logging.DEBUG)

handlerseq = logging.FileHandler('seqnum.log', mode = 'a')
handlerseq.setLevel(logging.INFO)

handlerack = logging.FileHandler('ack.log', mode = 'a')
handlerack.setLevel(logging.INFO)

handlerN = logging.FileHandler('N.log', mode = 'a')
handlerN.setLevel(logging.INFO)

loggerseq.addHandler(handlerseq)
loggerack.addHandler(handlerack)
loggerN.addHandler(handlerN)

if len(sys.argv) < 6:
    print("Sender requires 5 arguments:\n1: <nemulator_host_address>\n2: <nemulator_data_n_port>\n3: <sender_SACK_n_port>\n4: <timeout_interval_ms>\n5: <output_file>")
    exit()
if ((not sys.argv[2].isdigit()) or int(sys.argv[2]) < 1025) or (int(sys.argv[2]) > 65535):
    print("nemulator_data_n_port out of range. please enter integer from set [1025, 65535] matching server n_port")
    exit()
if ((not sys.argv[3].isdigit()) or int(sys.argv[3]) < 1025) or (int(sys.argv[3]) > 65535):
    print("sender_SACK_n_port out of range. please enter integer from set [1025, 65535] matching server n_port")
    exit()
if (not sys.argv[4].isdigit()):
    print("timeout interval must be an integer")
    exit()

EMULATOR_IP = sys.argv[1]
EMULATOR_PORT = int(sys.argv[2])
SACK_PORT = int(sys.argv[3])
TIMEOUT = int(sys.argv[4])/1000
MAX_WINDOW_SIZE = 10
MAX_L = 500

# read and store file data
out_file = Path(('./' + sys.argv[5]))
if not out_file.is_file():
    print("file does not exist")
    exit()
with open(out_file, 'r') as f:
    textlist = f.readlines()
data = ''
for i in textlist:
    data = data + i

# prepare strings for data packets
datalist = list()
for i in range(len(data)//MAX_L + 1):
    datalist.append(data[MAX_L*i:min((MAX_L*i) + MAX_L, len(data))])

# prepare packets
packetlist = list()
for i in range(len(datalist)):
    packetlist.append(Packet(1, i%32, len(datalist[i]), datalist[i]).encode())
num_packets = len(packetlist)

# Create the socket
sock = socket(AF_INET, SOCK_DGRAM)
sock.bind(('', SACK_PORT))
sock.settimeout(TIMEOUT)

# Initialize the sending window and buffers
base = 0
timers = [0] * MAX_WINDOW_SIZE
window_size = 1
start_time = time.time()

print('Beginning new transmission')
timestamp = 0
loggerN.info('t=' + str(timestamp) + ' ' + str(window_size))

# Send packets
while base < num_packets:
    print('base = ', base)
    print('window size = ', window_size)
    
    # Send packets in the window
    for i in range(base, min(base + window_size, num_packets)):
        if timers[i - base] == 0:
            tp, seq_num, length, outdata = Packet(packetlist[i]).decode()
            sock.sendto(packetlist[i], (EMULATOR_IP, EMULATOR_PORT))
            timers[i - base] = time.time()
            print('sent seq_no.', seq_num)
            timestamp += 1
            loggerseq.info('t=' + str(timestamp) + ' ' + str(seq_num))

    # Receive acknowledgements
    try:
        ack, _ = sock.recvfrom(1024)
        tp, seq_num, length, indata = Packet(ack).decode()
        print('ack received = ', seq_num)
        timestamp += 1
        loggerack.info('t=' + str(timestamp) + ' ' + str(seq_num))

        # if ack in max window and is new
        if (seq_num >= base%32 and (seq_num - base%32) < MAX_WINDOW_SIZE) and timers[seq_num - (base%32)] > 0:
            timers[seq_num - (base%32)] = -1
            if window_size < 10:
                window_size += 1
                loggerN.info('t=' + str(timestamp) + ' ' + str(window_size))
        elif base%32 + MAX_WINDOW_SIZE > 31 and (seq_num >= base%32 or seq_num < (base + MAX_WINDOW_SIZE)%32):
            if seq_num >= base%32 and timers[seq_num - (base%32)] > 0:
                timers[seq_num - (base%32)] = -1
            elif seq_num < base%32 and timers[seq_num + 32 - (base%32)] > 0:
                timers[seq_num + 32 - (base%32)] = -1
            if window_size < 10:
                window_size += 1
                loggerN.info('t=' + str(timestamp) + ' ' + str(window_size))

        # clear sacked consecutive packets from buffer base
        if seq_num == base%32:
            while base < num_packets and timers[0] == -1:
                base += 1
                timers.pop(0)
                timers.append(0)
                
    except timeout:
        # Retransmit packets if timeout
        for i in range(base, min(base+MAX_WINDOW_SIZE, num_packets)):
            if (timers[i - base] > 0) and (time.time() - timers[i - base] > TIMEOUT):
                print('timeout seq_no. = ', i%32)
                timestamp += 1
                if window_size > 1:
                    window_size = 1
                    loggerN.info('t=' + str(timestamp) + ' ' + str(window_size))
                if i - base == 0:
                    sock.sendto(packetlist[i], (EMULATOR_IP, EMULATOR_PORT))
                    loggerseq.info('t=' + str(timestamp) + ' ' + str(i%32))
                    print('resent seq_no. = ', i%32)
                    timers[i - base] = time.time()
                break

# Send EOT
eot = Packet(2, 0, 0, '').encode()
sock.sendto(eot, (EMULATOR_IP, EMULATOR_PORT))
timestamp += 1
loggerseq.info('t=' + str(timestamp) + ' ' + 'EOT')
timestamp += 1
while True:
    try:
        reot, _ = sock.recvfrom(1024)
        tp, seq_num, length, indata = Packet(reot).decode()
        if tp == 2:
            loggerack.info('t=' + str(timestamp) + ' ' + 'EOT')
        break
    except timeout:
        pass

sock.close()