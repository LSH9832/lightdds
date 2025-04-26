"""
Create: 2025-3-21
Edit:   2025-3-25

Author: Liu Shihan / He Xin

see usage: python3 thisFileName.py -h
"""
import os
import re
import os.path as osp
import argparse
import xml.etree.ElementTree as ET
from glob import glob
from typing import Dict, List

from .simpleLog import *
from .dds_path import *
from .version import __version__
import argcomplete


def get_msg_args(parser=None):
    isRootParser = parser is None
    if isRootParser:
        parser = argparse.ArgumentParser(description=f"DDS message generator parser {__version__}")
        
    # parser.add_argument("mode", choices=["generate", "clean"], help="mode")
    
    sp = parser.add_subparsers(dest="mode", help="subcommand")
    sp_generate = sp.add_parser("generate", help="generate message file", description=f"DDS message generate parser ({__version__})")
    sp_generate.add_argument("--path", type=str, default="./", help="xml file root path")
    sp_generate.add_argument("-f", "--files", type=str, default=None, nargs="+", help="files")
    sp_generate.add_argument("-d", "--dist", type=str, default=None, help="generate code root path")
    
    
    sp_clean = sp.add_parser("clean", help="clean message file", description=f"DDS message clean parser ({__version__})")
    sp_clean.add_argument("path", type=str, help="xml file root path")
    sp_clean.add_argument("-f", "--files", type=str, default=None, nargs="+", help="files")
    sp_clean.add_argument("-d", "--dist", type=str, default=None, help="clean code root path")
    
    
    sp_new = sp.add_parser("new", help="new message file", description=f"DDS message new parser ({__version__})")
    sp_new.add_argument("name", type=str, help="message name")
    sp_new.add_argument("--path", type=str, default="./", help="xml file root path")
    
    # parser.add_argument("path", type=str, help="xml file root path")
    # parser.add_argument("-f", "--files", type=str, default=None, nargs="+", help="files")
    # parser.add_argument("-d", "--dist", type=str, default=None, help="generate code root path")
    
    if isRootParser:
        argcomplete.autocomplete(parser)
        return parser.parse_args()
# ---------------------------- do not edit unless you know what will happen ---------------------------------


# # # # # # ------------- Support Type ------------- # # # # # #
BASIC_TYPE = {
    "uint8_t": 0, 
    "int8_t": 0, 
    "uint16_t": 0, 
    "int16_t": 0, 
    "uint32_t": 0, 
    "int32_t": 0, 
    "uint64_t": 0, 
    "int64_t": 0, 
    "float": 0.0, 
    "double": 0.0, 
    "bool": "false", 
    "string": None
}
ITERABLE_TYPE = ["vector", "array"]

# # # # # # ----------- End Support Type ----------- # # # # # #

# # # # # # ------------ Basic Function ------------ # # # # # #
def tabOnce(msg: str, space=4, tabFirstLine=True, prefix=None, suffix=None):
    spaces = " " * space
    if tabFirstLine:
        msg = spaces + msg
    flag = msg.endswith("\n")
    msg = msg.replace("\n", f"\n{spaces}")
    if flag:
        msg = msg[:-space]
    if prefix is not None:
        msg = msg.replace("\n", f"\n{prefix}")
    if suffix is not None:
        msg = msg.replace("\n", f"{suffix}\n")
    return msg


def dealFile(filePath: str):
    xmlStr = open(filePath, encoding="utf8").read()
    
    def deal_(str2deal: str, tname="vector"):
        xmlList = str2deal.split(f"{tname}<")
        ret = ""
        for i, piece in enumerate(xmlList):
            if i == 0:
                ret += piece
            else:
                lenTName = len(piece.split(">")[0])
                ret += f"{tname}[{piece[:lenTName]}]{piece[lenTName+1:]}"
        return ret
    
    xmlStr = deal_(xmlStr, "vector")
    xmlStr = deal_(xmlStr, "array")

    def escape_comment(match):
        quote_char = match.group(1)  # 捕获引号（' 或 "）
        content = match.group(2)
        endings = match.group(3)
        # 仅替换内容中的 < 和 >
        escaped_content = content.replace('<', '&lt;').replace('>', '&gt;')
        
        # print(quote_char, endings)
        return f'{quote_char}{escaped_content}{endings}'

    # 使用 re.DOTALL 确保跨行匹配
    pattern = r'(comment\s*=\s*["])(.*?)(["])'
    xmlStr = re.sub(pattern, escape_comment, xmlStr, flags=re.DOTALL)
    pattern = r'(comment\s*=\s*[\'])(.*?)([\'])'
    xmlStr = re.sub(pattern, escape_comment, xmlStr, flags=re.DOTALL)
    
    return xmlStr

# # # # # # ---------- End Basic Function ---------- # # # # # #

