import os
import os.path as osp
from glob import glob
from .simpleLog import *
from .dds_path import *
import yaml
import argparse
import argcomplete
from .dds_message import tabOnce, __version__


def get_workspace_args(parser=None):
    isRootParser = parser is None
    if isRootParser:
        parser = argparse.ArgumentParser()
    # parser.add_argument("mode", choices=["create", "update", "make", "launch_init"])
    
    sp = parser.add_subparsers(dest="mode", help="mode")
    sp_create = sp.add_parser("create", help="create workspace in current path", description=f"DDS workspace create argument parser ({__version__})")
    sp_create.add_argument("-n", "--name", type=str, help="name", default=None)
    sp_create.add_argument("--vscode", action="store_true", help="generate vscode settings")
    
    sp_update = sp.add_parser("update", help="update current workspace info", description=f"DDS workspace update parser ({__version__})")
    
    sp_make = sp.add_parser("make", help="make all projects which are set as default in this workspace.", description=f"DDS workspace make parser ({__version__})")
    sp_make.add_argument("--clean", action="store_true", help="clean before make")
    sp_make.add_argument("--nargs", type=str, nargs="+", help="cmake args and make args")   # whether startswith -D(cmake) or not(make)
    
    sp_launch_init = sp.add_parser("launch_init", help="update current workspace info")
    
    # parser.add_argument("--version", type=str, help="project version", default="0.0.1")
    
    if isRootParser:
        argcomplete.autocomplete(parser)
        return parser.parse_args()


def genSetup(root):
    root = osp.abspath(root)
    dist = osp.abspath(osp.join(root, "devel"))
    
    add_libStr = f":{root}/lib" if osp.isdir(f"{root}/lib") else ""
    add_libStr += f":{root}/install/lib/" if osp.isdir(osp.join(root, "install/lib")) else ""
    setupStr = f"""#! /bin/bash
export DDS_RUNTIME_PATH=$DDS_RUNTIME_PATH:{root}/install/bin
export DDS_LAUNCH_PATH=$DDS_LAUNCH_PATH:{root}/install/launch
# export PATH={root}/install/bin/:{root}/scripts/:$PATH
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH{add_libStr}
"""
    with open(osp.join(dist, "setup.bash"), "w") as f:
        f.write(setupStr)


def getAllProjects(root):
    project_cfg_file = osp.join(root, "devel", "project.yaml")
    if osp.isfile(project_cfg_file):
        with open(project_cfg_file, "r") as f:
            cfg:dict = yaml.load(f, Loader=yaml.Loader)
            if "__main__" in cfg:
                cfg.pop("__main__")
        return cfg
    return {}

def getWorkspaceName(root):
    project_cfg_file = osp.join(root, "devel", "project.yaml")
    if osp.isfile(project_cfg_file):
        with open(project_cfg_file, "r") as f:
            cfg:dict = yaml.load(f, Loader=yaml.Loader)
            if "__main__" in cfg:
                return cfg["__main__"]
    return osp.basename(root)


def update_dds_workspace(args):
    assert isWorkspaceRootPath(), "not a workspace root path."
    root = osp.abspath(os.getcwd())
    exist_projects: dict = getAllProjects(root)
    
    project_cfg_file = osp.join(root, "devel", "project.yaml")
    new2write = {"__main__": getWorkspaceName(root)}
    for k, v in exist_projects.items():
        if osp.isdir(osp.join(root, "src", k)):
            new2write[k] = v
    
    with open(project_cfg_file, "w") as f:
        yaml.dump(new2write, f, Dumper=yaml.Dumper)
    
    genWorkspaceCMakeList(args, root)
    
    genSetup(root)
    
    logger.success("workspace updated.")


def addProject(root, project_name, compile_in_default):
    project_cfg_file = osp.join(root, "devel", "project.yaml")
    exist_projects: dict = getAllProjects(root)
    
    exist_this_project = False
    new2write = {"__main__": getWorkspaceName(root)}
    for k, v in exist_projects.items():
        if k == project_name:
            logger.warning(f"project {project_name} already exists, will not create it again.")
            exist_this_project = True
        if osp.isdir(osp.join(root, "src", k)):
            new2write[k] = v
    
    if not exist_this_project:
        new2write[project_name] = compile_in_default
    
    with open(project_cfg_file, "w") as f:
        yaml.dump(new2write, f, Dumper=yaml.Dumper)


