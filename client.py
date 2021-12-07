import socket
import os
import signal
import sys
import sys
import argparse
from urllib.parse import urlparse
import struct
import hashlib
import selectors

UDP_IP = "localhost"

# Define a constant for our buffer size

BUFFER_SIZE = 1024

# Define a maximum string size for the text we'll be sending along.

MAX_STRING_SIZE = 256

# Selector for helping us select incoming data from the server and messages typed in by the user.

sel = selectors.DefaultSelector()

# Socket for sending messages.

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# User name for tagging sent messages.

user = ''

host = ""
port = 0


# Signal handler for graceful exiting.  Let the server know when we're gone.

def signal_handler(sig, frame):
    print('Interrupt received, shutting down ...')
    message = f'DISCONNECT {user} CHAT/1.0\n'
    sendMessage(client_socket, message)
    sys.exit(0)


# Simple function for setting up a prompt for the user.

def do_prompt(skip_line=False):
    if (skip_line):
        print("")
    print("> ", end='', flush=True)


# Read a single line (ending with \n) from a socket and return it.
# We will strip out the \r and the \n in the process.
"""
def get_line_from_socket(sock):

    done = False
    line = ''
    while (not done):
        char = sock.recv(1).decode()
        if (char == '\r'):
            pass
        elif (char == '\n'):
            done = True
        else:
            line = line + char
    return line
"""


# Function to handle incoming messages from server.  Also look for disconnect messages to shutdown and messages for sending and receiving files.

def handle_message_from_server(sock, mask):
    message = get_line_from_socket(sock)
    words = message.split(' ')
    print()

    # Handle server disconnection.

    if words[0] == 'DISCONNECT':
        print('Disconnected from server ... exiting!')
        sys.exit(0)

    # Handle file attachment request.

    elif words[0] == 'ATTACH':
        sock.setblocking(True)
        filename = words[1]
        if (os.path.exists(filename)):
            filesize = os.path.getsize(filename)
            header = f'Content-Length: {filesize}\n'
            sendMessage(sock, message)
            sock.send(header.encode())
            with open(filename, 'rb') as file_to_send:
                while True:
                    chunk = file_to_send.read(BUFFER_SIZE)
                    if chunk:
                        sock.send(chunk)
                    else:
                        break
        else:
            header = f'Content-Length: -1\n'
            sock.send(header.encode())
        # sock.setblocking(False)

    # Handle file attachment request.

    elif words[0] == 'ATTACHMENT':
        filename = words[1]
        sock.setblocking(True)
        print(f'Incoming file: {filename}')
        origin = get_line_from_socket(sock)
        print(origin)
        contentlength = get_line_from_socket(sock)
        print(contentlength)
        length_words = contentlength.split(' ')
        if (len(length_words) != 2) or (length_words[0] != 'Content-Length:'):
            print('Error:  Invalid attachment header')
        else:
            bytes_read = 0
            bytes_to_read = int(length_words[1])
            with open(filename, 'wb') as file_to_write:
                while (bytes_read < bytes_to_read):
                    chunk = sock.recv(BUFFER_SIZE)
                    bytes_read += len(chunk)
                    file_to_write.write(chunk)
        # sock.setblocking(False)
        do_prompt()

    # Handle regular messages.

    else:
        print(message)
        do_prompt()


# Function to handle incoming messages from server.

def handle_keyboard_input(file, mask):
    line = sys.stdin.readline()
    message = f'@{user}: {line}'
    sendMessage(client_socket, message)
    do_prompt()


def sendMessage(sock, message):
    sequence_number = 0
    data = message.encode()
    size = len(data)

    packet_tuple = (sequence_number, size, data)
    packet_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s')
    packed_data = packet_structure.pack(*packet_tuple)
    checksum = bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")

    packet_tuple = (sequence_number, size, data, checksum)
    UDP_packet_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
    UDP_packet = UDP_packet_structure.pack(*packet_tuple)
    print("Message to send: ", data)
    print("host, port", host, port)
    sock.sendto(UDP_packet, (host, port))


# Function that reads line from socket

def get_line_from_socket(sock):
    received_packet, addr = sock.recvfrom(1024)
    unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
    UDP_packet = unpacker.unpack(received_packet)

    # Extract out data that was received from the packet.  It unpacks to a tuple, but it's easy enough to split apart.
    received_sequence = UDP_packet[0]
    received_size = UDP_packet[1]
    received_data = UDP_packet[2]
    received_checksum = UDP_packet[3]

    # Print out what we received.
    print("Packet received from:", addr)
    print("Packet data:", UDP_packet)

    values = (received_sequence, received_size, received_data)
    packer = struct.Struct(f'I I {MAX_STRING_SIZE}s')
    packed_data = packer.pack(*values)
    computed_checksum = bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")

    if received_checksum == computed_checksum:
        print('Received and computed checksums match, so packet can be processed')
        received_text = received_data[:received_size].decode()
        print(f'Message text was:  {received_text}')
        return received_text
    else:
        print('Received and computed checksums do not match, so packet is corrupt and discarded')


# Our main function.

def main():
    global user
    global client_socket
    global host
    global port
    # Register our signal handler for shutting down.

    signal.signal(signal.SIGINT, signal_handler)

    # Check command line arguments to retrieve a URL.

    parser = argparse.ArgumentParser()
    parser.add_argument("user", help="user name for this user on the chat service")
    parser.add_argument("server", help="URL indicating server location in form of chat://host:port")
    parser.add_argument('-f', '--follow', nargs=1, default=[], help="comma separated list of users/topics to follow")
    args = parser.parse_args()

    # Check the URL passed in and make sure it's valid.  If so, keep track of
    # things for later.

    try:
        server_address = urlparse(args.server)
        if ((server_address.scheme != 'chat') or (server_address.port == None) or (server_address.hostname == None)):
            raise ValueError
        host = server_address.hostname
        port = server_address.port
    except ValueError:
        print('Error:  Invalid server.  Enter a URL of the form:  chat://host:port')
        sys.exit(1)
    user = args.user
    follow = args.follow

    # Now we try to make a connection to the server.

    print('Connecting to server ...')
    try:
        # client_socket.connect((host, port))
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except ConnectionRefusedError:
        print('Error:  That host or port is not accepting connections.')
        sys.exit(1)

    # The connection was successful, so we can prep and send a registration message.

    print('Connection to server established. Sending intro message...\n')
    message = f'REGISTER {user} CHAT/1.0\n'
    sendMessage(client_socket, message)
    '''
    # If we have terms to follow, we send them now.  Otherwise, we send an empty line to indicate we're done with registration.

    if follow != []:
        message = f'Follow: {follow[0]}\n\n'
    else:
        message = '\n'
    sendMessage(client_socket, message)
   
    # Receive the response from the server and start taking a look at it

    response_line = get_line_from_socket(client_socket)
    response_list = response_line.split(' ')
        
    # If an error is returned from the server, we dump everything sent and
    # exit right away.  
    
    if response_list[0] != '200':
        print('Error:  An error response was received from the server.  Details:\n')
        print(response_line)
        print('Exiting now ...')
        sys.exit(1)   
    else:
        print('Registration successful.  Ready for messaging!')

    # Set up our selector.
    '''
    # client_socket.setblocking(False)
    sel.register(client_socket, selectors.EVENT_READ, handle_message_from_server)
    sel.register(sys.stdin, selectors.EVENT_READ, handle_keyboard_input)

    # Prompt the user before beginning.
    do_prompt()

    # Now do the selection.

    while (True):
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)


if __name__ == '__main__':
    main()
