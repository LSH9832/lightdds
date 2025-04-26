#! /usr/bin/python3
import os
from multiprocessing import *
import platform
import os.path as osp
import time
import datetime
import argparse
import yaml
import argcomplete
from glob import glob

try:
    from .version import __version__
except:
    __version__ = "v0.0.1 beta"

def getLaunchFiles():
    launch_files = {}
    if "DDS_LAUNCH_PATH" in os.environ:
        for path in os.environ["DDS_LAUNCH_PATH"].split(":"):
            if len(path):
                for file in glob(osp.join(path, "*.yaml")):
                    launch_files[osp.basename(file)] = file
    return launch_files

DDS_LAUNCH_FILES = getLaunchFiles()


def get_launch_args(parser=None, set_choices=True):
    isRootParser = parser is None
    if isRootParser:
        parser = argparse.ArgumentParser(description=f"DDS launch parser {__version__}")
    if set_choices:
        parser.add_argument("file", type=str, choices=DDS_LAUNCH_FILES.keys(), help="launch yaml file")
    else:
        parser.add_argument("file", type=str, help="launch yaml file")
    parser.add_argument("-t", "--time", type=float, default=0.1)
    parser.add_argument("--no-log", action="store_true")
    parser.add_argument("--no-relaunch", action="store_true")
    parser.add_argument("--no-cd", action="store_true")
    parser.add_argument("--no-show", action="store_true")
    parser.add_argument("--no-debug", action="store_true")
    parser.add_argument("-c", "--config", type=str, default=None, help="replace config file")
    if isRootParser:
        argcomplete.autocomplete(parser)
        return parser.parse_args()


def do_one_process(node_name, command, wait_time, pid_data):
    pid_data[node_name] = os.getpid()
    time.sleep(wait_time)
    os.system(command)


def parse_command(cfg: dict, log_enabled=True, config=None, no_show=False, no_debug=False, no_cd=False):
    command = (f"cd {cfg['work_dir']} && " if "work_dir" in cfg and not no_cd else "") + f"{cfg['command']}"
    
    if "posArgs" in cfg.keys() and cfg["posArgs"] is not None:
        for k, v in cfg["posArgs"].items():
            command += f" {v}"

    if "optArgs" in cfg.keys() and cfg["optArgs"] is not None:
        for param in cfg["optArgs"]:
            if isinstance(cfg["optArgs"][param], bool):
                if no_show and param == "visualize":
                    cfg['optArgs'][param] = False
                if no_debug and param == "debug":
                    cfg['optArgs'][param] = False
                if cfg["optArgs"][param]:
                    command += f" {param}"
            elif isinstance(cfg["optArgs"][param], list):
                for v in cfg["optArgs"][param]:
                    command += f" {v}"
            else:
                if config is not None and param == "config":
                    cfg['optArgs'][param] = config
                command += f" {param} {cfg['optArgs'][param]}"
    
    if log_enabled and "write_log" in cfg and cfg["write_log"] and "log_file" in cfg:
        logpath = osp.join(
            cfg["log_path"], 
            (datetime.datetime.now().strftime("%Y%m%d-%H%M%S") if ("log_filename_addtime" in cfg and cfg["log_filename_addtime"]) else "") + cfg["log_file"]
        )
        command += f" --add-log {logpath}"
    
    return command


def kill_node(process, node_cfg: dict, pid):
    if "linux" == platform.system().lower():
        if node_cfg.get("kill_keyword", False):
            kw = node_cfg.get("kill_keyword")
            kws = []
            if isinstance(kw, list):
                kws = kw
                kw = kws[0]
            ban_kws = [f"grep {kw}", f"grep '{kw}'", f"grep --color=auto {kw}"]
            for line in os.popen(f"ps -ef | grep '{kw}'").read().split("\n"):
                if len(line):
                    if not any([line.endswith(kwstr) for kwstr in ban_kws]):
                        if all([nkw in line for nkw in kws]):
                            os.popen(f"kill -9 " + line.split()[1])
    
        process.terminate()
        os.system(f"kill -9 {pid}")



def do_launch_process(args: argparse.Namespace = None, set_choices=True):
    if args is None:
        args = get_launch_args(set_choices=set_choices)
    
    args.file = DDS_LAUNCH_FILES.get(args.file, args.file)
    if not osp.isfile(args.file):
        print(f"launch file {args.file} not found.")
        return
    
    cfg: dict = yaml.load(open(args.file), yaml.SafeLoader)
    from typing import List
    processes: List[Process] = []
    mng = Manager()
    mpdict = mng.dict()

    for i, node_name in enumerate(cfg):
        command = parse_command(cfg[node_name], not args.no_log, args.config, args.no_show, args.no_debug, args.no_cd)
        processes.append(Process(target=do_one_process, args=(node_name, command, i * 0.07, mpdict)))

    try:
        [process.start() for process in processes]

        flag = True
        while flag:
            time.sleep(args.time)
            for i, node_name in enumerate(cfg):
                if cfg[node_name].get("run_once", False):
                    continue
                if not processes[i].is_alive():
                    if args.no_relaunch:
                        print(f"node named '{node_name}' has been terminated. exit.")
                        for i, node_name in enumerate(cfg):
                            # processes[i].terminate()
                            kill_node(processes[i], cfg[node_name], mpdict[node_name])
                            if processes[i].is_alive():
                                # os.system(f"kill -9 {mpdict[node_name]}")
                                kill_node(processes[i], cfg[node_name], mpdict[node_name])
                        flag = False
                        break
                    else:
                        # os.system(f"kill -9 {mpdict[node_name]}")
                        command = parse_command(cfg[node_name], not args.no_log, args.config, args.no_show, args.no_debug, args.no_cd)
                        print(f"node named '{node_name}' has been terminated, try relaunch.")
                        processes[i] = Process(target=do_one_process, args=(node_name, command, i * 0.1, mpdict))
                        processes[i].start()
                        
    except KeyboardInterrupt:
        print()
        for i, node_name in enumerate(cfg):
            # processes[i].terminate()
            kill_node(processes[i], cfg[node_name], mpdict[node_name])
            if processes[i].is_alive():
                kill_node(processes[i], cfg[node_name], mpdict[node_name])
                # os.system(f"kill -9 {mpdict[node_name]}")
            print(f"killed {node_name}")
    except Exception as e:
        print(e)
        for i, node_name in enumerate(cfg):
            # processes[i].terminate()
            kill_node(processes[i], cfg[node_name], mpdict[node_name])
            if processes[i].is_alive():
                # os.system(f"kill -9 {mpdict[node_name]}")
                kill_node(processes[i], cfg[node_name], mpdict[node_name])
    finally:
        try:
            [process.join() for process in processes]
            mng.shutdown()
            time.sleep(0.3)
            print()
        except KeyboardInterrupt:
            pass
        except:
            pass


if __name__ == "__main__":
    do_launch_process(None, set_choices=False)