# # # # # # -------------- Decode XML -------------- # # # # # #
class OneItem:
    
    def __init__(self):
        self.isEnum = False
        self.type: str = None
        self.name: str = None
        self.comment: str = None
        self.default: str = None
        self.parent = []
        self.attrs = {}
        
        self.__relies = None                # 该元素类型依赖的其他头文件
        self.__isBasic = False              # 是否是基础类型
        self.__isIterable = False           # 是否是可递归的（vector或array）
        self.__isIterItemBasic = False      # 是否递归元素是基础类型
        self.__isVector = False             # 是否是vector（可变长度）
        self.__arrayLength = 0              # 如果是array，其指定的长度
        self.__prefix = ""
        self.__nameForCheckRelies = None    # 用于检查依赖的名称，如果是递归则是递归里的元素，否则是本身，为None则表示无需检查依赖
        self.__isFixedSize=True
        # self.__check()
    
    @property
    def isIterable(self):
        return self.__isIterable
    
    @property
    def isFixedSize(self):
        return self.__isFixedSize
    
    @property
    def isVector(self):
        return self.__isVector
    
    @property
    def arrayLength(self):
        return self.__arrayLength
    
    @property
    def fullType(self):
        if self.isEnum:
            return "int32_t"
        return f"{self.__prefix}{self.type}"
        
    def checkTypeEssential(self):
        """_summary_
        检查类型
        """
        if self.isEnum:
            return
        self.type = self.type.replace("[", "<").replace("]", ">")
        self.__isBasic = self.type in BASIC_TYPE
        if self.__isBasic:
            if self.default is None:
                self.default = BASIC_TYPE.get(self.type, None)
            if self.type == "string":
                self.__prefix = "std::"
                self.__isFixedSize = False
                if self.default is not None:
                    self.default = f'"{self.default}"'
        elif "<" in self.type and self.type.endswith(">"):
            self.__isIterable = True
            self.__prefix = "std::"
            if self.type.startswith("vector<"):
                elemtype = self.type[7:-1]
                self.__isVector = True
                self.__relies = "vector"
                self.__isFixedSize = False
            elif self.type.startswith("array<"):
                elemtypeAndLength = self.type[6:-1]
                assert "," in elemtypeAndLength
                elemtype, l_ = elemtypeAndLength.split(",")
                self.__arrayLength = int(l_)
                self.__isVector = False
                self.__relies = "array"
            else:
                raise TypeError(f"{self.type} is not support")
            
            assert not (elemtype.startswith("vector<") or elemtype.startswith("array<"))
            self.__isIterItemBasic = elemtype in BASIC_TYPE
            if not self.__isIterItemBasic:
                self.__nameForCheckRelies = elemtype
                # print(self.name, self.__nameForCheckRelies)
        else:
            self.__nameForCheckRelies = self.type
            
    def match(self, structName):
        return structName == self.getNameForRelyCheck()
    
    def getNameForRelyCheck(self):
        return self.__nameForCheckRelies
    
    def getRely(self):
        return self.__relies
    
    def setRely(self, rely):
        self.__relies = rely
    
    def showHead(self):
        showStr = ""
        if not self.isEnum:
            showStr += f"{self.fullType} "
        showStr += self.name
        if self.default is not None:
            showStr += f" = {self.default}"
        showStr += "," if self.isEnum else ";" 
        if self.comment is not None:
            self.comment = self.comment.replace('&lt;', '<').replace('&gt;', '>')
            showStr = f"// {self.comment}\n{showStr}"
        return showStr
        

