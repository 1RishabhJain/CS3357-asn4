import math
import socket
import os
import datetime
import signal
import sys
import selectors
import struct
import hashlib
from string import punctuation
import time

UDP_IP = "localhost"

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
        send_msg(reg[1], message)
    sys.exit(0)


# Function that reads line from socket
def get_line_from_socket():
    received_packet, addr = sock.recvfrom(1024)

    unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
    UDP_packet = unpacker.unpack(received_packet)

    # Extract out data that was received from the packet.  It unpacks to a tuple, but it's easy enough to split apart.
    received_sequence = UDP_packet[0]
    received_size = UDP_packet[1]
    received_data = UDP_packet[2]
    received_checksum = UDP_packet[3]

    # Print out what we received.
    print("Packet data:", UDP_packet)

    values = (received_sequence, received_size, received_data)
    packer = struct.Struct(f'I I {MAX_STRING_SIZE}s')
    packed_data = packer.pack(*values)
    computed_checksum = bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")

    if received_checksum == computed_checksum:
        print('Received and computed checksums match, so packet can be processed')
        received_text = received_data[:received_size].decode()
        print(f'Message text was:  {received_text}')
        if received_text != "Good Ack":
            message = "Good Ack"
            UDP_packet = createPacket(0, message.encode())
            print("SendMessage: ", message)
            print("host, port", host, addr[1])
            sock.sendto(UDP_packet, (host, addr[1]))
        print("Message is an ack, returning")
        return received_text, addr[1], received_sequence
    else:
        print('Received and computed checksums do not match, so packet is corrupt and discarded')
        message = "Bad Ack"
        UDP_packet = createPacket(0, message.encode())
        print("SendMessage: ", message)
        print("host, port", host, addr[1])
        sock.sendto(UDP_packet, (host, addr[1]))
        # sequence_number = sequence_number + 1


# Search the client list for a particular user.
def client_search(user):
    for reg in client_list:
        if reg[0] == user:
            return reg[1]
    return None


# Search the client list for a particular user by their port.
def client_search_by_port(port):
    for reg in client_list:
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
    user = client_search_by_port(addr)
    # Does this indicate a closed connection?
    if message == '':
        print('Closing connection')
        client_remove(user)
        # sel.unregister(sock)
        # sock.close()

    # Receive the message.
    else:
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

        # Check for specific commands.
        elif (len(words) == 2) and ((words[1] == '!list') or (words[1] == '!exit') or (words[1] == '!follow?')):
            if words[1] == '!list':
                response = list_clients()
                send_msg(addr, response)
            elif words[1] == '!exit':
                print('Disconnecting user ' + user)
                response = 'DISCONNECT CHAT/1.0\n'
                send_msg(addr, response)
                client_remove(user)
            elif words[1] == '!follow?':
                response = client_follows(user) + '\n'
                send_msg(addr, response)

        # Check for specific commands with a parameter.
        elif (len(words) == 3) and ((words[1] == '!follow') or (words[1] == '!unfollow')):
            if words[1] == '!follow':
                topic = words[2]
                if client_add_follow(user, topic):
                    response = f'Now following {topic}\n'
                else:
                    response = f'Error:  Was already following {topic}\n'
                send_msg(addr, response)
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
                send_msg(addr, response)

            # Check for user trying to upload/attach a file.  We strip the message to keep the user and any other text to help forward the file.  Will
            # send it to interested users like regular messages.

        elif (len(words) >= 3) and (words[1] == '!attach'):
            filename = words[2]
            fileSize = int(words[-1])
            # setting up the folders to download the file to
            folder = "receivedFiles/server/"
            os.makedirs(folder, exist_ok=True)
            path = f"receivedFiles/server/{filename}"
            incomingFile = open(path, 'wb')
            #remainingData = fileSize
            count = math.ceil(fileSize/BUFFER_SIZE)
            while count != 0:
                data, addr, received_sequence = get_line_from_socket()
                count = count - 1
                arr = bytes(data, 'utf-8')
                incomingFile.write(arr)
                incomingFile.flush()
            incomingFile.close()
            send_msg(addr, "!Done")
            # Calls function to send the file out to other clients
            clientsToSend(words, addr, user)

        # Look for follow terms and dispatch message to interested users.  Send at most only once, and don't send to yourself.  Trailing punctuation is stripped.
        # Need to re-add stripped newlines here.

        else:
            for reg in client_list:
                if reg[0] == user:
                    continue
                forwarded = False
                for term in reg[2]:
                    for word in words:
                        if (term == word.rstrip(punctuation)) and not forwarded:
                            client_port = reg[1]
                            forwarded_message = f'{message}'
                            # client_port.send(forwarded_message.encode())
                            send_msg(client_port, forwarded_message)
                            forwarded = True


# Function that will send the file to other clients
def clientsToSend(words, addr, user):
    atUser = f'@{user}'
    filename = words[2]
    fileSize = words[-1]
    # stores username in the term list
    termList = [atUser]
    # iterate through the terms entered and store them in the list
    for term in words[3:-1]:
        termList.append(term)
    for reg in client_list:
        if reg[1] == addr:
            continue
        else:
            currentUsername = reg[0]
            if bool(set(reg[2]).intersection(termList)):
                matchFound = True
                client_sock = reg[1]
                message = f"Incoming file: {filename}\nOrigin: {user}\nContent-length: {fileSize}\n"
                send_msg(reg[1], message)
                message = f"!FileTransfer {filename} fromServer {fileSize}\n"
                send_msg(reg[1], message)
                sendFile(reg[1], filename, fileSize, sock)


