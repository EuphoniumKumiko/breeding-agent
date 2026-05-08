"""Candidate-region variant calling helpers for genomics MVP."""

from __future__ import annotations

import csv
import gzip
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


TARGET_GENES = ("Si9g04210.1", "Si5g31340.1", "Si9g34380.1")

CANDIDATE_VARIANT_COLUMNS = [
    "chrom",
    "pos",
    "ref",
    "alt",
    "variant_type",
    "qual",
    "filter",
    "depth",
    "source_vcf",
    "nearest_or_target_gene",
    "marker_implication",
]
KASP_COLUMNS = [
    "chrom",
    "pos",
    "ref",
    "alt",
    "gene_id",
    "kasp_readiness",
    "reason",
]
CAPS_COLUMNS = [
    "chrom",
    "pos",
    "ref",
    "alt",
    "gene_id",
    "caps_status",
    "reason",
]


class VariantCallingError(RuntimeError):
    """Base error for candidate variant calling."""


class MissingToolError(VariantCallingError):
    """Raised when required external tools are unavailable."""


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: list[str]

    @property
    def rendered(self) -> str:
        return " ".join(self.command)


def require_tools(tools: tuple[str, ...] = ("samtools", "bcftools")) -> dict[str, str]:
    """Return executable paths or raise a clear installation error."""

    resolved = {}
    missing = []
    for tool in tools:
        path = shutil.which(tool)
        if path:
            resolved[tool] = path
        else:
            missing.append(tool)

    if missing:
        raise MissingToolError(
            "Required tool(s) not found: "
            + ", ".join(missing)
            + ". Install samtools and bcftools, for example with "
            "`micromamba install -c bioconda samtools bcftools`."
        )
    return resolved


def find_bam_files(bam_dir: Path) -> list[Path]:
    """Find BAM files in a directory."""

    if not bam_dir.exists():
        raise FileNotFoundError(f"BAM directory does not exist: {bam_dir}")
    if not bam_dir.is_dir():
        raise NotADirectoryError(f"BAM path is not a directory: {bam_dir}")
    bam_files = sorted(bam_dir.glob("*.bam"))
    if not bam_files:
        raise FileNotFoundError(f"No BAM files found in: {bam_dir}")
    return bam_files


def validate_variant_calling_inputs(
    *,
    bam_dir: Path,
    reference_fasta: Path,
    regions_bed: Path,
) -> list[Path]:
    """Validate required inputs and return BAM files."""

    bam_files = find_bam_files(bam_dir)
    if not reference_fasta.exists():
        raise FileNotFoundError(f"Reference FASTA does not exist: {reference_fasta}")
    if not regions_bed.exists():
        raise FileNotFoundError(f"Regions BED does not exist: {regions_bed}")
    return bam_files


def ensure_reference_index(
    *,
    reference_fasta: Path,
    log_file: Path,
    commands: list[CommandResult],
) -> Path:
    """Ensure a samtools faidx index exists for the reference."""

    fai = Path(str(reference_fasta) + ".fai")
    if fai.exists():
        return fai
    command = ["samtools", "faidx", str(reference_fasta)]
    run_logged_command(command, log_file=log_file)
    commands.append(CommandResult(name="samtools faidx", command=command))
    return fai


def ensure_bam_indexes(
    *,
    bam_files: list[Path],
    log_file: Path,
    commands: list[CommandResult],
) -> list[Path]:
    """Ensure BAM indexes exist, creating missing .bai files with samtools."""

    index_paths = []
    for bam in bam_files:
        default_index = Path(str(bam) + ".bai")
        alternate_index = bam.with_suffix(".bai")
        if default_index.exists():
            index_paths.append(default_index)
            continue
        if alternate_index.exists():
            index_paths.append(alternate_index)
            continue
        command = ["samtools", "index", str(bam)]
        run_logged_command(command, log_file=log_file)
        commands.append(CommandResult(name="samtools index", command=command))
        index_paths.append(default_index)
    return index_paths


def call_candidate_region_variants(
    *,
    bam_files: list[Path],
    reference_fasta: Path,
    regions_bed: Path,
    variants_dir: Path,
    log_file: Path,
    commands: list[CommandResult],
) -> dict[str, Path]:
    """Run bcftools candidate-region variant calling."""

    variants_dir.mkdir(parents=True, exist_ok=True)
    mpileup_bcf = variants_dir / "candidate_regions.mpileup.bcf"
    raw_vcf = variants_dir / "candidate_regions.raw.vcf.gz"
    filtered_vcf = variants_dir / "candidate_regions.filtered.vcf.gz"

    mpileup_command = [
        "bcftools",
        "mpileup",
        "-f",
        str(reference_fasta),
        "-R",
        str(regions_bed),
        "-Ou",
        "-o",
        str(mpileup_bcf),
        *[str(path) for path in bam_files],
    ]
    call_command = [
        "bcftools",
        "call",
        "-mv",
        "-Oz",
        "-o",
        str(raw_vcf),
        str(mpileup_bcf),
    ]
    filter_command = [
        "bcftools",
        "filter",
        "-s",
        "LowQual",
        "-e",
        "QUAL<20",
        "-Oz",
        "-o",
        str(filtered_vcf),
        str(raw_vcf),
    ]

    for name, command in [
        ("bcftools mpileup", mpileup_command),
        ("bcftools call", call_command),
        ("bcftools filter", filter_command),
    ]:
        run_logged_command(command, log_file=log_file)
        commands.append(CommandResult(name=name, command=command))

    return {
        "mpileup_bcf": mpileup_bcf,
        "raw_vcf": raw_vcf,
        "filtered_vcf": filtered_vcf,
    }


