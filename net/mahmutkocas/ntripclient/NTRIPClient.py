import base64
import socket

from net.mahmutkocas.ntripclient.NTRIPStatus import NTRIPStatus

CONNECTION_ERROR = NTRIPStatus("CONNECTION_ERROR", -2)
STREAM_NOT_VALID = NTRIPStatus("STREAM_NOT_VALID", -1)
IDLE = NTRIPStatus("IDLE", 0)
READY = NTRIPStatus("READY", 1)
SOURCE_TABLE_DOWNLOADING = NTRIPStatus("SOURCE_TABLE_DOWNLOADING", 2)
SOURCE_TABLE_DOWNLOADED = NTRIPStatus("SOURCE_TABLE_DOWNLOADED", 3)
NTRIP_DATA = NTRIPStatus("NTRIP_DATA", 4)


class NtripClient:
    successResponse = "ICY 200 OK"
    passWrongResponse = "401 Unauthorized"
    sourceTableResponse = "SOURCETABLE 200 OK"
    sourceTableEndResponse = "ENDSOURCETABLE"

    statusCallback = []
    mountPointsCallback = []
    ntripDataCallback = []

    latestGGA = ""
    mPoints = ""

    status = IDLE

    streamData = ''

    conn: socket
    SOCKET_BUFFER_SIZE = 2048

    connTimeout = 10

    def __init__(self, ip: str, port: int, mountPoint: str, username: str, password: str):
        self.ip = ip
        self.port = port
        self.mountPoint = mountPoint
        self.username = username
        self.password = password

    def updateGGA(self, gga):
        self.latestGGA = gga

    def addStatusCallback(self, callback):
        self.statusCallback.append(callback)

    def addMountPointsCallback(self, callback):
        self.mountPointsCallback.append(callback)

    def addNtripDataCallback(self, callback):
        self.ntripDataCallback.append(callback)

    def updateStatusCallback(self, status: NTRIPStatus):
        for c in self.mountPointsCallback:
            c(status)

    def updateMountPointsCallback(self, sTable):
        for c in self.mountPointsCallback:
            c(sTable)

    def updateNtripDataCallback(self, ntripData):
        for c in self.ntripDataCallback:
            c(ntripData)

    def updateStatus(self, stat: NTRIPStatus):
        self.status = stat
        self.updateStatusCallback(stat)

    def sendToServer(self, msg: str):
        self.conn.send(msg.encode('ascii'))

    def buildHttpHeader(self, mountPoint: str, username: str, password: str):
        header = "GET /" + mountPoint + " HTTP/1.0\r\n" \
                 + "User-Agent: NTRIP Client/1.0\r\n" \
                 + "Accept: */*\r\n" \
                 + "Connection: close\r\n" \
                 + "Authorization: Basic " \
                 + str((base64.b64encode((username + ":" + password).encode('ascii')) + b"\r\n").decode('ascii')) \
                 + "\r\n"
        return header

    def resolveSourceTableToMountPoints(self, sTable: str):
        """
        :param sTable: Source Table string which gets downloaded from ntrip stream.
        :return: True if source table resolved. False source table stream not ended.
        """

        if self.sourceTableEndResponse not in sTable:
            return False

        lines = sTable.split('\n')
        mPoints = ""

        for line in lines:
            if 'STR' in line:
                mPoints += line.split("STR;")[1].split(";")[0] + ";"

        self.mPoints = mPoints
        self.updateMountPointsCallback(mPoints)

        return True

    def closeSocket(self):
        self.conn.close()

    def parseStream(self, data):
        """
        :param data: str or bytes
        :return: NTRIPStatus
        """
        if self.status == IDLE or self.status == SOURCE_TABLE_DOWNLOADING:
            if isinstance(data, bytes) or isinstance(data, bytearray):
                data = data.decode('ascii')

            self.streamData += data

            if not isinstance(self.streamData, str):
                self.updateStatus(STREAM_NOT_VALID)
                return

        if self.status == IDLE:
            if self.successResponse in self.streamData:
                self.sendToServer(self.latestGGA + "\r\n")
                self.updateStatus(NTRIP_DATA)

            if self.sourceTableResponse in self.streamData:
                self.updateStatus(SOURCE_TABLE_DOWNLOADING)
                if self.resolveSourceTableToMountPoints(self.streamData):
                    self.updateStatus(SOURCE_TABLE_DOWNLOADED)

        elif self.status == SOURCE_TABLE_DOWNLOADING:
            if self.resolveSourceTableToMountPoints(self.streamData):
                self.updateStatus(SOURCE_TABLE_DOWNLOADED)

        elif self.status == NTRIP_DATA:
            self.updateNtripDataCallback(data)

    def runServer(self):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.connect((self.ip, self.port))
        self.conn.settimeout(self.connTimeout)
        self.conn.send(self.buildHttpHeader(self.mountPoint, self.username, self.password).encode('ascii'))
        while True:
            try:
                read = self.conn.recv(self.SOCKET_BUFFER_SIZE)
                if read == b'':
                    self.updateStatus(STREAM_NOT_VALID)
                    break
                self.parseStream(read)
            except Exception as e:
                self.status.exception = e
                self.updateStatus(CONNECTION_ERROR)
                raise e
        pass
