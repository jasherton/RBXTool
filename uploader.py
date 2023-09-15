from pathlib import Path
from PIL import Image
from PIL import ImageChops
import requests
import urllib3
import json
import time
import re
import os
import io
import glob

apiKey = "APIKEYHERE"
userId = "USERIDHERE"

writeAPI = "https://apis.roblox.com/assets/v1/assets"
readAPI = "https://apis.roblox.com/assets/v1/{0}"

universeAPI = "https://apis.roblox.com/universes/v1/{0}/places/{1}/versions?versionType=Published"

assetURL = "https://assetdelivery.roblox.com/v1/asset/?id={0}"

assetInfoURL = "https://assetdelivery.roblox.com/v2/asset/?id={0}"

uploadURL = "https://data.roblox.com/Data/Upload.ashx?assetid={0}"

inventoryURL = "https://inventory.roblox.com/v2/users/{0}/inventory/{1}?limit=10&sortOrder=Asc"

universeURL = "https://apis.roblox.com/universes/v1/places/{0}/universe"

audioURL = "https://apis.roblox.com/asset-permissions-api/v1/assets/{0}/permissions"

iconURL = "https://thumbnails.roblox.com/v1/assets?assetIds={0}&returnPolicy=PlaceHolder&size=30x30&format=Png&isCircular=false"

session = requests.Session()

session_public = requests.Session()

DecalRequest = '''{
"assetType":"Decal",
"displayName":"Image",
"description":"Upload",
"creationContext":{ "creator":{"userId":"'''+userId+'''"} }
}'''

AudioRequest = '''{
"assetType":"Audio",
"displayName":"Sound",
"description":"Upload",
"creationContext":{ "creator":{"userId":"'''+userId+'''"} }
}'''

CloudKeyCreatorURL = "https://apis.roblox.com/cloud-authentication/v1/apiKey"
CloudKeyCreatorJSON = {"cloudAuthUserConfiguredProperties":{"name":"dmaupload","description":"upload","isEnabled":True,"allowedCidrs":["0.0.0.0/0"],"scopes":[{"scopeType":"asset","targetParts":["U"],"operations":["read","write"]}]}}


def PermitAudio(assetID,PlaceID):
    res = session.get(universeURL.format(PlaceID))
    if res.status_code != 200:
        print("Permission Failed ({})".format(assetID))
        return
    content = json.loads(res.content.decode("utf-8"))
    universeId = str(content["universeId"])
    data = {"requests":[{"subjectType":"Universe","subjectId":universeId,"action":"Use"}]}
    nurl = audioURL.format(assetID)
    res = session.patch(nurl,json=data)
    if res.status_code == 403:
        if not "x-csrf-token" in res.headers:
            print("Permission Failed ({})".format(assetID))
            return
        session.headers.update({"x-csrf-token":res.headers["x-csrf-token"]})
    res = session.patch(nurl,json=data)
    if res.status_code != 200:
        print("Permission Failed ({})".format(assetID))
    else:
        print("Permission Granted ({})".format(assetID))

AssetRateLimitSeconds = 60
AssetRateLimitCount = 240
AssetRateClock = 0
AssetRateCount = 0

AssetIconBulkCount = 30

def CheckAssets(assetList,OutFile=None):
    badArray = []
    
    res = session.get(iconURL.format("145278994"))
    if res.status_code != 200:
        print("Operation Failed")
        return
    content = json.loads(res.content.decode("utf-8"))
    
    res = session.get(content["data"][0]["imageUrl"])
    if res.status_code != 200:
        print("Operation Failed")
        return
    BaseArchivedImage = Image.open(io.BytesIO(res.content)).convert("RGBA").convert("RGB")
    
    failedAssets = []
    
    def loop(loopList):
        global AssetRateClock
        global AssetRateCount
        nonlocal failedAssets
        nonlocal badArray
        listLength = len(loopList)
        listSegments = listLength//AssetIconBulkCount
        listRemainder = listLength%AssetIconBulkCount
        
        for x in range(listSegments+1):
            bulkArray = None
            if x < listSegments:
                bulkArray = loopList[x*AssetIconBulkCount : (x+1)*AssetIconBulkCount]
            else:
                bulkArray = loopList[x*AssetIconBulkCount : x*AssetIconBulkCount + listRemainder]
            
            ClockDiff = time.perf_counter()-AssetRateClock
            if AssetRateCount == AssetRateLimitCount-1 and ClockDiff < AssetRateLimitSeconds:
                print("Rate Limit Reached. Waiting...")
                time.sleep((AssetRateLimitSeconds-ClockDiff)+1)
                AssetRateCount = 0
            
            if AssetRateCount == 0:
                AssetRateClock = time.perf_counter()
            AssetRateCount += len(bulkArray)
            
            res = session.get(iconURL.format(",".join(bulkArray)))
            if res.status_code != 200:
                print("Operation Failed")
                return
            content = json.loads(res.content.decode("utf-8"))
            for info in content["data"]:
                print("Checking {}".format(info["targetId"]))
                res = session.get(info["imageUrl"])
                if res.status_code != 200:
                    failedAssets.append(str(info["targetId"]))
                    continue
                AssetImage = Image.open(io.BytesIO(res.content)).convert("RGBA").convert("RGB")
                if not ImageChops.difference(BaseArchivedImage,AssetImage).getbbox():
                    badArray.append(str(info["targetId"]))
    
    loop(assetList)
    
    #second pass for failed thumbnails
    if len(failedAssets) > 0:
        loop(failedAssets)
    
    if len(badArray) > 0 and OutFile:
        exists = Path(OutFile).exists()
        f = open(OutFile,"a+")
        if exists:
            f.write("\n")
        f.write("\n".join(badArray))
        f.close()
    
    return badArray

