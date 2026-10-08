"""Dependency groups shared by personal installation and read-only diagnostics."""

CORE_TOOLS = ('python3', 'tar', 'gzip', 'bzip2', 'xz', 'zstd')
BIO_TOOLS = ('samtools', 'bcftools', 'bgzip')
COMPANION_TOOLS = ('gdu', 'dust-du', 'dua', 'bat', 'rg', 'fd', 'eza')
KNOWN_TOOLS = CORE_TOOLS + BIO_TOOLS + COMPANION_TOOLS
PROFILES = ('full', 'core')


def required_tools(profile):
    if profile not in PROFILES:
        raise ValueError('Unknown installation profile: ' + str(profile))
    return KNOWN_TOOLS if profile == 'full' else CORE_TOOLS
