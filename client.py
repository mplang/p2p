"""
client.py
Author: Michael P. Lang
        Caleb Wrobel
Email: michael@mplang.net
Date Modified: 2 December 2012
"""

import socket
import random
import fnmatch
import os
import threading
from _thread import interrupt_main
import sys
import queue
import shlex

import rdt
import clientmsg


"""Set default values."""
MAX_COMM_ID = 2147483647
# Hostname/IP address of directory server
default_server_host = "localhost"
# UDP port of directory server
default_server_port = 50001
# TCP port to listen for P2P clients on
default_p2p_server_port = 50001
# UDP port to listen to response message from server
default_udp_listen_port = 60001
# Base folder of shared files
default_share = "mp3"
# List of files shared with the directory server
shared_files = []

hostname = socket.gethostname()
# Append a random 16-bit hex string to the hostname
host_id = hostname + "{:04x}".format(random.randrange(0xffff))
# Instantiate instance of Rdt class
r = rdt.Rdt(host_id)
# Each message corresponds to a unique comm_id
comm_id = random.randrange(MAX_COMM_ID)
# Queue to hold response messages from directory server
msg_queue = queue.Queue()
# Flag to prevent sending messages to server before IDENT
connected = False
# Most recent query response from server
current_query = []
# For thread-safe I/O
stdout_lock = threading.Lock()


def increment_comm_id():
    global comm_id
    if comm_id == MAX_COMM_ID:
        comm_id = 1
    else:
        comm_id += 1


def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_addr = s.getsockname()[0]
    s.close()

    return ip_addr


def get_shared_files(shared_dir):
    matches = []
    for root, dirnames, filenames in os.walk(shared_dir):
        for filename in fnmatch.filter(filenames, "*.mp3"):
            file = os.path.join(root, filename)
            matches.append((file, os.path.getsize(file)))

    return matches


def usage():
    with stdout_lock:
        print("Usage: command [options]")
        print("Allowable commands are:")
        print("exit\t\tTerminates the client.")
        print("quit\t\tTerminates the client.")
        print("usage\t\tUsage details (this!).")
        print("verbose\t\tToggle verbose display.")
        print("")
        print("connect [addr port]\tConnects to the server at the specified")
        print("\t\t\tIP address and port. Uses localhost 60001 if not specified.")
        print("")
        print("share [dirname]\t\tInforms the server of the availability of mp3")
        print("\t\t\tfiles to share in the path specified by [dirname].")
        print("\t\t\tDefaults to the current path if not specified.")


def stdin_listener():
    with stdout_lock:
        print("Type quit or exit to shut down the client and exit.")
        print("Type usage for usage details.")
    while True:
        kybd_in = input()
        kybd_in = shlex.split(kybd_in)
        #kybd_in = kybd_in.split(' ')
        if kybd_in[0] == "quit" or kybd_in[0] == "exit":
            with stdout_lock:
                print("***Received quit signal from stdin. Exiting application...")
            interrupt_main()
        elif kybd_in[0] == "usage":
            usage()
        elif kybd_in[0] == "status":
            status()
        elif kybd_in[0] == "connect":
            if len(kybd_in) == 1:
                ident(server_host, server_port)
            elif len(kybd_in) != 3:
                with stdout_lock:
                    print("***Invalid input!")
            else:
                ident(kybd_in[1], kybd_in[2])
        elif kybd_in[0] == "share":
            if len(kybd_in) == 2:
                share(kybd_in[1])
            elif len(kybd_in) == 1:
                share(default_share)
            else:
                with stdout_lock:
                    print("***Invalid input!")
        elif kybd_in[0] == "query":
            if len(kybd_in) == 3:
                query(kybd_in[1], kybd_in[2])
            elif len(kybd_in) == 2:
                query(kybd_in[1])
            else:
                with stdout_lock:
                    print("***Invalid input!")
        elif kybd_in[0] == "get":
            if len(kybd_in) == 2:
                get(kybd_in[1])
            else:
                with stdout_lock:
                    print("***Invalid input!")
        else:
            with stdout_lock:
                print("***Invalid input!")


