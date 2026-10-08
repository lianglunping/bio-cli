# 配套工具指南

[返回首页](../README.md) · [安装与恢复](installation.md)

先运行 `bio-cli tools` 查看全部工具的中文用途及示例；运行 `bio-cli doctor` 或 `bio-cli doctor --json` 检查实际依赖路径和版本。诊断最多等待每个工具 15 秒，不安装软件、不改配置、不扫描研究目录；仅路径和版本检查，不等于完整格式能力验收，输出含本机路径，公开分享前应检查。

这四个工具都是独立命令，直接在终端运行，不是 `peek` 的子命令，因此不列在 `peek --help` 中。`peek` 用于限量预览；下面的工具分别用于搜索内容、寻找文件、浏览目录和统计磁盘占用。

| 工具 | 主要用途 | 入门示例 |
|---|---|---|
| `rg`（ripgrep） | 搜索文本内容 | `rg -n 'gene_id' annotation.gtf` |
| `fd` | 按文件名或后缀查找文件 | `fd -t f -e bam .` |
| `eza` | 显示文件大小、权限、时间和目录层级 | `eza -l --group-directories-first .` |
| `dua` | 扫描文件或目录的磁盘占用 | `dua aggregate results/ reference/` |

以下目录名和文件名均为示例，请替换为自己的输入。

### rg：搜索日志和生信文本内容

```sh
# 输出匹配行及其行号；默认按正则表达式解释搜索模式
rg -n 'gene_id' annotation.gtf
rg -n 'ERROR|Traceback|failed' logs/

# 递归搜索时只选择 GFF3 文件；-F 表示按普通字符串搜索
rg -n -F -g '*.gff3' 'ID=example_gene;' annotations/

# 搜索 gzip/BGZF 压缩注释的解压文本，不生成解压文件
gzip -dc annotation.gff3.gz | rg -n -F 'ID=example_gene;'
```

`rg` 搜索的是文本，不理解基因模型、VCF 字段或基因组区间。BAM/CRAM/BCF 的内容和区间查询应使用 samtools/bcftools 等专用工具；不能直接把二进制文件当文本搜索。默认递归搜索会跳过隐藏文件和被忽略规则排除的文件，需要包括这些文件时可显式使用 `rg --hidden --no-ignore ...`。`peek ... | rg ...` 只搜索预览范围，不能用于判断全文件是否存在某条记录。以上 gzip 管道会扫描完整压缩流，开销随文件大小增加。

### fd：按名字寻找 FASTQ、比对文件和目录

```sh
# 在当前目录及子目录寻找 BAM 文件
fd -t f -e bam .

# 在 reads/ 下寻找普通或 gzip 压缩的 FASTQ 文件
fd -t f '\.(fastq|fq)(\.gz)?$' reads/

# 在当前目录下寻找名字包含 result 的目录
fd -t d result .

# 包括隐藏文件及被忽略规则排除的文件
fd --hidden --no-ignore -t f -e vcf .
```

`fd` 搜索文件名，默认模式为正则表达式；不检查文件内容。默认跳过隐藏文件和被忽略规则排除的文件。因此，普通 `fd` 输出不能直接作为完整数据清单。

### eza：查看目录、文件大小和层级

```sh
# 长列表：权限、大小、时间等；目录排在前面
eza -l --group-directories-first .

# 同时显示隐藏文件
eza -la .

# 显示两层目录树，避免把深层目录全部展开
eza --tree --level=2 reference/
```

`eza` 长列表中的目录大小不是递归汇总的目录内容大小；统计目录占用请用 `dua`。本项目提供 `eza` 命令，不自动修改已有的 `ls`、`ll` 或 `l` 别名。

### dua：统计目录占用

```sh
# 分别统计两个目录，并显示总计
dua aggregate results/ reference/

# 不提供路径时，分别汇总当前目录下的条目
dua aggregate

# 按文件逻辑大小统计，与默认的磁盘占用口径区分
dua aggregate --apparent-size results/
```

这些 `aggregate` 示例只统计，不删除文件。本项目的 `dua` 入口默认使用 2 个扫描线程。目录扫描会遍历内容，海量小文件可能耗时；权限不足会使结果不完整，应查看错误提示。逻辑大小与实际磁盘占用可能因稀疏文件、压缩等因素不同。交互界面可通过 `dua interactive` 打开，但其中包含删除操作，不属于上述统计示例。

### 查找命令入口与帮助

```sh
command -v rg fd eza dua
rg --help
fd --help
eza --help
dua --help
```

如果安装后旧终端提示 `command not found`，请重新打开终端或 SSH 会话，让安装时选择的 Shell 配置生效。默认安装目录的命令入口位于 `$HOME/.local/share/bio-cli/current/bin`；可先用该目录下的完整命令路径检查，例如 `"$HOME/.local/share/bio-cli/current/bin/rg" --version`。自定义 `--prefix` 时应使用对应 prefix 下的 `share/bio-cli/current/bin`。新会话仍找不到时，检查是否为实际使用的 Shell 指定了正确配置文件，以及该目录是否在 PATH 中。
