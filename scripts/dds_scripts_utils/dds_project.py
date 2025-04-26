import os
import os.path as osp
from glob import glob
import argparse
import argcomplete
from .dds_workspace import *
from typing import List
from .dds_message import OneFile, __version__

def get_project_args(parser=None):
    isRootParser = parser is None
    if isRootParser:
        parser = argparse.ArgumentParser()
    
    # init make remove purge readd
    sp = parser.add_subparsers(dest="mode", help="subcommand")
    
    sp_init = sp.add_parser("create", help="create project", description=f"DDS project create parser ({__version__})")
    sp_init.add_argument("name", type=str, help="project name", default=None)
    sp_init.add_argument("-deps", "--dependencies", type=str, help="dependencies names", nargs="+", default=None)   # to be done
    sp_init.add_argument("--no-compile-in-default", action="store_true", help="do not compile in default mode")
    
    choices = []
    for p in getAllProjects(os.getcwd()).keys():
        choices.append(p)
    
    sp_add_source = sp.add_parser("add_source", help="add source", description=f"DDS project add_source parser ({__version__})")
    sp_add_source.add_argument("name", type=str, choices=choices, help="project name", default=None)
    sp_add_source.add_argument("source", type=str, help="source file, suffix should be cpp/c/cc/cu")
    sp_add_source.add_argument("--publish", type=str, nargs="+", help="message types to publish in this source file")
    sp_add_source.add_argument("--subscribe", type=str, nargs="+", help="message types to subscribe in this source file")
    sp_add_source.add_argument("--overwrite", action="store_true", help="overwrite existing files")
    
    sp_make = sp.add_parser("make", help="make project", description=f"DDS project make parser ({__version__})")
    
    sp_make.add_argument("name", type=str, choices=choices, help="project name", default=None)
    sp_make.add_argument("--clean", action="store_true", help="clean before make")
    sp_make.add_argument("--nargs", type=str, nargs="+", help="cmake args and make args")   # whether startswith -D(cmake) or not(make)
    
    # sp_remove = 
    if isRootParser:
        argcomplete.autocomplete(parser)
        return parser.parse_args()


def init_project(args):
    root = os.getcwd()
    assert osp.isdir(osp.join(root, "src")), "workspace not initialized."
    assert osp.isdir(osp.join(root, "include")), "workspace not initialized."
    assert osp.isdir(osp.join(root, "devel")), "workspace not initialized."
    assert osp.isdir(osp.join(root, "lib")), "workspace not initialized."
    
    project_dir = osp.join(root, "src", args.name)
    
    if osp.isdir(project_dir):
        logger.error(f"project {args.name} already exists!")
        return
    
    os.makedirs(project_dir)
    os.makedirs(osp.join(project_dir, "include"))
    os.makedirs(osp.join(project_dir, "src"))
    # os.makedirs(osp.join(project_dir, "msg"))
    os.makedirs(osp.join(project_dir, "lib"))
    
    addProject(root, args.name, not args.no_compile_in_default)
    
    if args.dependencies is not None:
        if isinstance(args.dependencies, str):
            args.dependencies = [args.dependencies]
    genProjectCMakeList(args, root, project_dir, args.dependencies)
    genWorkspaceCMakeList(args, root)
    
    logger.success(f"project {args.name} initialized.")


def addSource2CMakeList(project_dir, sourcename):
    sourceName = osp.basename(sourcename).split(".")[0]
    
    ori_str = open(osp.join(project_dir, "CMakeLists.txt")).read()
    
    if "\n## example\n# add_executable(test" in ori_str:
        ori_str = ori_str.split("\n## example\n# add_executable(test")[0]
    
    with open(osp.join(project_dir, "CMakeLists.txt"), "w") as f:
        f.write(ori_str + f"""
# {sourceName}
add_executable({sourceName}
    ${{CMAKE_CURRENT_SOURCE_DIR}}/src/{osp.basename(sourcename)}

)

target_link_libraries({sourceName}
    ${{PROJECT_LIBS}}
    
)
""")

