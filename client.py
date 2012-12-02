"""
client.py
Author: Michael P. Lang
Email: michael@mplang.net
Date Modified: 2 December 2012
"""

from socket import gethostname, gethostbyname
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
serverHost = "localhost"
serverPort = 50001
listenPort = 60001
default_share = "mp3"
shared_files = []
hostname = gethostname()
host_id = hostname + "{:04x}".format(random.randrange(0xffff))
# port to bind to
listen_port = 60001
r = rdt.Rdt(host_id)
MAX_COMM_ID = 2147483647
# Each message corresponds to a unique comm_id
comm_id = random.randrange(MAX_COMM_ID)
msg = clientmsg.ClientMsg(host_id, gethostbyname(hostname))
msg_queue = queue.Queue()
connected = False
current_query = []


def increment_comm_id():
    global comm_id
    if comm_id == MAX_COMM_ID:
        comm_id = 1
    else:
        comm_id += 1


def get_shared_files(shared_dir):
    matches = []
    for root, dirnames, filenames in os.walk(shared_dir):
        for filename in fnmatch.filter(filenames, "*.mp3"):
            file = os.path.join(root, filename)
            matches.append((file, os.path.getsize(file)))

    return matches


def usage():
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
    print("Type quit or exit to shut down the client and exit.")
    print("Type usage for usage details.")
    while True:
        kybd_in = input()
        kybd_in = shlex.split(kybd_in)
        #kybd_in = kybd_in.split(' ')
        if kybd_in[0] == "quit" or kybd_in[0] == "exit":
            print("***Received quit signal from stdin. Exiting application...")
            interrupt_main()
        elif kybd_in[0] == "usage":
            usage()
        elif kybd_in[0] == "connect":
            if len(kybd_in) == 1:
                ident(serverHost, serverPort)
            elif len(kybd_in) != 3:
                print("***Invalid input!")
            else:
                ident(kybd_in[1], kybd_in[2])
        elif kybd_in[0] == "share":
            if len(kybd_in) == 2:
                share(kybd_in[1])
            elif len(kybd_in) == 1:
                share(default_share)
            else:
                print("***Invalid input!")
        elif kybd_in[0] == "query":
            if len(kybd_in) == 3:
                query(kybd_in[1], kybd_in[2])
            elif len(kybd_in) == 2:
                query(kybd_in[1])
            else:
                print("***Invalid input!")
        elif kybd_in[0] == "status":
            status()
        else:
            print("***Invalid input!")


def status():
    print("\nHost ID: {}\nSharing {} files".format(host_id, len(shared_files)))
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
    print("==>Sending IDENT message to server.")
    msg_queue.queue.clear()
    msg_success = r.send(comm_id, repr(msg), (server_ip, int(server_port)))
    increment_comm_id()
    if msg_success:
        print("\t-->Sent IDENT message successfully!")
        response = msg_queue.get()
        if response[0] == "202" and response[2][0].split(" ")[1] == host_id:
            print("\t-->Received IDENTOK message from server.")
            connected = True
        else:   # Bad response
            print("\t-->Could not connect to server.")
    else:   # not msg_success
        print("\t-->Failed to deliver IDENT message!")


def share(shared_dir):
    if connected:
        matches = get_shared_files(shared_dir)
        msg.inform(matches)
        print("==>Sending INFORM message to server.")
        msg_queue.queue.clear()
        msg_success = r.send(comm_id, repr(msg), (serverHost, serverPort))
        increment_comm_id()
        if msg_success:
            print("\t-->Sent INFORM message successfully!")
            response = msg_queue.get()
            body = response[2][0].split(" ")
            if response[0] == "200" and body[0] == "INFORM":
                print("\t-->Shared {} files with server.".format(body[1]))
                shared_files.extend(matches)
            else:
                print("\t-->Failed to share files with server.")
        else:   # not msg_success
            print("\t-->Failed to deliver INFORM message!")
    else:   # not connected
        print("You are not connected to a server! Please connect and try again.")


def query(search_string, hostname=''):
    if connected:
        msg.query(search_string, hostname)
        print("==>Sending QUERY message to server.")
        msg_queue.queue.clear()
        msg_success = r.send(comm_id, repr(msg), (serverHost, serverPort))
        increment_comm_id()
        if msg_success:
            print("\t-->Sent QUERY message successfully!")
            response = msg_queue.get()
            if response[0] == "800":
                print("\t-->Received QUERY response from server.")
                process_query_response(response[2])
                print_current_query()
            else:   # bad response
                print("\t-->Failed to receive QUERY response from server.")
        else:   # not msg_success
            print("\t-->Failed to deliver QUERY message!")
    else:   # not connected
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
            print("[{}]: {}\nFilesize: {}\tHost ID: {}\tIP Address: {}".
                  format(i, line[2], line[3], line[0], line[1]))
    else:   # no items returned in query response
        print("No items found which match your query.")


def stuff():
    try:
        # REMOVE test
        msg.remove([shared_files[0]])
        print("==>Sending REMOVE message to server.")
        msg_success = r.send(comm_id, repr(msg), (serverHost, serverPort))
        increment_comm_id()
        if not msg_success:
            print("\t-->Failed to deliver REMOVE message!")
        else:
            print("\t-->Sent REMOVE message successfully!")
    
        # QUERY test
        msg.query(shared_files[0])
        print("==>Sending QUERY message to server.")
        msg_success = r.send(comm_id, repr(msg), (serverHost, serverPort))
        increment_comm_id()
        if not msg_success:
            print("\t-->Failed to deliver QUERY message!")
        else:
            print("\t-->Sent QUERY message successfully!")
    finally:
        r.close()


def start_client(listen_port):
    try:
        r.start_server(listen_port)
        # Listen to terminal input from keyboard
        stdin_thread = threading.Thread(target=stdin_listener, args=())
        stdin_thread.start()
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
    start_client(listen_port)