class OneStruct:
    
    def __init__(self, node: ET.Element, is_enum=False, namespace=None):
        self.name = node.attrib["name"]
        self.node: ET.Element = node
        self.is_enum = is_enum
        self.namespace = [] if namespace is None else namespace
        self.items: List[OneItem] = []
        self.__subMsgs: List[OneStruct] = []
        self.__parse()
        
    def __parse(self):
        for elem in self.node:
            if elem.tag != "item":
                continue
            item = OneItem()
            for k, v in elem.attrib.items():
                if hasattr(item, k):
                    setattr(item, k, v)
                else:
                    item.attrs[k] = v
            item.isEnum = self.is_enum
            item.parent = self.namespace    # + [self.name]
            item.checkTypeEssential()
            self.items.append(item)
            
    def __addHelp(self, msg):
        return f"""/*!
 * @brief This class represents the structure {self.name} defined by the user in the xml file.
 * @comment 
 * @ingroup {self.name.upper()}
 */
""" + msg

    def __addFunctionDefinition(self):
        return f"""/*!
 * @brief Default constructor.
 */
{self.name}();

std::string typeName()
{{
    return "{self.fullName}";   
}}

/*!
 * @brief This function returns the maximum serialized size of an object
 * depending on the buffer alignment.
 * @param current_alignment Buffer alignment.
 * @return Maximum serialized size.
 */
static size_t getMaxSerializedSize(size_t current_alignment = 0);

/*!
 * @brief This function returns the serialized size of a data depending on the buffer alignment.
 * @param data Data which is calculated its serialized size.
 * @param current_alignment Buffer alignment.
 * @return Serialized size.
 */
static size_t getSerializedSize(
        const {self.name}& data,
        size_t current_alignment = 0);


/*!
 * @brief This function serializes an object using CDR serialization.
 * @param cdr CDR serialization object.
 */
void serialize(
    lightdds::SerializeStream& stream) const;

/*!
 * @brief This function deserializes an object using CDR serialization.
 * @param cdr CDR serialization object.
 */
void deserialize(
    lightdds::DeserializeStream& stream);

/*!
 * @brief This function returns the maximum serialized size of the Key of an object
 * depending on the buffer alignment.
 * @param current_alignment Buffer alignment.
 * @return Maximum serialized size.
 */
static size_t getKeyMaxSerializedSize(size_t current_alignment = 0);

static size_t getKeySerializedSize(const {self.name}& data,
                                   size_t current_alignment = 0);

static bool isKeyFixedSize();

/*!
 * @brief This function tells you if the Key has been defined for this type
 */
static bool isKeyDefined();

/*!
 * @brief This function serializes the key members of an object using serialization.
 * @param cdr CDR serialization object.
 */
void serializeKey(lightdds::SerializeStream& stream) const;


"""
    
    def getInnerRelies(self):
        return list(set([item.getRely() for item in self.items]))
    
    def addRelyStruct(self, structs):
        structs: List[OneStruct]
        for struct in structs:
            struct: OneStruct
            for item in self.items:
                if item.isFixedSize:
                    if item.match(struct.fullName):
                        self.__subMsgs.append(struct)
    
    def isFixedSize(self):
        for item in self.items:
            if not item.isFixedSize:
                return False

        for struct in self.__subMsgs:
            if not struct.isFixedSize():
                return False
        return True
            
    
    @property
    def unknownTypes(self):
        ret = []
        for item in self.items:
            # print(item.name, item.getNameForRelyCheck())
            if item.getNameForRelyCheck() is not None:
                ret.append(item.getNameForRelyCheck())
        # print(ret)
        return ret

    @property
    def prefix(self):
        pre_ = ""
        for n in self.namespace:
            pre_ += f"{n}::"
        return pre_
    
    @property
    def fullName(self):
        return self.prefix + self.name
    
    def showHead(self):
        showStr = f"{'enum' if self.is_enum else 'class'} {self.name}{' : int32_t' if self.is_enum else ''}\n"
        showStr += "{\n"
        if not self.is_enum:
            showStr += "public:\n"
            showStr += tabOnce(self.__addFunctionDefinition())
        
        for item in self.items:
            showStr += tabOnce(item.showHead())
            showStr += "\n"
        showStr += "};\n"
        
        # print(showStr)
        return self.__addHelp(showStr)
    
    def showSerialize(self):
        if self.is_enum:
            return f"CREATE_SIMPLE_SERIALIZER_NAMESPACE({self.fullName})"

        def stream(m="s"):   # s, d, l
            ret = ""
            numItems = len(self.items)
            for i, item in enumerate(self.items):
                if m == "s":
                    ret += f"stream<<data.{item.name};\n"
                elif m == "d":
                    ret += f"stream>>data.{item.name};\n"
                elif m == "l":
                    ret += f"lightdds::GetSerializeDataLength(data.{item.name})"
                    if i+1 < numItems:
                        ret += " +\n"
                    else:
                        ret += ";"
            if m != "l":
                ret = ret[:-1]
            return ret
        
        return f"""template<>
struct lightdds::Serializer<{self.fullName}>
{{
    inline static void Serialize(lightdds::SerializeStream& stream, const {self.fullName}& data)
    {{
        {tabOnce(stream("s"), 8, False)}
    }}

    inline static void Deserialize(lightdds::DeserializeStream& stream, {self.fullName}& data)
    {{
        {tabOnce(stream("d"), 8, False)}
    }}

    inline static uint32_t GetSerializeLength(const {self.fullName}& data)
    {{
        return {tabOnce(stream("l"), 15, False)}
    }}

    inline static bool IsSimpleType(const {self.fullName}& data)
    {{
        return false;
    }}

    inline static bool IsFixedSize(const {self.fullName}& data)
    {{
        return {"true" if self.isFixedSize() else "false"};
    }}
}};"""
  
    def showCPP(self):
        if self.is_enum:
            return ""
        return f"""
#define {self.name}_max_cdr_typesize 500ULL;
#define {self.name}_max_key_cdr_typesize 16ULL;

{self.name}::{self.name}() {{}}

size_t {self.name}::getMaxSerializedSize(size_t current_alignment)
{{
    static_cast<void>(current_alignment);
    return {self.name}_max_cdr_typesize;
}}

size_t {self.name}::getSerializedSize(const {self.name}& data, size_t current_alignment)
{{
    (void)current_alignment;
    return lightdds::GetSerializeDataLength(data);
}}

void {self.name}::serialize(lightdds::SerializeStream& stream) const
{{
    lightdds::SerializeData(stream,*this);
}}

void {self.name}::deserialize(lightdds::DeserializeStream& stream)
{{
    lightdds::DeserializeData(stream,*this);
}}

size_t {self.name}::getKeyMaxSerializedSize(size_t current_alignment)
{{
    static_cast<void>(current_alignment);
    return {self.name}_max_key_cdr_typesize;
}}

size_t {self.name}::getKeySerializedSize(
    const {self.name}& data,
    size_t current_alignment
)
{{
    static_cast<void>(current_alignment);
    size_t size = 0;
    


    return size;
}}

bool {self.name}::isKeyFixedSize()
{{
    return true;
}}

bool {self.name}::isKeyDefined()
{{
    return false;
}}

void {self.name}::serializeKey(lightdds::SerializeStream& stream) const
{{
    (void)stream;
}}
"""
    
    def showPubSubTypeHead(self):
        if self.is_enum:
            return ""
        return f"""
/*!
 * @brief This class represents the TopicDataType of the type {self.name} defined by the user in the XML file.
 * @ingroup {self.name.upper()}
 */
class {self.name}PubSubType : public lightdds::TopicDataType
{{
public:

    typedef {self.name} type;

    {self.name}PubSubType();

    virtual ~{self.name}PubSubType() override;

    virtual bool serialize(
        void* data,
        lightdds::SerializedPayload_t* payload
    ) override;

    virtual bool deserialize(
        lightdds::SerializedPayload_t* payload,
        void* data
    ) override;

    virtual std::function<uint32_t()> getSerializedSizeProvider(void* data) override;

    virtual bool getKey(
        void* data,
        lightdds::InstanceHandle_t* ihandle,
        lightdds::SerializedPayload_t* payload,
        bool force_md5 = false
    ) override;

    virtual void* createData() override;

    virtual void deleteData(void* data) override;

    inline bool is_bounded() const override
    {{
        return m_isBounded;
    }}

    inline bool is_plain() const override
    {{
        return false;
    }}

    inline bool construct_sample(
            void* memory) const override
    {{
        new (memory) {self.name}();
        return true;
    }}

private:
    lightdds::MD5 m_md5;

    bool m_isBounded;
    bool m_isKeyBounded;
}};
"""

    def showPubSubTypeCPP(self):
        if self.is_enum:
            return ""
        return f"""
{self.name}PubSubType::{self.name}PubSubType()
{{
    setName("{self.fullName}");

    m_isBounded = false;
    {self.name} obj;
    m_isBounded = lightdds::IsSerializeDataFixedSize(obj);
    size_t type_size = 0;
    if(m_isBounded)
    {{
        type_size = {self.name}::getSerializedSize(obj);
    }}
    else
    {{
        type_size = {self.name}::getMaxSerializedSize();
    }}

    // type_size += eprosima::fastcdr::Cdr::alignment(type_size, 4); /* possible submessage alignment */
    m_typeSize = static_cast<uint32_t>(type_size) + 4; /*encapsulation*/
    m_isGetKeyDefined = {self.name}::isKeyDefined();

    m_isKeyBounded = {self.name}::isKeyFixedSize();
    if(m_isKeyBounded)
    {{
        m_keySize = {self.name}::getKeySerializedSize(obj);
    }}
    else
    {{
        m_keySize = {self.name}::getKeyMaxSerializedSize();
    }}
    m_keySize = m_keySize > 16 ? m_keySize : 16;
}}

{self.name}PubSubType::~{self.name}PubSubType()
{{

}}

bool {self.name}PubSubType::serialize(
    void* data,
    lightdds::SerializedPayload_t* payload)
{{
    {self.name}* p_type = static_cast<{self.name}*>(data);
    lightdds::SerializeStream stream(payload->data,payload->max_size);
    lightdds::SerializeData(stream,*p_type);

    if(stream.getErr())
    {{
        return false;
    }}

    payload->length = stream.getProcessLength();

    return true;
}}

bool {self.name}PubSubType::deserialize(
    lightdds::SerializedPayload_t* payload,
    void* data)
{{
    //Convert DATA to pointer of your type
    {self.name}* p_type = static_cast<{self.name}*>(data);
    lightdds::DeserializeStream stream(payload->data,payload->length);
    lightdds::DeserializeData(stream,*p_type);
    if(stream.getErr())
    {{
        return false;
    }}

    return true;
}}

std::function<uint32_t()> {self.name}PubSubType::getSerializedSizeProvider(void* data)
{{
    return [data]() -> uint32_t
           {{
               return static_cast<uint32_t>(type::getSerializedSize(*static_cast<{self.name}*>(data))) +
                      4u /*encapsulation*/;
           }};
}}

void* {self.name}PubSubType::createData()
{{
    return reinterpret_cast<void*>(new {self.name}());
}}

void {self.name}PubSubType::deleteData(
        void* data)
{{
    delete(reinterpret_cast<{self.name}*>(data));
}}

bool {self.name}PubSubType::getKey(
    void* data,
    lightdds::InstanceHandle_t* handle,
    lightdds::SerializedPayload_t* payload,
    bool force_md5)
{{
    if (!m_isGetKeyDefined)
    {{
        return false;
    }}

    {self.name}* p_type = static_cast<{self.name}*>(data);

    if(m_isKeyBounded)
    {{
        payload->reserve(m_keySize);
    }}
    else
    {{
        payload->reserve({self.name}::getKeySerializedSize(*p_type));
    }}
    lightdds::SerializeStream stream(payload->data,payload->max_size);
    p_type->serializeKey(stream);
    if(stream.getErr())
    {{
        return false;
    }}
    if (force_md5 || stream.getProcessLength() > 16)
    {{
        m_md5.init();
        m_md5.update(stream.getStart(), static_cast<unsigned int>(stream.getProcessLength()));
        m_md5.finalize();
        for (uint8_t i = 0; i < 16; ++i)
        {{
            handle->value[i] = m_md5.digest[i];
        }}
    }}
    else
    {{
        for (uint8_t i = 0; i < 16; ++i)
        {{
            handle->value[i] = stream.getStart()[i];
        }}
    }}
    return true;
}}
"""

