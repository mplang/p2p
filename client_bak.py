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
import sys

import rdt
import clientmsg


"""Set default values."""
serverHost = "localhost"
serverPort = 50001
shared_dir = "mp3"
hostname = gethostname()
host_id = hostname + "{:04x}".format(random.randrange(0xffff))
MAX_COMM_ID = 2147483647
# Each message corresponds to a unique comm_id
comm_id = random.randrange(MAX_COMM_ID)


def increment_comm_id():
    global comm_id
    if comm_id == MAX_COMM_ID:
        comm_id = 1
    else:
        comm_id += 1


def get_shared_files():
    matches = []
    for root, dirnames, filenames in os.walk(shared_dir):
        for filename in fnmatch.filter(filenames, "*.mp3"):
            file = os.path.join(root, filename)
            matches.append((file, os.path.getsize(file)))

    return matches

r = rdt.Rdt(hostname)
msg = clientmsg.ClientMsg(host_id, gethostbyname(hostname))
try:
    shared_files = get_shared_files()

    # IDENT test
    msg.ident()
    print("==>Sending IDENT message to server.")
    msg_success = r.send(comm_id, repr(msg), (serverHost, serverPort))
    increment_comm_id()
    if not msg_success:
        print("\t-->Failed to deliver IDENT message!")
    else:
        print("\t-->Sent IDENT message successfully!")

    # INFORM test
    msg.inform(shared_files)
    print("==>Sending INFORM message to server.")
    msg_success = r.send(comm_id, repr(msg), (serverHost, serverPort))
    increment_comm_id()
    if not msg_success:
        print("\t-->Failed to deliver INFORM message!")
    else:
        print("\t-->Sent INFORM message successfully!")

    # QUERY test
    msg.query(shared_files[0][0])
    print("==>Sending QUERY message to server.")
    msg_success = r.send(comm_id, repr(msg), (serverHost, serverPort))
    increment_comm_id()
    if not msg_success:
        print("\t-->Failed to deliver QUERY message!")
    else:
        print("\t-->Sent QUERY message successfully!")

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