def add_source(args, sourceName: str, publish: List[str], subscribe: List[str], overwrite: bool = False):
    root = os.getcwd()
    project_dir = osp.join(root, "src", args.name)
    assert osp.isdir(project_dir), f"project {args.name} not exists."
    
    if sourceName.split(".")[-1] not in ["cpp", "cc", "c", "cu"]:
        sourceName += ".cpp"
    
    if osp.isfile(osp.join(project_dir, "src", sourceName)) and not overwrite:
        logger.error(f"source {sourceName} already exists!")
        return
    
    
    includeNames = ""
    psNames = ""
    callBackFunctions = ""
    nameFoundPub = []
    nameFoundSub = []
    
    
    def deal_list(src):
        if src is None:
            src = []
        if isinstance(src, str):
            src = [src]
        return src
    
    publish = deal_list(publish)
    subscribe = deal_list(subscribe)
    
    messages = publish + subscribe
    
    if len(messages):
        xmlFiles = glob(osp.join(root, "include/dds/message/**/*.xml"), recursive=True)
        basicXmlFiles = glob(osp.join(DDS_INCLUDE_PATH, "dds/message/**/*.xml"), recursive=True)
        
        xmlRoot1 = osp.join(root, "include/dds/message")
        xmlRoot2 = osp.join(DDS_INCLUDE_PATH, "dds/message")
        fs = [OneFile(file, xmlRoot1) for file in xmlFiles]
        basicFs = [OneFile(file, xmlRoot2) for file in basicXmlFiles]
        
        
        for i, m in enumerate(messages):
            success = False
            for file in fs + basicFs:
                success, *_ = file.findStructFromThisFile(m)
                if success:
                    includeName = osp.relpath(file.fp, osp.dirname(osp.dirname(file.rootPath)))
                    if includeName.startswith("./"):
                        includeName = includeName[2:]
                    
                    str2add = f'#include <{includeName[:-4] + "PubSubType.cpp"}>\n'
                    if str2add not in psNames:
                        includeNames += f'// #include <{includeName[:-4] + ".cpp"}>\n'   # ----------------------------------------------
                        psNames += f'#include <{includeName[:-4] + "PubSubType.cpp"}>\n'
                        
                    if i < len(publish):
                        nameFoundPub.append(m)
                    else:
                        nameFoundSub.append(m)
                    break
            if not success:
                logger.warning(f"can not find message {m}")
    
    
    sname = sourceName.split(".")[0]
    defName = f"{args.name.replace('/', '_')}_{sname}_CPP".upper()
    pubStr = ""
    subStr = ""
    msgStr = ""
    sendStr = ""

    for i, nf in enumerate(nameFoundPub):
        pubStr += f'lightdds::DDSPublisher* pub{i+1} = nh::advertise<{nf}>("/topic/{nf.replace("::", "/")}", max_buffer_size, "{sname}_pub_node{i+1}");\n'
        msgStr += f'{nf} msg{i+1};\n'
        sendStr += f"// pub{i+1}->publish(msg{i+1});\n"

    for i, nf in enumerate(nameFoundSub):
        subStr += f'lightdds::DDSSubscriber* sub{i+1} = nh::subscribe("/topic/{nf.replace("::", "/")}", max_buffer_size, &{nf.split("::")[-1]}CallBack, "{sname}_sub_node{i+1}");\n'
        callBackFunctions += f"""
void {nf.split("::")[-1]}CallBack(const {nf}& msg)
{{
    // do something
    std::cout << "{nf} received: " /* << msg.XXX */ << std::endl;
}}
"""
    sourceStr = f"""#ifndef {defName}
#define {defName}

#include <pylike/argparse.h>
// first include the DDS generated files
{psNames}{includeNames if False else ""}
// then include the DDS publisher and subscriber
{"" if len(publish) else "// "}#include <dds/publisher/DDSPublisher.h>
{"" if len(subscribe) else "// "}#include <dds/subscriber/DDSSubscriber.h>


{"#define nh lightdds::nodeHandle" if len(messages) else ""}

argparse::ArgumentParser getArgs(int argc, char** argv)
{{
    argparse::ArgumentParser parser("{osp.basename(project_dir)}_{sname} parser", argc, argv);
    
    /* ------------------- please edit the following parser ------------------- */
    /**
     * args:
     * 1. parse names {{shortname, longname}}, you can set parse name with only longname
     * 2. default value, support type: string, int, float, double, bool, std::vector<int/string/float/double>
     * 3. help message
     * 4. if it is a vector, your parse strategy(string): 
     *    "1": only accpet first arg, "2": only accept first two args, ..., "+": accept all args
     */
    parser.add_argument({{"-n", "--node-name"}}, "{sname}_node", "this node name");
    parser.add_argument({{"--config-file"}}, "/path/to/your/config.ini", "path to your config file");
    parser.add_argument({{"--buffer-size"}}, 5, "publisher max buffer size");
    parser.add_argument({{"--debug"}}, STORE_TRUE, "use debug mode");  // bool
    
    /* ------------------------------------------------------------------------ */
    logaddAndSetFromParser2(parser);
    logsetStdoutFormat(((bool)parser["debug"])?"$TIME | $LEVEL | $LOCATION - $MSG":"$TIME | $MSG");
    return parser;
}}

{callBackFunctions}

int main(int argc, char** argv)
{{
    // init params
    auto args = getArgs(argc, argv);
    std::string node_name = args["node-name"];
    std::string config_file = args["config-file"];
    int max_buffer_size = args["buffer-size"];
    bool debug = args["debug"];
    
    std::cout << "debug mode enabled: " << (debug?"true":"false") << std::endl;

{tabOnce(subStr)}
{tabOnce(pubStr)}
{tabOnce(msgStr)}
    while (true)
    {{
        // do something
{tabOnce(sendStr, 8)}
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }}
    
    return 0;
}}


#endif /* {defName} */
"""
    sf = osp.abspath(osp.join(project_dir, "src", sourceName))
    with open(sf, "w") as f:
        f.write(sourceStr)
    if osp.isfile(sf):
        logger.success(f"source {sourceName} added.")
    else:
        logger.error(f"source {sourceName} added failed.")

    addSource2CMakeList(osp.abspath(project_dir), sourceName)

