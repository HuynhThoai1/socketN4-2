import sys
from time import time
HEADER_SIZE = 12

class RtpPacket:
    
    def __init__(self):
        # header/payload là thuộc tính của instance (không dùng mutable class attr)
        self.header = bytearray(HEADER_SIZE)
        self.payload = b''
		
    def encode(self, version, padding, extension, cc, seqnum, marker, pt, ssrc, payload):
        """Encode the RTP packet with header fields and payload."""
        timestamp = int(time()) & 0xFFFFFFFF
        header = bytearray(HEADER_SIZE)

        # First byte: V (2b), P (1b), X (1b), CC (4b)
        header[0] = ((version & 0x03) << 6) | ((padding & 0x01) << 5) | ((extension & 0x01) << 4) | (cc & 0x0F)
        # Second byte: M (1b), PT (7b)
        header[1] = ((marker & 0x01) << 7) | (pt & 0x7F)
        # Sequence number (16 bits)
        header[2] = (seqnum >> 8) & 0xFF
        header[3] = seqnum & 0xFF
        # Timestamp (32 bits)
        header[4] = (timestamp >> 24) & 0xFF
        header[5] = (timestamp >> 16) & 0xFF
        header[6] = (timestamp >> 8) & 0xFF
        header[7] = timestamp & 0xFF
        # SSRC (32 bits)
        header[8] = (ssrc >> 24) & 0xFF
        header[9] = (ssrc >> 16) & 0xFF
        header[10] = (ssrc >> 8) & 0xFF
        header[11] = ssrc & 0xFF

        # Ensure payload is bytes
        if isinstance(payload, str):
            payload = payload.encode()
        elif not isinstance(payload, (bytes, bytearray)):
            payload = bytes(payload)

        self.header = header
        self.payload = bytes(payload)
		
    def decode(self, byteStream):
        """Decode the RTP packet."""
        self.header = bytearray(byteStream[:HEADER_SIZE])
        self.payload = byteStream[HEADER_SIZE:]
	
    def version(self):
        """Return RTP version."""
        return int(self.header[0] >> 6)
	
    def seqNum(self):
        """Return sequence (frame) number."""
        seqNum = self.header[2] << 8 | self.header[3]
        return int(seqNum)
	
    def timestamp(self):
        """Return timestamp."""
        timestamp = self.header[4] << 24 | self.header[5] << 16 | self.header[6] << 8 | self.header[7]
        return int(timestamp)
	
    def payloadType(self):
        """Return payload type."""
        pt = self.header[1] & 127
        return int(pt)
	
    def getPayload(self):
        """Return payload."""
        return self.payload
		
    def getPacket(self):
        """Return RTP packet."""
        return self.header + self.payload