# helper function to the file sending
def sendFile(addr, filename, fileSize, sock):
    outgoingFile = open(f"receivedFiles/server/{filename}", "rb")
    remainingData = int(fileSize)
    count = math.ceil(remainingData / BUFFER_SIZE)
    while count != 0:
        if remainingData <= BUFFER_SIZE:
            sendAmount = remainingData
            remainingData = 0
        else:
            sendAmount = BUFFER_SIZE
        msg = outgoingFile.read(sendAmount)
        UDP_packet = createPacket(0, msg)
        sock.sendto(UDP_packet, (host, addr))
        count = count - 1
    outgoingFile.close()
    waiting = True
    while waiting:
        try:
            wait, addr, received_sequence = get_line_from_socket()
            if wait == "!Done":
                waiting = False
            break
        except BlockingIOError as e:
            waiting = True


# Function to create and return a UDP packet based on the provided sequence number and data
def createPacket(sequence_number, data):
    size = len(data)
    packet_tuple = (sequence_number, size, data)
    packet_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s')
    packed_data = packet_structure.pack(*packet_tuple)
    checksum = bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")

    packet_tuple = (sequence_number, size, data, checksum)
    UDP_packet_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
    UDP_packet = UDP_packet_structure.pack(*packet_tuple)
    return UDP_packet


# Send message function to send the packet over UDP
def send_msg(port, message):
    sequence_number = 0

    data = message.encode()
    UDP_packet = createPacket(sequence_number, data)
    print("UDP PACKET: ", UDP_packet)
    print("Message to Send: ", data)
    sock.sendto(UDP_packet, (host, port))

    Valid_ACK = False
    while not Valid_ACK:
        start_time = time.time()
        while start_time < time.time() + 1:
            try:
                received_text, addr, received_sequence = get_line_from_socket()
                if addr == port:
                    if received_text == "Good Ack":
                        if received_sequence == sequence_number:
                            print("Good Ack, continuing")
                            Valid_ACK = True
                            break
                        else:
                            print("Good ACK but Incorrect sequence_number")
                    elif received_text == "Bad Ack":
                        if received_sequence == sequence_number:
                            print("Bad Ack, resending")
                            sequence_number = sequence_number + 1
                            UDP_packet = createPacket(sequence_number, data)
                            sock.sendto(UDP_packet, (host, port))
                        else:
                            print("Bad ACK but Incorrect sequence_number")
                    else:
                        print("Other message", received_text)
                else:
                    print("Incorrect Port")
            except socket.timeout:
                print("Wait...")
                continue
        if not Valid_ACK:
            print("Timeout: did not receive ACK, resending")
        sequence_number = sequence_number + 1
    print("Done Sending, received ACK")


# Function to accept and set up clients.
def accept_client(sock, mask):
    message, addr, received_sequence = get_line_from_socket()
    message_parts = message.split()

    # If it is a new client
    if not client_search_by_port(addr):
        print('Accepted connection from client address:', addr)
        # Check format of request.
        if (len(message_parts) != 3) or (message_parts[0] != 'REGISTER') or (message_parts[2] != 'CHAT/1.0'):
            print('Error:  Invalid registration message.')
            print('Received: ' + message)
            print('Connection closing ...')
            response = '400 Invalid registration\n'
            send_msg(addr, response)

        # If request is properly formatted and user not already listed, go ahead with registration.
        else:
            user = message_parts[1]
            if user == 'all':
                print('Error:  Client cannot use reserved user name \'all\'.')
                print('Connection closing ...')
                response = '402 Forbidden user name\n'
                send_msg(addr, response)

            elif client_search(user) is None:
                # Add the user to their follow list, so @user finds them.  We'll also do @all as well for broadcast messages.
                follow_terms = [f'@{user}', '@all']

                # Finally add the user. (username, address, follow terms)
                client_add(user, addr, follow_terms)
                print(f'Connection to client established, waiting to receive messages from user \'{user}\'...')
                response = '200 Registration successful\n'
                send_msg(addr, response)

            # If user already in list, return a registration error.
            else:
                print('Error:  Client already registered.')
                print('Connection closing ...')
                response = '401 Client already registered\n'
                send_msg(addr, response)
    # If it is an existing client, go to the read_message function
    else:
        read_message(message, addr)


# Our main function.
def main():
    # Register our signal handler for shutting down.
    signal.signal(signal.SIGINT, signal_handler)

    # Create the socket.  We will ask this to work on any interface and to pick a free port at random.
    # We'll print this out for clients to use.
    sock.bind(('', 0))
    print('Will wait for client connections at port ' + str(sock.getsockname()[1]))
    sel.register(sock, selectors.EVENT_READ, accept_client)
    print('Waiting for incoming client connections ...')
    # sock.settimeout(0.2)

    # Keep the server running forever, waiting for connections or messages.
    while (True):
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)


if __name__ == '__main__':
    main()