def make_project(args):
    root = os.getcwd()
    buildPath = osp.join(root, f"devel/build/project/{args.name}")
    os.makedirs(buildPath, exist_ok=True)
    if args.clean:
        os.system(f"rm -rf {buildPath}/*")
    project_dir = osp.join(root, "src", args.name)
    assert osp.isdir(project_dir), f"project {args.name} not exists."
    
    if args.nargs is None:
        args.nargs = []
    
    cmakeArgs = ""
    makeArgs = ""
    hasJ = False
    for arg in args.nargs:
        if arg.upper().startswith("CMAKE"):
            arg = arg[5:]
            cmakeArgs += arg + " "
        elif arg.upper().startswith("MAKE"):
            arg = arg[4:]
            if arg.startswith("-j"):
                if arg[2:].isdigit():
                    hasJ = True
            makeArgs += arg + " "
    
    for arg in getAllProjects(root):
        if arg != args.name:
            arg = arg.replace("/", "_").upper()
            cmakeArgs += f"-DENABLE_{arg}=OFF "
        else:
            arg = arg.replace("/", "_").upper()
            cmakeArgs += f"-DENABLE_{arg}=ON "
    
    cmakeCMD = f"cmake {osp.abspath(root)} {cmakeArgs}-B {buildPath}"
    logger.info(f"cmake command: {cmakeCMD}")
    os.system(cmakeCMD)
    
    makeCMD = f"cd {buildPath};make {makeArgs}{'' if hasJ else '-j$(nproc) '};cd {osp.abspath(root)}"
    logger.info(f"make command: {makeCMD}")
    os.system(makeCMD)
    

    
def do_project_process(parser=None):
    args =  get_project_args(parser) if parser is None else parser
    assert isWorkspaceRootPath(), "current path is not a workspace root path."
    # print(args)
    if args.mode == "create":
        init_project(args)
    elif args.mode == "add_source":
        add_source(args, args.source, args.publish, args.subscribe, args.overwrite)
    elif args.mode == "make":
        make_project(args)
    else:
        logger.error(f"mode {args.mode} not supported.")
        exit(1)
