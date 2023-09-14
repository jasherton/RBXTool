import lz4.block
import sys
import re
import random

#http://dom.rojo.space/binary.html#file-structure

class BinaryStream:
    def __init__(self,binary):
        self.stream = binary
        self.idx = 0

    def ReadU32LE(self):
        val = int.from_bytes(self.stream[self.idx:self.idx+4],"little")
        self.idx += 4
        return val

    def ReadI32LE(self,interleaving=0):
        if interleaving != 0:
            val = int.from_bytes(
            self.stream[self.idx:self.idx+1] + self.stream[self.idx+interleaving:self.idx+interleaving+1] + self.stream[self.idx+interleaving*2:self.idx+interleaving*2+1] + self.stream[self.idx+interleaving*3:self.idx+interleaving*3+1],
            "little",
            signed=True)
            self.idx += 1
        else:
            val = int.from_bytes(self.stream[self.idx:self.idx+4],"little",signed=True)
            self.idx += 4
        return val
    
    def ReadU8(self):
        val = int.from_bytes(self.stream[self.idx:self.idx+1],"little")
        self.idx += 1
        return val
    
    def ReadString(self,length):
        strn = self.stream[self.idx:self.idx+length]
        self.idx += length
        return strn
    
    def ReadStringTerm(self):
        strn = b""
        while True:
            byte = self.stream[self.idx:self.idx+1]
            self.idx += 1
            if byte == b"\x00":
                break
            strn += byte
        return strn
        
    def ReadStringRBX(self):
        length = self.ReadU32LE()
        return self.ReadString(length)
    
#bytearray is way faster than bytestring (almost instantaneous)
class BinaryWriter:
    def __init__(self):
        self.stream = bytearray()
    
    def WriteU32LE(self,number):
        self.stream += number.to_bytes(4,byteorder="little")
    
    def WriteU8(self,number):
        self.stream += number.to_bytes(1,byteorder="little")
        
    def WriteStringUTF8(self,string):
        bstring = type(string) == bytes and string or string.encode("utf-8","ignore")
        self.stream += bstring
        
    def WriteStringRBX(self,string):
        bstring = type(string) == bytes and string or string.encode("utf-8","ignore")
        self.WriteU32LE(len(bstring))
        self.stream += bstring
    
    def WriteBytes(self,data):
        self.stream += data

def ReadChunk(streamObj):
    chunkType = streamObj.ReadString(4)
    chunkCompLen = streamObj.ReadU32LE()
    chunkLen = streamObj.ReadU32LE()
    chunkReserved = streamObj.ReadU32LE()
    if chunkReserved != 0:
        raise Exception("bad chunk")
    chunkData = b""
    compressedBlock = b""
    if chunkCompLen != 0:
        compressedBlock = streamObj.ReadString(chunkCompLen)
        if compressedBlock[0:4] == b"\x28\xb5\x2f\xfd":
            raise Exception("cannot read ZSTD compressed chunk")
        chunkData = lz4.block.decompress(compressedBlock,uncompressed_size=chunkLen)
    else:
        chunkData = streamObj.ReadString(chunkLen)
    return [chunkType,chunkData,chunkCompLen != 0,compressedBlock]
    
def DecodeMeta(data):
    pass

def DecodeSSTR(data):
    stream = BinaryStream(data)
    version = stream.ReadU32LE()
    count = stream.ReadU32LE()
    strings = []
    for x in range(count):
        MD5Hash = stream.ReadString(16)
        string = stream.ReadStringRBX()
        strings.append(string)
    return strings

def DecodeInst(data):
    stream = BinaryStream(data)
    classID = stream.ReadU32LE()
    ClassName = stream.ReadStringRBX()
    objectformat = stream.ReadU8()
    numinstances = stream.ReadU32LE()
    
    value = 0
    referents = []
    for x in range(numinstances):
        value += stream.ReadI32LE(interleaving=numinstances)
        referents.append(value)
    
    markers = []
    if objectformat == 1:
        for x in range(numinstances):
            markers.append(stream.ReadU8())
    
    return [classID,ClassName,referents,markers]

def DecodeProp(data,place):
    stream = BinaryStream(data)
    classID = stream.ReadU32LE()
    propertyName = stream.ReadStringRBX()
    typeID = stream.ReadU8()
    
    #malformed PROP chunk (not sure why this happens)
    if len(propertyName) == 0:
        return None
    
    numValues = len(place.INSTDict[classID][2])
    values = []
    
    if typeID == 0x01:
        for x in range(numValues):
            values.append(stream.ReadStringRBX().decode("utf-8","ignore"))
    
    return [classID,propertyName,values]

PropertyTypeLUT = {str:0x01}
def EncodeProp(data):
    writer = BinaryWriter()
    writer.WriteU32LE(data[0])
    writer.WriteStringRBX(data[1])
    
    vtype = type(data[2][0])
    if not vtype in PropertyTypeLUT:
        raise Exception("Method not implemented for PropertyType "+str(vtype))
    typeID = PropertyTypeLUT[vtype]
    
    writer.WriteU8(typeID)
    
    if typeID == 0x01:
        for string in data[2]:
            writer.WriteStringRBX(string)
    
    return writer.stream

