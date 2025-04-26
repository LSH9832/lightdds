# LightDDS Linux开发工具使用说明

## LightDDS核心源码暂不公开，敬请谅解

## 1. 介绍

LightDDS 是一个基于DDS（Data Distribution Service）的轻量级消息中间件，支持发布订阅等功能，本开发工具能以帮助你快速创建DDS工作空间，DDS工程，DDS消息等，方便你快速开发DDS应用。

## 2. 安装

将本文件夹放置在任意目录下，保证本文件夹位置不再移动，同时不要手动向本文件夹中添加其他文件及文件夹，然后执行以下命令

```shell
./install.sh
source ~/.bashrc
```

即安装完毕

## 3. 使用
### 3.1. 创建DDS工作空间

假设你希望使`/home/dds/dds_workspace`作为一个新的dds工作空间并命名为test，那么执行以下命令

```shell
mkdir -p /home/dds/dds_workspace
cd /home/dds/dds_workspace
dds workspace create --name test
```

若对命名无要求，则可以省略`--name`参数，直接执行`dds workspace create`即可，此时会使用当前文件夹名称作为工作空间名称，即`dds_workspace`。

文件夹/home/dds/dds_workspace结构如下

```shell
dds_workspace
├── CMakeLists.txt
├── devel
│   ├── setup.bash
│   ├── project.yaml
│   └── build  # 其中文件(夹)在运行其他dds命令时生成
├── install    # 其中文件(夹)在运行其他dds命令时生成
│   ├── bin
│   ├── lib
│   ├── launch
│   └── logs
├── include    # 请向里面添加多个工程都需要用到的头文件
├── lib        # 请向里面添加多个工程都需要用到的库文件
└── src
```

在使用该工作空间前，请先在该工作空间目录下执行如下命令

```shell
source devel/setup.bash
```

### 3.2. 创建DDS自定义消息

#### 3.2.1. 快速使用

不同于ROS1消息的txt格式，LightDDS消息采用xml格式， 并支持对自定义消息中的基本类型变量指定其默认值，创建自定义消息的命令步骤如下：
假设你希望创建一个名为`custom_msgs::test_msg`的自定义消息，那么在工作空间执行以下命令

```shell
dds message new custom_msgs::test_msg
```

此时会自动在`/home/dds/dds_workspace/include/dds/custom_msgs`文件夹下创建一个名为`test_msg.xml`的文件，其内容如下

```xml
<document>
    <namespace name = "custom_msgs">
        <struct name = "test_msg">
            <!-- base type: (u)int(8/16/32/64)_t, float, double, bool, string, vector<>, array<> -->
            <item type = "std_msgs::Header" name = "header"/>
            
        </struct>
    </namespace>
</document>
```

其中:`<item>`标签用于定义消息中的变量,完整的`<item>`标签属性展示如下

```xml
<item type = "vector<int64_t>" name = "ages", default= "-1" comment = "ages of these people">
```

`type`用于指定该变量的类型

`name`属性用于指定该变量的名称

`default`属性用于指定该变量的默认值，若不指定`default`属性，除数值类型赋0以外，其他类型则不对该变量进行初始化赋值

`comment`属性用于指定该变量的注释，若不指定`comment`属性，则该变量无注释。

#### 3.2.2. 枚举类型

LightDDS也支持枚举类型，需要在xml文件中手动添加，假设你希望创建一个名为Gender的枚举类型，那么可参考以下结构

```xml
<document>
    <namespace name = "custom_msgs">
        <enum name = "Gender">
            <item name = "MALE" default = "0"/>
            <item name = "FEMALE" default = "1"/>
            <item name = "UNKNOWN" default = "-1">
        </enum>
        <struct name = "test_msg">
            <item type = "std_msgs::Header" name = "header"/>
            <item type = "uint8_t" name = "age", default = "30">
            <item type = "array<int32_t, 10>" name = "genders">
        </struct>
    </namespace>
</document>
```

注意，枚举类型中成员类型为int32_t，不支持更改类型，若不指定`default`属性，则默认从0累加。

### 3.3. DDS工程

#### 3.3.1. 创建工程

假设你希望创建一个名为`test_project`的工程，并且该工程需要使用OpenCV、PCL库，那么在工作空间执行以下命令

```shell
dds project create test_project --dependencies OpenCV PCL
```

此时会自动在`/home/dds/dds_workspace/src`文件夹下创建一个名为`test_project`的文件夹，其结构如下

```shell
test_project
├── CMakeLists.txt
├── include  # 向里面添加仅该工程需要用到的头文件
├── lib      # 向里面添加仅该工程需要用到的库文件
└── src
```

### 3.3.2. 复制工程

如果希望将已经存在的DDS工程复制到本工作空间中，在将其拷贝到本工作空间src文件夹下后，执行以下命令

```shell
dds workspace update
```

### 3.3.3. 新建源文件

假设你希望创建一个名为`test.cpp`的源文件作为程序入口文件，且需要通过该文件发布类型为`custom_msgs::test_msg`以及`sensor_msgs::Image`的自定义消息，并订阅类型为`sensor_msgs::CompressedImage`的消息，那么在工作空间执行以下命令

```shell
dds project add_source test.cpp \
    --publish custom_msgs::test_msg sensor_msgs::Image \
    --subscribe sensor_msgs::CompressedImage
```

