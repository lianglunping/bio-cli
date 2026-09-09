# bio-cli

面向 macOS 和 Linux 的轻量生信文件预览、压缩和恢复工具。需要 Python 3.8+；专用格式调用已有命令行工具。所有示例均为合成名称，不附带真实数据、服务器配置或访问凭据。

## 使用

```sh
bio-cli tools                 # 工具总览、用途和示例
bio-cli doctor                # 只读检查本机工具路径和版本
peek annotation.gff3.gz
peek -n 30 reference.fa.gz
peek reference.fa.fai
peek --header alignments.bam
peek variants.bcf
peek --reference reference.fa alignments.cram
peek archive.tar.zst
peek --timeout 10 variants.bcf
peek --no-pager variants.vcf.gz | head -10

packz table.tsv
packz project_directory
packz --format gzip reads.fastq
packz --format bgzip variants.vcf
packz -t 2 -l 6 -o archive.tar.zst project_directory
unpackz table.tsv.zst -o restored.tsv
unpackz archive.tar.zst -C new_restore_directory
unpackz archive.tar.zst -C bounded_restore --max-members 100000 --max-output-bytes 10737418240
```

`peek` 默认最多预览 200 行、1 MiB；`-n` 是行数，不是序列数或变异数，`--max-bytes` 可调整字节上限。长行会被截断，提示在标准错误流。终端使用 `less` 分页；管道不添加颜色或行号。终端控制字符会转义。预览不等于完整性检查；只有读完整个压缩流才会遇到末尾校验和，提前截断不声称排除了后部损坏。输出顺序和生物学坐标不变。

支持 FASTA/FASTQ、GFF/GFF3/GTF、BED/bedGraph/WIG、VCF/gVCF、SAM、TSV/CSV/MTX、FAI/DICT、文本 ANN/AMB 及 gzip/BGZF、zstd、xz、bzip2 压缩文本。压缩按文件魔数识别。BAM/CRAM 使用 samtools，BCF 使用 bcftools。CRAM 记录预览要求本地参考及已有 `.fai`；头部查看不需要参考。不会自动创建索引、排序、标准化或查询远程数据。

BAI/CSI/TBI/GZI、BWA/BWA-MEM2 的 PAC/BWT/SA/0123/BWT.2bit.64 索引只显示元数据；BigWig/BigBed/HDF5/H5AD/RDS/RData 首版只标识类别，不读取对象内容。普通文本 `.ann`、`.amb` 不误判为二进制。归档支持 tar、tar.gz/tgz、tar.zst/tzst、tar.xz/txz、tar.bz2/tbz2、ZIP 的目录列表；ZIP 中央目录由 Python 标准库读取，含极多成员的 ZIP 仍可能占较多内存。

`packz` 默认 zstd 级别 3、2 个工作线程，源文件保留，目录输出 `.tar.zst` 并放在源目录外。单文件可选 gzip 或 BGZF；gzip 为单线程，线程参数不改变它。BGZF 与普通 gzip 都可用 `.gz` 后缀，但只有 BGZF 提供分块随机访问基础；本工具不会自动创建索引。gzip/BGZF 的级别最高为 9，高于 9 的参数按 9 使用。

压缩写入唯一临时文件，完整性测试成功后以同文件系统硬链接实现原子且不覆盖的发布。如果文件系统不支持硬链接，发布会失败并保留临时文件。打包和压缩任一阶段报错均不发布正式输出。打包前会遍历目录，拒绝绝对或逃逸符号链接及 FIFO/设备等恢复端不支持的成员，不跟随外部链接、不静默跳过文件。额外预检增加一次目录元数据遍历，海量小文件和共享存储上可能耗时；它不是并发修改防护或快照。压缩过程中不要修改源目录；tar 返回成功并非文件系统快照，也不保证捕捉所有并发修改。单文件检查压缩前后大小、时间和 inode。

