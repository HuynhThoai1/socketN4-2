# ServerWorker.py (sửa để tương thích với Client.py và convert_tool)
from random import randint
import sys, traceback, threading, socket
import time

from VideoStream import VideoStream
from RtpPacket import RtpPacket

# Kích thước payload tối đa trên mỗi RTP packet.
# Nếu chạy real network nên giảm về ~1400 để tránh fragmentation IP.
MAX_RTP_PAYLOAD = 1400


class ServerWorker:
    SETUP = 'SETUP'
    PLAY = 'PLAY'
    PAUSE = 'PAUSE'
    TEARDOWN = 'TEARDOWN'

    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    OK_200 = 0
    FILE_NOT_FOUND_404 = 1
    CON_ERR_500 = 2

    clientInfo = {}

    def __init__(self, clientInfo):
        """
        clientInfo is expected to contain at least:
          'rtspSocket': (connSocket, clientAddr)
        """
        self.clientInfo = clientInfo

    def run(self):
        threading.Thread(target=self.recvRtspRequest).start()

    def recvRtspRequest(self):
        """Receive RTSP request from the client (blocking loop)."""
        connSocket = self.clientInfo['rtspSocket'][0]
        while True:
            try:
                data = connSocket.recv(256)
                if data:
                    print("DATA RECEIVED: \n", data.decode())
                    self.processRtspRequest(data)
            except Exception:
                # socket closed or error
                traceback.print_exc(file=sys.stdout)
                break

    def processRtspRequest(self, data):
        """Process RTSP request sent from the client."""
        try:
            request = data.decode().split('\n')
            # safety: skip empty lines
            if len(request) == 0 or request[0].strip() == '':
                return

            line1 = request[0].split(' ')
            requestType = line1[0].strip()

            # Get the media file name (if present)
            filename = line1[1] if len(line1) > 1 else None

            # Get the RTSP sequence number 
            seq = None
            if len(request) > 1 and 'CSeq' in request[1]:
                seq = request[1].split(' ')[1].strip()

            # Process SETUP request
            if requestType == self.SETUP:
                if self.state == self.INIT:
                    print("PROCESSING SETUP\n")
                    if not filename:
                        self.replyRtsp(self.FILE_NOT_FOUND_404, seq)
                        return
                    try:
                        # Create VideoStream (may raise IOError)
                        self.clientInfo['videoStream'] = VideoStream(filename)
                        self.state = self.READY
                    except IOError:
                        self.replyRtsp(self.FILE_NOT_FOUND_404, seq)
                        return

                    # Generate a randomized RTSP session ID
                    self.clientInfo['session'] = randint(100000, 999999)

                    # Initialize a per-client RTP sequence counter (increments per RTP packet/fragment)
                    self.clientInfo['rtpSeq'] = 0

                    # Send RTSP reply
                    self.replyRtsp(self.OK_200, seq)

                    # Parse RTP/UDP port from Transport header robustly
                    # request[2] might be like: "Transport: RTP/UDP; client_port= 25000"
                    if len(request) > 2 and 'client_port' in request[2]:
                        try:
                            # split by '=' and take last part, strip spaces
                            self.clientInfo['rtpPort'] = request[2].split('=')[-1].strip()
                        except Exception:
                            pass

            # Process PLAY request      
            elif requestType == self.PLAY:
                if self.state == self.READY:
                    print("PROCESSING PLAY\n")
                    self.state = self.PLAYING

                    # Create a new socket for RTP/UDP (sender socket)
                    self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                    # reply first
                    self.replyRtsp(self.OK_200, seq)

                    # Create a new thread and start sending RTP packets
                    self.clientInfo['event'] = threading.Event()
                    self.clientInfo['worker'] = threading.Thread(target=self.sendRtp)
                    self.clientInfo['worker'].start()

            # Process PAUSE request
            elif requestType == self.PAUSE:
                if self.state == self.PLAYING:
                    print("PROCESSING PAUSE\n")
                    self.state = self.READY
                    # signal the sender thread to pause/stop
                    if 'event' in self.clientInfo:
                        self.clientInfo['event'].set()
                    self.replyRtsp(self.OK_200, seq)

            # Process TEARDOWN request
            elif requestType == self.TEARDOWN:
                print("PROCESSING TEARDOWN\n")
                if 'event' in self.clientInfo:
                    self.clientInfo['event'].set()
                self.replyRtsp(self.OK_200, seq)

                # Close the RTP socket if exists
                try:
                    if 'rtpSocket' in self.clientInfo:
                        self.clientInfo['rtpSocket'].close()
                except Exception:
                    pass
        except Exception:
            traceback.print_exc(file=sys.stdout)

    def sendRtp(self):
        """Send RTP packets over UDP with fragmentation support."""
        # get video stream
        videoStream = self.clientInfo.get('videoStream', None)
        if videoStream is None:
            return

        while True:
            # wait small amount or until event set
            # using wait with timeout yields False unless event set
            self.clientInfo['event'].wait(0.01)

            # Stop sending if request is PAUSE or TEARDOWN
            if self.clientInfo['event'].isSet():
                break

            data = videoStream.nextFrame()

            if data:
                # frameNumber (incremental per frame) - may be used as timestamp or for logging
                frameNumber = videoStream.frameNbr()
                try:
                    address = self.clientInfo['rtspSocket'][1][0]
                    port = int(self.clientInfo.get('rtpPort', 0))

                    # timestamp for this frame (can be same for all fragments of this frame)
                    current_timestamp = int(time.time())

                    data_len = len(data)
                    offset = 0

                    # Fragmentation loop: cut payload into MAX_RTP_PAYLOAD-sized chunks
                    while offset < data_len:
                        chunk = data[offset: offset + MAX_RTP_PAYLOAD]
                        offset += MAX_RTP_PAYLOAD

                        # Marker = 1 for last fragment of this frame
                        if offset >= data_len:
                            marker = 1
                        else:
                            marker = 0

                        # increase global RTP sequence for each fragment
                        # ensure an integer sequence number
                        self.clientInfo['rtpSeq'] = int(self.clientInfo.get('rtpSeq', 0)) + 1
                        seqnum = self.clientInfo['rtpSeq']

                        # Create RTP packet with current seqnum and timestamp
                        packet = self.makeRtp(chunk, seqnum, marker, current_timestamp)

                        # send packet
                        self.clientInfo['rtpSocket'].sendto(packet, (address, port))

                except Exception:
                    print("Connection Error while sending RTP")
                    traceback.print_exc(file=sys.stdout)
                    break

    def makeRtp(self, payload, seqnum, marker, timestamp):
        """RTP-packetize the video data.

        We pass seqnum (per-fragment sequence number), marker (0/1), and timestamp.
        """
        version = 2
        padding = 0
        extension = 0
        cc = 0
        pt = 26  # MJPEG
        ssrc = 0

        rtpPacket = RtpPacket()
        # Expect RtpPacket.encode signature to accept: (version,padding,extension,cc,seqnum,marker,pt,ssrc,payload,timestamp)
        rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload, timestamp)
        return rtpPacket.getPacket()

    def replyRtsp(self, code, seq):
        """Send RTSP reply to the client.

        Client.parseRtspReply expects three lines:
          RTSP/1.0 <statusCode> <msg>\nCSeq: <n>\nSession: <id>
        """
        connSocket = self.clientInfo['rtspSocket'][0]
        if code == self.OK_200:
            reply = 'RTSP/1.0 200 OK\nCSeq: ' + str(seq) + '\nSession: ' + str(self.clientInfo.get('session', 0))
            try:
                connSocket.send(reply.encode())
            except Exception:
                traceback.print_exc(file=sys.stdout)

        elif code == self.FILE_NOT_FOUND_404:
            print("404 NOT FOUND")
            # still send a reply with 404 so client doesn't hang
            try:
                reply = 'RTSP/1.0 404 NOT FOUND\nCSeq: ' + str(seq) + '\nSession: ' + str(
                    self.clientInfo.get('session', 0))
                connSocket.send(reply.encode())
            except Exception:
                pass
        elif code == self.CON_ERR_500:
            print("500 CONNECTION ERROR")
            try:
                reply = 'RTSP/1.0 500 SERVER ERROR\nCSeq: ' + str(seq) + '\nSession: ' + str(
                    self.clientInfo.get('session', 0))
                connSocket.send(reply.encode())
            except Exception:
                pass