def status():
    with stdout_lock:
        print("\nHost ID: {}\nSharing {} files".format(host_id, len(shared_files)))
        print("P2P Listening Port: {}".format(p2p_server_port))
        if connected:
            print("Connected to a directory server.")
        else:
            print("Not connected to a directory server.")
        print("")


def process_message(message):
    # ignore empty lines
    body = [line for line in message.split("\r\n") if line]
    header = body[0].split(' ')
    body = body[1:]
    status_code, status_phrase = header
    msg_queue.put((status_code, status_phrase, body))


def ident(server_ip, server_port):
    global connected
    connected = False
    msg.ident()
    with stdout_lock:
        print("==>Sending IDENT message to server.")
    msg_queue.queue.clear()
    msg_success = r.send(comm_id, repr(msg), (server_ip, int(server_port)))
    increment_comm_id()
    if msg_success:
        with stdout_lock:
            print("\t-->Sent IDENT message successfully!")
        response = msg_queue.get()
        if response[0] == "202" and response[2][0].split(" ")[1] == host_id:
            with stdout_lock:
                print("\t-->Received IDENTOK message from server.")
            connected = True
        else:   # Bad response
            with stdout_lock:
                print("\t-->Could not connect to server.")
    else:   # not msg_success
        with stdout_lock:
            print("\t-->Failed to deliver IDENT message!")


def share(shared_dir):
    if connected:
        matches = get_shared_files(shared_dir)
        msg.inform(matches)
        with stdout_lock:
            print("==>Sending INFORM message to server.")
        msg_queue.queue.clear()
        msg_success = r.send(comm_id, repr(msg), (server_host, server_port))
        increment_comm_id()
        if msg_success:
            with stdout_lock:
                print("\t-->Sent INFORM message successfully!")
            response = msg_queue.get()
            body = response[2][0].split(" ")
            if response[0] == "200" and body[0] == "INFORM":
                with stdout_lock:
                    print("\t-->Shared {} files with server.".format(body[1]))
                shared_files.extend(matches)
            else:
                with stdout_lock:
                    print("\t-->Failed to share files with server.")
        else:   # not msg_success
            with stdout_lock:
                print("\t-->Failed to deliver INFORM message!")
    else:   # not connected
        with stdout_lock:
            print("You are not connected to a server! Please connect and try again.")


def query(search_string, hostname=''):
    if connected:
        msg.query(search_string, hostname)
        with stdout_lock:
            print("==>Sending QUERY message to server.")
        msg_queue.queue.clear()
        msg_success = r.send(comm_id, repr(msg), (server_host, server_port))
        increment_comm_id()
        if msg_success:
            with stdout_lock:
                print("\t-->Sent QUERY message successfully!")
            response = msg_queue.get()
            if response[0] == "800":
                with stdout_lock:
                    print("\t-->Received QUERY response from server.")
                process_query_response(response[2])
                print_current_query()
            else:   # bad response
                with stdout_lock:
                    print("\t-->Failed to receive QUERY response from server.")
        else:   # not msg_success
            with stdout_lock:
                print("\t-->Failed to deliver QUERY message!")
    else:   # not connected
        with stdout_lock:
            print("You are not connected to a server! Please connect and try again.")


def process_query_response(query_response):
    global current_query
    current_query = []
    for i in range(0, len(query_response), 2):
        host_id, ip_addr = query_response[i].split(' ')
        filename = query_response[i+1].split(' ')
        filesize = filename[-1]
        filename = ' '.join(filename[:-1])
        current_query.append((host_id, ip_addr, filename, filesize))


def print_current_query():
    if len(current_query) != 0:
        for i, line in enumerate(current_query):
            with stdout_lock:
                print("[{}]: {}\nFilesize: {}\tHost ID: {}\tIP Address: {}".
                      format(i, line[2], line[3], line[0], line[1]))
    else:   # no items returned in query response
        with stdout_lock:
            print("No items found which match your query.")


