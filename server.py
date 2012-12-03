"""
server.py
Author: Michael P. Lang
Email: michael@mplang.net
Date Modified: 3 December 2012

Notes:
    As it stands, the server doesn't check for duplicate files
    shared by a given client.
"""

import sys
import os
import socket
import sqlite3
import time
import queue
import threading
from _thread import interrupt_main
import random
import shlex

import rdt
import servermsg

# port to bind to
listen_port = 50001

MAX_COMM_ID = 2147483647
# Each message corresponds to a unique comm_id
comm_id = random.randrange(MAX_COMM_ID)

r = rdt.Rdt(socket.gethostname())

activity_tracker = {}
dbname = "filedir.db"

stdout_lock = threading.Lock()
tracker_lock = threading.Lock()
db_lock = threading.Lock()

verbose = False


def now():
    """
    Returns the current time. Used for logging and debugging purposes.

    """
    return time.ctime(time.time())


def increment_comm_id():
    global comm_id
    if comm_id == MAX_COMM_ID:
        comm_id = 1
    else:
        comm_id += 1


def init_database():
    c = sqlite3.connect(dbname)
    with c:
        cursor = c.cursor()
        cursor.execute("drop table if exists directory")
        cursor.execute("""create table if not exists directory
                       (hostid text, hostip text, filename text,
                       filesize integer)""")


def stdin_listener():
    with stdout_lock:
        print("Enter quit or exit to shut down the server and exit.")
    while True:
        kybd_in = input()
        kybd_in = shlex.split(kybd_in)
        if kybd_in[0] == "quit" or kybd_in[0] == "exit":
            with stdout_lock:
                print("***Received quit signal from stdin. Exiting application...")
            interrupt_main()
        elif kybd_in[0] == "query":
            if len(kybd_in) == 2:
                print_database_query(database_query("localhost", kybd_in[1] + " "))
            else:
                with stdout_lock:
                    print("***Invalid query.")
        elif kybd_in[0] == "reset":
            reset_server()
            with stdout_lock:
                print("\t-->Server reset complete!")
        elif kybd_in[0] == "status":
            connected_clients = get_db_clients()
            with stdout_lock:
                print("\t-->{} connected clients.".format(len(connected_clients)))
        else:
            with stdout_lock:
                print("***Invalid Input!")


def reset_server():
    init_database()
    global activity_tracker
    activity_tracker = {}
    increment_comm_id()


def process_message(message):
    # ignore empty lines
    body = [line for line in message.split("\r\n") if line]
    header = body[0].split(' ')
    body = body[1:]
    method, client_id, client_ip_addr = header
    msg = servermsg.ServerMsg()

    if method == "IDENT":
        with stdout_lock:
            print("==>Server received IDENT message from {} @ {} at {}.".
                  format(client_id, client_ip_addr, now()))
        activity_tracker[(client_id, client_ip_addr)] = time.time()
        msg.identok(client_id)
        increment_comm_id()
        with stdout_lock:
            print("\t-->Sending IDENTOK message to {}.".format(client_id))
            if verbose:
                print(('*' * 25) + '\n' + repr(msg) + '\n' + ('*' * 25))
        r.send(comm_id, repr(msg), (client_ip_addr, 60001))
    elif method == "INFORM":
        with stdout_lock:
            print("==>Server received INFORM message from {} @ {} at {}.".
                  format(client_id, client_ip_addr, now()))
        num_entries = database_add(client_id, client_ip_addr, body)
        print("\t-->Added {} entries to the database.".format(num_entries))
        activity_tracker[(client_id, client_ip_addr)] = time.time()
        msg.ok("INFORM", str(num_entries))
        increment_comm_id()
        with stdout_lock:
            print("\t-->Sending INFORMOK message to {}.".format(client_id))
            if verbose:
                print(('*' * 25) + '\n' + repr(msg) + '\n' + ('*' * 25))
        r.send(comm_id, repr(msg), (client_ip_addr, 60001))
    elif method == "QUERY":
        with stdout_lock:
            print("==>Server received QUERY message from {}@{} at {}.".
                  format(client_id, client_ip_addr, now()))
        result_list = database_query(client_id, body)
        with stdout_lock:
            print("\t-->Server found {} query matches.".
                  format(len(result_list)))
        activity_tracker[(client_id, client_ip_addr)] = time.time()
        msg.queryresponse(result_list)
        increment_comm_id()
        with stdout_lock:
            print("\t-->Sending QUERYRESPONSE message to {}.".format(client_id))
            if verbose:
                print(('*' * 25) + '\n' + repr(msg) + '\n' + ('*' * 25))
        r.send(comm_id, repr(msg), (client_ip_addr, 60001))
    elif method == "REMOVE":
        with stdout_lock:
            print("==>Server received REMOVE message from {}@{} at {}.".
                  format(client_id, client_ip_addr, now()))
        num_entries = database_remove_files(client_id, body)
        with stdout_lock:
            print("\t-->Removed {} entries from the database.".format(num_entries))
        activity_tracker[(client_id, client_ip_addr)] = time.time()
        msg.ok("REMOVE", str(num_entries))
        with stdout_lock:
            print("\t-->Sending REMOVEOK message to {}.".format(client_id))
            if verbose:
                print(('*' * 25) + '\n' + repr(msg) + '\n' + ('*' * 25))
    elif method == "EXIT":
        with stdout_lock:
            print("==>Server received EXIT message from {}@{} at {}.".
                  format(client_id, client_ip_addr, now()))
        num_entries = database_remove_host(client_id)
        activity_tracker.pop((client_id, client_ip_addr), None)
        with stdout_lock:
            print("\t-->Removed {} from the database ({} entries).".format(host_id, num_entries))


