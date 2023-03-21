from socket import *
import sys
from packet import Packet
import logging

loggerarr = logging.getLogger('logger1')
loggerarr.setLevel(logging.DEBUG)

handlerarr = logging.FileHandler('arrival.log', mode = 'a')
handlerarr.setLevel(logging.INFO)

loggerarr.addHandler(handlerarr)

if len(sys.argv) < 5:
    print("Sender requires 4 arguments:\n1: <nemulator_host_address>\n2: <nemulator_ACK_n_port>\n3: <receiver_data_n_port>\n4: <input_file.txt>")
    exit()
if ((not sys.argv[2].isdigit()) or int(sys.argv[2]) < 1025) or (int(sys.argv[2]) > 65535):
    print("nemulator_ACK_n_port out of range. please enter integer from set [1025, 65535] matching server n_port")
    exit()
if ((not sys.argv[3].isdigit()) or int(sys.argv[3]) < 1025) or (int(sys.argv[3]) > 65535):
    print("receiver_data_n_port out of range. please enter integer from set [1025, 65535] matching server n_port")
    exit()

EMULATOR_IP = sys.argv[1]
EMULATOR_PORT = int(sys.argv[2])
RECV_PORT = int(sys.argv[3])
in_file = sys.argv[4]

# Define packet size and window size
MAX_WINDOW_SIZE = 10

# Create the socket
sock = socket(AF_INET, SOCK_DGRAM)
sock.bind(('', RECV_PORT))
sock.settimeout(1)

# Initialize the receiving window
expected_seq_num = 0
receive_buffer = [None]*MAX_WINDOW_SIZE

outstring = ''

# Receive packets
while True:
    try:
        # Receive a packet
        packet, _ = sock.recvfrom(1024)
        tp, seq_num, length, indata = Packet(packet).decode()

        # Check if the packet is in the window
        if tp == 1:
            loggerarr.info(seq_num)
            if (seq_num >= expected_seq_num and seq_num < (expected_seq_num+MAX_WINDOW_SIZE)%32) or (expected_seq_num+MAX_WINDOW_SIZE > 31 and (seq_num >= expected_seq_num or seq_num <(expected_seq_num+MAX_WINDOW_SIZE)%32)):
                # Send an acknowledgement
                ack = Packet(0, seq_num, 0, '').encode()
                sock.sendto(ack, (EMULATOR_IP, EMULATOR_PORT))
                print('sent ack seq_no. = ', seq_num)
                if seq_num >= expected_seq_num and seq_num - expected_seq_num < MAX_WINDOW_SIZE and receive_buffer[seq_num - expected_seq_num] == None:
                    receive_buffer[seq_num - expected_seq_num] = indata
                elif expected_seq_num + MAX_WINDOW_SIZE > 31 and (seq_num >= expected_seq_num or seq_num < (expected_seq_num + MAX_WINDOW_SIZE)%32):
                    if seq_num >= expected_seq_num and receive_buffer[seq_num - expected_seq_num] == None:
                        receive_buffer[seq_num - expected_seq_num] = indata
                    elif seq_num < expected_seq_num and receive_buffer[seq_num + 32 - expected_seq_num] == None:
                        receive_buffer[seq_num + 32 - expected_seq_num] = indata

                if seq_num == expected_seq_num:
                    while receive_buffer[0] != None:
                        expected_seq_num = (expected_seq_num + 1)%32
                        print('expected seq_no. = ', expected_seq_num)
                        outstring += receive_buffer[0]
                        receive_buffer.pop(0)
                        receive_buffer.append(None)

            # Send a duplicate acknowledgement
            elif seq_num < expected_seq_num or seq_num >= (expected_seq_num + MAX_WINDOW_SIZE)%32:
                ack = Packet(0, seq_num, 0, '').encode()
                sock.sendto(ack, (EMULATOR_IP, EMULATOR_PORT))
                print('sent dupe ack seq_no. = ', seq_num)

        elif tp == 2:
            loggerarr.info('EOT')
            eot = Packet(2, 0, 0, '').encode()
            sock.sendto(eot, (EMULATOR_IP, EMULATOR_PORT))
            break

    except timeout:
        pass    

with open (in_file, 'w') as f:
    f.write(outstring)
print('transmission complete')

# Close the socket
sock.close()