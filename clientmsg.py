import glob


class ClientMsg(object):
    """
    P2P Client to Directory Server messages.

    See client messages specification for message format details.

    """
    def __init__(self, hostname, ip_address):
        self.hostname = hostname
        self.ip_address = ip_address
        self.method = ""
        self.body = ""

    def ident(self):
        """
        Inform and Update Message

        """
        self.method = "IDENT"
        self.body = ""

    def inform(self, file_list):
        """
        Inform and Update message.

        Arguments:
        file_list -- List of file entries as (filename, filesize) tuple, where
                     filename is a quoted string and filesize is the size of
                     the file in bytes.

        """
        self.method = "INFORM"
        self.body = ""
        for file in file_list:
            self.body = "{}{} {}\r\n".format(self.body, file[0], file[1])

    def query(self, search_string, hostname=""):
        """
        Query message.

        Arguments:
        search_string -- Substring to search for - within filenames stored in the database
                         server - as a quoted string (e.g., "Birthday" will search for all
                         filenames which contain the string "Birthday". Case matters. To
                         search for quotation marks within a filename, they must be
                         quoted).

        hostname -- Hostname of the specific client to search, if specified.

        """
        self.method = "QUERY"
        self.body = "{} {}\r\n".format(search_string, hostname)

    def remove(self, file_list):
        """
        Remove message.

        Arguments:
        file_list -- List of file entries as (filename, filesize) tuple, where
                     filename is a quoted string and filesize is the size of
                     the file in bytes.

        """
        self.method = "REMOVE"
        self.body = ""
        for line in file_list:
            self.body = "{}{} {}\r\n".format(self.body, line[0], line[1])

    def exit(self):
        self.method = "EXIT"
        self.body = ""

    def __repr__(self):
        self.message = "{} {} {}\r\n{}\r\n".format(self.method, self.hostname, self.ip_address, self.body)

        return self.message
