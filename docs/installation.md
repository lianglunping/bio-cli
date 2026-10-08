# 安装、升级与恢复

[返回首页](../README.md) · [使用说明](usage.md) · [开发与验证](development.md)

## 安装前准备

需要 Python 3.8+。从源码仓库执行安装脚本：

```sh
git clone https://github.com/lianglunping/bio-cli.git
cd bio-cli
```

安装器提供 `core` 和 `full` 两种模式，默认 `full` 保留原有完整安装。下载器只提供 `tools.lock.json` 中锁定的配套工具；它不会安装 samtools/bcftools/HTSlib 等依赖。下载清单支持 `linux-x86_64` 和 `darwin-arm64`；其他架构未提供下载清单。

## 核心安装

`--profile core` 要求 `python3`、`tar`、`gzip`、`bzip2`、`xz`、`zstd` 六项依赖，支持文本和常见压缩文本预览、zstd/gzip 单文件压缩、tar.zst 目录打包与恢复。ZIP 目录预览使用 Python 标准库。

```sh
python3 scripts/install.py --profile core --shell-file "$HOME/.bashrc"
# macOS / Zsh 使用 --shell-file "$HOME/.zshrc"
```

BAM/CRAM 记录与头部预览需要 samtools，BCF 需要 bcftools，BGZF 压缩需要 bgzip。核心安装会记录已找到的这三个后端；缺失时不阻断安装，使用对应功能时会明确报出缺少依赖。后续可把后端加入 PATH，无需重装；若安装时已经固定了该后端的路径，应保持它可用。自动发现的可选后端版本检查失败会在安装日志和收据中标为 `OPTIONAL_ERROR`；显式 `--tool` 指定的无效或检查失败路径仍会拒绝安装。

core 不生成配套工具包装器和 `dust-du` 用户入口，不接管已有的搜索或磁盘工具。`bio-cli tools` 仍显示全工具用途，供按需选择。

## 完整安装

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

安装模式写入运行配置和收据，core/full 具有不同的 release 标识。core 可在同一 prefix 下升级为 full；安装器复用真实依赖并保留旧 release。full 切换为 core 要求新的个人 `--prefix`，避免已有配套入口变成失效链接。切换前可按收据核对原安装；本工具不自动删除旧入口。

同一源码 release 的运行配置保持固定；重装时显式指定与已安装配置不同的 `--tool` 会报错，应使用新的个人 `--prefix`；从同一 staging 重试时，已复制到 vendor 且内容相同的依赖可安全复用。安装记录中的依赖路径对应实际运行配置，包括安装器复制的 vendor 文件。

## 安装后检查

```sh
bio-cli --version
bio-cli doctor
peek --help
packz --help
unpackz --help
```

`doctor` 自动读取安装模式，旧版无模式标记的安装按 full 检查。JSON 的 `profile` 与每行 `required` 表明检查口径：必需依赖失败为 `ERROR` 并返回非零；可选缺失为 `OPTIONAL_MISSING`，可选版本检查失败为 `OPTIONAL_ERROR`，均不导致核心检查失败。`bio-cli doctor --profile full` 可以显式检查完整依赖；源码调用默认 full，可用 `--profile core` 检查基础依赖。它只检查路径与版本，不能代替格式能力测试。源码回归测试和环境验收要求见[开发与验证](development.md)。

## 回退与停用

安装记录保存在所选 prefix 下的 `state/bio-cli/`。回退时按记录将 `share/bio-cli/current` 链接切回上一 release；首次安装则移除本工具的 PATH 段和实际创建的托管入口（core 为 `bio-cli`、`peek`、`packz`、`unpackz`；full 另有 `dust-du`）即可停用。core 升为 full 后若手动切回旧 core release，新增加的 `dust-du` 用户入口可能成为悬空链接，应按安装收据核对该入口；已有旧 release 保留，不自动清理。Shell 已有后续编辑时，仅移除本工具标记段，不直接恢复整份旧备份。不会删除其他工具或数据。
