# bio-cli

面向 macOS 和 Linux 的轻量生信文件预览、压缩和恢复工具。需要 Python 3.8+；专用格式调用已有命令行工具。所有示例均为合成名称，不附带真实数据、服务器配置或访问凭据。

## 使用

```sh
peek annotation.gff3.gz
peek -n 30 reference.fa.gz
peek reference.fa.fai
peek --header alignments.bam
peek variants.bcf
peek --reference reference.fa alignments.cram
peek archive.tar.zst
peek --no-pager variants.vcf.gz | head -10

packz table.tsv
packz project_directory
packz --format gzip reads.fastq
packz --format bgzip variants.vcf
packz -t 2 -l 6 -o archive.tar.zst project_directory
unpackz table.tsv.zst -o restored.tsv
unpackz archive.tar.zst -C new_restore_directory
```

`peek` 默认最多预览 200 行、1 MiB；`-n` 是行数，不是序列数或变异数，`--max-bytes` 可调整字节上限。长行会被截断，提示在标准错误流。终端使用 `less` 分页；管道不添加颜色或行号。终端控制字符会转义。预览不等于完整性检查；只有读完整个压缩流才会遇到末尾校验和，提前截断不声称排除了后部损坏。输出顺序和生物学坐标不变。

支持 FASTA/FASTQ、GFF/GFF3/GTF、BED/bedGraph/WIG、VCF/gVCF、SAM、TSV/CSV/MTX、FAI/DICT、文本 ANN/AMB 及 gzip/BGZF、zstd、xz、bzip2 压缩文本。压缩按文件魔数识别。BAM/CRAM 使用 samtools，BCF 使用 bcftools。CRAM 记录预览要求本地参考及已有 `.fai`；头部查看不需要参考。不会自动创建索引、排序、标准化或查询远程数据。

BAI/CSI/TBI/GZI、BWA/BWA-MEM2 的 PAC/BWT/SA/0123/BWT.2bit.64 索引只显示元数据；BigWig/BigBed/HDF5/H5AD/RDS/RData 首版只标识类别，不读取对象内容。普通文本 `.ann`、`.amb` 不误判为二进制。归档支持 tar、tar.gz/tgz、tar.zst/tzst、tar.xz/txz、tar.bz2/tbz2、ZIP 的目录列表；ZIP 中央目录由 Python 标准库读取，含极多成员的 ZIP 仍可能占较多内存。

`packz` 默认 zstd 级别 3、2 个工作线程，源文件保留，目录输出 `.tar.zst` 并放在源目录外。单文件可选 gzip 或 BGZF；gzip 为单线程，线程参数不改变它。BGZF 与普通 gzip 都可用 `.gz` 后缀，但只有 BGZF 提供分块随机访问基础；本工具不会自动创建索引。gzip/BGZF 的级别最高为 9，高于 9 的参数按 9 使用。

压缩写入唯一临时文件，完整性测试成功后以同文件系统硬链接实现原子且不覆盖的发布。如果文件系统不支持硬链接，发布会失败并保留临时文件。打包和压缩任一阶段报错均不发布正式输出。压缩过程中不要修改源目录；tar 返回成功并非文件系统快照，也不保证捕捉所有并发修改。单文件检查压缩前后大小、时间和 inode。

`unpackz` 支持 gzip/BGZF、zstd、xz、bzip2 单文件及上述 tar 归档。ZIP 仅预览，不解包。拒绝覆盖目标；目录恢复要求新的目标目录。绝对路径、`..`、逃逸符号链接和特殊设备成员被拒绝。正常内部符号链接与已出现目标的硬链接可恢复；前向硬链接拒绝。失败的恢复目录保留 `.bio-cli-incomplete` 标志。保留常规权限、文件修改时间及内部链接；不保证 ACL、扩展属性、资源叉、所有者或文件系统快照语义。单文件压缩只保留内容，不保存原权限与时间。

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

分页器中按 `q` 退出、`/` 搜索、空格翻页。`--header` 只适用于 BAM/CRAM/BCF，文本格式使用 `-n`。二进制索引显示元数据属于预期行为，不表示文件损坏。

## 性能设计

Python 负责命令入口、限量预览、终端转义和安全恢复；压缩与专用格式读取调用原生 zstd/gzip/bgzip、samtools/bcftools。压缩过程中不使用 Python 逐字节执行压缩算法，目录打包的 tar 输出直接交给压缩器。

