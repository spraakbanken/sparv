"""SBX specific annotation and export functions related to the stats export."""
from pathlib import Path
from typing import Optional

from sparv.api import (
    AllSourceFilenames,
    Annotation,
    AnnotationAllSourceFiles,
    Config,
    Corpus,
    Export,
    ExportInput,
    MarkerOptional,
    Output,
    OutputMarker,
    SparvErrorMessage,
    annotator,
    exporter,
    get_logger,
    installer,
    uninstaller,
    util,
)

from .stats_export import freq_list
from .utils import compress

logger = get_logger(__name__)


@annotator("Extract the complemgram with the highest score", language=["swe"])
def best_complemgram(
        out: Output = Output("<token>:stats_export.complemgram_best", description="Complemgram annotation with highest score"),
        complemgram: Annotation = Annotation("<token>:saldo.complemgram")):
    """Extract the complemgram with the highest score."""
    from sparv.modules.misc import misc
    misc.best_from_set(out, complemgram, is_sorted=True)


@annotator("Extract the sense with the highest score", language=["swe"])
def best_sense(
        out: Output = Output("<token>:stats_export.sense_best", description="Sense annotation with highest score"),
        sense: Annotation = Annotation("<token>:wsd.sense")):
    """Extract the sense annotation with the highest score."""
    from sparv.modules.misc import misc
    misc.best_from_set(out, sense, is_sorted=True)


@annotator("Extract the first baseform annotation from a set of baseforms", language=["swe"])
def first_baseform(
        out: Output = Output("<token>:stats_export.baseform_first", description="First baseform from a set of baseforms"),
        baseform: Annotation = Annotation("<token:baseform>")):
    """Extract the first baseform annotation from a set of baseforms."""
    from sparv.modules.misc import misc
    misc.first_from_set(out, baseform)


@annotator("Extract the first lemgram annotation from a set of lemgrams", language=["swe"])
def first_lemgram(
        out: Output = Output("<token>:stats_export.lemgram_first", description="First lemgram from a set of lemgrams"),
        lemgram: Annotation = Annotation("<token>:saldo.lemgram")):
    """Extract the first lemgram annotation from a set of lemgrams."""
    from sparv.modules.misc import misc
    misc.first_from_set(out, lemgram)


@annotator("Get the best complemgram if the token is lacking a sense annotation", language=["swe"])
def conditional_best_complemgram(
    out_complemgrams: Output = Output("<token>:stats_export.complemgram_best_cond",
                                      description="Compound analysis using lemgrams"),
    complemgrams: Annotation = Annotation("<token>:stats_export.complemgram_best"),
    sense: Annotation = Annotation("<token:sense>")):
    """Get the best complemgram if the token is lacking a sense annotation."""
    all_annotations = list(complemgrams.read_attributes((complemgrams, sense)))
    short_complemgrams = []
    for complemgram, sense in all_annotations:
        if sense and sense != "|":
            complemgram = ""
        short_complemgrams.append(complemgram)
    out_complemgrams.write(short_complemgrams)


