# bio-cli

面向 macOS 和 Linux 的轻量生信工具：预览常见文件、压缩文件或目录、恢复到新目标，并提供常用文件搜索与磁盘统计工具的用途总览。Python 3.8+，压缩与专用格式读取调用已有原生工具。

| 想做什么 | 命令 | 示例 |
|---|---|---|
| 预览生信文件或压缩包目录 | `peek` | `peek annotation.gff3.gz` |
| 压缩文件或目录 | `packz` | `packz project_directory` |
| 恢复到新文件或新目录 | `unpackz` | `unpackz archive.tar.zst -C restored` |
| 查看工具用途与示例 | `bio-cli tools` | `bio-cli tools` |
| 检查本机依赖路径与版本 | `bio-cli doctor` | `bio-cli doctor --json` |

所有文件名均为示例。源数据保留；已有输出不会被覆盖。`peek` 默认最多预览 200 行、1 MiB 文本，预览结果不能代替完整性检查。

## 安装

从源码安装到个人目录。先准备 `python3`、`tar`、`gzip`、`bzip2`、`xz`、`zstd`、`samtools`、`bcftools` 和 `bgzip`；安装器要求完整工具组合，下载器提供锁定版本的配套工具。详细依赖、覆盖路径及升级规则见[安装指南](docs/installation.md)。

```sh
git clone https://github.com/lianglunping/bio-cli.git
cd bio-cli
```

**Linux x86_64 / Bash：**

```sh
python3 scripts/fetch_tools.py --platform linux-x86_64 --destination "$HOME/tool_staging"
python3 scripts/install.py --tools-dir "$HOME/tool_staging/bin" --shell-file "$HOME/.bashrc"
```

**macOS arm64 / Zsh：** 先在个人环境准备 `eza`（下载清单不含 macOS eza），再执行：

```sh
python3 scripts/fetch_tools.py --platform darwin-arm64 --destination "$HOME/tool_staging"
python3 scripts/install.py --tools-dir "$HOME/tool_staging/bin" --tool "eza=$(command -v eza)" --shell-file "$HOME/.zshrc"
```

重新打开终端或 SSH 会话，然后运行 `bio-cli --version` 和 `bio-cli doctor`。默认入口位于 `$HOME/.local/share/bio-cli/current/bin`。Shell 文件按实际环境选择；自定义安装目录、缺失依赖和 PATH 问题见[安装指南](docs/installation.md)。

## 常用命令

```sh
peek -n 30 reference.fa.gz                          # 前 30 行，不是 30 条序列
peek --header alignments.bam                       # BAM 头部
peek --reference reference.fa alignments.cram      # 需要已有 reference.fa.fai
peek variants.bcf                                 # 转为 VCF 文本预览
peek -n 10 archive.tar.zst                         # 列出归档成员，不解包
peek --no-pager table.tsv                          # 直接输出；管道自动关闭分页

packz table.tsv                                   # 输出 table.tsv.zst
packz project_directory                           # 输出 project_directory.tar.zst
packz --format bgzip variants.vcf                  # 输出 BGZF；不自动建索引
unpackz table.tsv.zst -o restored.tsv
unpackz project_directory.tar.zst -C restored      # 内容在 restored/project_directory/ 下
```

`peek -n` 的单位是文本行，归档时是成员数。FASTA 跨行序列和 VCF 头部都会影响行数；`--max-bytes` 限制预览文本读取量，归档时限制成员列表输出量，不限制所有归档输入 I/O。终端分页器按 `q` 退出。更多参数、恢复限额及失败状态见[使用说明](docs/usage.md)。

## 支持范围

| 类型 | 行为与依赖 |
|---|---|
| FASTA/FASTQ、GFF/GTF、BED、VCF/gVCF、SAM、TSV/CSV 等文本 | 限量读取；支持 gzip/BGZF、zstd、xz、bzip2，压缩按魔数识别 |
| BAM / CRAM / BCF | samtools / bcftools 转为文本；CRAM 记录预览需本地参考及已有 `.fai` |
| tar 及压缩 tar、ZIP | 列出成员；ZIP 仅预览 |
| BAI/CSI/TBI、常见 BWA 索引、BigWig/BigBed、HDF5/H5AD、RDS/RData | 仅显示文件元数据，不读取对象内容 |

目录压缩使用 `.tar.zst`，默认 2 个线程、zstd 级别 3；单文件还可选 gzip/BGZF。恢复要求新目标，失败会保留临时输出或 `<目标目录名>.bio-cli-incomplete` 状态。工具不自动排序、标准化或建立索引。具体安全检查、元数据保留范围及性能边界见[使用说明](docs/usage.md)与[开发说明](docs/development.md)。

## 详细文档

| 文档 | 内容 |
|---|---|
| [使用说明](docs/usage.md) | `peek` 参数、格式边界、压缩与恢复、限额和不完整状态 |
| [配套工具](docs/tools.md) | `rg`、`fd`、`eza`、`dua` 的生信场景与示例 |
| [安装与恢复](docs/installation.md) | 依赖、个人目录安装、升级、失败恢复和回退 |
| [开发与验证](docs/development.md) | 源码结构、合成回归、自动测试、性能与上游来源 |
| [变更记录](CHANGELOG.md) | 已发布版本与未发布改动 |

配套工具都是独立命令；运行 `bio-cli tools` 查看总览，`NAME --help` 查看各自参数。版本以 [VERSION](VERSION) 为准。
