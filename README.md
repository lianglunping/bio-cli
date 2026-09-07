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
