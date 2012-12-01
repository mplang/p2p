class ServerMsg(object):
    """
    P2P Directory Server to Client messages.

    See server messages specification for message format details.

    """
    def __init__(self):
        self.status_code = ""
        self.status_phrase = ""
        self.body = ""
        self.message = ""

    def identok(self, host_id):
        """
        IDENT Response Message

        Arguments:
        host_id -- host_id value as received by the server (should be the
                   same value sent by the client).

        """
        self.status_code = "202"
        self.status_phrase = "IDENTOK"
        self.body = "IDENT {}\r\n".format(host_id)

    def ok(self, method, count):
        """
        INFORM, REMOVE, and EXIT response message.

        Arguments:
        method -- The method the server is responding to. Must be one of
                  INFORM, REMOVE, or EXIT.
        count -- The number of items added or removed from the database.

        """
        self.status_code = "200"
        self.status_phrase = "OK"
        self.body = "{} {}\r\n".format(method, count)

    def error(self, method, error_msg=""):
        """
        Acknowledges receipt of INFORM, REMOVE, QUERY, LIST, and EXIT messages,
        and notifies sender that some error has occurred in processing.

        Arguments:
        method -- INFORM | REMOVE | QUERY | LIST | EXIT
        error_msg -- Error message as quoted string. Field must not be empty (though
                     the error message inside the quotes may be empty). Format for
                     this message is not specified by this standard.

        """
        self.status_code = "400"
        self.status_phrase = "ERROR"
        self.body = "{} {}\r\n".format(method, error_msg)

    def queryresponse(self, results_list):
        """
        Acknowledges receipt of QUERY message and returns the query results. If there
        are no results, an ERROR message is returned with QUERY as the method.
        Note: This response uses two consecutive value lines per query match.
    
        Arguments:
        results_list -- List of query results in the format:
                        (hostid, host_ip_addr, filename, filesize)
    
        """
        self.status_code = "800"
        self.status_phrase = "QUERYRESPONSE"
        self.body = ""
        for line in results_list:
            self.body = "{}{} {}\r\n{} {}\r\n".format(self.body, line[0], line[1], line[2], line[3])
    
    def __repr__(self):
        self.message = "{} {}\r\n{}\r\n".format(self.status_code, self.status_phrase, self.body)
    
        return self.message