def VerifyAssets(assetList,PlaceID=None,Public=False):
    global AssetRateClock
    global AssetRateCount
    
    if Public:
        session_public.headers.update({"Roblox-Place-Id":PlaceID})
        session_public.headers.update({"User-Agent":"Roblox/WinInet"})
        
        for asset in assetList:
            ClockDiff = time.perf_counter()-AssetRateClock
            if AssetRateCount == AssetRateLimitCount-1 and ClockDiff < AssetRateLimitSeconds:
                print("Rate Limit Reached. Waiting...")
                time.sleep((AssetRateLimitSeconds-ClockDiff)+1)
                AssetRateCount = 0
            
            if AssetRateCount == 0:
                AssetRateClock = time.perf_counter()
            AssetRateCount += 1
            
            res = session_public.get(assetInfoURL.format(asset))
            if res.status_code != 200:
                print("Not Allowed ({})".format(asset))
                continue
        
        session_public.headers.update({"Roblox-Place-Id":None})
        session_public.headers.update({"User-Agent":None})
    else:
        session.headers.update({"Roblox-Place-Id":PlaceID})
        session.headers.update({"User-Agent":"Roblox/WinInet"})
        
        for asset in assetList:
            ClockDiff = time.perf_counter()-AssetRateClock
            if AssetRateCount == AssetRateLimitCount-1 and ClockDiff < AssetRateLimitSeconds:
                print("Rate Limit Reached. Waiting...")
                time.sleep((AssetRateLimitSeconds-ClockDiff)+1)
                AssetRateCount = 0
            
            if AssetRateCount == 0:
                AssetRateClock = time.perf_counter()
            AssetRateCount += 1
            
            res = session.get(assetInfoURL.format(asset))
            if res.status_code != 200:
                print("Not Allowed ({})".format(asset))
                continue
        
        session.headers.update({"Roblox-Place-Id":None})
        session.headers.update({"User-Agent":None})

def DownloadAssets(assetList,PlaceID=None,OutDir=None):
    global AssetRateClock
    global AssetRateCount
    session.headers.update({"Roblox-Place-Id":PlaceID})
    session.headers.update({"User-Agent":"Roblox/WinInet"})
    dataArray = []
    for asset in assetList:
        ClockDiff = time.perf_counter()-AssetRateClock
        if AssetRateCount == AssetRateLimitCount-1 and ClockDiff < AssetRateLimitSeconds:
            print("Rate Limit Reached. Waiting...")
            time.sleep((AssetRateLimitSeconds-ClockDiff)+1)
            AssetRateCount = 0
        
        if AssetRateCount == 0:
            AssetRateClock = time.perf_counter()
        AssetRateCount += 1
        
        res = session.get(assetInfoURL.format(asset))
        if res.status_code != 200:
            print("Invalid ID ({})".format(asset))
            continue
        
        print("Downloading {}".format(asset))
        
        content = json.loads(res.content.decode("utf-8"))
        assetTypeId = content["assetTypeId"]
        if assetTypeId == 1:
            res = session.get(content["locations"][0]["location"])
            ext = ".png"
            if res.content[0:4] == b"\xFF\xD8\xFF\xE0":
                ext = ".jpg"
            dataArray.append((asset+ext,res.content))
            if OutDir:
                f = open(OutDir+asset+ext,"wb+")
                f.write(res.content)
                f.close()
        elif assetTypeId == 3:
            res = session.get(content["locations"][0]["location"])
            ext = ".mp3"
            if res.content[0:4] == b"\x4F\x67\x67\x53":
                ext = ".ogg"
            dataArray.append((asset+ext,res.content))
            if OutDir:
                f = open(OutDir+asset+ext,"wb+")
                f.write(res.content)
                f.close()
    
    session.headers.update({"Roblox-Place-Id":None})
    session.headers.update({"User-Agent":None})
    return dataArray

