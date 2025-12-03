import os
import pickle
from PIL import Image


class ClientSideCaching:
    def __init__(self):
        self.buffer = {}


    def getFrame(self, frameNumber, sessionId):
        key = self.makeKey(frameNumber, sessionId)

        if key in self.buffer:
            return self.buffer[key]
        else:
            return None

    def cacheFrame(self, frameNumber, sessionId, frameData):
        key = self.makeKey(frameNumber, sessionId)

        if key in self.buffer:
            return

        else:
            print("Caching frame {}".format(frameNumber))
            self.buffer[key] = frameData


    def makeKey(self, frameNumber, sessionId):
        return (frameNumber, sessionId)


    def getCachedFrames(self, sessionId):
        return [
            frameNumber for (frameNumber, sessId) in self.buffer.keys()
            if sessId == sessionId
        ]

