import socket
import os
import datetime
import signal
import sys
import selectors
import struct
import hashlib
from string import punctuation

UDP_IP = "localhost"
UDP_PORT = 54321

# Constant for our buffer size

BUFFER_SIZE = 1024

# Define a maximum string size for the text we'll be receiving.

MAX_STRING_SIZE = 256

# Selector for helping us select incoming data and connections from multiple sources.

sel = selectors.DefaultSelector()

# Client list for mapping connected clients to their connections.

client_list = []

host = ""

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


# Signal handler for graceful exiting.  We let clients know in the process so they can disconnect too.

def signal_handler(sig, frame):
    print('Interrupt received, shutting down ...')
    message = 'DISCONNECT CHAT/1.0\n'
    for reg in client_list:
        send_msg(sock, reg[1], message)
    sys.exit(0)


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
        return received_text, addr[1]
    else:
        print('Received and computed checksums do not match, so packet is corrupt and discarded')


# Search the client list for a particular user.

def client_search(user):
    for reg in client_list:
        if reg[0] == user:
            return reg[1]
    return None


# Search the client list for a particular user by their port.

def client_search_by_port(port):
    print("client list: ", client_list)
    for reg in client_list:
        print(reg)
        if reg[1] == port:
            return reg[0]
    return False


# Add a user to the client list.

def client_add(user, conn, follow_terms):
    registration = (user, conn, follow_terms)
    client_list.append(registration)


# Remove a client when disconnected.

def client_remove(user):
    for reg in client_list:
        if reg[0] == user:
            client_list.remove(reg)
            break


# Function to list clients.

def list_clients():
    first = True
    list = ''
    for reg in client_list:
        if first:
            list = reg[0]
            first = False
        else:
            list = f'{list}, {reg[0]}'
    return list


# Function to return list of followed topics of a user.

def client_follows(user):
    for reg in client_list:
        if reg[0] == user:
            first = True
            list = ''
            for topic in reg[2]:
                if first:
                    list = topic
                    first = False
                else:
                    list = f'{list}, {topic}'
            return list
    return None


# Function to add to list of followed topics of a user, returning True if added or False if topic already there.

def client_add_follow(user, topic):
    for reg in client_list:
        if reg[0] == user:
            if topic in reg[2]:
                return False
            else:
                reg[2].append(topic)
                return True
    return None


# Function to remove from list of followed topics of a user, returning True if removed or False if topic was not already there.

def client_remove_follow(user, topic):
    for reg in client_list:
        if reg[0] == user:
            if topic in reg[2]:
                reg[2].remove(topic)
                return True
            else:
                return False
    return None


# Function to read messages from clients.

def read_message(message, addr):
    print("message reading")
    # message, addr = get_line_from_socket(sock)

    # Does this indicate a closed connection?

    if message == '':
        print('Closing connection')
        # sel.unregister(sock)
        # sock.close()

    # Receive the message.  

    else:
        user = client_search_by_port(addr)
        print(f'Received message from user {user}:  ' + message)
        split_words = message.split(' ')
        words = []
        # Remove trailing
        for i in split_words:
            words.append(i.strip("\n\r"))
        # Check for client disconnections.

        if words[0] == 'DISCONNECT':
            print('Disconnecting user ' + user)
            client_remove(user)
            # sel.unregister(sock)
            # sock.close()

        # Check for specific commands.

        elif ((len(words) == 2) and ((words[1] == '!list') or (words[1] == '!exit') or (words[1] == '!follow?'))):
            if words[1] == '!list':
                print('!list')
                response = list_clients() + '\n'
                send_msg(sock, addr, response)
                # sock.send(response.encode())
            elif words[1] == '!exit':
                print('Disconnecting user ' + user)
                response = 'DISCONNECT CHAT/1.0\n'
                send_msg(sock, addr, response)
                # sock.send(response.encode())
                client_remove(user)
                # sel.unregister(sock)
                # sock.close()
            elif words[1] == '!follow?':
                print('!follow?')
                response = client_follows(user) + '\n'
                send_msg(sock, addr, response)
                # sock.send(response.encode())

        # Check for specific commands with a parameter.

        elif ((len(words) == 3) and ((words[1] == '!follow') or (words[1] == '!unfollow'))):
            if words[1] == '!follow':
                topic = words[2]
                if client_add_follow(user, topic):
                    response = f'Now following {topic}\n'
                else:
                    response = f'Error:  Was already following {topic}\n'
                # sock.send(response.encode())
                send_msg(sock, addr, response)
            elif words[1] == '!unfollow':
                topic = words[2]
                if topic == '@all':
                    response = 'Error:  All users must follow @all\n'
                elif topic == '@' + user:
                    response = 'Error:  Cannot unfollow yourself\n'
                elif client_remove_follow(user, topic):
                    response = f'No longer following {topic}\n'
                else:
                    response = f'Error:  Was not following {topic}\n'
                # sock.send(response.encode())
                send_msg(sock, addr, response)

        # Check for user trying to upload/attach a file.  We strip the message to keep the user and any other text to help forward the file.  Will
        # send it to interested users like regular messages.

        elif ((len(words) >= 3) and (words[1] == '!attach')):
            # sock.setblocking(True)
            filename = words[2]
            words.remove('!attach')
            words.remove(filename)
            response = f'ATTACH {filename} CHAT/1.0\n'
            # sock.send(response.encode())
            send_msg(sock, addr, response)
            header, addr = get_line_from_socket(sock)
            header_words = header.split(' ')
            if (len(header_words) != 2) or (header_words[0] != 'Content-Length:'):
                response = f'Error:  Invalid attachment header\n'
            elif header_words[1] == '-1':
                response = f'Error:  Attached file {filename} could not be sent\n'
            else:
                interested_clients = []
                attach_size = header_words[1]
                attach_notice = f'ATTACHMENT {filename} CHAT/1.0\nOrigin: {user}\nContent-Length: {attach_size}\n'
                for reg in client_list:
                    if reg[0] == user:
                        continue
                    forwarded = False
                    for term in reg[2]:
                        for word in words:
                            if ((term == word.rstrip(punctuation)) and not forwarded):
                                interested_clients.append(reg[1])
                                send_msg(reg[1], addr, attach_notice)
                                # reg[1].send(attach_notice.encode())
                                forwarded = True
                bytes_read = 0
                bytes_to_read = int(attach_size)
                while (bytes_read < bytes_to_read):
                    chunk = sock.recv(BUFFER_SIZE)
                    bytes_read += len(chunk)
                    for client in interested_clients:
                        client.send(chunk)
                response = f'Attachment {filename} attached and distributed\n'
            # sock.send(response.encode())
            send_msg(sock, addr, response)
            # sock.setblocking(False)

        # Look for follow terms and dispatch message to interested users.  Send at most only once, and don't send to yourself.  Trailing punctuation is stripped.
        # Need to re-add stripped newlines here.

        else:
            for reg in client_list:
                if reg[0] == user:
                    continue
                forwarded = False
                for term in reg[2]:
                    for word in words:
                        if ((term == word.rstrip(punctuation)) and not forwarded):
                            client_port = reg[1]
                            forwarded_message = f'{message}\n'
                            # client_port.send(forwarded_message.encode())
                            send_msg(sock, client_port, forwarded_message)
                            forwarded = True