def DownloadPlace(PlaceID,NoFile=False):
    res = session.get(assetInfoURL.format(PlaceID))
    if res.status_code != 200:
        print("Invalid ID")
        return
    content = json.loads(res.content.decode("utf-8"))
    if content["assetTypeId"] != 9:
        print("Invalid ID")
        return
    res = session.get(content["locations"][0]["location"])
    if NoFile:
        return res.content
    fname = res.content[0:8] == b"<roblox!" and PlaceID+".rbxl" or PlaceID+".rbxlx"
    f = open(fname,"wb+")
    f.write(res.content)
    f.close()
    print("Downloaded Successfully! ({0})".format(fname))

def GetUser(ROBLOSECURITY):
    session.cookies.update({".ROBLOSECURITY":ROBLOSECURITY})
    res = session.get("https://users.roblox.com/v1/users/authenticated")
    if res.status_code != 200:
        print("Invalid Token")
        return
    content = json.loads(res.content.decode("utf-8"))
    return content

def ReadKey(filePath):
    f = open(filePath,"r")
    lines = f.readlines()
    f.close()
    data = []
    for line in lines:
        rline = line.rstrip()
        if len(rline) == 0:
            continue
        data.append(rline)
    return data

def MakeKey(ROBLOSECURITY):
    global apiKey
    global userId
    global DecalRequest
    global AudioRequest
    
    if not Path("keys").exists():
        os.mkdir("keys")
    
    secFilePath = "keys/"+ROBLOSECURITY[116:116+32]+".txt"
    if Path(secFilePath).exists():
        data = ReadKey(secFilePath)
        userId = data[1]
        apiKey = data[2]
    else:
        session.cookies.update({".ROBLOSECURITY":ROBLOSECURITY})
        res = session.get("https://users.roblox.com/v1/users/authenticated")
        if res.status_code != 200:
            print("Invalid Token")
            return
        content = json.loads(res.content.decode("utf-8"))
        userId = str(content["id"])
        res = session.post(CloudKeyCreatorURL)
        if res.status_code == 403:
            session.headers.update({"x-csrf-token":res.headers["x-csrf-token"]})
        res = session.post(CloudKeyCreatorURL,json=CloudKeyCreatorJSON)
        if res.status_code != 200:
            print("Failed To Create API Key")
            return
        content = json.loads(res.content.decode("utf-8"))
        apiKey = content["apikeySecret"]
        f = open(secFilePath,"w+")
        f.write(ROBLOSECURITY+"\n"+userId+"\n"+apiKey+"\n")
        f.close()
    
    session.headers.update({"x-api-key":apiKey})
    DecalRequest = DecalRequest.replace("USERIDHERE",userId)
    AudioRequest = AudioRequest.replace("USERIDHERE",userId)
    
    return True

#publish to PlaceID
def Publish(filePath=None,PlaceID=None,PlaceData=None):
    if not PlaceID:
        res = session.get(inventoryURL.format(userId,9))
        content = json.loads(res.content.decode("utf-8"))
        PlaceID = content["data"][0]["assetId"]
    
    if not filePath and not PlaceData:
        raise Exception("No Binary Data Provided")
            
    if not PlaceData:
        f = open(filePath,"rb")
        PlaceData = f.read()
        f.close()
    
    uploadFormat = uploadURL.format(PlaceID)
    res = session.post(uploadFormat)
    
    if res.status_code == 403:
        session.headers.update({"x-csrf-token":res.headers["x-csrf-token"]})
    res = session.post(uploadFormat,data=PlaceData,headers={"User-Agent":"Roblox/WinInet","Accept":"application/json","Content-Type":"application/octet-stream"})
    if res.status_code != 200:
        print("Failed To Publish")
    else:
        print("Published Successfully")
    
def GetMimeType(filePath):
    ext = Path(filePath).suffix
    if ext == ".ogg":
        return "audio/ogg"
    elif ext == ".mp3":
        return "audio/mpeg"
    return urllib3.fields.guess_content_type(filePath)

#upload decal and return operation path
def StartDecalOperation(filePath):
    fileName = Path(filePath).name
    
    formdata = {
    "request":DecalRequest,
    "fileContent":(fileName,open(filePath,"rb").read(),GetMimeType(fileName)),
    }
    
    formTuple = urllib3.encode_multipart_formdata(formdata)
    res = session.post(writeAPI,data=formTuple[0],headers={"Content-Type":formTuple[1]})
    
    #uploaded and pending
    if res.status_code == 200:
        content = json.loads(res.content.decode("utf-8"))
        objectPath = content["path"]
        return res.status_code,objectPath
    else:
        return res.status_code,res.content

