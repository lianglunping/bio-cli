# 安装、升级与恢复

[返回首页](../README.md) · [使用说明](usage.md) · [开发与验证](development.md)

## 安装前准备

需要 Python 3.8+。从源码仓库执行安装脚本：

```sh
git clone https://github.com/lianglunping/bio-cli.git
cd bio-cli
```

以下安装器要求完整工具组合，下载器只提供 `tools.lock.json` 中锁定的配套工具；它不会安装 samtools/bcftools/HTSlib 等依赖。先在个人环境准备依赖，再按平台选择下载与安装命令。下载清单支持 `linux-x86_64` 和 `darwin-arm64`；其他架构未提供下载清单。

## 下载与安装

依赖：`python3`, `tar`, `gzip`, `bzip2`, `xz`, `zstd`, `samtools`, `bcftools`, `bgzip`。完整工具组合另含 `gdu`, `dust-du`, `dua`, `bat`, `rg`, `fd`, `eza`。本项目不执行系统级包安装，不修改 Conda base，不替换传统 `du/cat/ls`。

```sh
python3 scripts/fetch_tools.py --platform linux-x86_64 --destination "$HOME/tool_staging"
python3 scripts/install.py --tools-dir "$HOME/tool_staging/bin" --shell-file "$HOME/.bashrc"
# macOS 使用 --platform darwin-arm64，Shell 文件按实际选择 .zshrc。
# 无官方 macOS eza 二进制时，先在个人环境安装 eza，再用 --tool eza=/path/to/eza 指定。
# 所有依赖都支持 --tool NAME=/path/to/executable；--prefix 可指定个人安装目录。
```

下载清单固定官方发布版本和 SHA-256。下载与可执行文件提取均写入唯一临时文件，校验后以硬链接不覆盖发布；拒绝目标符号链接，不替换不同内容的已有文件，相同内容可复用。中断或校验失败保留临时文件，重试重新下载，不自动续传或清理失败文件。下载工具只提取预期可执行文件；原始归档留在用户指定的 staging 中。安装器复用可用工具，缺失工具可来自 staging。安装前检查版本，独立保留每个 release，生成的 `runtime.json` 和安装记录仅在本机。Shell 仅添加一段 PATH，并保存原文件备份。公开仓库不会包含这些本地记录。

磁盘工具：`gdu` 包装入口默认 `--no-delete --no-spawn-shell -m 2`；`dua` 和 `dust-du` 默认 2 个扫描线程。`dust-du` 的名字避免遮蔽生信环境可能已有的 `dust`。`dua` 的交互模式本身具有删除功能，工具安装不代表执行清理；使用者需自行决定操作。共享存储的扫描开销取决于元数据服务，不承诺并发一定提速。

不希望改动 Shell 文件时可省略 `--shell-file`，安装后手动把所选 prefix 的 `share/bio-cli/current/bin` 加入 PATH。Linux 和 macOS 的完整分步示例见[首页](../README.md#安装)。

## 升级与失败恢复

升级会识别 `current/bin` 和个人 `bin` 中的托管入口，复用其真实依赖，避免包装器调用自身。安装通过原子创建互斥目录锁定同一 prefix，不依赖共享文件系统可能不支持的 flock/lockf；另一个安装器遇到锁时明确退出。锁内记录主机和 PID；强制终止可能遗留锁，必须确认原安装器已经停止后再人工恢复，安装器不会自动夺取或删除已有锁。安装器先在独立临时目录构建并检查入口，再发布完整 release；构建失败保留未激活临时目录，重试使用新的临时目录。完整 release 复用时校验托管入口的内容和可执行权限，不重写入口；被改动的入口会使重装在激活前失败。激活和 Shell/收据处理若抛出异常，会尝试恢复旧 current、配置及本次新建入口，失败细节保存在安装状态目录；突然断电或强制终止不等于可捕获异常，恢复前仍须检查 current 和收据状态。

同一源码 release 的运行配置保持固定；重装时显式指定与已安装配置不同的 `--tool` 会报错，应使用新的个人 `--prefix`；从同一 staging 重试时，已复制到 vendor 且内容相同的依赖可安全复用。安装记录中的依赖路径对应实际运行配置，包括安装器复制的 vendor 文件。

## 安装后检查

```sh
bio-cli --version
bio-cli doctor
peek --help
packz --help
unpackz --help
```

`doctor` 只检查本机路径与版本。源码回归测试和环境验收要求见[开发与验证](development.md)。

## 回退与停用

安装记录保存在所选 prefix 下的 `state/bio-cli/`。回退时按记录将 `share/bio-cli/current` 链接切回上一 release；首次安装则移除本工具的 PATH 段和五个托管入口（`bio-cli`、`peek`、`packz`、`unpackz`、`dust-du`）即可停用。Shell 已有后续编辑时，仅移除本工具标记段，不直接恢复整份旧备份。不会删除其他工具或数据。