class OneNameSpace:
    
    def __init__(self, name, parents=None):
        self.name = name
        self.parents: List[str] = [] if parents is None else parents
        self.namespaces: Dict[str, OneNameSpace] = {}
        self.structs: Dict[str, OneStruct] = {}
        self.enums: Dict[str, OneStruct] = {}
        
    def addNameSpaceNode(self, node: ET.Element):
        for child in node:
            if child.tag == "namespace":
                assert "name" in child.attrib, "no name of a namespace!"
                namespaceName = child.attrib["name"]
                if self.namespaces.get(namespaceName, None) is None:
                    self.namespaces[namespaceName] = OneNameSpace(namespaceName, self.parents + [namespaceName])
                self.namespaces[namespaceName].addNameSpaceNode(child)
            elif child.tag == "struct":
                assert "name" in child.attrib, "no name of a struct!"
                self.addStruct(child)
            elif child.tag == "enum":
                assert "name" in child.attrib, "no name of a enum!"
                self.addEnum(child)
            else:
                assert False, f"can not parse elem name '{child.tag}'"
    
    def addStruct(self, node: ET.Element):
        new_struct = OneStruct(node, False, self.parents)
        self.structs[node.attrib["name"]] = new_struct
    
    def addEnum(self, node: ET.Element):
        new_enum = OneStruct(node, True, self.parents)
        self.enums[node.attrib["name"]] = new_enum
        
    def getInnerRelies(self):
        ret = []
        [ret.extend(v.getInnerRelies()) for _, v in self.structs.items()]
        [ret.extend(v.getInnerRelies()) for _, v in self.namespaces.items()]
        return list(set(ret))
    
    @property
    def structNames(self) -> List[str]:  # 获取本身所有的结构体名称（不包含枚举类型，请所有枚举类型都用int32_t）
        return [k for k, _ in self.structs.items()]
    
    def fullStructNames(self): # 获取该命名空间及其子命名空间的所有结构体（不包含枚举）并附上完整命名空间
        ret = []
        prefix = "" if self.name is None else (self.name + "::")
        for k, _ in self.structs.items():
            ret.append(prefix + k)
        
        for _, v in self.namespaces.items():
            for sonstruct in v.fullStructNames():
                ret.append(prefix + sonstruct)
        return ret
    
    def addStructs(self, structs: List[OneStruct]):
        for k, v in self.structs.items():
            for struct in structs:
                pass
            
    def getAllStructs(self) -> List[OneStruct]:
        ret = []
        for _, v in self.structs.items():
            ret.append(v)
        for _, v in self.namespaces.items():
            ret.extend(v.getAllStructs())
        return ret
    
    def getStructByName(self, fullname: str):
        for struct in self.getAllStructs():
            if struct.fullName == fullname:
                return struct
        return None
    
    @property
    def unknownTypes(self) -> List[str]:  # 本命名空间（不包括子命名空间）的所有未知类型
        ret = []
        for _, v in self.structs.items():
            ret.extend(v.unknownTypes)
        return list(set(ret))
    
    def getSonStructNames(self) -> List[str]:
        ret = []
        for k0, v in self.namespaces.items():
            for k, _ in v.structs.items():
                if k0 is not None:
                    k = k0 + "::" + k
                ret.append(k)
            for s in v.getSonStructNames():
                if k0 is not None:
                    s = k0 + "::" + s
                ret.append(s)
        return ret
    
    # 查找所有该命名空间（子空间递归）内未知类型变量是否来自同一命名空间或父空间
    # 最后返回仍未找到的未知类型（需要查找别的文件，找到则引用，否则报错）
    def reliesNeeded(self, parentStructNames: str = None):
        if parentStructNames is None:
            parentStructNames = []
        
        # 列出在本级没有找到的未知类型
        typesNotFount = []
        typeNameSpaces = []
        # 遍历每个在本级的未知类型
        for unknownType in self.unknownTypes:
            *namespaces, baseUnknownType = unknownType.split("::")
            
            # 是否在父空间
            if baseUnknownType in parentStructNames:
                if not len(namespaces):
                    continue
                idx = -1
                found = True
                for i, namespace in enumerate(namespaces):
                    if namespace not in self.parents:
                        found = False
                        break
                    if i == 0:
                        idx = self.parents.index(namespace)
                    elif idx+i >= len(self.parents):
                        found = False
                        break
                    elif namespace != self.parents[idx+i]:
                        found = False
                        break
                if found:
                    continue
            
            # 是否在本空间
            if baseUnknownType in self.structNames:
                # print(baseUnknownType)
                if len(namespaces) == 0:
                    continue
                if len(namespaces) <= len(self.parents)+1:
                    ns = self.parents + [self.name]
                    if namespaces == ns[-len(namespaces):]:
                        continue
            
            # 是否在子空间
            found = False
            sonStructNames = self.getSonStructNames()
            for sonStructName in sonStructNames:
                if sonStructName == unknownType:
                    found = True
                    break
                elif unknownType.endswith(sonStructName):
                    prefix = unknownType[:-len(sonStructName)]
                    if not prefix.endswith("::"):
                        continue
                    ns = prefix[:-2].split("::")
                    if len(ns) <= len(self.parents)+1:
                        nss = self.parents + [self.name]
                        if ns == nss[-len(ns):]:
                            found = True
            if found:
                continue
            
            typesNotFount.append(unknownType)
            if self.name is not None:
                typeNameSpaces.append(self.name + "::")
            else:
                typeNameSpaces.append("")
        
        # 加入子空间的未知类型
        for k, v in self.namespaces.items():
            ns, ts = v.reliesNeeded(self.structNames)
            typesNotFount.extend(ns)
            for t in ts:
                if self.name is not None:
                    typeNameSpaces.append(self.name + "::" + t)
                else:
                    typeNameSpaces.append(t)
        
        return typesNotFount, typeNameSpaces
    
    def showSerialize(self):
        showStr = ""
        
        for _, v in self.namespaces.items():
            showStr += v.showSerialize()
            showStr += "\n\n"
        
        for _, v in self.enums.items():
            showStr += v.showSerialize()
            showStr += "\n\n"
        
        for _, v in self.structs.items():
            showStr += v.showSerialize()
            showStr += "\n\n"
        
        while showStr.endswith("\n"):
            showStr = showStr[:-1]
        
        return showStr + "\n"

    def showHead(self):
        showStr = ""
        
        for _, v in self.enums.items():
            showStr += v.showHead()
            showStr += "\n\n"
        
        for _, v in self.structs.items():
            showStr += v.showHead()
            showStr += "\n\n"
            
        for _, v in self.namespaces.items():
            showStr += v.showHead()
            showStr += "\n\n"
        
        while showStr.endswith("\n"):
            showStr = showStr[:-1]
        
        if self.name is not None:
            showStr = f"namespace {self.name}\n" + "{\n" + tabOnce(showStr) + "\n\n}"
        
        return showStr
    
    def showCPP(self):
        showStr = ""
        for _, v in self.structs.items():
            showStr += v.showCPP()
            showStr += "\n\n"
        
        for _, v in self.namespaces.items():
            showStr += v.showCPP()
            showStr += "\n\n"
        
        while showStr.endswith("\n"):
            showStr = showStr[:-1]
        
        if self.name is not None:
            showStr = f"namespace {self.name}\n" + "{\n" + tabOnce(showStr) + "\n\n}"
        
        return showStr

    def showPubSubTypeHead(self):
        showStr = ""
        for _, v in self.structs.items():
            showStr += v.showPubSubTypeHead()
            showStr += "\n\n"
        
        for _, v in self.namespaces.items():
            showStr += v.showPubSubTypeHead()
            showStr += "\n\n"
        
        while showStr.endswith("\n"):
            showStr = showStr[:-1]
        
        if self.name is not None:
            showStr = f"namespace {self.name}\n" + "{\n" + tabOnce(showStr) + "\n\n}"
        
        return showStr
        
    def showPubSubTypeCPP(self):
        showStr = ""
        for _, v in self.structs.items():
            showStr += v.showPubSubTypeCPP()
            showStr += "\n\n"
        
        for _, v in self.namespaces.items():
            showStr += v.showPubSubTypeCPP()
            showStr += "\n\n"
        
        while showStr.endswith("\n"):
            showStr = showStr[:-1]
        
        if self.name is not None:
            showStr = f"namespace {self.name}\n" + "{\n" + tabOnce(showStr) + "\n\n}"
        
        return showStr

