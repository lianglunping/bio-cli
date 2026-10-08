# 文件预览、压缩与恢复

[返回首页](../README.md) · [安装与恢复](installation.md)

## peek：基本用法

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
```

## peek：格式与预览边界

`peek` 默认最多预览 200 行、1 MiB；`-n` 是行数，不是序列数或变异数，`--max-bytes` 可调整字节上限。长行会被截断，提示在标准错误流。终端使用 `less` 分页；管道不添加颜色或行号。终端控制字符会转义。预览不等于完整性检查；只有读完整个压缩流才会遇到末尾校验和，提前截断不声称排除了后部损坏。输出顺序和生物学坐标不变。

支持 FASTA/FASTQ、GFF/GFF3/GTF、BED/bedGraph/WIG、VCF/gVCF、SAM、TSV/CSV/MTX、FAI/DICT、文本 ANN/AMB 及 gzip/BGZF、zstd、xz、bzip2 压缩文本。压缩按文件魔数识别。BAM/CRAM 使用 samtools，BCF 使用 bcftools。CRAM 记录预览要求本地参考及已有 `.fai`；头部查看不需要参考。不会自动创建索引、排序、标准化或查询远程数据。

BAI/CSI/TBI/GZI、BWA/BWA-MEM2 的 PAC/BWT/SA/0123/BWT.2bit.64 索引只显示元数据；BigWig/BigBed/HDF5/H5AD/RDS/RData 首版只标识类别，不读取对象内容。普通文本 `.ann`、`.amb` 不误判为二进制。归档支持 tar、tar.gz/tgz、tar.zst/tzst、tar.xz/txz、tar.bz2/tbz2、ZIP 的目录列表；ZIP 中央目录由 Python 标准库读取，含极多成员的 ZIP 仍可能占较多内存。



## peek：参数与场景

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

## packz / unpackz：基本用法

```sh
packz table.tsv
packz project_directory
packz --format gzip reads.fastq
packz --format bgzip variants.vcf
packz -t 2 -l 6 -o archive.tar.zst project_directory
unpackz table.tsv.zst -o restored.tsv
unpackz archive.tar.zst -C new_restore_directory
unpackz archive.tar.zst -C bounded_restore --max-members 100000 --max-output-bytes 10737418240
```

## packz：格式、线程与输出

`packz` 默认 zstd 级别 3、2 个工作线程，源文件保留，目录输出 `.tar.zst` 并放在源目录外。单文件可选 gzip 或 BGZF；gzip 为单线程，线程参数不改变它。BGZF 与普通 gzip 都可用 `.gz` 后缀，但只有 BGZF 提供分块随机访问基础；本工具不会自动创建索引。gzip/BGZF 的级别最高为 9，高于 9 的参数按 9 使用。

## packz：发布与源目录约定

压缩写入唯一临时文件，完整性测试成功后以同文件系统硬链接实现原子且不覆盖的发布。如果文件系统不支持硬链接，发布会失败并保留临时文件。打包和压缩任一阶段报错均不发布正式输出。打包前会遍历目录，拒绝绝对或逃逸符号链接及 FIFO/设备等恢复端不支持的成员，不跟随外部链接、不静默跳过文件。额外预检增加一次目录元数据遍历，海量小文件和共享存储上可能耗时；它不是并发修改防护或快照。压缩过程中不要修改源目录；tar 返回成功并非文件系统快照，也不保证捕捉所有并发修改。单文件检查压缩前后大小、时间和 inode。

## unpackz：恢复模式与状态

`unpackz` 支持 gzip/BGZF、zstd、xz、bzip2 单文件及上述 tar 归档。`-C` 显式选择 tar 目录恢复，`-o` 显式选择单个压缩流恢复，两者互斥，显式选择优先于文件后缀。例如目录打包为 `backup.zst` 后可用 `unpackz backup.zst -C restored`；压缩已有 tar 文件后可用 `unpackz existing.tar.zst -o restored.tar` 恢复 tar 文件本身。未指定模式时，仅用后缀提供默认分类。ZIP 仅预览，不解包。拒绝覆盖目标；目录恢复要求新的目标目录。绝对路径、`..`、逃逸符号链接和特殊设备成员被拒绝。正常内部符号链接与已出现目标的硬链接可恢复；前向硬链接拒绝。恢复期间会在目标目录旁创建 `<目标目录名>.bio-cli-incomplete` 状态文件；只有内容及权限/时间全部处理成功才删除。失败时该相邻状态文件保留，目录内也尽力保留 `.bio-cli-incomplete` 兼容标记。只读根目录可能阻止目录内标记写入，因此以相邻状态文件为准；不会自动删除失败目录或原始归档。归档根层的 `.bio-cli-incomplete` 成员名被保留给状态管理，冲突会报错。保留常规权限、文件修改时间及内部链接；不保证 ACL、扩展属性、资源叉、所有者或文件系统快照语义。单文件压缩只保留内容，不保存原权限与时间。

## unpackz：成员与字节限额

恢复限额均为可选正整数，默认不设上限。`--max-members` 限制 tar 实际成员条目数（目录与链接也计入）；`--max-output-bytes` 限制 tar 普通文件声明大小之和，或单个压缩流实际恢复的字节数。例如上面的命令允许最多 100000 个 tar 成员和 10 GiB 文件内容。限额触发时退出、保留不完整状态，不发布单文件正式目标。它们不衡量物理磁盘用量、不限制所有归档元数据和输入 I/O，也不保证处理任意恶意归档的固定内存上限。

## tar 目录预览的读取范围

tar 目录预览达到请求的条数后立即停止，不为寻找下一条记录而读完当前文件载荷；因此即使归档恰好只有这些条目，也会提示预览上限。查看更靠后的成员仍需要扫描前面的载荷，`--max-bytes` 限制输出而非所有输入 I/O。完整校验需单独执行。
