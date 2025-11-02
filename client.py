import tkinter
from tkinter import *
import socket
import sys,threading

class Client:
    INIT=0
    READY=1
    PLAYING=2
    state=INIT

    SETUP=0
    PLAY=1
    PAUSE=2
    TEARDOWN=3

    def __init__(self,master,serverAddr,serverPort,rtpPort,fileName):
        self.master=master
        self.serverAddr = serverAddr
        self.serverPort = int(serverPort)
        self.rtpPort=int(rtpPort)
        self.fileName=fileName
        self.rtspSeq=0
        self.sessionId=-1
        self.requestSent=-1
        self.createConsole()


    def openRtspSocket(self):
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr,self.serverPort))
        except:
            tkinter.messagebox.showwarning('Unable to connect to server','Unable to connect to server' %self.serverAddr)


    def openRtpSocket(self):
            self.rtpSocket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            self.rtpSocket.settimeout(0.5)
            try:
                self.rtpSocket.bind(("", self.rtpPort))
            except:
                tkinter.messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)


    def sendRtspRequest(self,command):

        self.rtspSeq+=1
        if (command == self.SETUP):
            self.openRtspSocket()
            self.openRtpSocket()
            # threading.Thread(target=self.recvServerReply()).start()

            request = f"SETUP rtsp://{self.serverAddr}:{self.serverPort}/{self.fileName} RTSP/1.0\n"
            request += f"CSeq: {self.rtspSeq}\n"
            request += f"Transport: RTP/AVP;unicast;client_port={self.rtpPort}"

            self.label.config(text="Trạng thái: Đang kết nối server...")
            self.state=self.READY
            self.requestSent = self.SETUP
        if (command == self.PLAY):

            request = f"PLAY rtsp://{self.serverAddr}:{self.serverPort}/{self.fileName} RTSP/1.0\n"
            request += f"CSeq: {self.rtspSeq}\n"
            request += f"Session: {self.sessionId}"

            self.label.config(text="Trạng thái: Đang chạy video...")
            self.state=self.PLAYING
            self.requestSent = self.PLAY
        if (command == self.PAUSE):

            request = f"PAUSE rtsp://{self.serverAddr}:{self.serverPort}/{self.fileName} RTSP/1.0\n"
            request += f"CSeq: {self.rtspSeq}\n"
            request += f"Session: {self.sessionId}"

            self.label.config(text="Trạng thái: Đang dừng video...")
            self.state=self.READY
            self.requestSent = self.PAUSE
        if (command == self.TEARDOWN):

            request = f"TEARDOWN rtsp://{self.serverAddr}:{self.serverPort}/{self.fileName} RTSP/1.0\n"
            request += f"CSeq: {self.rtspSeq}\n"
            request += f"Session: {self.sessionId}"

            self.label.config(text="Trạng thái: Đang ngắt kết nối server...")
            self.state=self.TEARDOWN
            self.requestSent=self.TEARDOWN

        self.rtspSocket.send(request.encode("utf-8"))

    # def recvData(self):
    #
    #     while (True):
    #         try:
    #             data = self.rtpSocket.recv(2048)
    #             # TODO:
    #         except socket.timeout:
    #             pass
    #
    # def recvServerReply(self):
    #
    #     while (True):
    #         try:
    #             reply=self.rtspSocket.recv(1024)

    def setUpMovie(self):
        if (self.state == self.INIT):
            self.sendRtspRequest(self.SETUP)

    def playMovie(self):
        if (self.state == self.READY):
            # threading.Thread(target=self.reveiveData).start()
            self.playMovie=threading.Event()
            self.playMovie.clear()
            self.sendRtspRequest(self.PLAY)

    def pauseMovie(self):
        if (self.state == self.PLAYING):
            self.sendRtspRequest(self.PAUSE)

    def tearDown(self):
         if (self.state==self.READY):
             self.sendRtspRequest(self.TEARDOWN)

    def createConsole(self):
        self.master.title("Video Streaming")
        self.setupButton()
        self.playButton()
        self.pauseButton()
        self.teardownButton()
        self.screen()


    def setupButton(self):
        self.setup=Button(self.master,width=40,padx=5,pady=5)
        self.setup["text"]="Set Up"
        self.setup["command"]=self.setUpMovie
        self.setup.grid(row=1,column=0,padx=5,pady=5)

    def playButton(self):
        self.play=Button(self.master,width=40,padx=5,pady=5)
        self.play["text"]="Play"
        self.play["command"]=self.playMovie
        self.play.grid(row=1,column=1,padx=5,pady=5)

    def pauseButton(self):
        self.pause=Button(self.master,width=40,padx=5,pady=5)
        self.pause["text"]="Pause"
        self.pause["command"]=self.pauseMovie
        self.pause.grid(row=1,column=2,padx=5,pady=5)

    def teardownButton(self):
        self.teardown=Button(self.master,width=40,padx=5,pady=5)
        self.teardown["text"]="Tear down"
        self.teardown["command"]=self.tearDown
        self.teardown.grid(row=1,column=3,padx=5,pady=5)

    def screen(self):
        self.label=Label(self.master,height=20)
        self.label.grid(row=0,column=0, columnspan=4, sticky=W + E + N + S,padx=5,pady=5)



if __name__ == "__main__":
    try:
        serverAddr,serverPort,rtpPort,fileName=sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4]
    except IndexError:
        print("Usage: python Server.py [ServerAddr]:[ServerPort]")
        sys.exit(1)
    root = Tk()
    client=Client(root,serverAddr,serverPort,rtpPort,fileName)
    root.mainloop()
