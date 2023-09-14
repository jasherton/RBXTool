from pathlib import Path
import io
import zipfile
import requests
import json

#Automatic Updating
FileVersion = "2"
GitRepo = "https://api.github.com/repos/jasherton/RBXTool/releases/latest"

if not Path(".git").exists():
    res = requests.get(GitRepo,headers={"User-Agent":"Python"})
    if res.status_code == 200:
        content = json.loads(res.content.decode("utf-8"))
        res = requests.get(content["assets"][0]["browser_download_url"])
        data = zipfile.ZipFile(io.BytesIO(res.content))
        names = data.namelist()
        versionText = None
        if "app.py" in names:
            text = data.read("app.py").decode("utf-8")
            match = text.find("FileVersion = \"")
            if match != -1:
                versionText = text[match+15:text.find("\"",match+16)]
        if versionText and versionText != FileVersion:
            data.extractall()

from interface import Main
Main()