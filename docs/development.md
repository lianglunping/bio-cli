# 开发与验证

[返回首页](../README.md) · [使用说明](usage.md)

## 版本与源码结构

`VERSION` 是命令显示版本和安装 release 版本的唯一来源。未发布改动记在 `CHANGELOG.md` 的 `Unreleased` 中。

| 文件 | 职责 |
|---|---|
| `bio_cli.py` | 参数、格式分派、限量预览、压缩与安全恢复 |
| `bio_runtime.py` | 后端进程组、超时与有上限的诊断输出 |
| `scripts/install.py` | 个人目录安装、release 校验与失败回退 |
| `scripts/fetch_tools.py` | 下载锁定版本并校验 SHA-256 |
| `tools.lock.json` | 下载平台、官方来源、版本与校验和 |
| `tests/` | 临时目录中的合成数据回归 |

## 本地回归

```sh
python3 -m unittest discover -s tests -v
peek --version
packz --help
unpackz --help
```

测试在临时目录生成明确标识的合成数据，覆盖文本压缩、BAM/BCF/CRAM、链接、目录恢复、内容哈希、错误输入、拒绝覆盖、路径逃逸及限量读取；另覆盖超时与中断回收、继承管道的子进程、海量诊断输出、下载／写入故障、并发发布、恢复限额、乱序目录元数据及入口完整性。测试需要上述生信依赖，不用跳过用例代替通过。

## 自动回归

`.github/workflows/tests.yml` 在主分支推送、PR 和手动触发时运行完整测试：Ubuntu 22.04 的 Python 3.8 / 3.12，以及 macOS 14 的 Python 3.12。CI 安装原生测试依赖并打印实际版本；测试不使用研究数据，不通过跳过用例掩盖缺失依赖。依赖由 runner 的包管理器提供，版本可能变化，以每次 CI 日志为准；CI 不等同于指定 HPC 环境的部署验收。

新增命令或修改文件行为时应同时更新用法、合成回归和安装文件清单。安装后的 README、CHANGELOG 与 `docs/` 也纳入 release 校验。文档中的相对链接应在源码与安装 release 中均有效。

## 性能与资源边界

Python 负责命令入口、限量预览、终端转义和安全恢复；压缩与专用格式读取调用原生 zstd/gzip/bgzip、samtools/bcftools。压缩过程中不使用 Python 逐字节执行压缩算法，目录打包的 tar 输出直接交给压缩器。

性能取决于启动开销、解压吞吐、存储速度、归档成员位置和安全检查。文本转义使用编译后的控制字符扫描，避免对普通文本逐字符执行 Python 循环。目录恢复仍包含 Python tar 解析和逐成员路径检查，海量小文件与反复启动进程的批处理可能受其影响；不能把本工具视为原生命令的零开销替代品。tar 流式处理不再缓存所有普通成员对象，仅保留恢复目录权限和时间所需的目录记录，并从最深目录开始应用元数据，避免父目录先变为只读而阻断子目录。外部后端共用进程生命周期管理，错误诊断最多保留 64 KiB，版本探测每个输出流最多保留 8 KiB；退出、预览截断和超时会清理所拥有的进程组。主动脱离进程组的进程不属于该回收保证。

全量重写需先用同一数据和同等校验要求比较，不能只凭实现语言预测提速。

## 上游来源

版本见 [`VERSION`](../VERSION)；代码通过 Git 提交记录版本。官方上游：
[gdu](https://github.com/dundee/gdu)、[dust](https://github.com/bootandy/dust)、[dua](https://github.com/Byron/dua-cli)、[bat](https://github.com/sharkdp/bat)、[ripgrep](https://github.com/BurntSushi/ripgrep)、[fd](https://github.com/sharkdp/fd)、[eza](https://github.com/eza-community/eza)、[zstd](https://github.com/facebook/zstd)、[HTSlib](https://www.htslib.org/)。上游软件遵循各自许可，不作为本仓库二进制附件发布。