def database_add(host_id, host_ip_addr, body):
    file_list = [(' '.join(entry[:-1]), entry[-1]) for entry in [line.split(' ') for line in body]]
    c = sqlite3.connect(dbname)
    with c:
        cur = c.cursor()
        for line in file_list:
            cur.execute("insert into directory(hostid, hostip, filename, filesize) values (?, ?, ?, ?)",
                        (host_id, host_ip_addr, line[0], line[1]))

    return c.total_changes


def database_query(client_id, body):
    search_string, search_host = ([(' '.join(entry[:-1]), entry[-1])
                                  for entry in [line.split(' ') for line in body]][0])
    c = sqlite3.connect(dbname)
    with c:
        cur = c.cursor()
        if search_host:
            cur.execute("select * from directory where filename like ? and hostid = ? and hostid != ?",
                        ['%' + search_string + '%', search_host, client_id])
        else:
            cur.execute("select * from directory where filename like ? and hostid != ?",
                        ['%' + search_string + '%', client_id])
        rows = cur.fetchall()

    return rows


def print_database_query(query_results):
    with stdout_lock:
        print("")
        if len(query_results) != 0:
            for i, line in enumerate(query_results):
                print("[{}]: {}\nFilesize: {}\tHost ID: {}\tIP Address: {}".
                      format(i, line[2], line[3], line[0], line[1]))
        else:
            print("\t-->No items found which match your query.")


def database_remove_files(host_id, body):
    file_list = [(' '.join(entry[:-1]), entry[-1]) for entry in [line.split(' ') for line in body]]
    c = sqlite3.connect(dbname)
    with c:
        cur = c.cursor()
        for file in file_list:
            cur.execute("delete from directory where filename = ? and hostid = ?", [file[0], host_id])

    return c.total_changes


def database_remove_host(host_id):
    c = sqlite3.connect(dbname)
    with c:
        cur = c.cursor()
        cur.execute("delete from directory where hostid = ?", [host_id])

    return c.total_changes


def get_db_clients():
    c = sqlite3.connect(dbname)
    with c:
        cur = c.cursor()
        cur.execute("select distinct hostid, hostip from directory")
        current_clients = cur.fetchall()

    print(current_clients)
    return current_clients


def server(listen_port):
    try:
        r.start_server(listen_port)
        stdin_thread = threading.Thread(target=stdin_listener, args=())
        stdin_thread.start()
        while True:
            # Server loop
            curr_time = time.time()
            for activity in activity_tracker:
                if curr_time - activity_tracker[activity] > 3600:
                    # Clean database of hosts with activity more than one hour ago.
                    with stdout_lock:
                        print("Remove host from database: {}".format(activity[0]))
                    database_remove_host(activity[0])
            try:
                message = r.receive_data()
                process_message(message)
            except queue.Empty:
                continue
            except:
                with stdout_lock:
                    print("Unexpected error:", sys.exec_info()[0])
    except KeyboardInterrupt:
        with stdout_lock:
            print("Goodbye!")
    except:
        with stdout_lock:
            print("Unexpected error:", sys.exec_info()[0])
    finally:
        r.close()
        os._exit(1)

if __name__ == "__main__":
    init_database()
    server(listen_port)