class OneFile:
    
    def __init__(self, filePath: str, rootPath: str, isBasic: bool = False):
        self.fp = filePath.replace('\\', '/')
        self.isBasic = isBasic
        if not osp.isfile(filePath):
            logger.error("can not find file", filePath)
            exit(-1)
        elif not filePath.lower().endswith(".xml"):
            logger.error(f"{osp.abspath(filePath)} is not a xml file!")
            exit(-1)
        
        self.rootPath = rootPath
        
        self.pathList: str = osp.relpath(filePath, rootPath).replace("\\", "/")
        assert not self.pathList.startswith("..")
        if self.pathList.startswith("./"):
            self.pathList: str = self.pathList[2:]
        self.pathList: List[str] = self.pathList.split("/")
        self.pathList[-1] = self.pathList[-1][:-4]
        # print(self.pathList)
        
        self.__includes: List[str] = []
        
        
        self.space = OneNameSpace(None, None)
        
        inputString = dealFile(filePath)
        self.inputString = inputString
        try:
            root = ET.fromstring(inputString)
        except Exception as e:
            logger.error(self.fp)
            logger.error(e)
            logger.info(inputString)
            exit(-1)
        # print(root.tag, root.text, root.attrib, root.tail)
        assert root.tag == "document", "file not support!"
        self.space.addNameSpaceNode(root)
        
    def addIncludeFile(self, file):
        if isinstance(file, str):
            self.__includes.append(file)
        elif isinstance(file, list):
            self.__includes.extend(file)
        else:
            assert False
        self.__includes = list(set(self.__includes))
    
    @property
    def includeStr(self):
        incStr = ""
        for inc in self.space.getInnerRelies():
            # if inc in ITERABLE_TYPE:
            if inc is not None:
                incStr += f"#include <{inc}>\n"
        for inc in self.__includes:
            if (inc.startswith("<") and inc.endswith(">")) or (inc.startswith('"') and inc.endswith('"')):
                incStr += f"#include {inc}\n"
                continue
            elif not inc.startswith("."):
                inc = f"./{inc}"
            incStr += f"#include \"{inc}.cpp\"\n"      # ---------------------------------------------------------------
        
        return incStr
        
    def addHeadFileDef(self, msg: str):
        defName = "DDSMSG_"
        for p in self.pathList:
            defName += f"{p.upper()}_"
        defName += "H"
        return f"""#ifndef {defName}
#define {defName}

{self.includeStr}
#include "dds/serialization/Serializer.h"

/* origin xml file
{self.inputString} */

{msg}
#endif  /* {defName} */"""

    def addCPPFileDef(self, msg: str):
        defName = "DDSMSG_"
        for p in self.pathList:
            defName += f"{p.upper()}_"
        defName += "CPP"
        return f"""#ifndef {defName}
#define {defName}

#include "./{osp.basename(self.fp[:-4])}.h"

{msg}
#endif  /* {defName} */"""

    def addPubSubTypeHeadFileDef(self, msg: str):
        defName = "DDSMSG_"
        for p in self.pathList:
            defName += f"{p.upper()}_"
        defName += "PUBSUBTYPE_H"
        
        include_oriFile = f"./{osp.basename(self.fp[:-4])}.cpp"  # -------------------------------
        
        register_str = ""
        for s in self.space.getAllStructs():
            register_str += f"REGISTER_PUBSUB_TYPE({s.fullName});\n"
        
        return f"""#ifndef {defName}
#define {defName}

#include "dds/topic/TopicDataType.h"
#include "dds/utils/MD5.h"
#include "dds/utils/pubsubUtils.h"
#include "./{include_oriFile}"

{msg}

{register_str}

#endif  /* {defName} */"""

    def addPubSubTypeCPPFileDef(self, msg: str):
        defName = "DDSMSG_"
        for p in self.pathList:
            defName += f"{p.upper()}_"
        defName += "PUBSUBTYPE_CPP"
        return f"""#ifndef {defName}
#define {defName}

#include "dds/common/SerializedPayload_t.h"
#include "dds/common/InstanceHandle_t.h"

#include "./{osp.basename(self.fp[:-4])}PubSubType.h"

{msg}
#endif  /* {defName} */"""

        
    def showHead(self):
        mainStr = self.space.showHead() + "\n\n" + self.space.showSerialize()
        return self.addHeadFileDef(mainStr)
    
    def showCPP(self):
        mainStr = self.space.showCPP()
        return self.addCPPFileDef(mainStr)

    def showPubSubTypeHead(self):
        mainStr = self.space.showPubSubTypeHead()
        return self.addPubSubTypeHeadFileDef(mainStr)
    
    def showPubSubTypeCPP(self):
        mainStr = self.space.showPubSubTypeCPP()
        return self.addPubSubTypeCPPFileDef(mainStr)
    
    @property
    def unknownTypeNames(self):  # 获取所有需要外部依赖的未知类型名称
        typeNames, spaceNames = self.space.reliesNeeded()
        ret: Dict[str, List[str]] = {}
        for tn in typeNames:
            ret[tn] = []
            
        for i, tn in enumerate(typeNames):
            sn = spaceNames[i]
            if len(sn):
                ret[tn].append(sn)
        
        for tn in typeNames:
            ret[tn] = list(set(ret[tn]))
        
        # 在使用返回值寻找需要引用的文件时，如果未加命名空间无法匹配，则对应列表中的每一项都要匹配
        return ret
    
    def getStructByName(self, name):
        return self.space.getStructByName(name)
    
    def addStructs(self, struct):
        pass
    
    def findStructFromThisFile(self, data: Dict[str, List[str]]):
        allStructs = self.space.fullStructNames()
        rest = {}
        success = False   # 只要有一个匹配上了就sucecss
        
        structs: List[OneStruct] = []
        
        if isinstance(data, str):
            data = {data: []}

        for k, v in data.items():
            preList = []
            if k not in allStructs:
                if not len(v):
                    rest[k] = preList   # 本来就没有命名空间还匹配不上
                    continue
                for pre in v:
                    if (pre+k) not in allStructs:
                        preList.append(pre)
                    else:
                        this_struct = self.getStructByName(pre+k)
                        if this_struct is not None:
                            structs.append(this_struct)
                        success = True
                if len(preList):
                    rest[k] = preList   # 存在命名空间匹配不上就加进去
            else:
                this_struct = self.getStructByName(k)
                if this_struct is not None:
                    structs.append(this_struct)
                success = True
        return success, rest, structs
        
    def relPathOf(self, fp: str):
        if self.isBasic:
            rp = osp.relpath(self.fp, DDS_INCLUDE_PATH)[:-4]
            if rp.startswith("./"):
                rp = rp[2:]
            return f"<{rp}.cpp>"    # ----------------------------------------------
        
        absF = osp.abspath(self.fp)
        absfp = osp.abspath(fp)
        if osp.isfile(absfp):
            absfp = osp.dirname(absfp)
        assert osp.isdir(absfp)
        return osp.relpath(absF, absfp)[:-4].replace("\\", "/")       

