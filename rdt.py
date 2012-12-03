"""
rdt.py
Author: Michael P. Lang
Email: michael@mplang.net
Data Modified: 1 December 2012
"""

import threading
import socket
import time
import queue
from math import ceil


class Rdt(object):
    seq_number = 1  # Static sequence number variable shared amongst all
                    # instances of the Rdt class. Valid values are [1,
                    # 2147483647] (i.e., a 32-bit signed integer).

    def __init__(self, hostname):
        """
        Initialize default values.

        Arguments:
        hostname -- hostname of this (sending) client.

        """
        self.hostname = hostname
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.message_queue = queue.Queue()
        self.stdout_lock = threading.Lock()
        self.fragments = {}
        self.MTU = 128
        # Estimated RTT in seconds
        self.estimated_RTT = 0.1
        self.dev_RTT = 0.0
        # Socket timeout interval in seconds
        self.timeout_interval = 1.0
        # Maximum number of retransmission attempts for a packet
        self.max_retries = 3
        # Maximum sequence number value (2^31 - 1)
        self.MAX_SEQ_NUM = 2147483647
        # If a (host_id, comm_id) pair has already been processed
        # add it to the list
        self.closed_communications = []

    def send(self, comm_id, data, address):
        """
        Method called from upper layer to handle message. Complete RDT packets
        are transmitted via UDP.

        Arguments:
        data -- the (unencoded) upper-layer data to transmit.
        address -- the destination IP address/FQDN and port passed as a
                   2-tuple.

        Returns:
        True if upper-layer data was sent successfully, else returns False.

        """
        for header, packet in self.make_packets(comm_id, data):
            ack_seq = 0
            retries = 0
            sample_RTT = 0.0
            while not ack_seq:
                if retries == self.max_retries:
                    # Reached maximum number of retransmissions.
                    # TODO: Send RST packet?
                    self.sock.settimeout(None)  # Place socket in blocking mode
                    self.increment_seq_number()
                    return False

                #print("Sending to {} @ {}".format(address[0], address[1]))
                self.sock.sendto(packet.encode(), address)
                self.sock.settimeout(self.timeout_interval)
                while True:
                    try:
                        start_time = time.perf_counter()
                        response = self.sock.recv(1024)
                        sample_RTT = time.perf_counter() - start_time
                        ack_seq = self.process_response(header, response)
                        if ack_seq == Rdt.seq_number or ack_seq == 0:
                            # Keep only packets with the correct seq_number,
                            # drop other packets
                            break
                    except:
                        # Transmission timed-out
                        # TODO: Catch only timeout exceptions
                        self.timeout_interval *= 2
                        ack_seq = 0
                        break
                retries += 1

            if retries == 1:
                # Packet was successfully sent and acknowledged on first try
                self.estimated_RTT *= 0.875
                self.estimated_RTT += (0.125 * sample_RTT)
                self.dev_RTT *= 0.75
                self.dev_RTT += (0.25 * abs(sample_RTT - self.estimated_RTT))
                self.timeout_interval = self.estimated_RTT + 4 * self.dev_RTT
            self.sock.settimeout(None)  # Place socket in blocking mode
            self.increment_seq_number()

        return True

    def increment_seq_number(self):
        if Rdt.seq_number == self.MAX_SEQ_NUM:
            Rdt.seq_number = 1
        else:
            Rdt.seq_number += 1

    def make_packets(self, comm_id, data):
        """
        Creates packets containing the payload from the upper layer for
        transmissiond to the receiver. Data is split into MTU-byte chunks (each
        of which will be the payload for an individual packet), creates a
        header for each chunk, and makes a packet by prepending the header to
        the payload.

        Arguments:
        comm_id -- The communication ID associated with this message. Used to
                   keep track of separate messages from the same host.
        data -- The (unencoded) payload to be sent in this packet.

        Returns:
        Yields a tuple containing the current header and complete packet as
        unencoded strings.

        """
        data_length = len(data)
        # Number of packets to be sent
        num_packets = self.MTU * (ceil(data_length / self.MTU) - 1)
        for i in range(0, data_length, self.MTU):
            flags = ""
            if i == 0:
                # First packet
                flags += "SYN"
            if i == num_packets:
                # Last packet
                flags += "FIN"

            payload = data[i:i + self.MTU]

            header = [self.hostname, str(comm_id), str(Rdt.seq_number), flags]
            packet = "{0} {1} {2} {3} {4}".format(header[0], header[1], header[2], header[3], payload)

            yield (header, packet)

    def start_server(self, port):
        """
        Called by upper-layer server to initialize the server.

        Arguments:
        port -- The port number to listen on.

        """
        self.listen_sock.bind(('', port))
        thread = threading.Thread(target=self.listen_thread, args=())
        thread.start()
        #_thread.start_new(self.listen_thread, ())

    def listen_thread(self):
        """
        Listens to socket. Creates a new thread to handle received data.

        """
        while True:
            data, address = self.listen_sock.recvfrom(1024)
            if not data:
                break
            thread = threading.Thread(target=self.process_pkt, args=(data, address))
            thread.start()

    def process_pkt(self, data, address):
        """
        Decodes and processes the packet.

        Arguments:
        data -- Complete packet fresh from the socket as a bytestring.
        address -- The address tuple of the incoming connection.

        """
        header, payload = self.extract(data.decode())
        self.send_ack(header, address)

        if "SYN" in header[3]:
            self.fragments[(header[0], header[1])] = {}
        if (header[0], header[1]) in self.fragments:
            self.fragments[(header[0], header[1])][header[2]] = payload

            if "FIN" in header[3]:
                # If we get a FIN packet without a SYN packet, ignore it.
                # This should mean a duplicate FIN that we've already processed.
                self.reassemble_message((header[0], header[1]))

    def extract(self, data):
        """
        Extracts the upper-layer message payload from the packet.

        This implementation creates a list of strings split by the space character.
        The header fields: pkt_host, pkt_commid, pkt_seq, and pkt_flags are
        extracted from the list. Then the data payload portion is reassembled by
        joining the remaining items.

        Arguments:
        data -- An RDT packet.

        Returns:
        A tuple containing the RDT header(as a list) and the upper-layer
        message payload string.

        """
        split_pkt = [field for field in data.split(" ")]
        # pkt_host, pkt_commid, pkt_seq, pkt_flags = split_pkt[:4]
        pkt_header = split_pkt[:4]
        pkt_payload = " ".join(split_pkt[4:])

        return (pkt_header, pkt_payload)

    def send_ack(self, header, address):
        ack_header = "{} {} {} {}ACK".format(self.hostname, header[1], header[2], header[3])
        self.sock.sendto(ack_header.encode(), address)

    def reassemble_message(self, msgkey):
        if msgkey in self.closed_communications:
            del self.fragments[msgkey]
        else:
            message = ''.join([self.fragments[msgkey][i] for i in sorted(self.fragments[msgkey], key=int)])
            del self.fragments[msgkey]
            self.closed_communications.append(msgkey)

            self.message_queue.put(message)

    def close(self):
        """
        Explicitly releases the socket. Called by upper-layer application.

        """
        self.sock.close()
        self.listen_sock.close()

    def now(self):
        """
        Returns the current time. Used for logging and debugging purposes.

        """
        return time.ctime(time.time())

    def process_response(self, out_header, response):
        """
        Returns the sequence number of the response packet or 0 if the
        response packet is not an ACK.

        """
        in_header = self.extract(response.decode())[0]

        if "ACK" in in_header[3]:
            return int(in_header[2])

        return 0

    def receive_data(self):
        """
        Called by upper layer to receive messages from the queue.

        """
        return self.message_queue.get(True, 5)
        #return self.message_queue.get_nowait()
