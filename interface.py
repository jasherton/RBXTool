from pathlib import Path
from tkinter import Tk
from rbxl import RobloxPlace
import uploader
import os
import glob

BASEROBLOSECURITY = "_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|_"

def GetClipboard():
    wnd = Tk()
    clipboard = wnd.clipboard_get()
    wnd.destroy()
    del wnd
    return clipboard

HelpText = """
Commands List
---------------
download PlaceID
    - downloads a roblox place that you have access to

check FileName/PlaceID
    - checks for any archived assets in a place
    - and writes them to a file
    - affected by rate limiting

extract FileName/PlaceID (optional)PlaceID
    - extracts all assets from a roblox place and downloads them
    - affected by rate limiting
    - adding a PlaceID at the end allows you to
    - download sounds from copied games

up FileName/Folder
    - upload file(s) and get the new AssetID(s)
    - All AssetIDs will be written to "assets.txt" in this format:
    - "FileName (AssetID)"
    - affected by rate limiting

reup FileName PlaceID
    - publishes a file to the specified PlaceID
    - AssetIDs within the place will be replaced if found in "assets.txt"

permit PlaceID SoundID(s)/FileName
    - gives permission for any number of SoundIDs to play
    - in the supplied PlaceID
    - supplying a FileName makes it easier to modify
    - sounds in bulk

help
    - shows this list

exit
    - closes out of this program

clear
    - clears text in the console
"""

AssetCheckDict = {}
if Path("assets.txt").exists():
    f = open("assets.txt","r+")
    lines = f.readlines()
    f.close()
    for line in lines:
        if len(line) == 0:
            continue
        sep = line.split(" ")
        AssetCheckDict[sep[0]] = sep[1][1:len(sep[1])-1]

def UploadWrapper(uploadPath):
    cpath = Path(uploadPath)
    if not cpath.exists():
        print("Invalid FileName/Folder")
        return
    if cpath.is_file():
        if cpath.name == "Thumbs.db":
            return
        if cpath.stem in AssetCheckDict:
            res = input(cpath.stem + " already exists. Do you want to replace it? (Y/[N]) ").lower()
            if res != "y":
                return
        assetId = uploader.UploadFile(uploadPath)
        if assetId:
            print("Uploaded {0} ({1})".format(cpath.name,assetId))
            if cpath.stem in AssetCheckDict:
                f = open("assets.txt","r+")
                lines = f.readlines()
                f.seek(0)
                for line in lines:
                    if line.split(" ")[0] != cpath.stem:
                        f.write(line)
                    else:
                        f.write("{0} ({1})\n".format(cpath.stem,assetId))
                f.truncate()
            else:
                f = open("assets.txt","a+")
                f.write("{0} ({1})\n".format(cpath.stem,assetId))
                f.close()
            AssetCheckDict[cpath.stem] = assetId
    elif cpath.is_dir():
        files = glob.glob(str(cpath)+"/*.*")
        for file in files:
            UploadWrapper(file)

ROBLOSECURITY = None

