import os
import os.path as osp

import yaml
import argparse
import argcomplete
from glob import glob

from .version import __version__
from .dds_workspace import isWorkspaceRootPath
from .simpleLog import logger
import shutil

def get_export_args(parser=None, set_choices=True):
    isRootParser = parser is None
    if isRootParser:
        parser = argparse.ArgumentParser(description=f"DDS export parser {__version__}")

    parser.add_argument("dist", type=str, help="export dist dir")
    parser.add_argument("--add", type=str, nargs="+", default=[], help="add files and dirs to export")
    if isRootParser:
        argcomplete.autocomplete(parser)
        return parser.parse_args()
    
    
def isSkipFile(file):
    # skip library files that almost exist in every kind of linux system
    skip_keys = ["libpthread.so", "libdl.so", "librt.so", "libm.so", "libgcc_s.so", 
                 "libstdc++.so", "libc.so", "libz.so", "librt.so"]
    for key in skip_keys:
        if key in file:
            return True
    return False


def do_export_process(args):
    if not isWorkspaceRootPath():
        logger.error("Not a workspace root path")
        return
    dist = args.dist
    if not osp.exists(dist):
        os.makedirs(dist)
    
    root = osp.abspath(os.getcwd())
    
    if isinstance(args.add, str):
        args.add = [args.add]
    
    for add in args.add:
        if osp.isfile(add):
            shutil.copy(add, dist)
        elif osp.isdir(add):
            if add.endswith("/"):
                add = add[:-1]
            logger.info(f"copy dir: {add} to {osp.join(dist, osp.basename(add))}")
            shutil.copytree(add, osp.join(dist, osp.basename(add)), dirs_exist_ok=True)

    shutil.copytree(osp.join(root, "install"), dist, dirs_exist_ok=True)
    
    lib_files = []
    for executable_file in glob(osp.join(root, "install", "bin/**/*"), recursive=True):
        # judge if it is a executable file
        if osp.isfile(executable_file) and os.access(executable_file, os.X_OK):
            command = f"ldd {executable_file}"
            for line in os.popen(command).read().split("\n"):
                if "=>" in line:
                    lib_path = line.split("=>")[1].split()[0]
                    if not isSkipFile(lib_path):
                        lib_files.append(lib_path)
    
    lib_files = list(set(lib_files))
    if len(lib_files):
        lib_dir = osp.join(dist, "lib")
        if not osp.exists(lib_dir):
            os.makedirs(lib_dir)
        for lib_file in lib_files:
            if not osp.isfile(osp.join(lib_dir, osp.basename(lib_file))):
                logger.info(f"copy lib file: {lib_file}")
                os.system(f"cp {lib_file} {lib_dir}")
    
    setupStr = f"""export RT_PATH=$(dirname "$(readlink -f "$0")")
export LD_LIBRARY_PATH=$RT_PATH/lib:$LD_LIBRARY_PATH
"""
    
    setupFile = osp.join(dist, "setup.bash")
    with open(setupFile, "w") as f:
        f.write(setupStr)
    
    os.system(f"chmod +x {setupFile}")
    with open(osp.join(dist, "dds_launch"), "w") as f:
        f.write(open(osp.join(osp.dirname(__file__), 'dds_launch.py'), 'r').read())
    
    os.system(f"chmod +x {osp.join(dist, 'dds_launch')}")
    
    ori_install_path = osp.join(root, "install").replace("\\", "/")
    if ori_install_path.endswith("/"):
        ori_install_path = ori_install_path[:-1]
    for yaml_file in glob(osp.join(dist, "**/*.yaml"), recursive=True):
        yamlStr = open(yaml_file, "r").read()
        yamlStr = yamlStr.replace(ori_install_path, "$RT_PATH")
        yamlStr = yamlStr.replace(root, "$RT_PATH")
        with open(yaml_file, "w") as f:
            f.write(yamlStr)
    
    logger.info(f"export dist dir: {dist}")
    
    return dist
    
if __name__ == "__main__":
    args = get_export_args()
    do_export_process(args)
    
    # yaml_file = osp.join(osp.dirname(__file__), 'dds_launch.py')
    # with open(yaml_file, "r") as f:
    #     yaml_dict = yaml.load(f, yaml.SafeLoader)
    # yaml_dict["launch"]["file"] = "launch"
    # yaml_dict["launch"]["args"]["config"] = "config.yaml"
    # yaml_dict["launch"]["args"]["dist"] = "dist"
    # with open(yaml_file, "w") as f:
    #     yaml.dump(yaml_dict, f, default_flow_style=False)
    
    