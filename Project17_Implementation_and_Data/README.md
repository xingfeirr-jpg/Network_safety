# COMP5355 Project 17

- [code/](code/) 存放检测、计时、输入准备和结果重建的代码。各工具实际采用的命令与配置见[配置记录](data/records/formal_comparison_20261030/Frozen_Configuration.json)。
- [data/](data/) 存放[原始输出与计时索引](data/records/formal_comparison_20261030/Reuse_Assessment.json)、[30 组比较结果](data/records/formal_comparison_20261030/Final_Matrix.csv)、[725 条告警账本](data/records/ten_project_synthesis_20261029/Candidate_Review_Combined.csv)及[固定源码来源](data/Third_Party_Sources.json)。

## 重建结果

在解压目录用 Python 3.10 或以上运行以下命令，从已保存的数据重建 CSV、JSON 和结果表。原始记录中的路径沿用实验时的命名，逐库核查原表留在本地。

    python code/rebuild_results.py

## 重跑检测

在独立 Ubuntu/WSL 工作副本中准备 Flawfinder 2.0.20、Cppcheck 2.13.0、CodeChecker 6.29.1、Clang 18.1.3，以及 CMake、Ninja 和 GNU time。将 code/scripts/ 复制到课程工作目录的 scripts/，将 code/experiment_inputs/ 和 data/records/ 合并到其 review_evidence/。原脚本及编译数据库含绝对路径。执行原脚本时按[配置记录](data/records/formal_comparison_20261030/Frozen_Configuration.json)恢复原来的 Linux 工作根目录及课程目录映射，包括 Expat 使用的 /mnt/d/Project/COMP5355 Cyber and Internet Security。把本次输出写入独立工作副本中的空运行目录。

- **libjpeg-turbo 与 utf8proc**。按下载链接获取固定归档并准备源码。继续既有准备阶段时，把相应原始验收记录按下表放回脚本预期路径。若执行原下载或解包步骤，应让该步骤的输出目录保持为空。后续守卫会核对验收记录的哈希。
- **cJSON 补测**。重跑三次计时前，在执行副本中为 FORM-P03-CC-001、FORM-P03-FF-001 和 FORM-P03-CP-001 留出空的 Linux 结果目录及准备目录，同时从执行副本的 cJSON_cost_supplement_20261030/runs/ 和 execution_preparation/ 移开同名历史输出。原前置验收和各阶段验收文件用于输入校验。使用已验收输入按 CodeChecker、Flawfinder、Cppcheck 的顺序重跑。

| 包内原始记录 | 原 Ubuntu 位置 |
| --- | --- |
| [JPEG 下载验收](data/records/libjpeg_turbo_pretest_20261029/raw_download/DL-P09-001/archive-check.json) | $HOME/comp5355/downloads/libjpeg-turbo-3.1.1-DL-P09-001/archive-check.json |
| [JPEG 源码验收](data/records/libjpeg_turbo_pretest_20261029/source/source-check.json) | $HOME/comp5355/results/pretest-libjpeg-turbo-3.1.1/preparation/SRC-P09-001/source-check.json |
| [utf8proc 下载验收目录](data/records/utf8proc_pretest_20261029/download/utf8proc-2.10.0-DL-P10-001/) | $HOME/comp5355/downloads/utf8proc-2.10.0-DL-P10-001/ |
| [utf8proc 源码验收](data/records/utf8proc_pretest_20261029/source/SRC-P10-001/source-check.json) | $HOME/comp5355/results/pretest-utf8proc-2.10.0/preparation/SRC-P10-001/source-check.json |

## 固定版本源码下载

重跑时按以下地址下载。原实验的归档文件名和 SHA-256 见[源码清单](data/Third_Party_Sources.json)。结果重建直接读取包内的实验输出和计时数据。

- [zlib v1.3.2](https://github.com/madler/zlib/archive/da607da739fa6047df13e66a2af6b8bec7c2a498.tar.gz)
- [LZ4 v1.10.0](https://github.com/lz4/lz4/archive/ebb370ca83af193212df4dcbadcc5d87bc0de2f0.tar.gz)
- [cJSON v1.7.19](https://github.com/DaveGamble/cJSON/archive/c859b25da02955fef659d658b8f324b5cde87be3.tar.gz)
- [libyaml 0.2.5](https://github.com/yaml/libyaml/archive/2c891fc7a770e8ba2fec34fc6b545c672beb37e6.tar.gz)
- [json-c json-c-0.18-20240915](https://codeload.github.com/json-c/json-c/tar.gz/41a55cfcedb54d9c1874f2f0eb07b504091d7e37)
- [yyjson 0.12.0](https://codeload.github.com/ibireme/yyjson/tar.gz/8b4a38dc994a110abaec8a400615567bd996105f)
- [Expat R_2_7_1](https://codeload.github.com/libexpat/libexpat/tar.gz/f9a3eeb3e09fbea04b1c451ffc422ab2f1e45744)
- [libpng v1.6.50](https://codeload.github.com/pnggroup/libpng/tar.gz/2b978915d82377df13fcbb1fb56660195ded868a)
- [libjpeg-turbo 3.1.1](https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/3.1.1/libjpeg-turbo-3.1.1.tar.gz)
- [utf8proc v2.10.0](https://codeload.github.com/JuliaStrings/utf8proc/tar.gz/a1b99daa2a3393884220264c927a48ba1251a9c6)