def run_logged_command(command: list[str], *, log_file: Path) -> None:
    """Run an external command and append stdout/stderr to a log file."""

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n")
        completed = subprocess.run(
            command,
            stdout=log,
            stderr=log,
            text=True,
            check=False,
        )
        log.write(f"[exit_code] {completed.returncode}\n")
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, command)


def build_variant_tables_from_vcf(
    *,
    vcf_path: Path,
    tables_dir: Path,
    gff: Path | None,
    regions_bed: Path | None,
) -> dict[str, object]:
    """Parse VCF records and write candidate marker tables."""

    tables_dir.mkdir(parents=True, exist_ok=True)
    gene_intervals = read_gene_intervals(gff) if gff else []
    region_intervals = read_bed_intervals(regions_bed) if regions_bed else []
    candidate_rows = parse_vcf_candidate_variants(
        vcf_path=vcf_path,
        gene_intervals=gene_intervals,
        region_intervals=region_intervals,
    )
    snp_rows = [row for row in candidate_rows if row["variant_type"] == "SNP"]
    indel_rows = [row for row in candidate_rows if row["variant_type"] == "INDEL"]
    kasp_rows = build_kasp_candidate_rows(snp_rows)
    caps_rows = build_caps_candidate_rows(candidate_rows)

    candidate_file = tables_dir / "candidate_variants.tsv"
    snp_file = tables_dir / "snp_candidates.tsv"
    indel_file = tables_dir / "indel_candidates.tsv"
    kasp_file = tables_dir / "kasp_candidate_sites.tsv"
    caps_file = tables_dir / "caps_candidate_sites.tsv"

    write_tsv(candidate_file, CANDIDATE_VARIANT_COLUMNS, candidate_rows)
    write_tsv(snp_file, CANDIDATE_VARIANT_COLUMNS, snp_rows)
    write_tsv(indel_file, CANDIDATE_VARIANT_COLUMNS, indel_rows)
    write_tsv(kasp_file, KASP_COLUMNS, kasp_rows)
    write_tsv(caps_file, CAPS_COLUMNS, caps_rows)

    covered_genes = sorted(
        {
            row["nearest_or_target_gene"]
            for row in candidate_rows
            if row["nearest_or_target_gene"] in TARGET_GENES
        }
    )
    return {
        "candidate_rows": candidate_rows,
        "snp_rows": snp_rows,
        "indel_rows": indel_rows,
        "kasp_rows": kasp_rows,
        "caps_rows": caps_rows,
        "covered_target_genes": covered_genes,
        "outputs": {
            "candidate_variants": str(candidate_file),
            "snp_candidates": str(snp_file),
            "indel_candidates": str(indel_file),
            "kasp_candidate_sites": str(kasp_file),
            "caps_candidate_sites": str(caps_file),
        },
        "counts": {
            "candidate_variants": len(candidate_rows),
            "snps": len(snp_rows),
            "indels": len(indel_rows),
            "kasp_candidate_sites": len(kasp_rows),
            "caps_candidate_sites": len(caps_rows),
        },
    }


def parse_vcf_candidate_variants(
    *,
    vcf_path: Path,
    gene_intervals: list[dict[str, object]] | None = None,
    region_intervals: list[dict[str, object]] | None = None,
) -> list[dict[str, str]]:
    """Parse actual VCF records into candidate variant rows."""

    rows = []
    gene_intervals = gene_intervals or []
    region_intervals = region_intervals or []
    with open_text_maybe_gzip(vcf_path) as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 8:
                continue
            chrom, pos, _id, ref, alt, qual, filt, info = fields[:8]
            depth = extract_depth(info, fields[8:])
            gene_id = annotate_gene_or_region(
                chrom=chrom,
                pos=int(pos),
                gene_intervals=gene_intervals,
                region_intervals=region_intervals,
            )
            variant_type = classify_variant(ref, alt)
            rows.append(
                {
                    "chrom": chrom,
                    "pos": pos,
                    "ref": ref,
                    "alt": alt,
                    "variant_type": variant_type,
                    "qual": qual,
                    "filter": filt,
                    "depth": depth,
                    "source_vcf": str(vcf_path),
                    "nearest_or_target_gene": gene_id,
                    "marker_implication": marker_implication(variant_type),
                }
            )
    return rows