`unpackz` 支持 gzip/BGZF、zstd、xz、bzip2 单文件及上述 tar 归档。`-C` 显式选择 tar 目录恢复，`-o` 显式选择单个压缩流恢复，两者互斥，显式选择优先于文件后缀。例如目录打包为 `backup.zst` 后可用 `unpackz backup.zst -C restored`；压缩已有 tar 文件后可用 `unpackz existing.tar.zst -o restored.tar` 恢复 tar 文件本身。未指定模式时，仅用后缀提供默认分类。ZIP 仅预览，不解包。拒绝覆盖目标；目录恢复要求新的目标目录。绝对路径、`..`、逃逸符号链接和特殊设备成员被拒绝。正常内部符号链接与已出现目标的硬链接可恢复；前向硬链接拒绝。恢复期间会在目标目录旁创建 `<目标目录名>.bio-cli-incomplete` 状态文件；只有内容及权限/时间全部处理成功才删除。失败时该相邻状态文件保留，目录内也尽力保留 `.bio-cli-incomplete` 兼容标记。只读根目录可能阻止目录内标记写入，因此以相邻状态文件为准；不会自动删除失败目录或原始归档。归档根层的 `.bio-cli-incomplete` 成员名被保留给状态管理，冲突会报错。保留常规权限、文件修改时间及内部链接；不保证 ACL、扩展属性、资源叉、所有者或文件系统快照语义。单文件压缩只保留内容，不保存原权限与时间。

恢复限额均为可选正整数，默认不设上限。`--max-members` 限制 tar 实际成员条目数（目录与链接也计入）；`--max-output-bytes` 限制 tar 普通文件声明大小之和，或单个压缩流实际恢复的字节数。例如上面的命令允许最多 100000 个 tar 成员和 10 GiB 文件内容。限额触发时退出、保留不完整状态，不发布单文件正式目标。它们不衡量物理磁盘用量、不限制所有归档元数据和输入 I/O，也不保证处理任意恶意归档的固定内存上限。

## peek 参数与场景

运行 `peek --help` 可在终端直接查看中文说明和示例，无需额外输入 `peek` 子命令或 Python 脚本名。

| 目的 | 命令示例 | 说明 |
|---|---|---|
| 预览注释 | `peek annotation.gff3.gz` | 直接读取压缩内容；同样支持 GTF |
| 预览参考序列 | `peek -n 30 reference.fa.gz` | 前 30 行，可能包含跨行序列的一部分 |
| 预览测序数据 | `peek -n 20 reads.fastq.gz` | 标准四行 FASTQ 且未触及字节上限时为 5 条记录 |
| 预览变异 | `peek -n 50 variants.vcf.gz` | 元信息、表头均计入 50 行，并非 50 个变异 |
| 查看比对头部 | `peek --header alignments.bam` | 仍受行数与字节上限限制 |
| 查看 CRAM 记录 | `peek --reference reference.fa alignments.cram` | 要求本地参考及已有的 reference.fa.fai |
| 查看 BCF | `peek variants.bcf` | 由 bcftools 输出 VCF 文本 |
| 查看压缩包目录 | `peek -n 10 archive.tar.zst` | 列出前 10 个成员，不解包到磁盘 |
| 限制预览大小 | `peek --max-bytes 65536 large.tsv.zst` | 设置 64 KiB 上限，参数填写整数 |
| 直接输出 | `peek --no-pager table.tsv` | 不进入分页器；管道也自动禁用分页 |
| 文件名含空格 | `peek "sample notes.tsv"` | 使用引号 |
| 文件名以短横线开头 | `peek -- -sample.fa` | 用 `--` 结束选项解析 |

`--timeout 10` 为本次预览启动的解压／格式转换后端设置 10 秒期限；超时会终止该进程组并报错，默认不设置期限。它不能打断 Python 主进程陷入的共享文件系统读取，也不是整个命令的硬性墙钟限制。普通未压缩文本没有这样的后端。

分页器中按 `q` 退出、`/` 搜索、空格翻页。`--header` 只适用于 BAM/CRAM/BCF，文本格式使用 `-n`。二进制索引显示元数据属于预期行为，不表示文件损坏。

## rg / fd / eza / dua 配套工具

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

## 性能设计

Python 负责命令入口、限量预览、终端转义和安全恢复；压缩与专用格式读取调用原生 zstd/gzip/bgzip、samtools/bcftools。压缩过程中不使用 Python 逐字节执行压缩算法，目录打包的 tar 输出直接交给压缩器。

