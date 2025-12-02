from tkinter import *
import tkinter.messagebox as messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os, io

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
    SETUP_STR = 'SETUP'
    PLAY_STR = 'PLAY'
    PAUSE_STR = 'PAUSE'
    TEARDOWN_STR = 'TEARDOWN'
    INIT = 0
    READY = 1
    PLAYING = 2

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3

    RTSP_VER = "RTSP/1.0"
    TRANSPORT = "RTP/UDP"

    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.state = self.INIT
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        self.frameNbr = 0

        # Buffer để chứa các mảnh của frame đang nhận
        self.currentFrameBuffer = bytearray()
        # last received RTP sequence (per-fragment)
        self.lastRtpSeq = 0

        # playEvent used to stop listen thread on pause/teardown
        self.playEvent = None

    def createWidgets(self):
        """Build GUI."""
        self.setup = Button(self.master, width=20, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=1, column=0, padx=2, pady=2)

        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=1, padx=2, pady=2)

        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=2, padx=2, pady=2)

        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] =  self.exitClient
        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

    def setupMovie(self):
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        self.sendRtspRequest(self.TEARDOWN)
        # Ensure RTP socket is closed
        try:
            if hasattr(self, 'rtpSocket'):
                try:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.rtpSocket.close()
        except Exception:
            pass

        self.master.destroy()
        try:
            os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
        except OSError:
            pass

    def pauseMovie(self):
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)

    def playMovie(self):
        if self.state == self.READY:
            # start listening thread
            self.playEvent = threading.Event()
            self.playEvent.clear()
            threading.Thread(target=self.listenRtp, daemon=True).start()
            self.sendRtspRequest(self.PLAY)

    def listenRtp(self):
        """Listen for RTP packets and assemble fragments into complete JPEG frames.

        Important points:
        - Server sends fragmentation; marker bit (M) set to 1 for last fragment of a frame.
        - Server uses per-fragment increasing sequence numbers.
        - We accept fragments with seq > lastRtpSeq to avoid re-processing duplicates.
        """
        while True:
            try:
                data = self.rtpSocket.recv(65535)
                if not data:
                    continue

                # Decode RTP packet
                rtpPacket = RtpPacket()
                rtpPacket.decode(data)

                currSeq = rtpPacket.seqNum()

                # Accept only newer fragments to avoid duplicates/reorders
                if currSeq <= self.lastRtpSeq:
                    # duplicate or old packet -> discard
                    continue

                self.lastRtpSeq = currSeq

                payload = rtpPacket.getPayload()

                # Append to current frame buffer
                self.currentFrameBuffer.extend(payload)

                # Determine marker bit from raw packet (byte 1: flags, marker is MSB)
                is_last_packet = (data[1] >> 7) & 1

                if is_last_packet:
                    # Completed a frame: decode from bytes (no intermediate file required)
                    frame_bytes = bytes(self.currentFrameBuffer)
                    # Reset buffer for next frame
                    self.currentFrameBuffer = bytearray()

                    # Update GUI (use BytesIO to avoid file corruption issues)
                    self.updateMovieFromBytes(frame_bytes)

            except socket.timeout:
                # periodic timeout to allow checking playEvent/teardown
                if self.playEvent and self.playEvent.is_set():
                    break
                if getattr(self, 'teardownAcked', 0) == 1:
                    break
                continue
            except Exception:
                # Stop listening upon requesting PAUSE or TEARDOWN
                traceback.print_exc(file=sys.stdout)
                if self.playEvent and self.playEvent.is_set():
                    break
                if getattr(self, 'teardownAcked', 0) == 1:
                    try:
                        self.rtpSocket.close()
                    except Exception:
                        pass
                    break

    def writeFrame(self, data):
        """Maintain backward compatibility: write frame to cache file and return filename."""
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        with open(cachename, "wb") as f:
            f.write(data)
        return cachename

    def updateMovie(self, imageFile):
        """Old code kept for compatibility: load image from filename."""
        try:
            photo = ImageTk.PhotoImage(Image.open(imageFile))
            self.label.configure(image = photo, height=288)
            self.label.image = photo
        except Exception as e:
            print(f"Frame error (file): {e}")

    def updateMovieFromBytes(self, jpeg_bytes):
        """Preferred: update GUI directly from JPEG bytes without writing to disk."""
        try:
            image = Image.open(io.BytesIO(jpeg_bytes))
            photo = ImageTk.PhotoImage(image)
            self.label.configure(image=photo, height=288)
            self.label.image = photo
        except Exception as e:
            # If decoding fails, optionally write to disk for debugging
            print(f"Frame error (bytes): {e}")
            try:
                fname = self.writeFrame(jpeg_bytes)
                # attempt to load from file fallback
                self.updateMovie(fname)
            except Exception:
                pass

    def connectToServer(self):
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except Exception:
            messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)

    def sendRtspRequest(self, requestCode):
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply, daemon=True).start()
            self.rtspSeq+=1
            request = "%s %s %s" % (self.SETUP_STR,self.fileName,self.RTSP_VER)
            request+="\nCSeq: %d" % self.rtspSeq
            request+="\nTransport: %s; client_port= %d" % (self.TRANSPORT,self.rtpPort)
            self.requestSent = self.SETUP
        elif requestCode == self.PLAY and self.state == self.READY:
            self.rtspSeq+=1
            request = "%s %s %s" % (self.PLAY_STR,self.fileName,self.RTSP_VER)
            request+="\nCSeq: %d" % self.rtspSeq
            request+="\nSession: %d"%self.sessionId
            self.requestSent = self.PLAY
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            self.rtspSeq+=1
            request = "%s %s %s" % (self.PAUSE_STR,self.fileName,self.RTSP_VER)
            request+="\nCSeq: %d" % self.rtspSeq
            request+="\nSession: %d"%self.sessionId
            self.requestSent = self.PAUSE
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            self.rtspSeq+=1
            request = "%s %s %s" % (self.TEARDOWN_STR, self.fileName, self.RTSP_VER)
            request+="\nCSeq: %d" % self.rtspSeq
            request+="\nSession: %d" % self.sessionId
            self.requestSent = self.TEARDOWN
        else:
            return

        try:
            self.rtspSocket.send(request.encode())
            print ('\nData Sent:\n' + request)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    def recvRtspReply(self):
        while True:
            try:
                reply = self.rtspSocket.recv(1024)
                if reply:
                    self.parseRtspReply(reply)
                if self.requestSent == self.TEARDOWN:
                    try:
                        self.rtspSocket.shutdown(socket.SHUT_RDWR)
                    except Exception:
                        pass
                    self.rtspSocket.close()
                    break
            except Exception:
                traceback.print_exc(file=sys.stdout)
                break

    def parseRtspReply(self, data):
        try:
            lines = data.decode().split('\n')
            seqNum = int(lines[1].split(' ')[1])
            if seqNum == self.rtspSeq:
                session = int(lines[2].split(' ')[1])
                if self.sessionId == 0:
                    self.sessionId = session
                if self.sessionId == session:
                    if int(lines[0].split(' ')[1]) == 200:
                        if self.requestSent == self.SETUP:
                            self.state = self.READY
                            self.openRtpPort()
                        elif self.requestSent == self.PLAY:
                            self.state = self.PLAYING
                        elif self.requestSent == self.PAUSE:
                            self.state = self.READY
                            if self.playEvent:
                                self.playEvent.set()
                        elif self.requestSent == self.TEARDOWN:
                            self.state = self.INIT
                            self.teardownAcked = 1
        except Exception:
            traceback.print_exc(file=sys.stdout)

    def openRtpPort(self):
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpSocket.settimeout(0.5)
        try:
            self.state=self.READY
            self.rtpSocket.bind(('',self.rtpPort))
        except Exception:
            messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

    def handler(self):
        self.pauseMovie()
        if messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:
            self.playMovie()