def stuff():
    try:
        # REMOVE test
        msg.remove([shared_files[0]])
        with stdout_lock:
            print("==>Sending REMOVE message to server.")
        msg_success = r.send(comm_id, repr(msg), (server_host, server_port))
        increment_comm_id()
        if not msg_success:
            with stdout_lock:
                print("\t-->Failed to deliver REMOVE message!")
        else:
            with stdout_lock:
                print("\t-->Sent REMOVE message successfully!")
    finally:
        r.close()


def get(query_index):
    query_index = int(query_index)
    if query_index >= len(current_query):
        with stdout_lock:
            print("\t-->Invalid index!")
    else:
        req_file = current_query[query_index]
        with stdout_lock:
            print(req_file)
        get_msg = "GET {} HTTP/1.1\r\n\r\n".format(req_file[2])
        # "HTTP/1.1 200 OK\r\nContent-Length: {}\r\n\r\n".format(filelength)
        # if content-length != database file length: FAILED!
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((req_file[1], p2p_server_port))
        s.send(get_msg.encode())
        #data = s.recv(BUFFER_SIZE)
        writefile = open(req_file[2], 'wb')
        with stdout_lock:
            print("Waiting for file...")
        length = int(req_file[3])
        data = s.recv(min(1024, length))
        writefile.write(data)
        length -= len(data)
        with stdout_lock:
            print("Receiving file...")
        while(length > 0):
            data = s.recv(min(1024, length))
            writefile.write(data)
            length -= len(data)
        s.close()
        with stdout_lock:
            print("File download complete!")


def send_file(conn, addr):
    with stdout_lock:
        print("==>Connected by peer {}".format(addr))
    data = conn.recv(1024)
    if data:
        data = data.decode()
        with stdout_lock:
            print("\t-->Peer request: {}".format(data))
        data = data.split(" ")
        method = data[0]
        version = data[-1]
        filename = ' '.join(data[1:-1])
        sendfile = open(filename, 'rb')
        with stdout_lock:
            print("\t-->Sending file to peer {}".format(addr))
        filedata = sendfile.read()
        conn.sendall(filedata)
        conn.close()
        with stdout_lock:
            print("\t-->File transfer complete!")


def tcp_listener():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', p2p_server_port))
    s.listen(5)

    while True:
        conn, addr = s.accept()
        file_send_thread = threading.Thread(target=send_file, args=(conn, addr))
        file_send_thread.start()
    s.close()


def start_client(server_ip=default_server_host, server_prt=default_server_port,
                 p2p_server_prt=default_p2p_server_port,
                 udp_listen_prt=default_udp_listen_port):
    global server_host
    global server_port
    global p2p_server_port
    global udp_listen_port
    global msg
    server_host = server_ip
    server_port = int(server_prt)
    p2p_server_port = int(p2p_server_prt)
    udp_listen_port = int(udp_listen_prt)
    msg = clientmsg.ClientMsg(host_id, get_ip_address())

    try:
        r.start_server(udp_listen_port)
        # Listen to terminal input from keyboard
        stdin_thread = threading.Thread(target=stdin_listener, args=())
        stdin_thread.start()
        tcp_thread = threading.Thread(target=tcp_listener, args=())
        tcp_thread.start()
        while True:
            # Client loop
            try:
                message = r.receive_data()
                process_message(message)
            except queue.Empty:
                continue
            except:
                print("Unexpected error:", sys.exec_info()[0])
    except KeyboardInterrupt:
        print("Goodbye!")
    except:
        print("Unexpected error:", sys.exec_info()[0])
    finally:
        r.close()
        os._exit(1)


if __name__ == "__main__":
    """
    Usage:
        python3 client.py [server_ip [server_port [p2p_server_port [udp_listen_port]]]]

    """
    if len(sys.argv) == 5:
        start_client(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 4:
        start_client(sys.argv[1], sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3:
        start_client(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        start_client(sys.argv[1])
    else:
        start_client()