class RobloxPlace:
    def __init__(self,filePath=None,data=None):
        if not filePath and not data:
            raise Exception("No Binary Data Provided")
            
        if not data:
            f = open(filePath,"rb")
            data = f.read()
            f.close()
        
        if data[0:8] != b"<roblox!":
            raise Exception("Invalid Place Format")
        
        stream = BinaryStream(data)
        
        #roblox header
        self.Header = stream.ReadString(32)
        
        #chunks written in order
        ChunkArray = []
        
        #indices to chunk types in order
        PROPChunks = []
        
        #decoded INST chunks for PROP manipulation
        INSTDict = {}
        
        #chunk loop
        while stream.idx < len(stream.stream):
            chunk = ReadChunk(stream)
            ChunkArray.append(chunk)
            if chunk[0] == b"PROP":
                PROPChunks.append(len(ChunkArray))
            elif chunk[0] == b"INST":
                data = DecodeInst(chunk[1])
                INSTDict[data[0]] = data
                
            #if chunk[0] == b"META":
            #    DecodeMeta(chunk[1])
            #elif chunk[0] == b"SSTR":
            #    strings = DecodeSSTR(chunk[1])
            #    SharedStringList.append(strings)
            #elif chunk[0] == b"INST":
            #    DecodeInst(chunk[1],stream.idx)
            #elif chunk[0] == b"PROP":
            #    classID,value = DecodeProp(chunk[1])
            #    if type(value) == str:
            #        StringPropertyList.append(value)
            #elif chunk[0] == b"END\x00":
            #   break
            
        self.stream = stream
        self.ChunkArray = ChunkArray
        self.PROPChunks = PROPChunks
        self.INSTDict = INSTDict
        
    def GetAssets(self,propertyNames=None):
        """Return all asset ids found in order"""
        assets = []
        
        for idx in self.PROPChunks:
            chunk = self.ChunkArray[idx]
            data = DecodeProp(chunk[1],self)
            if not data:
                continue
            if propertyNames and not data[1].decode("utf-8","ignore") in propertyNames:
                continue
            for value in data[2]:
                if type(value) == str:
                    matches = re.findall(r"(http://www.roblox.com/asset\?id\=|http://www.roblox.com/asset/\?id\=|https://www.roblox.com/asset/\?id\=|rbxassetid://)(\d+)",value)
                    if len(matches) != 0:
                        for x in matches:
                            assets.append(x[1])
        
        return set(assets)
    
    def ReplaceAssets(self,replacements):
        """Replace asset ids returned from GetAssets"""
        IDLUT = {}
        for pair in replacements:
            IDLUT[pair[0]] = pair[1]
        
        for idx in self.PROPChunks:
            chunk = self.ChunkArray[idx]
            data = DecodeProp(chunk[1],self)
            if not data:
                continue
            changed = False
            vidx = 0
            for value in data[2]:
                if type(value) == str:
                    matches = re.findall(r"(http://www.roblox.com/asset\?id\=|http://www.roblox.com/asset/\?id\=|https://www.roblox.com/asset/\?id\=|rbxassetid://)(\d+)",value)
                    if len(matches) != 0:
                        for x in matches:
                            assetID = x[1]
                            if assetID in IDLUT:
                                changed = True
                                data[2][vidx] = data[2][vidx].replace("".join(x),"rbxassetid://"+IDLUT[assetID])
                vidx += 1
            if changed:
                ndata = EncodeProp(data)
                chunk[1] = ndata
                chunk[3] = None
    
    def RandomizeAssets(self,assets):
        """Replace all assets with random choices from the provided list"""
        """Every type of asset will be replaced regardless of ClassName"""
        for idx in self.PROPChunks:
            chunk = self.ChunkArray[idx]
            data = DecodeProp(chunk[1],self)
            if not data:
                continue
            changed = False
            vidx = 0
            for value in data[2]:
                if type(value) == str:
                    matches = re.findall(r"(http://www.roblox.com/asset\?id\=|http://www.roblox.com/asset/\?id\=|https://www.roblox.com/asset/\?id\=|rbxassetid://)(\d+)",value)
                    if len(matches) != 0:
                        for x in matches:
                            changed = True
                            data[2][vidx] = data[2][vidx].replace("".join(x),"rbxassetid://"+assets[random.randint(0,len(assets)-1)])
                vidx += 1
            if changed:
                ndata = EncodeProp(data)
                chunk[1] = ndata
                chunk[3] = None
    
    def Save(self,filePath=None):
        """Save changes to new file"""
        writer = BinaryWriter()
        writer.WriteBytes(self.Header)
        for chunk in self.ChunkArray:
            writer.WriteBytes(chunk[0])
            if chunk[2]:
                compressedBlock = chunk[3] or lz4.block.compress(chunk[1],store_size=False)
                writer.WriteU32LE(len(compressedBlock))
                writer.WriteU32LE(len(chunk[1]))
                writer.WriteU32LE(0)
                writer.WriteBytes(compressedBlock)
            else:
                writer.WriteU32LE(0)
                writer.WriteU32LE(len(chunk[1]))
                writer.WriteU32LE(0)
                writer.WriteBytes(chunk[1])
        
        if filePath:
            f = open(filePath,"wb+")
            f.write(writer.stream)
            f.close()
        else:
            return writer.stream