def send_msg(sock, port, message):
    print("test")
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
    print("SendMessage: ", data)
    print("host, port", host, port)
    sock.sendto(UDP_packet, (host, port))


# def check_new_user(message_parts):


# Function to accept and set up clients.

def accept_client(sock, mask):
    # conn, addr = sock.accept()
    conn = sock.getsockname()[0]
    addr = sock.getsockname()[1]
    message, addr = get_line_from_socket(sock)
    message_parts = message.split()
    # print(message)
    # message = "test sending from server"
    # send_msg(sock, addr, message)

    # Check format of request.
    # if check_new_user(message_parts)
    if not client_search_by_port(addr):
        print('Accepted connection from client address:', addr)
        if ((len(message_parts) != 3) or (message_parts[0] != 'REGISTER') or (message_parts[2] != 'CHAT/1.0')):
            print('Error:  Invalid registration message.')
            print('Received: ' + message)
            print('Connection closing ...')
            response = '400 Invalid registration\n'
            send_msg(sock, addr, response)
            # conn.send(response.encode())
            # conn.close()

        # If request is properly formatted and user not already listed, go ahead with registration.

        else:
            user = message_parts[1]
            if user == 'all':
                print('Error:  Client cannot use reserved user name \'all\'.')
                print('Connection closing ...')
                response = '402 Forbidden user name\n'
                send_msg(sock, addr, response)
                # conn.send(response.encode())
                # conn.close()

            elif (client_search(user) == None):
                follow_terms = []
                """
                # Check for following terms or an issue with the request.
                follow_message = get_line_from_socket(sock)
                if follow_message != "":
                    if follow_message.startswith('Follow: '):
                        follow_terms = follow_message[len('Follow: '):].split(',')
                        blank_line = get_line_from_socket(sock)
                        if blank_line != "":
                            print('Error:  Invalid registration message.  Issue in follow list.')
                            print('Received: ' + message)
                            print('Connection closing ...')
                            response = '400 Invalid registration\n'
                            conn.send(response.encode())
                            conn.close()
                            return
                    else:
                        print('Error:  Invalid registration message.  Issue in follow list.')
                        print('Received: ' + message)
                        print('Connection closing ...')
                        response = '400 Invalid registration\n'
                        conn.send(response.encode())
                        conn.close()
                        return
                """
                # Add the user to their follow list, so @user finds them.  We'll also do @all as well for broadcast messages.

                follow_terms.append(f'@{user}')
                follow_terms.append('@all')

                # Finally add the user.

                client_add(user, addr, follow_terms)
                print(f'Connection to client established, waiting to receive messages from user \'{user}\'...')
                response = '200 Registration succesful\n'
                send_msg(sock, addr, response)
                # conn.send(response.encode())
                # conn.setblocking(False)
                # sel.register(addr, selectors.EVENT_READ, read_message)

            # If user already in list, return a registration error.

            else:
                print('Error:  Client already registered.')
                print('Connection closing ...')
                response = '401 Client already registered\n'
                send_msg(sock, addr, response)
                # conn.send(response.encode())
                # conn.close()
    else:
        read_message(message, addr)


# Our main function.

def main():
    # Register our signal handler for shutting down.

    signal.signal(signal.SIGINT, signal_handler)

    # Create the socket.  We will ask this to work on any interface and to pick
    # a free port at random.  We'll print this out for clients to use.

    sock.bind(('', 0))
    print('Will wait for client connections at port ' + str(sock.getsockname()[1]))
    # sock.listen(100)
    # sock.setblocking(False)
    sel.register(sock, selectors.EVENT_READ, accept_client)
    print('Waiting for incoming client connections ...')

    # Keep the server running forever, waiting for connections or messages.

    while (True):
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)


if __name__ == '__main__':
    main()