# # # # # # ------------ End Decode XML ------------ # # # # # #

def generate_once(args):
    genFilesList = []
    assert args.path != DDS_INCLUDE_PATH
    
    assert args.path is not None
    assert osp.isdir(args.path)
    args.path = osp.join(args.path, "include/dds/message")
    if args.dist is None:
        args.dist = args.path
    assert osp.isdir(args.path)
    
    basicFileNames = glob(osp.join(DDS_INCLUDE_PATH, "dds/message/**/*.xml"), recursive=True)
    if args.files is not None:
        if isinstance(args.files, str):
            args.files = [args.files]
        genFilesList = args.files
        args.files = glob(osp.join(args.path, "**", "*.xml"), recursive=True)
    else:
        args.files = glob(osp.join(args.path, "**", "*.xml"), recursive=True)
        genFilesList = args.files
    
    all_xml_files: List[str] = args.files
    
    if isinstance(args.files, str):
        args.files = [args.files]
    assert isinstance(args.files, list)
    args.files = [file.replace("\\", "/") for file in args.files]
    genFilesList = [file.replace("\\", "/") for file in genFilesList]
    
    files2gen: List[OneFile] = []
    for file in genFilesList:
        logger.info(f"parsing genfile {file}")
        thisFile = OneFile(file, args.path)
        files2gen.append(thisFile)
    logger.success(f"parsing genfile done.")
    
    files: List[OneFile] = []
    for file in args.files:
        logger.info(f"parsing include file {file}")
        thisFile = OneFile(file, args.path)
        files.append(thisFile)
    
    for file in basicFileNames:
        logger.info(f"parsing basic file {file}")
        thisFile = OneFile(file, DDS_INCLUDE_PATH, True)
        files.append(thisFile)
    logger.success(f"parsing include file done.")
    # print(files2gen)
    
    logger.info("now check type")
    has_unknow_type = False
    for f1 in files2gen:
        
        f1UnknownTypes = f1.unknownTypeNames
        for f2 in files:
            if f1.fp == f2.fp:
                continue
            success, f1UnknownTypes, structs = f2.findStructFromThisFile(f1UnknownTypes)
            
            
            if success:
                f1.addIncludeFile(f2.relPathOf(f1.fp))

            if len(f1UnknownTypes.keys()) == 0:
                break

        for k, v in f1UnknownTypes.items():
            has_unknow_type = True
            logger.warning(f"Unknown Type {k} in {f1.fp}")
    
    if not has_unknow_type:
        logger.success("Check type success")
    
    logger.info("start generate code.")
    for file in files2gen:
        rp = file.relPathOf(args.path)
        
        h_save_path = osp.join(args.dist, rp).replace("\\", "/") + ".h"   # 头文件
        cpp_save_path = osp.join(args.dist, rp).replace("\\", "/") + ".cpp"   # cpp文件
        pubSubTypeH_save_path = osp.join(args.dist, rp + "PubSubType").replace("\\", "/") + ".h"   # 头文件
        pubSubTypeCpp_save_path = osp.join(args.dist, rp + "PubSubType").replace("\\", "/") + ".cpp"   # cpp文件
        
        os.makedirs(osp.dirname(h_save_path), exist_ok=True)
        
        logger.info(f"generating {h_save_path}")
        open(h_save_path, "w", encoding="utf8").write(file.showHead())
        
        logger.info(f"generating {cpp_save_path}")
        open(cpp_save_path, "w", encoding="utf8").write(file.showCPP())
        
        logger.info(f"generating {pubSubTypeH_save_path}")
        open(pubSubTypeH_save_path, "w", encoding="utf8").write(file.showPubSubTypeHead())
        
        logger.info(f"generating {pubSubTypeCpp_save_path}")
        open(pubSubTypeCpp_save_path, "w", encoding="utf8").write(file.showPubSubTypeCPP())
        
    logger.info("done")