性能取决于启动开销、解压吞吐、存储速度、归档成员位置和安全检查。文本转义使用编译后的控制字符扫描，避免对普通文本逐字符执行 Python 循环。目录恢复仍包含 Python tar 解析和逐成员路径检查，海量小文件与反复启动进程的批处理可能受其影响；不能把本工具视为原生命令的零开销替代品。tar 流式处理不再缓存所有普通成员对象，仅保留恢复目录权限和时间所需的目录记录，并从最深目录开始应用元数据，避免父目录先变为只读而阻断子目录。外部后端共用进程生命周期管理，错误诊断最多保留 64 KiB，版本探测每个输出流最多保留 8 KiB；退出、预览截断和超时会清理所拥有的进程组。主动脱离进程组的进程不属于该回收保证。

全量重写需先用同一数据和同等校验要求比较，不能只凭实现语言预测提速。

## 安装

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

## 验证与回退

升级会识别 `current/bin` 和个人 `bin` 中的托管入口，复用其真实依赖，避免包装器调用自身。安装通过原子创建互斥目录锁定同一 prefix，不依赖共享文件系统可能不支持的 flock/lockf；另一个安装器遇到锁时明确退出。锁内记录主机和 PID；强制终止可能遗留锁，必须确认原安装器已经停止后再人工恢复，安装器不会自动夺取或删除已有锁。安装器先在独立临时目录构建并检查入口，再发布完整 release；构建失败保留未激活临时目录，重试使用新的临时目录。完整 release 复用时校验托管入口的内容和可执行权限，不重写入口；被改动的入口会使重装在激活前失败。激活和 Shell/收据处理若抛出异常，会尝试恢复旧 current、配置及本次新建入口，失败细节保存在安装状态目录；突然断电或强制终止不等于可捕获异常，恢复前仍须检查 current 和收据状态。

同一源码 release 的运行配置保持固定；重装时显式指定与已安装配置不同的 `--tool` 会报错，应使用新的个人 `--prefix`；从同一 staging 重试时，已复制到 vendor 且内容相同的依赖可安全复用。安装记录中的依赖路径对应实际运行配置，包括安装器复制的 vendor 文件。

tar 目录预览达到请求的条数后立即停止，不为寻找下一条记录而读完当前文件载荷；因此即使归档恰好只有这些条目，也会提示预览上限。查看更靠后的成员仍需要扫描前面的载荷，`--max-bytes` 限制输出而非所有输入 I/O。完整校验需单独执行。

```sh
python3 -m unittest discover -s tests -v
peek --version
packz --help
unpackz --help
```

测试在临时目录生成明确标识的合成数据，覆盖文本压缩、BAM/BCF/CRAM、链接、目录恢复、内容哈希、错误输入、拒绝覆盖、路径逃逸及限量读取；另覆盖超时与中断回收、继承管道的子进程、海量诊断输出、下载／写入故障、并发发布、恢复限额、乱序目录元数据及入口完整性。测试需要上述生信依赖，不用跳过用例代替通过。

安装记录保存在所选 prefix 下的 `state/bio-cli/`。回退时按记录将 `share/bio-cli/current` 链接切回上一 release；首次安装则移除本工具的 PATH 段和五个托管入口（`bio-cli`、`peek`、`packz`、`unpackz`、`dust-du`）即可停用。Shell 已有后续编辑时，仅移除本工具标记段，不直接恢复整份旧备份。不会删除其他工具或数据。

## 开发与来源

版本见 `VERSION`；代码通过 Git 提交记录版本。官方上游：
[gdu](https://github.com/dundee/gdu)、[dust](https://github.com/bootandy/dust)、[dua](https://github.com/Byron/dua-cli)、[bat](https://github.com/sharkdp/bat)、[ripgrep](https://github.com/BurntSushi/ripgrep)、[fd](https://github.com/sharkdp/fd)、[eza](https://github.com/eza-community/eza)、[zstd](https://github.com/facebook/zstd)、[HTSlib](https://www.htslib.org/)。上游软件遵循各自许可，不作为本仓库二进制附件发布。