def genProjectAddSubStr(root):
    cmakeStr0 = ""
    cmakeStr1 = ""
    projects = getAllProjects(root)
    for project_name in projects:
        pro_base = project_name.replace("/", "_")
        default_enabled = "ON" if projects[project_name] else "OFF"
        cmakeStr0 += f'option(ENABLE_{pro_base.upper()} "enable {pro_base}" {default_enabled})\n'
        cmakeStr1 += f"if(ENABLE_{pro_base.upper()})\n"
        cmakeStr1 += f"  add_subdirectory(src/{project_name})\n"
        cmakeStr1 += f"endif()\n"
    return cmakeStr0 + cmakeStr1

def genWorkspaceCMakeList(args, root):
    cmakeStr = f"""cmake_minimum_required(VERSION 3.10)

project(dds_workspace LANGUAGES CXX)


{genProjectAddSubStr(root)}

"""
    with open(osp.join(root, "CMakeLists.txt"), "w") as f:
        f.write(cmakeStr)


def genVSCodeSettingFile(root):
    import platform
    # get architecture str:  x86_64 or aarch64
    map_arch = {
        "x86_64": "x64",
    }
    
    json_str =  f"""{{
    "configurations": [
        {{
            "name": "Linux",
            "includePath": [
                "${{workspaceFolder}}/**",
                "${{workspaceFolder}}/include",
                "{DDS_INCLUDE_PATH}"
            ],
            "defines": [],
            "compilerPath": "/usr/bin/clang",
            "cStandard": "c17",
            "cppStandard": "c++14",
            "intelliSenseMode": "linux-clang-{map_arch.get(platform.machine(), platform.machine())}"
        }}
    ],
    "version": 4
}}
"""
    os.makedirs(osp.join(root, ".vscode"), exist_ok=True)
    with open(osp.join(root, ".vscode", "c_cpp_properties.json"), "w") as f:
        f.write(json_str)
    


def genProjectCMakeList(args, root, project_dir, dependencies=None):
    name = args.name.replace("\\", "/").split("/")[-1]
    
    deps2findStr = ""
    depsIncludeStr = ""
    depsLibStr = ""
    depsDefStr = ""
    if dependencies is None:
        dependencies = []
    if "Boost" not in dependencies:    # add boost as default dependency
        dependencies.append("Boost")
    for dep in dependencies:
        deps2findStr += f"find_package({dep} REQUIRED)\n"
        depsIncludeStr += f"${{{dep}_INCLUDE_DIRS}}\n"
        
        if dep.lower() not in ["eigen3"]:
            depsLibStr += f"${{{dep}_LIBRARIES}}\n"
        
        if dep.upper() not in ["PCL"]:
            depsDefStr += "# "
        depsDefStr += f"add_definitions(${{{dep}_DEFINITIONS}})\n"
            
    cmakeStr = f"""cmake_minimum_required(VERSION 3.10)

project({name} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_FLAGS "-O3 -fPIC -pthread -w ${{CMAKE_CXX_FLAGS}}")
set(CMAKE_BUILD_TYPE Release) # Debug

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${{CMAKE_SOURCE_DIR}}/install/bin/")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${{CMAKE_SOURCE_DIR}}/install/lib/")

{deps2findStr}

include_directories(
    $ENV{{DDS_INCLUDE_PATH}}
    ${{CMAKE_SOURCE_DIR}}/include
    ${{CMAKE_CURRENT_SOURCE_DIR}}/include
{tabOnce(depsIncludeStr)}
)

link_directories(
    $ENV{{DDS_LIBRARY_PATH}}
    ${{CMAKE_SOURCE_DIR}}/lib
    ${{CMAKE_SOURCE_DIR}}/install/lib
    ${{CMAKE_CURRENT_SOURCE_DIR}}/lib
)

{depsDefStr}

set(PROJECT_LIBS
    -pthread
    yaml-cpp
    LightDDSLib
{tabOnce(depsLibStr)}
)

## example
# add_executable({name}
#     ${{CMAKE_CURRENT_SOURCE_DIR}}/src/main.cpp
#     
# )
# 
# target_link_libraries({name}
#     ${{PROJECT_LIBS}}
# )
"""
    with open(osp.join(project_dir, "CMakeLists.txt"), "w") as f:
        f.write(cmakeStr)