性能取决于启动开销、解压吞吐、存储速度、归档成员位置和安全检查。文本转义使用编译后的控制字符扫描，避免对普通文本逐字符执行 Python 循环。目录恢复仍包含 Python tar 解析和逐成员路径检查，海量小文件与反复启动进程的批处理可能受其影响；不能把本工具视为原生命令的零开销替代品。全量重写需先用同一数据和同等校验要求比较，不能只凭实现语言预测提速。

## 安装

依赖：`python3`, `tar`, `gzip`, `bzip2`, `xz`, `zstd`, `samtools`, `bcftools`, `bgzip`。完整工具组合另含 `gdu`, `dust-du`, `dua`, `bat`, `rg`, `fd`, `eza`。本项目不执行系统级包安装，不修改 Conda base，不替换传统 `du/cat/ls`。

```sh
python3 scripts/fetch_tools.py --platform linux-x86_64 --destination "$HOME/tool_staging"
python3 scripts/install.py --tools-dir "$HOME/tool_staging/bin" --shell-file "$HOME/.bashrc"
# macOS 使用 --platform darwin-arm64，Shell 文件按实际选择 .zshrc。
# 无官方 macOS eza 二进制时，先在个人环境安装 eza，再用 --tool eza=/path/to/eza 指定。
# 所有依赖都支持 --tool NAME=/path/to/executable；--prefix 可指定个人安装目录。
```

下载清单固定官方发布版本和 SHA-256。下载工具只提取预期可执行文件；原始归档留在用户指定的 staging 中。安装器复用可用工具，缺失工具可来自 staging。安装前检查版本，独立保留每个 release，生成的 `runtime.json` 和安装记录仅在本机。Shell 仅添加一段 PATH，并保存原文件备份。公开仓库不会包含这些本地记录。

磁盘工具：`gdu` 包装入口默认 `--no-delete --no-spawn-shell -m 2`；`dua` 和 `dust-du` 默认 2 个扫描线程。`dust-du` 的名字避免遮蔽生信环境可能已有的 `dust`。`dua` 的交互模式本身具有删除功能，工具安装不代表执行清理；使用者需自行决定操作。共享存储的扫描开销取决于元数据服务，不承诺并发一定提速。

## 验证与回退

升级会识别 `current/bin` 和个人 `bin` 中的托管入口，复用其真实依赖，避免包装器调用自身。同一源码 release 的运行配置保持固定；重装时显式指定与已安装配置不同的 `--tool` 会报错，应使用新的个人 `--prefix`。安装记录中的依赖路径对应实际运行配置，包括安装器复制的 vendor 文件。

tar 目录预览达到请求的条数后立即停止，不为寻找下一条记录而读完当前文件载荷；因此即使归档恰好只有这些条目，也会提示预览上限。查看更靠后的成员仍需要扫描前面的载荷，`--max-bytes` 限制输出而非所有输入 I/O。完整校验需单独执行。

```sh
python3 -m unittest discover -s tests -v
peek --version
packz --help
unpackz --help
```

测试在临时目录生成明确标识的合成数据，覆盖文本压缩、BAM/BCF/CRAM、链接、目录恢复、内容哈希、错误输入、拒绝覆盖、路径逃逸及限量读取。测试需要上述生信依赖，不用跳过用例代替通过。

安装记录保存在所选 prefix 下的 `state/bio-cli/`。回退时按记录将 `share/bio-cli/current` 链接切回上一 release；首次安装则移除本工具的 PATH 段和四个托管入口即可停用。Shell 已有后续编辑时，仅移除本工具标记段，不直接恢复整份旧备份。不会删除其他工具或数据。

## 开发与来源

版本见 `VERSION`；代码通过 Git 提交记录版本。官方上游：
[gdu](https://github.com/dundee/gdu)、[dust](https://github.com/bootandy/dust)、[dua](https://github.com/Byron/dua-cli)、[bat](https://github.com/sharkdp/bat)、[ripgrep](https://github.com/BurntSushi/ripgrep)、[fd](https://github.com/sharkdp/fd)、[eza](https://github.com/eza-community/eza)、[zstd](https://github.com/facebook/zstd)、[HTSlib](https://www.htslib.org/)。上游软件遵循各自许可，不作为本仓库二进制附件发布。
