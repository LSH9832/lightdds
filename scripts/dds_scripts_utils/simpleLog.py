import inspect
from datetime import datetime
from threading import Thread
import os.path as osp

# # # # # # -------------- Log System -------------- # # # # # #
LOG_LEVEL_DEBUG   = 0
LOG_LEVEL_INFO    = 1
LOG_LEVEL_SUCCESS = 2
LOG_LEVEL_WARNING = 3
LOG_LEVEL_ERROR   = 4

LOG_COLOR_BLUE    = "\033[34m"
LOG_COLOR_GREEN   = "\033[32m"
LOG_COLOR_YELLOW  = "\033[33m"
LOG_COLOR_RED     = "\033[31m"
LOG_COLOR_PURPLE  = "\033[35m"
LOG_COLOR_CYAN    = "\033[36m"
LOG_COLOR_WHITE   = "\033[37m"
LOG_FONT_BOLD     = "\033[1m"
LOG_NORMAL        = "\033[0m"

class Log:
    
    level_map = {
        0: "DEBUG  ",
        1: "INFO   ",
        2: "SUCCESS",
        3: "WARNING",
        4: "ERROR  "
    }
    
    level_map_simple = {
        0: "D",
        1: "I",
        2: "S",
        3: "W",
        4: "E"
    }
    
    color_map = {
        0: LOG_COLOR_BLUE,
        1: LOG_COLOR_WHITE,
        2: LOG_COLOR_GREEN,
        3: LOG_COLOR_YELLOW,
        4: LOG_COLOR_RED
    }
    
    def __init__(self, level: int = 1, enable_color=True, out=None):
        self.level = level
        self.color = enable_color
        self.out = out
        
    def __Log(self, level, msg, loc, color=False):
        nowtime = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-(3 if self.out is None else 7)]
        level = max(0, level)
        level = min(4, level)
        if not color:
            if self.out is not None:
                return f"{nowtime} [{self.level_map_simple[level]}] {msg}"
            return f"{nowtime} | {self.level_map[level]} | {loc} - {msg}"
        
        return f"{LOG_COLOR_GREEN}{nowtime}{LOG_NORMAL} | "\
               f"{LOG_FONT_BOLD}{self.color_map[level]}{self.level_map[level]}{LOG_NORMAL} | " \
               f"{LOG_COLOR_CYAN}{loc}{LOG_NORMAL} - " \
               f"{LOG_FONT_BOLD}{self.color_map[level]}{msg}{LOG_NORMAL}"
    
    def _Log(self, level, *args):
        if level < self.level:
            return
        msg = self.__Log(level, self.__dealArgs(*args), self.__location(), self.color)
        if self.out is None:
            print(msg)
        else:
            Thread(target=self.out, args=(msg, level)).start()
            # self.out(msg, level)
    
    def __dealArgs(self, *args):
        str2log = ""
        for i, arg in enumerate(args):
            if i:
                str2log += " "
            str2log += f"{arg}"
        return str2log

    def __location(self):
        frame_info = inspect.getouterframes(inspect.currentframe())[3]
        line_number = frame_info.lineno
        func_name = frame_info.function.replace("<module>", "__main__")
        fname = osp.basename(frame_info.filename)
        loc = f"{fname}:{line_number}:<{func_name}>"
        return loc

    def setLevel(self, level: int):
        self.level = level
    
    def setColor(self, enabled=True):
        self.color = enabled
    
    def setOutputFunction(self, func=None):
        self.out = func
    
    def debug(self, *args):
        self._Log(0, *args)
        
    def info(self, *args):
        self._Log(1, *args)
    
    def success(self, *args):
        self._Log(2, *args)
        
    def warning(self, *args):
        self._Log(3, *args)
        
    def error(self, *args):
        self._Log(4, *args)
        
logger = Log(LOG_LEVEL_DEBUG, enable_color=True)
# # # # # # ------------ End Log System ------------ # # # # # #