def create_new_xml(path, name):
    path = osp.join(osp.abspath(path), "include/dds/message")
    assert osp.isdir(path)
    assert name is not None
    assert isinstance(name, str)
    assert len(name)
    
    name = name.replace("\\", "/").replace("::", "/")
    for forbidden in [".", ":", "?", "*", "\"", "<", ">", "|", "=", "+", ",", ";", "!", "@", "#", "$", "%", "^", "&", "(", ")", "{", "}", "[", "]"]:
        if forbidden in name:
            logger.error(f"forbidden char {forbidden} in name {name}")
            exit(-1)
    
    file_path = osp.join(path, name + ".xml")
    
    if osp.isfile(file_path):
        logger.error(f"{file_path} already exists!")
        exit(-1)
    
    baseMsgFile = osp.join(DDS_INCLUDE_PATH, "dds/message", name + ".xml")
    if osp.isfile(baseMsgFile):
        logger.error(f"{baseMsgFile} already exists!")
        exit(-1)
    # print(baseMsgFile)
    
    basename = name.split("/")[-1]
    namespaces = name.split("/")[:-1]
    namespaces.reverse()
    
    xmlStr = f"""<struct name = "{basename}">
    <!-- base type: (u)int(8/16/32/64)_t, float, double, bool, string, vector<>, array<> -->
    <item type = "std_msgs::Header" name = "header"/>
    
</struct>"""
    
    for namespace in namespaces:
        if len(namespace) == 0:
            continue
        xmlStr = f"""<namespace name = "{namespace}">
{tabOnce(xmlStr)}
</namespace>"""
        
    os.makedirs(osp.dirname(file_path), exist_ok=True)
    open(file_path, "w", encoding="utf8").write(f"""<document>
{tabOnce(xmlStr)}
</document>""")
    logger.success(f"create new xml file {file_path}")
    