@exporter("Corpus word frequency list", language=["swe"], order=1)
def sbx_freq_list(
    source_files: AllSourceFilenames = AllSourceFilenames(),
    word: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:word>"),
    token: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>"),
    msd: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:msd>"),
    baseform: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>:stats_export.baseform_first"),
    sense: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>:stats_export.sense_best"),
    lemgram: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>:stats_export.lemgram_first"),
    complemgram: AnnotationAllSourceFiles = AnnotationAllSourceFiles(
                                            "<token>:stats_export.complemgram_best_cond"),
    out: Export = Export("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    delimiter: str = Config("stats_export.delimiter"),
    cutoff: int = Config("stats_export.cutoff")):
    """Create a word frequency list for the entire corpus.

    Args:
        source_files: The source files belonging to this corpus.
        word: Word annotations.
        token: Token span annotations.
        msd: MSD annotations.
        baseform: Annotations with first baseform from each set.
        sense: Best sense annotations.
        lemgram: Annotations with first lemgram from each set.
        complemgram: Conditional best compound lemgram annotations.
        out: The output word frequency file.
        delimiter: Column delimiter to use in the csv.
        cutoff: The minimum frequency a word must have in order to be included in the result.
    """
    annotations = [(word, "token"), (msd, "POS"), (baseform, "lemma"), (sense, "SALDO sense"), (lemgram, "lemgram"),
                   (complemgram, "compound")]

    freq_list(source_files=source_files, word=word, token=token, annotations=annotations, source_annotations=[],
              out=out, sparv_namespace="", source_namespace="", delimiter=delimiter, cutoff=cutoff)


@exporter("Corpus word frequency list (compressed)", language=["swe"], order=1)
def sbx_freq_list_compressed(
    stats_file: ExportInput = ExportInput("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    out_file: Export = Export("stats_export.frequency_list_sbx/stats_[metadata.id].csv.[stats_export.compression]"),
    compression: str = Config("stats_export.compression"),
) -> None:
    """Compress statistics file.

    Args:
        stats_file: Path to statistics file.
        out_file: Path to output file.
        compression: The compression method to use.
    """
    compress(stats_file, out_file, compression)


@exporter("Corpus word frequency list with dates", language=["swe"])
def sbx_freq_list_date(
    source_files: AllSourceFilenames = AllSourceFilenames(),
    word: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:word>"),
    token: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>"),
    msd: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:msd>"),
    baseform: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>:stats_export.baseform_first"),
    sense: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>:stats_export.sense_best"),
    lemgram: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>:stats_export.lemgram_first"),
    complemgram: AnnotationAllSourceFiles = AnnotationAllSourceFiles(
                                            "<token>:stats_export.complemgram_best_cond"),
    date: AnnotationAllSourceFiles = AnnotationAllSourceFiles("[dateformat.out_annotation]:dateformat.date_pretty"),
    out: Export = Export("stats_export.frequency_list_sbx_date/stats_[metadata.id].csv"),
    delimiter: str = Config("stats_export.delimiter"),
    cutoff: int = Config("stats_export.cutoff")):
    """Create a word frequency list for the entire corpus.

    Args:
        source_files: The source files belonging to this corpus.
        word: Word annotations.
        token: Token span annotations.
        msd: MSD annotations.
        baseform: Annotations with first baseform from each set.
        sense: Best sense annotations.
        lemgram: Annotations with first lemgram from each set.
        complemgram: Conditional best compound lemgram annotations.
        date: date annotation
        out: The output word frequency file.
        delimiter: Column delimiter to use in the csv.
        cutoff: The minimum frequency a word must have in order to be included in the result.
    """
    annotations = [(word, "token"), (msd, "POS"), (baseform, "lemma"), (sense, "SALDO sense"), (lemgram, "lemgram"),
                   (complemgram, "compound"), (date, "date")]

    freq_list(source_files=source_files, word=word, token=token, annotations=annotations, source_annotations=[],
              out=out, sparv_namespace="", source_namespace="", delimiter=delimiter, cutoff=cutoff)


@exporter("Corpus word frequency list with dates (compressed)", language=["swe"])
def sbx_freq_list_date_compressed(
    stats_file: ExportInput = ExportInput("stats_export.frequency_list_sbx_date/stats_[metadata.id].csv"),
    out_file: Export = Export(
        "stats_export.frequency_list_sbx_date/stats_[metadata.id].csv.[stats_export.compression]"
    ),
    compression: str = Config("stats_export.compression"),
) -> None:
    """Compress statistics file with dates.

    Args:
        stats_file: Path to statistics file.
        out_file: Path to output file.
        compression: The compression method to use.
    """
    compress(stats_file, out_file, compression)


@exporter("Corpus word frequency list (without Swedish annotations)", language=["swe"], order=2)
def sbx_freq_list_simple_swe(
    source_files: AllSourceFilenames = AllSourceFilenames(),
    token: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>"),
    word: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:word>"),
    pos: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:pos>"),
    baseform: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>:stats_export.baseform_first"),
    out: Export = Export("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    delimiter: str = Config("stats_export.delimiter"),
    cutoff: int = Config("stats_export.cutoff")):
    """Create a word frequency list for a corpus without sense, lemgram and complemgram annotations."""
    annotations = [(word, "token"), (pos, "POS"), (baseform, "lemma")]

    freq_list(source_files=source_files, word=word, token=token, annotations=annotations, source_annotations=[],
              out=out, sparv_namespace="", source_namespace="", delimiter=delimiter, cutoff=cutoff)


@exporter("Corpus word frequency list (without Swedish annotations, compressed)", language=["swe"], order=2)
def sbx_freq_list_simple_swe_compressed(
    stats_file: ExportInput = ExportInput("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    out_file: Export = Export("stats_export.frequency_list_sbx/stats_[metadata.id].csv.[stats_export.compression]"),
    compression: str = Config("stats_export.compression"),
) -> None:
    """Compress simple Swedish statistics file.

    Args:
        stats_file: Path to statistics file.
        out_file: Path to output file.
        compression: The compression method to use.
    """
    compress(stats_file, out_file, compression)


@exporter("Corpus word frequency list (without Swedish annotations)", order=3)
def sbx_freq_list_simple(
    source_files: AllSourceFilenames = AllSourceFilenames(),
    token: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>"),
    word: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:word>"),
    pos: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:pos>"),
    baseform: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:baseform>"),
    out: Export = Export("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    delimiter: str = Config("stats_export.delimiter"),
    cutoff: int = Config("stats_export.cutoff")):
    """Create a word frequency list for a corpus without sense, lemgram and complemgram annotations."""
    annotations = [(word, "token"), (pos, "POS"), (baseform, "lemma")]

    freq_list(source_files=source_files, word=word, token=token, annotations=annotations, source_annotations=[],
              out=out, sparv_namespace="", source_namespace="", delimiter=delimiter, cutoff=cutoff)


@exporter("Corpus word frequency list (without Swedish annotations, compressed)", order=3)
def sbx_freq_list_simple_compressed(
    stats_file: ExportInput = ExportInput("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    out_file: Export = Export("stats_export.frequency_list_sbx/stats_[metadata.id].csv.[stats_export.compression]"),
    compression: str = Config("stats_export.compression"),
) -> None:
    """Compress simple statistics file.

    Args:
        stats_file: Path to statistics file.
        out_file: Path to output file.
        compression: The compression method to use.
    """
    compress(stats_file, out_file, compression)


@exporter("Corpus word frequency list for Swedish from the 1800's", language=["swe-1800"], order=4)
def sbx_freq_list_1800(
    source_files: AllSourceFilenames = AllSourceFilenames(),
    word: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:word>"),
    token: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>"),
    msd: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:msd>"),
    baseform: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>:stats_export.baseform_first"),
    sense: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>:hist.sense"),
    lemgram: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>:stats_export.lemgram_first"),
    complemgram: AnnotationAllSourceFiles = AnnotationAllSourceFiles(
                                            "<token>:stats_export.complemgram_best_cond"),
    out: Export = Export("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    delimiter: str = Config("stats_export.delimiter"),
    cutoff: int = Config("stats_export.cutoff")):
    """Create a word frequency list for the entire corpus."""
    annotations = [(word, "token"), (msd, "POS"), (baseform, "lemma"), (sense, "SALDO sense"), (lemgram, "lemgram"),
                   (complemgram, "compound")]

    freq_list(source_files=source_files, word=word, token=token, annotations=annotations, source_annotations=[],
              out=out, sparv_namespace="", source_namespace="", delimiter=delimiter, cutoff=cutoff)


@exporter("Corpus word frequency list for Swedish from the 1800's (compressed)", language=["swe-1800"], order=4)
def sbx_freq_list_1800_compressed(
    stats_file: ExportInput = ExportInput("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    out_file: Export = Export("stats_export.frequency_list_sbx/stats_[metadata.id].csv.[stats_export.compression]"),
    compression: str = Config("stats_export.compression"),
) -> None:
    """Compress 1800's Swedish statistics file.

    Args:
        stats_file: Path to statistics file.
        out_file: Path to output file.
        compression: The compression method to use.
    """
    compress(stats_file, out_file, compression)


@exporter("Corpus word frequency list for Old Swedish (without part-of-speech)", language=["swe-fsv"], order=5)
def sbx_freq_list_fsv(
    source_files: AllSourceFilenames = AllSourceFilenames(),
    token: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token>"),
    word: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:word>"),
    baseform: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:baseform>"),
    lemgram: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:lemgram>"),
    out: Export = Export("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    delimiter: str = Config("stats_export.delimiter"),
    cutoff: int = Config("stats_export.cutoff")):
    """Create a word frequency list for a corpus without sense, lemgram and complemgram annotations."""
    annotations = [(word, "token"), (baseform, "lemma"), (lemgram, "lemgram")]

    freq_list(source_files=source_files, word=word, token=token, annotations=annotations, source_annotations=[],
              out=out, sparv_namespace="", source_namespace="", delimiter=delimiter, cutoff=cutoff)


@exporter(
    "Corpus word frequency list for Old Swedish (without part-of-speech, compressed)", language=["swe-fsv"], order=5
)
def sbx_freq_list_fsv_compressed(
    stats_file: ExportInput = ExportInput("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    out_file: Export = Export("stats_export.frequency_list_sbx/stats_[metadata.id].csv.[stats_export.compression]"),
    compression: str = Config("stats_export.compression"),
) -> None:
    """Compress Old Swedish statistics file.

    Args:
        stats_file: Path to statistics file.
        out_file: Path to output file.
        compression: The compression method to use.
    """
    compress(stats_file, out_file, compression)


@installer("Install SBX word frequency list on remote host", uninstaller="stats_export:uninstall_sbx_freq_list")
def install_sbx_freq_list(
    freq_list: ExportInput = ExportInput("stats_export.frequency_list_sbx/stats_[metadata.id].csv"),
    marker: OutputMarker = OutputMarker("stats_export.install_sbx_freq_list_marker"),
    uninstall_marker: MarkerOptional = MarkerOptional("stats_export.uninstall_sbx_freq_list_marker"),
    host: Optional[str] = Config("stats_export.remote_host"),
    target_dir: Optional[str] = Config("stats_export.remote_dir")
) -> None:
    """Install frequency list on server by rsyncing, or install to an SVN repository.

    Args:
        freq_list: Path to frequency list.
        marker: Output marker.
        uninstall_marker: Uninstall marker.
        host: Remote host.
        target_dir: Remote directory.

    Raises:
        SparvErrorMessage: If neither host nor target directory is specified.
    """
    if not host and not target_dir:
        raise SparvErrorMessage("Either remote host or target directory must be specified.")
    if host and host.startswith("svn+"):
        url = host.rstrip("/") + "/" + Path(freq_list).name
        util.install.install_svn(freq_list, url, remove_existing=True)
    else:
        util.install.install_path(freq_list, host, target_dir)
    uninstall_marker.remove()
    marker.write()


@installer(
    "Install SBX word frequency list on remote host (compressed)",
    uninstaller="stats_export:uninstall_sbx_freq_list_compressed",
)
def install_sbx_freq_list_compressed(
    freq_list: ExportInput = ExportInput(
        "stats_export.frequency_list_sbx/stats_[metadata.id].csv.[stats_export.compression]"
    ),
    marker: OutputMarker = OutputMarker("stats_export.install_sbx_freq_list_compressed_marker"),
    uninstall_marker: MarkerOptional = MarkerOptional("stats_export.uninstall_sbx_freq_list_compressed_marker"),
    host: Optional[str] = Config("stats_export.remote_host"),
    target_dir: Optional[str] = Config("stats_export.remote_dir"),
) -> None:
    """Install compressed frequency list on server by rsyncing, or install to an SVN repository.

    Args:
        freq_list: Path to frequency list.
        marker: Output marker.
        uninstall_marker: Uninstall marker.
        host: Remote host.
        target_dir: Remote directory.

    Raises:
        SparvErrorMessage: If neither host nor target directory is specified.
    """
    if not host and not target_dir:
        raise SparvErrorMessage("Either remote host or target directory must be specified.")
    if host and host.startswith("svn+"):
        url = host.rstrip("/") + "/" + Path(freq_list).name
        util.install.install_svn(freq_list, url, remove_existing=True)
    else:
        util.install.install_path(freq_list, host, target_dir)
    uninstall_marker.remove()
    marker.write()


@installer("Install SBX word frequency list with dates on remote host",
           uninstaller="stats_export:uninstall_sbx_freq_list_date")
def install_sbx_freq_list_date(
    freq_list: ExportInput = ExportInput("stats_export.frequency_list_sbx_date/stats_[metadata.id].csv"),
    marker: OutputMarker = OutputMarker("stats_export.install_sbx_freq_list_date_marker"),
    uninstall_marker: MarkerOptional = MarkerOptional("stats_export.uninstall_sbx_freq_list_date_marker"),
    host: Optional[str] = Config("stats_export.remote_host"),
    target_dir: Optional[str] = Config("stats_export.remote_dir")
) -> None:
    """Install frequency list with dates on server by rsyncing, or install to an SVN repository.

    Args:
        freq_list: Path to frequency list.
        marker: Output marker.
        uninstall_marker: Uninstall marker.
        host: Remote host.
        target_dir: Remote directory.

    Raises:
        SparvErrorMessage: If neither host nor target directory is specified.
    """
    if not host and not target_dir:
        raise SparvErrorMessage("Either remote host or target directory must be specified.")
    if host and host.startswith("svn+"):
        url = host.rstrip("/") + "/" + Path(freq_list).name
        util.install.install_svn(freq_list, url, remove_existing=True)
    else:
        util.install.install_path(freq_list, host, target_dir)
    uninstall_marker.remove()
    marker.write()


@installer(
    "Install SBX word frequency list with dates on remote host (compressed)",
    uninstaller="stats_export:uninstall_sbx_freq_list_date_compressed",
)
def install_sbx_freq_list_date_compressed(
    freq_list: ExportInput = ExportInput(
        "stats_export.frequency_list_sbx_date/stats_[metadata.id].csv.[stats_export.compression]"
    ),
    marker: OutputMarker = OutputMarker("stats_export.install_sbx_freq_list_date_compressed_marker"),
    uninstall_marker: MarkerOptional = MarkerOptional("stats_export.uninstall_sbx_freq_list_date_compressed_marker"),
    host: Optional[str] = Config("stats_export.remote_host"),
    target_dir: Optional[str] = Config("stats_export.remote_dir"),
) -> None:
    """Install compressed frequency list with dates on server by rsyncing, or install to an SVN repository.

    Args:
        freq_list: Path to frequency list.
        marker: Output marker.
        uninstall_marker: Uninstall marker.
        host: Remote host.
        target_dir: Remote directory.

    Raises:
        SparvErrorMessage: If neither host nor target directory is specified.
    """
    if not host and not target_dir:
        raise SparvErrorMessage("Either remote host or target directory must be specified.")
    if host and host.startswith("svn+"):
        url = host.rstrip("/") + "/" + Path(freq_list).name
        util.install.install_svn(freq_list, url, remove_existing=True)
    else:
        util.install.install_path(freq_list, host, target_dir)
    uninstall_marker.remove()
    marker.write()


@uninstaller("Uninstall SBX word frequency list")
def uninstall_sbx_freq_list(
    corpus_id: Corpus = Corpus(),
    marker: OutputMarker = OutputMarker("stats_export.uninstall_sbx_freq_list_marker"),
    install_marker: MarkerOptional = MarkerOptional("stats_export.install_sbx_freq_list_marker"),
    host: Optional[str] = Config("stats_export.remote_host"),
    remote_dir: Optional[str] = Config("stats_export.remote_dir")
) -> None:
    """Uninstall SBX word frequency list.

    Args:
        corpus_id: The corpus ID.
        marker: Output marker.
        install_marker: Install marker.
        host: Remote host.
        remote_dir: Remote directory.

    Raises:
        SparvErrorMessage: If neither host nor remote directory is specified.
    """
    if not host and not remote_dir:
        raise SparvErrorMessage("Either remote host or remote directory must be specified.")

    uninstall_file = f"stats_{corpus_id}.csv"
    if host and host.startswith("svn+"):
        url = host.rstrip("/") + "/" + uninstall_file
        util.install.uninstall_svn(url)
    else:
        remote_dir = remote_dir or ""
        remote_file = Path(remote_dir) / uninstall_file
        logger.info("Removing SBX word frequency file %s%s", host + ":" if host else "", remote_file)
        util.install.uninstall_path(remote_file, host)
    install_marker.remove()
    marker.write()


@uninstaller("Uninstall SBX word frequency list (compressed)")
def uninstall_sbx_freq_list_compressed(
    corpus_id: Corpus = Corpus(),
    marker: OutputMarker = OutputMarker("stats_export.uninstall_sbx_freq_list_compressed_marker"),
    install_marker: MarkerOptional = MarkerOptional("stats_export.install_sbx_freq_list_compressed_marker"),
    host: Optional[str] = Config("stats_export.remote_host"),
    remote_dir: Optional[str] = Config("stats_export.remote_dir"),
    compression: str = Config("stats_export.compression"),
) -> None:
    """Uninstall compressed SBX word frequency list.

    Args:
        corpus_id: The corpus ID.
        marker: Output marker.
        install_marker: Install marker.
        host: Remote host.
        remote_dir: Remote directory.
        compression: The compression method used.

    Raises:
        SparvErrorMessage: If neither host nor remote directory is specified.
    """
    if not host and not remote_dir:
        raise SparvErrorMessage("Either remote host or remote directory must be specified.")

    uninstall_file = f"stats_{corpus_id}.csv.{compression}"
    if host and host.startswith("svn+"):
        url = host.rstrip("/") + "/" + uninstall_file
        util.install.uninstall_svn(url)
    else:
        remote_dir = remote_dir or ""
        remote_file = Path(remote_dir) / uninstall_file
        logger.info("Removing SBX word frequency file %s%s", host + ":" if host else "", remote_file)
        util.install.uninstall_path(remote_file, host)
    install_marker.remove()
    marker.write()


@uninstaller("Uninstall SBX word frequency list with dates")
def uninstall_sbx_freq_list_date(
    corpus_id: Corpus = Corpus(),
    marker: OutputMarker = OutputMarker("stats_export.uninstall_sbx_freq_list_date_marker"),
    install_marker: MarkerOptional = MarkerOptional("stats_export.install_sbx_freq_list_date_marker"),
    host: Optional[str] = Config("stats_export.remote_host"),
    remote_dir: Optional[str] = Config("stats_export.remote_dir")
) -> None:
    """Uninstall SBX word frequency list with dates.

    Args:
        corpus_id: The corpus ID.
        marker: Output marker.
        install_marker: Install marker.
        host: Remote host.
        remote_dir: Remote directory.

    Raises:
        SparvErrorMessage: If neither host nor remote directory is specified.
    """
    if not host and not remote_dir:
        raise SparvErrorMessage("Either remote host or remote directory must be specified.")

    uninstall_file = f"stats_{corpus_id}.csv"
    if host and host.startswith("svn+"):
        url = host.rstrip("/") + "/" + uninstall_file
        util.install.uninstall_svn(url)
    else:
        remote_dir = remote_dir or ""
        remote_file = Path(remote_dir) / uninstall_file
        logger.info("Removing SBX word frequency with dates file %s%s", host + ":" if host else "", remote_file)
        util.install.uninstall_path(remote_file, host)
    install_marker.remove()
    marker.write()


@uninstaller("Uninstall SBX word frequency list with dates (compressed)")
def uninstall_sbx_freq_list_date_compressed(
    corpus_id: Corpus = Corpus(),
    marker: OutputMarker = OutputMarker("stats_export.uninstall_sbx_freq_list_date_compressed_marker"),
    install_marker: MarkerOptional = MarkerOptional("stats_export.install_sbx_freq_list_date_compressed_marker"),
    host: Optional[str] = Config("stats_export.remote_host"),
    remote_dir: Optional[str] = Config("stats_export.remote_dir"),
    compression: str = Config("stats_export.compression"),
) -> None:
    """Uninstall compressed SBX word frequency list with dates.

    Args:
        corpus_id: The corpus ID.
        marker: Output marker.
        install_marker: Install marker.
        host: Remote host.
        remote_dir: Remote directory.
        compression: The compression method used.

    Raises:
        SparvErrorMessage: If neither host nor remote directory is specified.
    """
    if not host and not remote_dir:
        raise SparvErrorMessage("Either remote host or remote directory must be specified.")

    uninstall_file = f"stats_{corpus_id}.csv.{compression}"
    if host and host.startswith("svn+"):
        url = host.rstrip("/") + "/" + uninstall_file
        util.install.uninstall_svn(url)
    else:
        remote_dir = remote_dir or ""
        remote_file = Path(remote_dir) / uninstall_file
        logger.info("Removing SBX word frequency with dates file %s%s", host + ":" if host else "", remote_file)
        util.install.uninstall_path(remote_file, host)
    install_marker.remove()
    marker.write()