def Main():
    global ROBLOSECURITY
    os.system("cls")
    
    keyPath = Path("keys")
    if keyPath.exists() and keyPath.is_dir():
        files = glob.glob("keys/*.txt")
        keys = []
        for file in files:
            data = uploader.ReadKey(file)
            keys.append(data)
        print("Select an Account:")
        for x in range(len(keys)):
            print("{0}. {1}".format(x+1,keys[x][1]))
        print("{0}. {1}".format(len(keys)+1,"Add Account"))
        print("{0}. {1}".format(len(keys)+2,"Exit\n"))
        inputstr = ""
        inputnum = 0
        while not inputstr.isnumeric():
            inputstr = input()
            if inputstr.isnumeric():
                inputnum = int(inputstr)-1
                if inputnum < 0 or inputnum > len(keys)+1:
                    inputstr = ""
                    print("Invalid Number")
        if inputnum == len(keys)+1:
            os.system("cls")
            return
        if inputnum < len(keys) and inputnum >= 0:
            ROBLOSECURITY = keys[inputnum][0]
    
    if not ROBLOSECURITY:
        clipboard = GetClipboard()
        if clipboard.find(BASEROBLOSECURITY) == -1:
            input("Copy your ROBLOSECURITY Cookie and press Enter to continue")
            clipboard = GetClipboard()
            while clipboard.find(BASEROBLOSECURITY) == -1:
                input("Invalid Cookie; Press Enter to try again")
                clipboard = GetClipboard()
        ROBLOSECURITY = clipboard
    
    uploader.MakeKey(ROBLOSECURITY)
    UserInfo = uploader.GetUser(ROBLOSECURITY)
    os.system("cls")
    print("Logged in as {0} ({1})".format(UserInfo["name"],UserInfo["id"]))
    print("Type help and press Enter to see a list of commands\n")
    
    while True:
        command = input()
        if len(command) == 0:
            continue
        elif command == "exit":
            os.system("cls")
            break
        elif command == "clear":
            os.system("cls")
            continue
        elif command == "help":
            print(HelpText)
            continue
        
        csplit = command.split(" ")
        if csplit[0] == "download" and len(csplit) == 2 and csplit[1].isnumeric():
            uploader.DownloadPlace(csplit[1])
        elif csplit[0] == "reup" and len(csplit) == 3 and csplit[2].isnumeric():
            if not Path(csplit[1]).exists():
                print("Invalid FileName")
                continue
            if Path("assets.txt").exists():
                place = RobloxPlace(csplit[1])
                f = open("assets.txt","r")
                lines = f.readlines()
                f.close()
                
                assets = []
                for line in lines:
                    if len(line) == 0:
                        continue
                    sep = line.split(" ")
                    assets.append((sep[0],sep[1][1:len(sep[1])-1]))
                
                place.ReplaceAssets(assets)
                data = place.Save()
                print("Replaced Assets")
                uploader.Publish(PlaceData=data,PlaceID=csplit[2])
            else:
                uploader.Publish(csplit[1],csplit[2])
        elif csplit[0] == "up" and len(csplit) == 2:
            UploadWrapper(csplit[1])
        elif csplit[0] == "check" and len(csplit) > 1:
            place = None
            outpath = Path(csplit[1]).stem+"_archived.txt"
            
            if csplit[1].isnumeric():
                data = uploader.DownloadPlace(csplit[1],NoFile=True)
                if not data:
                    continue
                place = RobloxPlace(data=data)
            else:
                cpath = Path(csplit[1])
                if not cpath.exists():
                    print("Invalid FileName")
                    continue
                place = RobloxPlace(csplit[1])
            
            sounds = place.GetAssets(["Source","SoundId"])
            images = place.GetAssets(["Source","Image","Texture","SkyboxBk","SkyboxDn","SkyboxFt","SkyboxLf","SkyboxRt","SkyboxUp"])
            
            print("Total Assets: {}".format(len(sounds)+len(images)))
            
            TotalSounds = len(sounds)
            TotalImages = len(images)
            PreCheckedImages = 0
            PreCheckedSounds = 0
            
            if Path(outpath).exists():
                f = open(outpath,"r")
                lines = f.readlines()
                f.close()
                for line in lines:
                    rline = line.rstrip()
                    
                    #this has to be separate from the remove calls due to script Source overlap for Sounds and Images
                    if rline in sounds:
                        PreCheckedSounds += 1
                    elif rline in images:
                        PreCheckedImages += 1
                        
                    if rline in sounds:
                        sounds.remove(rline)
                    if rline in images:
                        images.remove(rline)
                if len(images) == 0 and len(sounds) == 0:
                    print("Assets already checked.")
                    print("Delete or rename \"{}\" to check again.".format(outpath))
            
            print("Unchecked Images: {}".format(len(images)))
            print("Unchecked Sounds: {}\n".format(len(sounds)))
            
            if len(images) != 0 or len(sounds) != 0:
                print("Checking Assets...")
                badArray = uploader.CheckAssets(list(images | sounds),OutFile=outpath)
                if type(badArray) == None:
                    continue
                print("Finished.")
                imgCount = 0
                sndCount = 0
                for asset in badArray:
                    if asset in images:
                        imgCount += 1
                    if asset in sounds:
                        sndCount += 1
                print("\nArchived Assets: {}/{}".format(len(badArray) + PreCheckedImages + PreCheckedSounds,TotalImages+TotalSounds))
                print("Archived Images: {}/{}".format(imgCount + PreCheckedImages,TotalImages))
                print("Archived Sounds: {}/{}".format(sndCount + PreCheckedSounds,TotalSounds))
            else:
                print("No Assets")
        elif csplit[0] == "extract" and len(csplit) > 1:
            place = None
            folderName = ""
            
            PlaceID = None
            if len(csplit) == 3:
                if csplit[2].isnumeric():
                    PlaceID = csplit[2]
                else:
                    print("Invalid PlaceID")
                    continue
            
            if csplit[1].isnumeric():
                PlaceID = PlaceID or csplit[1]
                data = uploader.DownloadPlace(csplit[1],NoFile=True)
                if not data:
                    continue
                place = RobloxPlace(data=data)
                folderName = csplit[1] + "_assets"
            else:
                cpath = Path(csplit[1])
                if not cpath.exists():
                    print("Invalid FileName")
                    continue
                place = RobloxPlace(csplit[1])
                folderName = cpath.stem + "_assets"
            
            if not Path(folderName).exists():
                os.mkdir(folderName)
            
            sounds = place.GetAssets(["Source","SoundId"])
            images = place.GetAssets(["Source","Image","Texture","SkyboxBk","SkyboxDn","SkyboxFt","SkyboxLf","SkyboxRt","SkyboxUp"])
            print("Images: {}".format(len(images)))
            print("Sounds: {}".format(len(sounds)))
            if len(images) > 0:
                npath = folderName+"/images"
                if not Path(npath).exists():
                    os.mkdir(npath)
                files = glob.glob(npath+"/*.*")
                for file in files:
                    assetName = Path(file).stem
                    if assetName in images:
                        images.remove(assetName)
                if len(images) != 0:
                    print("\nDownloading Images...")
                    uploader.DownloadAssets(images,PlaceID=PlaceID,OutDir=npath+"/")
                else:
                    print("\nAll Images already downloaded.")
            if len(sounds) > 0:
                npath = folderName+"/sounds"
                if not Path(npath).exists():
                    os.mkdir(npath)
                files = glob.glob(npath+"/*.*")
                for file in files:
                    assetName = Path(file).stem
                    if assetName in sounds:
                        sounds.remove(assetName)
                if len(sounds) != 0:
                    print("\nDownloading Sounds...")
                    uploader.DownloadAssets(sounds,PlaceID=PlaceID,OutDir=npath+"/")
                else:
                    print("\nAll Sounds already downloaded.")
            print("\nExtraction Finished.")
        elif csplit[0] == "permit" and len(csplit) > 2:
            if not csplit[1].isnumeric():
                print("Invalid PlaceID")
                continue
            cpath = Path(csplit[2])
            if cpath.exists() and cpath.is_file():
                f = open(csplit[2],"r")
                lines = f.readlines()
                f.close()
                for line in lines:
                    asset = line.rstrip()
                    if not asset.isnumeric():
                        continue
                    uploader.PermitAudio(asset,csplit[1])
            else:
                for x in range(2,len(csplit)):
                    asset = csplit[x]
                    if not asset.isnumeric():
                        continue
                    uploader.PermitAudio(asset,csplit[1])