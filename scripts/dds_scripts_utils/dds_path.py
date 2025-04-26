import os.path as osp

DDS_PATH = osp.abspath((osp.dirname(osp.dirname(osp.dirname(__file__)))))
DDS_INCLUDE_PATH = osp.join(DDS_PATH, "include")
DDS_LIBRARY_PATH = osp.join(DDS_PATH, "lib")
DDS_SCRIPTS_PATH = osp.join(DDS_PATH, "scripts")