def create_dds_workspace(args):
    root = os.getcwd()
    os.makedirs(osp.join(root, "include/dds/message"), exist_ok=True)
    os.makedirs(osp.join(root, "src"), exist_ok=True)
    os.makedirs(osp.join(root, "devel"), exist_ok=True)
    os.makedirs(osp.join(root, "lib"), exist_ok=True)
    
    genSetup(root)
    
    if args.name is None:
        args.name = osp.basename(root)
    
    assert "/" not in args.name.replace("\\", "/")
    with open(osp.join(root, "devel", "project.yaml"), "w") as f:
        f.write(f"__main__: {args.name}")
    
    genWorkspaceCMakeList(args, root)
    if args.vscode:
        genVSCodeSettingFile(root)
    
    logger.success("workspace created.")


def isWorkspaceRootPath():
    root = os.getcwd()
    return osp.isfile(osp.join(root, "devel", "project.yaml"))

def launch_init_dds_workspace(args):
    assert isWorkspaceRootPath(), "not a workspace root path."
    root = osp.abspath(os.getcwd()).replace("\\", "/")
    runtimePath = osp.join(root, "install/bin")
    launchCfgStr = ""
    
    for file in glob(osp.join(runtimePath, "*")):
        file = file.replace("\\", "/")
        if osp.isfile(file):
            # check whether it is a executable file
            if os.access(file, os.X_OK):
                optArgStr = ""
                posArgStr = ""
                for line in os.popen(f"{file} --?").read().split("\n"):
                    if not len(line):
                        continue
                    k, v = line.split()
                    if k == "--add-log":
                        continue
                    if k.startswith("--"):
                        optArgStr += f"    {k}: {v}\n"
                    else:
                        posArgStr += f"    {k}: {v}\n"
                if not len(optArgStr):
                    optArgStr = " null"
                else:
                    optArgStr = "\n" + optArgStr[:-1]
                if not len(posArgStr):
                    posArgStr = " null"
                else:
                    posArgStr = "\n" + posArgStr[:-1]
                runTimeStr = f"""{osp.basename(file) + "_node"}:
  work_dir: {root}
  command: {file}
  run_once: false    # run only once, will not restart if crashed
  write_log: true
  log_path: {osp.join(root, f"install/logs/{osp.basename(file)}")}
  log_file: .log
  log_filename_addtime: true
  posArgs:{posArgStr}
  optArgs:{optArgStr}
"""
                launchCfgStr += runTimeStr
                
    # dump yaml
    launch_dir = osp.join(root, "install", "launch")
    os.makedirs(launch_dir, exist_ok=True)
    launchFile = osp.join(launch_dir, f"{getWorkspaceName(root)}.yaml")
    
    if len(launchCfgStr):
        with open(launchFile, "w") as f:
            f.write(launchCfgStr)
        logger.success(f"launch file created: {launchFile}")
    else:
        logger.error(f"no executable file found in {runtimePath}")
                    
                        
def make_dds_workspace(args):
    root = os.getcwd()
    buildPath = osp.join(root, f"devel/build/workspace")
    os.makedirs(buildPath, exist_ok=True)
    if args.clean:
        os.system(f"rm -rf {buildPath}/*")
    
    if args.nargs is None:
        args.nargs = []
    
    cmakeArgs = ""
    makeArgs = ""
    hasJ = False
    for arg in args.nargs:
        if arg.startswith("CMAKE"):
            arg = arg[5:]
            cmakeArgs += arg + " "
        elif arg.startswith("MAKE"):
            arg = arg[4:]
            if arg.startswith("-j"):
                if arg[2:].isdigit():
                    hasJ = True
            makeArgs += arg + " "
    
    cmakeCMD = f"cmake {osp.abspath(root)} {cmakeArgs}-B {buildPath}"
    logger.info(f"cmake command: {cmakeCMD}")
    os.system(cmakeCMD)
    
    makeCMD = f"cd {buildPath};make {makeArgs}{'' if hasJ else '-j$(nproc) '};cd {osp.abspath(root)}"
    logger.info(f"make command: {makeCMD}")
    os.system(makeCMD)


def do_workspace_process(parser=None):
    args = get_workspace_args(parser) if parser is None else parser
    
    eval(f"{args.mode}_dds_workspace")(args)
    
    # if args.mode == "create":
    #     create_dds_workspace(args)
    # elif args.mode == "update":
    #     update_dds_workspace(args)
    # elif args.mode == "launch_init":
    #     launch_init_dds_workspace(args)
    # elif args.mode == "make":
    #     make_dds_workspace(args)
    # else:
    #     logger.error(f"unknown mode: {args.mode}")
    #     exit(1)