#upload audio and return operation path
def StartSoundOperation(filePath):
    fileName = Path(filePath).name

    formdata = {
    "request":AudioRequest,
    "fileContent":(fileName,open(filePath,"rb").read(),GetMimeType(fileName)),
    }

    formTuple = urllib3.encode_multipart_formdata(formdata)
    res = session.post(writeAPI,data=formTuple[0],headers={"Content-Type":formTuple[1]})

    #uploaded and pending
    if res.status_code == 200:
        content = json.loads(res.content.decode("utf-8"))
        objectPath = content["path"]
        return res.status_code,objectPath
    else:
        return res.status_code,res.content

#get upload state; supply operationPath for value sanitization
def GetOperationState(operationPath=None,operationURL=None):
    if operationPath:
        operationID = False
        if len(operationPath) == 36:
            if operationPath[8:9] == "-" and operationPath[13:14] == "-" and operationPath[18:19] == "-" and operationPath[23:24] == "-":
                operationID = operationPath
            else:
                return 500,None
        elif operationPath[:11] == "operations/":
            operationID = operationPath[11:]
        else:
            return 500,None
        operationURL = readAPI.format("operations/"+operationID)
    if not operationURL:
        return 500,None
    res = session.get(operationURL)
    if res.status_code == 200:
        return res.status_code,json.loads(res.content.decode("utf-8"))
    else:
        return res.status_code,res.content

def GetOperationAssetID(operationPath):
    status,content = GetOperationState(operationPath)
    if status == 200:
        if "done" in content:
            return content["response"]["assetId"]
    return None

#upload decal and return assetId (synchronous)
def UploadDecal(filePath,maxRetry=60):
    #print("Uploading Decal \""+Path(filePath).name+"\"")
    status,operation = StartDecalOperation(filePath)
    if status == 200:
        AssetID = GetOperationAssetID(operation)
        attempts = 0
        while not AssetID:
            if attempts >= maxRetry:
                break
            time.sleep(1)
            AssetID = GetOperationAssetID(operation)
            attempts += 1
        return AssetID
    print("Upload Failed ({})".format(Path(filePath).name))
    return None

#get image id of decal or image
def DeriveImageID(assetID):
    res = session.get(assetURL.format(assetID))
    if res.status_code == 200:
        content = res.content
        if content[0:7] == b"<roblox" and content[7:9] == b"\x20\x78":
            rstr = content.decode("utf-8")
            idx = rstr.find("<url>")
            imageID = "".join(re.findall(r'\d+',rstr[idx+5:idx+5+rstr[idx+5:].find("</url>")]))
            return imageID
        else:
            return assetID
    return None

#upload audio and return assetId (synchronous)
def UploadSound(filePath,maxRetry=60):
    status,operation = StartSoundOperation(filePath)
    if status == 200:
        AssetID = GetOperationAssetID(operation)
        attempts = 0
        while not AssetID:
            if attempts >= maxRetry:
                break
            time.sleep(1)
            AssetID = GetOperationAssetID(operation)
            attempts += 1
        return AssetID
    print("Upload Failed ({})".format(Path(filePath).name))
    return None

UploadRateLimitSeconds = 60
UploadRateLimitCount = 60
UploadRateClock = 0
UploadRateCount = 0
def UploadFile(filePath):
    global UploadRateClock
    global UploadRateCount
    mimeType = GetMimeType(filePath)
    
    if mimeType == "image/jpeg" or mimeType == "image/png" or mimeType == "audio/ogg" or mimeType == "audio/mpeg":
        ClockDiff = time.perf_counter()-UploadRateClock
        if UploadRateCount == UploadRateLimitCount-1 and ClockDiff < UploadRateLimitSeconds:
            print("Rate Limit Reached. Waiting...")
            time.sleep((UploadRateLimitSeconds-ClockDiff)+1)
            UploadRateCount = 0
        
        if UploadRateCount == 0:
            UploadRateClock = time.perf_counter()
        UploadRateCount += 1
    
    if mimeType == "image/jpeg" or mimeType == "image/png":
        assetId = UploadDecal(filePath)
        imageId = None
        if assetId:
            imageId = DeriveImageID(assetId)
        return imageId
    elif mimeType == "audio/ogg" or mimeType == "audio/mpeg":
        assetId = UploadSound(filePath)
        return assetId
    else:
        print("Invalid File (" + Path(filePath).name + ")")