def open_text_maybe_gzip(path: Path):
    """Open plain-text or gzip-compressed VCF files."""

    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def classify_variant(ref: str, alt: str) -> str:
    """Classify a VCF REF/ALT combination."""

    alts = [item for item in alt.split(",") if item]
    if alts and all(len(ref) == 1 and len(item) == 1 for item in alts):
        return "SNP"
    if alts and any(len(ref) != len(item) for item in alts):
        return "INDEL"
    return "MIXED"


def marker_implication(variant_type: str) -> str:
    if variant_type == "SNP":
        return (
            "SNP candidate from bcftools VCF; preliminary KASP conversion possible "
            "after manual flanking-sequence review."
        )
    if variant_type == "INDEL":
        return (
            "InDel candidate from bcftools VCF; review size and flanking sequence "
            "before marker conversion."
        )
    return "Mixed or complex variant from bcftools VCF; manual review required."


def build_kasp_candidate_rows(
    snp_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build first-pass KASP candidate rows from SNPs only."""

    rows = []
    for row in snp_rows:
        alt = row["alt"]
        if "," in alt:
            readiness = "not_recommended"
            reason = "Multi-allelic SNP; first MVP does not recommend direct KASP design."
        else:
            readiness = "preliminary"
            reason = (
                "Biallelic SNP from VCF; requires manual flanking sequence review "
                "before KASP assay design."
            )
        rows.append(
            {
                "chrom": row["chrom"],
                "pos": row["pos"],
                "ref": row["ref"],
                "alt": row["alt"],
                "gene_id": row["nearest_or_target_gene"],
                "kasp_readiness": readiness,
                "reason": reason,
            }
        )
    return rows


def build_caps_candidate_rows(
    candidate_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build CAPS screening rows without inventing restriction enzyme sites."""

    return [
        {
            "chrom": row["chrom"],
            "pos": row["pos"],
            "ref": row["ref"],
            "alt": row["alt"],
            "gene_id": row["nearest_or_target_gene"],
            "caps_status": "requires_restriction_enzyme_screening",
            "reason": (
                "Do not assume an enzyme site. Screen whether this variant changes "
                "a restriction enzyme recognition sequence before CAPS/dCAPS design."
            ),
        }
        for row in candidate_rows
    ]


def extract_depth(info: str, remaining_fields: list[str]) -> str:
    """Extract depth from INFO/DP or FORMAT sample DP fields if available."""

    info_values = parse_info(info)
    if info_values.get("DP"):
        return info_values["DP"]
    if not remaining_fields:
        return ""
    format_keys = remaining_fields[0].split(":")
    if "DP" not in format_keys:
        return ""
    dp_index = format_keys.index("DP")
    depths = []
    for sample_field in remaining_fields[1:]:
        sample_values = sample_field.split(":")
        if dp_index < len(sample_values) and sample_values[dp_index].isdigit():
            depths.append(int(sample_values[dp_index]))
    return str(sum(depths)) if depths else ""


def parse_info(info: str) -> dict[str, str]:
    values = {}
    for item in info.split(";"):
        if not item:
            continue
        if "=" in item:
            key, value = item.split("=", 1)
            values[key] = value
        else:
            values[item] = "true"
    return values


def read_gene_intervals(gff: Path) -> list[dict[str, object]]:
    """Read target-gene intervals from GFF attributes."""

    if not gff.exists():
        return []
    intervals = []
    with gff.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 9:
                continue
            chrom, _source, _feature, start, end, _score, _strand, _phase, attrs = fields
            gene_id = target_gene_from_attributes(attrs)
            if not gene_id:
                continue
            intervals.append(
                {
                    "chrom": chrom,
                    "start": int(start),
                    "end": int(end),
                    "gene_id": gene_id,
                }
            )
    return intervals


def target_gene_from_attributes(attributes: str) -> str:
    for gene_id in TARGET_GENES:
        if gene_id in attributes:
            return gene_id
    return ""


def read_bed_intervals(path: Path) -> list[dict[str, object]]:
    """Read BED intervals and convert starts to 1-based inclusive coordinates."""

    if not path.exists():
        return []
    intervals = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) < 3:
                continue
            name = row[3] if len(row) > 3 else ""
            intervals.append(
                {
                    "chrom": row[0],
                    "start": int(row[1]) + 1,
                    "end": int(row[2]),
                    "name": name,
                }
            )
    return intervals


def annotate_gene_or_region(
    *,
    chrom: str,
    pos: int,
    gene_intervals: list[dict[str, object]],
    region_intervals: list[dict[str, object]],
) -> str:
    """Annotate a variant with a target gene or containing region name."""

    for interval in gene_intervals:
        if (
            interval["chrom"] == chrom
            and int(interval["start"]) <= pos <= int(interval["end"])
        ):
            return str(interval["gene_id"])
    for interval in region_intervals:
        if (
            interval["chrom"] == chrom
            and int(interval["start"]) <= pos <= int(interval["end"])
        ):
            return str(interval.get("name") or "candidate_region")
    return ""


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