此时会自动在`/home/dds/dds_workspace/src/test_project/src`文件夹下创建一个名为`test.cpp`的文件，该文件中会自动include所需文件，并给出相关订阅发布代码模板，使用方法类似ROS1。

### 3.3.4. 编译工程
#### 3.3.4.1. 编译指定工程

在工作空间执行以下命令

```shell
dds project make test_project
```

作为第一个测试工程，如果想观察订阅发布效果，可以按照以下步骤新建源文件

```shell
dds project add_source test.cpp \
    --publish custom_msgs::test_msg \  # 任意消息类型均可
    --subscribe custom_msgs::test_msg
```

后将其生成的代码中将主函数循环中的`// pub1->publish(msg1)`取消注释并在循环中加入打印发布消息内容，在相应subscribe回调函数中更改打印内容，再执行上述编译命令。

编译完成后，会自动在`/home/dds/dds_workspace/install/bin`文件夹下生成可执行文件`test`
运行`install/bin/test`即可看到订阅发布效果。

#### 3.3.4.2. 编译所有工程

在工作空间执行以下命令
```shell
dds workspace make
```

## 3.4. 运行程序

### 3.4.1. 自动生成launch文件

**注意：** 本小节仅适用于以下情况

- 对于文件夹`install/bin`中**所有**可执行文件的源文件，均包含且使用了通过`dds project add_source`命令自动生成的代码中的`argparse::ArgumentParser getArgs(int argc, char** argv);`函数

假设在`install/bin`中存在两个可执行文件`test1`和`test2`，在工作空间执行以下命令

```shell
dds workspace launch_init
```

将会在`/home/dds/dds_workspace/install/launch`文件夹下生成一个名为`dds_workspace.yaml`的文件，其内容如下

```yaml
test1_node:
  work_dir: /home/dds/dds_workspace
  command: /home/dds/dds_workspace/install/bin/test1
  run_once: false    # run only once, will not restart if crashed
  write_log: true
  log_path: /home/dds/dds_workspace/install/logs/test1
  log_file: .log
  log_filename_addtime: true
  posArgs: null
  optArgs:
    --node-name: test1_node
    --config-file: /path/to/your/config.ini
    --debug: false
    # 0: DEBUG, 1: INFO, 2: SUCCESS, 3: WARNING, 4: ERROR
    --log-level: 0    # write to log file
    --show-level: 0   # show on screen
test2_node:
  work_dir: /home/dds/dds_workspace
  command: /home/dds/dds_workspace/install/bin/test2
  run_once: false
  write_log: true
  log_path: /home/dds/dds_workspace/install/logs/test2
  log_file: .log
  log_filename_addtime: true
  posArgs: null
  optArgs:
    --node-name: test2_node
    --config-file: /path/to/your/config.ini
    --debug: false
    --log-level: 0
    --show-level: 0
```

其中

`work_dir`为可执行文件所在文件夹

`command`为可执行文件路径，

`run_once`为是否只运行一次，

`write_log`为是否将日志写入文件，

`log_path`为日志文件所在文件夹，

`log_file`为日志文件名，

`log_filename_addtime`为是否在日志文件名中添加时间戳，

`posArgs`为位置参数，
`optArgs`为可选参数，均根据源代码中`argparse::ArgumentParser getArgs(int argc, char** argv);`函数中`add_argument`的参数进行设置，参数前缀为`--`为可选参数，无前缀为位置参数。

### 3.4.2. 手动创建launch文件

如果存在某个可执行文件，其源代码中未使用`dds project add_source`命令自动生成的代码中的`argparse::ArgumentParser getArgs(int argc, char** argv);`函数，那么需要手动创建launch.yaml文件。

除`write_log`，`log_path`，`log_file`，`log_filename_addtime`不可用需要删去，通过其他方式实现读取命令行位置参数和可选参数后也可使用`posArgs`和`optArgs`（前提是解析方式相同）以外，其余参数均与`dds workspace launch_init`命令生成的launch.yaml文件相同。

### 3.4.3. 其他

如果只想执行某个或某几个可执行文件，删去在配置文件中其他可执行文件对应的配置即可。为避免被重新自动生成dds_workspace.yaml文件覆盖，建议改为其他文件名，如`dds_workspace_test1.yaml`，但仍需放在`/home/dds/dds_workspace/install/launch`文件夹下。

### 3.4.4. 运行

在工作空间执行以下命令即可运行对应配置文件中包含的所有可执行文件

```shell
source devel/setup.bash
dds launch dds_workspace_test1.yaml
```

## 3.5. 导出程序

如果想将程序打包，方便在其他同架构电脑上运行，想先把所有需要的文件打包到文件夹`/home/dds/export`中，且在`/home/dds/dds_workspace/configs`中的配置文件需要一并导出，则在工作空间执行以下命令即可导出`install`文件夹下所有文件并打包所有相关库文件

```shell
dds export /home/dds/export --add /home/dds/dds_workspace/configs
```

然后将`/home/dds/export`文件夹拷贝到其他电脑上，进入`export`文件夹并执行以下命令即可运行
```shell
source ./setup.bash
dds_launch launch/dds_workspace_test1.yaml
```