def do_message_process(parser=None):
    args = get_msg_args(parser) if parser is None else parser
    if args.mode == "clean":
        assert args.path is not None
        assert osp.isdir(args.path)
        args.path = osp.join(args.path, "include/dds/message")
        assert osp.isdir(args.path)
        if args.dist is None:
            args.dist = args.path
        for file in glob(osp.join(args.path, "**", "*.xml"), recursive=True):
            file = osp.relpath(file, args.path)[:-4]
            hf = osp.join(args.dist, file + ".h")
            cppf = osp.join(args.dist, file + ".cpp")
            pubSubTypeHf = osp.join(args.dist, file + "PubSubType.h")
            pubSubTypeCppf = osp.join(args.dist, file + "PubSubType.cpp")
            for f in [hf, cppf, pubSubTypeHf, pubSubTypeCppf]:
                if osp.isfile(f):
                    logger.info(f"removing {f}")
                    os.remove(f)
                    if osp.isfile(f):
                        logger.error(f"remove {f} failed!")
                # else:
                #     logger.warning(f"{f} not exist")
        logger.success("clean done")
    elif args.mode == "generate":
        generate_once(args)
    elif  args.mode == "new":
        create_new_xml(args.path, args.name)
    else:
        logger.error(f"unknown mode {args.mode}")
        exit(-1)
    return 0