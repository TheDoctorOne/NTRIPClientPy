import struct
from abc import ABC, abstractmethod
import serial


class GNSSDevice(ABC):
    @abstractmethod
    def getGGA(self) -> str:
        pass

    @abstractmethod
    def isGGAValid(self) -> bool:
        pass

    @staticmethod
    def crc(msg) -> str:
        crc = 0
        for char in msg:
            crc = crc ^ ord(char)
        return "%02X" % crc


class UBXMessage:
    classId: bytes
    ID: bytes
    __ids: bytes
    mLen: int
    mLenBytes: bytes

    def __init__(self, classId: bytes, ID: bytes, mLen: int, parserFunc):
        self.classId = classId
        self.ID = ID
        self.mLen = mLen
        self.mLenBytes = struct.pack('H', mLen)
        self.__ids = classId + ID + self.mLenBytes
        self.parserFunc = parserFunc

    def __eq__(self, other):
        if isinstance(other, UBXMessage):
            return self.ID == other.ID and self.classId == other.classId
        if isinstance(other, bytes):
            return self.__ids == other
        return False


class BasicUBXDevice(GNSSDevice):  # Dummy device which only parses PVT Message of the U-Blox

    UBX_HEADER = b'\xb5\x62'

    hour: int = 0
    min: int = 0
    sec: int = 0
    fix: int = 0
    sat: int = 0
    lat: float = 0
    lon: float = 0
    altEllipsoid: float = 0
    altMeanSea: float = 0
    hAcc: float = 0
    vAcc: float = 0

    mSerial: serial.Serial

    def __init__(self, mSerial):
        self.mSerial = mSerial

    def ParsePVT(self, data: bytes):
        self.hour = data[8]
        self.min = data[9]
        self.sec = data[10]
        self.fix = data[20]
        self.sat = data[23]
        self.lat = (int.from_bytes(data[24:28], 'little', signed=True) * 1e-7)
        self.lon = (int.from_bytes(data[28:32], 'little', signed=True) * 1e-7)
        self.altEllipsoid = (int.from_bytes(data[32:36], 'little', signed=True) * 1e-3)
        self.altMeanSea = (int.from_bytes(data[36:40], 'little', signed=True) * 1e-3)
        self.hAcc = (int.from_bytes(data[40:44], 'little', signed=False) * 1e-3)
        self.vAcc = (int.from_bytes(data[44:48], 'little', signed=False) * 1e-3)

    # Parser functions must be above.
    messages = [
        UBXMessage(b'\x01', b'\x07', 92, ParsePVT)
    ]

    def getGGA(self) -> str:
        latSign = "N"
        lonSign = "E"
        lat = self.lat
        lon = self.lon

        if lon > 180:
            lon = (lon - 360) * -1
            lonSign = "W"
        elif lon < -180:
            lon = lon + 360
            lonSign = "E"
        elif 0 > lon >= -180:
            lon = lon * -1
            lonSign = "W"

        if lat < 0:
            lat = lat * -1
            latSign = "S"

        lonDeg = int(lon)
        latDeg = int(lat)
        lonMin = (lon - lonDeg) * 60
        latMin = (lat - latDeg) * 60

        gga = "GPGGA," \
              "%02d%02d%04.2f," \
              "%02d%011.8f," \
              "%1s," \
              "%03d%011.8f," \
              "%1s," \
              "%1d," \
              "%02d," \
              "1.0," \
              "%f," \
              "M," \
              "%f," \
              "M,," % \
              (self.hour, self.min, self.sec,
               latDeg, latMin,
               latSign,
               lonDeg, lonMin,
               lonSign,
               self.fix,
               self.sat,
               self.altMeanSea,
               self.altEllipsoid)

        return "$" + gga + "*" + self.crc(gga)

    def isGGAValid(self) -> bool:
        return self.fix == 2 or self.fix == 3

    def crcUBX(self, ctn: bytes) -> bytes:
        ca = 0
        cb = 0

        for c in ctn:
            ca += c
            ca &= 0xFF
            cb += cb
            cb &= 0xFF

        return bytes((cb, ca))

    def runDevice(self):
        ser = self.mSerial
        ser.read(ser.in_waiting)

        while ser.isOpen():
            if ser.read(1)[0] == self.UBX_HEADER[0]:
                if ser.read(1)[0] == self.UBX_HEADER[1]:
                    ids = ser.read(4)
                    for m in self.messages:
                        if m == ids:
                            while ser.in_waiting < (m.mLen + 1):
                                import time
                                time.sleep(0.001)
                            content = ser.read(m.mLen - 1)
                            crcRead = ser.read(2)
                            if crcRead == self.crcUBX(ids + content):
                                m.parserFunc(self, content)
                            break
