import os
from time import strftime, localtime
from uuid import uuid4
from shutil import copytree, ignore_patterns
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("root", type=str, help="项目根目录")
args = parser.parse_args()


root = args.root
os.chdir(root)


bp = "src/bp/"
rp = "src/rp/"
bp_manifest = bp + "manifest.json"
rp_manifest = rp + "manifest.json"
scripts = "src/bp/template_scripts/"
common = "src/bp/template_scripts/common/"
constant = common + "constant.py"
config = common + "config.py"
main_client = scripts + "main_client.py"
main_server = scripts + "main_server.py"
mcdev = ".mcdev.json"


name = root.split("\\") if "\\" in root else root.split("/")
name = name[-1]
lower = name.lower()
date = strftime("%Y-%m-%d", localtime())


DATE = ("$DATE$", date)
MOD_NAME = ("$MOD_NAME$", name)
UUID1 = ("$UUID1$", str(uuid4()))
UUID2 = ("$UUID2$", str(uuid4()))
UUID3 = ("$UUID3$", str(uuid4()))
UUID4 = ("$UUID4$", str(uuid4()))


def _open(path, mode):
    return open(path, mode, encoding="utf-8")


with _open(constant, "r") as f:
    constant_str = f.read()
with _open(constant, "w") as f:
    constant_str = constant_str.replace(*DATE).replace(*MOD_NAME)
    f.write(constant_str)


with _open(config, "r") as f:
    config_str = f.read()
with _open(config, "w") as f:
    config_str = config_str.replace(*DATE)
    f.write(config_str)


with _open(bp_manifest, "r") as f:
    manifest_str = f.read()
with _open(bp_manifest, "w") as f:
    manifest_str = manifest_str.replace(*MOD_NAME).replace(*UUID1).replace(*UUID2)
    f.write(manifest_str)


with _open(rp_manifest, "r") as f:
    manifest_str = f.read()
with _open(rp_manifest, "w") as f:
    manifest_str = manifest_str.replace(*MOD_NAME).replace(*UUID3).replace(*UUID4)
    f.write(manifest_str)


with _open(main_client, "r") as f:
    main_client_str = f.read()
with _open(main_client, "w") as f:
    main_client_str = main_client_str.replace(*DATE)
    f.write(main_client_str)


with _open(main_server, "r") as f:
    main_server_str = f.read()
with _open(main_server, "w") as f:
    main_server_str = main_server_str.replace(*DATE)
    f.write(main_server_str)


copytree(
    "E:/MCMod/nuoyanlib/src/nuoyanlib",
    scripts + "nuoyanlib",
    ignore=ignore_patterns("*.pyc", "__pycache__"),
)


os.rename(bp + "template_scripts", bp + "%s_scripts" % lower)


version = [0, 0, 0, 0]
for dir_name in os.listdir("S:/MCStudioDownload/game/MinecraftPE_Netease"):
    ver = dir_name.split(".")
    for i in range(4):
        ver_num = int(ver[i])
        if ver_num > version[i]:
            version[i] = ver_num


with _open(mcdev, "r") as f:
    mcdev_str = f.read()
with _open(mcdev, "w") as f:
    mcdev_str = mcdev_str.replace("$VERSION$", ".".join(str(v) for v in version))
    f.write(mcdev_str)











