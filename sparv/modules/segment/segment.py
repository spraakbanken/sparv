"""Segmentation mostly based on NLTK."""

import logging
import pickle
import re
from typing import Optional

import nltk

import sparv.util as util
from sparv import Annotation, Config, Model, ModelOutput, Output, Text, annotator, modelbuilder
from sparv.modules.saldo.saldo_model import split_triple

try:
    from . import crf  # for CRF++ models
except ImportError:
    pass

log = logging.getLogger(__name__)


@annotator("Automatic tokenization", config=[
    Config("segment.token_segmenter", default="better_word"),
    Config("segment.token_chunk", default="<sentence>"),
    Config("segment.existing_tokens"),
    Config("segment.tokenizer_config", default="segment/bettertokenizer.sv"),
    Config("segment.token_list", default="segment/bettertokenizer.sv.saldo-tokens")
])
def tokenize(text: Text = Text(),
             out: Output = Output("segment.token", cls="token", description="Token segments"),
             chunk: Annotation = Annotation("[segment.token_chunk]"),
             segmenter: str = Config("segment.token_segmenter"),
             existing_segments: str = Config("segment.existing_tokens"),
             model: Optional[Model] = Model("[segment.tokenizer_config]"),
             token_list: Optional[Model] = Model("[segment.token_list]")):
    """Tokenize text."""
    do_segmentation(text=text, out=out, chunk=chunk, segmenter=segmenter, existing_segments=existing_segments,
                    model=model, token_list=token_list)


@annotator("Automatic segmentation of sentences", config=[
    Config("segment.sentence_segmenter", default="punkt_sentence"),
    Config("segment.sentence_chunk", default="<text>"),
    Config("segment.existing_sentences"),
    Config("segment.sentence_model", default="segment/punkt-nltk-svenska.pickle")
])
def sentence(text: Text = Text(),
             out: Output = Output("segment.sentence", cls="sentence", description="Sentence segments"),
             chunk: Optional[Annotation] = Annotation("[segment.sentence_chunk]"),
             segmenter: str = Config("segment.sentence_segmenter"),
             existing_segments: str = Config("segment.existing_sentences"),
             model: Optional[Model] = Model("[segment.sentence_model]")):
    """Split text into sentences."""
    do_segmentation(text=text, out=out, chunk=chunk, segmenter=segmenter, existing_segments=existing_segments,
                    model=model)


@annotator("Automatic segmentation of paragraphs", config=[
    Config("segment.paragraph_segmenter", default="blanklines"),
    Config("segment.paragraph_chunk", default="<text>"),
    Config("segment.existing_paragraphs")
])
def paragraph(text: Text = Text(),
              out: Output = Output("segment.paragraph", cls="paragraph", description="Paragraph segments"),
              chunk: Optional[Annotation] = Annotation("[segment.paragraph_chunk]"),
              segmenter: str = Config("segment.paragraph_segmenter"),
              existing_segments: str = Config("segment.existing_paragraphs"),
              model: Optional[Model] = None):
    """Split text into paragraphs."""
    do_segmentation(text=text, out=out, chunk=chunk, segmenter=segmenter, existing_segments=existing_segments,
                    model=model)


def do_segmentation(text: Text, out: Output, segmenter, chunk: Optional[Annotation] = None, existing_segments=None,
                    model: Optional[Model] = None, token_list: Optional[Model] = None):
    """Segment all chunks (e.g. sentences) into smaller "tokens" (e.g. words), and annotate them as "element" (e.g. w).

    Segmentation is done by the given "segmenter"; some segmenters take
    an extra argument which is a pickled "model" object.
    """
    segmenter_args = []
    if model:
        if model.path.suffix in ["pickle", "pkl"]:
            with open(model, "rb") as M:
                model_arg = pickle.load(M, encoding="UTF-8")
        else:
            model_arg = str(model.path)
        segmenter_args.append(model_arg)
    assert segmenter in SEGMENTERS, "Available segmenters: %s" % ", ".join(sorted(SEGMENTERS))
    segmenter = SEGMENTERS[segmenter]
    segmenter = segmenter(*segmenter_args)
    assert hasattr(segmenter, "span_tokenize"), "Segmenter needs a 'span_tokenize' method: %r" % segmenter

    corpus_text = text.read()

    # First we read the chunks and partition the text into spans
    # E.g., "one two <s>three four</s> five <s>six</s>"
    #   ==> ["one two ", "three four", " five ", "six"]
    #   (but using spans (pairs of anchors) instead of strings)

    positions = set()
    chunk_spans = chunk.read_spans() if chunk else []
    positions = positions.union(set(pos for span in chunk_spans for pos in span))
    positions = sorted({0, len(corpus_text)} | positions)
    chunk_spans = list(zip(positions, positions[1:]))

    if existing_segments:
        segments = list(existing_segments.read_spans())
        for n, (chunk_start, chunk_end) in enumerate(chunk_spans[:]):
            for segment_start, segment_end in segments:
                if segment_end <= chunk_start:
                    continue
                if segment_start >= chunk_end:
                    break
                if chunk_start != segment_start:
                    chunk_spans.append((chunk_start, segment_start))
                chunk_start = segment_end
                chunk_spans[n] = (chunk_start, chunk_end)
        chunk_spans.sort()
        log.info("Reorganized into %d chunks" % len(chunk_spans))
    else:
        segments = []

    # Now we can segment each chunk span into tokens
    for start, end in chunk_spans:
        for spanstart, spanend in segmenter.span_tokenize(corpus_text[start:end]):
            spanstart += start
            spanend += start
            if corpus_text[spanstart:spanend].strip():
                span = (spanstart, spanend)
                segments.append(span)

    segments.sort()
    out.write(segments)


@modelbuilder("Model for PunktSentenceTokenizer", language=["swe"])
def download_punkt_model(out: ModelOutput = ModelOutput("segment/punkt-nltk-svenska.pickle")):
    """Download model for use with PunktSentenceTokenizer."""
    out.download("https://github.com/spraakbanken/sparv-models/raw/master/segment/punkt-nltk-svenska.pickle")


@modelbuilder("Model for BetterWordTokenizer", language=["swe"])
def download_bettertokenizer(out: ModelOutput = ModelOutput("segment/bettertokenizer.sv")):
    """Download model for use with BetterWordTokenizer."""
    out.download("https://github.com/spraakbanken/sparv-models/raw/master/segment/bettertokenizer.sv")


@modelbuilder("Token list for BetterWordTokenizer", language=["swe"])
def build_tokenlist(saldo_model: Model = Model("saldo/saldo.pickle"),
                    out: ModelOutput = ModelOutput("segment/bettertokenizer.sv.saldo-tokens"),
                    segmenter: str = Config("segment.token_wordlist_segmenter", "better_word"),
                    model: Model = Model("segment/bettertokenizer.sv")):
    """Build a list of words from a SALDO model, to help BetterWordTokenizer."""
    segmenter_args = []
    if model:
        if model.path.suffix in ["pickle", "pkl"]:
            with open(model, "rb") as m:
                model_arg = pickle.load(m)
        else:
            model_arg = model.path
        segmenter_args.append(model_arg)
    assert segmenter in SEGMENTERS, "Available segmenters: %s" % ", ".join(sorted(SEGMENTERS))
    segmenter = SEGMENTERS[segmenter]
    segmenter = segmenter(*segmenter_args)
    assert hasattr(segmenter, "span_tokenize"), "Segmenter needs a 'span_tokenize' method: %r" % segmenter

    wordforms = set()

    # Skip strings already handled by the tokenizer.
    # Also skip words ending in comma (used by some multi word expressions in SALDO).
    with open(saldo_model.path, "rb") as F:
        lexicon = pickle.load(F)
        for w in lexicon:
            w2 = list(map(split_triple, lexicon[w]))
            mwu_extras = [contw for w3 in w2 for cont in w3[2] for contw in cont if contw not in lexicon]
            for wf in mwu_extras + [w]:
                spans = list(segmenter.span_tokenize(wf))
                if len(spans) > 1 and not wf.endswith(","):
                    wordforms.add(wf)

    out.write("\n".join(sorted(wordforms)))


######################################################################

def train_punkt_segmenter(textfiles, modelfile, encoding=util.UTF8, protocol=-1):
    """Train a Punkt sentence tokenizer."""
    if isinstance(textfiles, str):
        textfiles = textfiles.split()

    log.info("Reading files")
    text = u""
    for filename in textfiles:
        with open(filename) as stream:
            text += stream.read().decode(encoding)
    log.info("Training model")
    trainer = nltk.tokenize.PunktTrainer(text, verbose=True)
    log.info("Saving pickled model")
    params = trainer.get_params()
    with open(modelfile, "wb") as stream:
        pickle.dump(params, stream, protocol=protocol)
    log.info("OK")


######################################################################

class LinebreakTokenizer(nltk.RegexpTokenizer):
    """Tokenizer that separates tokens by line breaks (based on NLTK's RegexpTokenizer)."""

    def __init__(self):
        """Initialize class."""
        nltk.RegexpTokenizer.__init__(self, r"\s*\n\s*", gaps=True)


class PunctuationTokenizer(nltk.RegexpTokenizer):
    """A very simple sentence tokenizer, separating sentences on every .!? no matter the context.

    Use only when PunktSentenceTokenizer does not work, for example when there's no whitespace after punctuation.
    """

    def __init__(self):
        """Initialize class."""
        nltk.RegexpTokenizer.__init__(self, r"[\.!\?]\s*", gaps=True)

    def span_tokenize(self, s):
        """Tokenize s and return list with tokens."""
        result = []
        spans = nltk.RegexpTokenizer.span_tokenize(self, s)
        first = True
        temp = [0, 0]

        for start, _ in spans:
            if not first:
                temp[1] = start
                result.append(tuple(temp))
            temp[0] = start
            first = False

        temp[1] = len(s)
        result.append(tuple(temp))

        return result


class BetterWordTokenizer:
    """A word tokenizer based on the PunktWordTokenizer code.

    Heavily modified to add support for custom regular expressions, wordlists, and external configuration files.
    http://nltk.googlecode.com/svn/trunk/doc/api/nltk.tokenize.punkt.PunktSentenceTokenizer-class.html
    """

    # Format for the complete regular expression to be used for tokenization
    _word_tokenize_fmt = r'''(
        %(misc)s
        |
        %(multi)s
        |
        (?:(?:(?<=^)|(?<=\s))%(number)s(?=\s|$))  # Numbers with decimal mark
        |
        (?=[^%(start)s])
        (?:%(tokens)s%(abbrevs)s(?<=\s)(?:[^\.\s]+\.){2,}|\S+?)  # Accept word characters until end is found
        (?= # Sequences marking a word's end
            \s|                                 # White-space
            $|                                  # End-of-string
            (?:[%(within)s])|%(multi)s|         # Punctuation
            [%(end)s](?=$|\s|(?:[%(within)s])|%(multi)s)  # Misc characters if at end of word
        )
        |
        \S
    )'''

    # Used to realign punctuation that should be included in a sentence although it follows the period (or ?, !).
    re_boundary_realignment = re.compile(r'[“”"\')\]}]+?(?:\s+|(?=--)|$)', re.MULTILINE)

    re_punctuated_token = re.compile(r"\w.*\.$", re.UNICODE)

    def __init__(self, model, token_list=None):
        """Parse configuration file (model) and token_list (if supplied)."""
        self.case_sensitive = False
        self.patterns = {"misc": [], "tokens": []}
        self.abbreviations = set()
        in_abbr = False

        if token_list:
            with open(token_list, encoding="UTF-8") as saldotokens:
                self.patterns["tokens"] = [re.escape(t.strip()) for t in saldotokens.readlines()]

        with open(model, encoding="UTF-8") as conf:
            for line in conf:
                if line.startswith("#") or not line.strip():
                    continue
                if not in_abbr:
                    if not in_abbr and line.strip() == "abbreviations:":
                        in_abbr = True
                        continue
                    else:
                        try:
                            key, val = line.strip().split(None, 1)
                        except ValueError as e:
                            log.error("Error parsing configuration file: %s", line)
                            raise e
                        key = key[:-1]

                        if key == "case_sensitive":
                            self.case_sensitive = (val.lower() == "true")
                        elif key.startswith("misc_"):
                            self.patterns["misc"].append(val)
                        elif key in ("start", "within", "end"):
                            self.patterns[key] = re.escape(val)
                        elif key in ("multi", "number"):
                            self.patterns[key] = val
                        # For backwards compatibility
                        elif key == "token_list":
                            pass
                        else:
                            raise ValueError("Unknown option: %s" % key)
                else:
                    self.abbreviations.add(line.strip())

    def _word_tokenizer_re(self):
        """Compile and return a regular expression for word tokenization."""
        try:
            return self._re_word_tokenizer
        except AttributeError:
            modifiers = (re.UNICODE | re.VERBOSE) if self.case_sensitive else (re.UNICODE | re.VERBOSE | re.IGNORECASE)
            self._re_word_tokenizer = re.compile(
                self._word_tokenize_fmt %
                {
                    "tokens": ("(?:" + "|".join(self.patterns["tokens"]) + ")|") if self.patterns["tokens"] else "",
                    "abbrevs": ("(?:" + "|".join(re.escape(a + ".") for a in self.abbreviations) + ")|") if self.abbreviations else "",
                    "misc": "|".join(self.patterns["misc"]),
                    "number": self.patterns["number"],
                    "within": self.patterns["within"],
                    "multi": self.patterns["multi"],
                    "start": self.patterns["start"],
                    "end": self.patterns["end"]
                },
                modifiers
            )
            return self._re_word_tokenizer

    def word_tokenize(self, s):
        """Tokenize a string to split off punctuation other than periods."""
        words = self._word_tokenizer_re().findall(s)
        if not words:
            return words
        pos = len(words) - 1

        # Split sentence-final . from the final word.
        # i.e., "peter." "piper." ")" => "peter." "piper" "." ")"
        # but not "t.ex." => "t.ex" "."
        while pos >= 0 and self.re_boundary_realignment.match(words[pos]):
            pos -= 1
        endword = words[pos]
        if self.re_punctuated_token.search(endword):
            endword = endword[:-1]
            if endword not in self.abbreviations:
                words[pos] = endword
                words.insert(pos + 1, ".")

        return words

    def span_tokenize(self, s):
        """Tokenize s."""
        begin = 0
        for w in self.word_tokenize(s):
            begin = s.find(w, begin)
            yield begin, begin + len(w)
            begin += len(w)


class CRFTokenizer:
    """Tokenization based on Conditional Random Fields.

    Implemented for Old Swedish, see crf.py for more details.
    """

    def __init__(self, model):
        """Initialize class."""
        self.model = model

    def span_tokenize(self, s):
        """Tokenize s and return list with tokens."""
        return crf.segment(s, self.model)


class FSVParagraphSplitter:
    """A paragraph splitter for old Swedish."""

    def __init__(self):
        """Initialize class."""
        pass

    def span_tokenize(self, s):
        """Tokenize s and return list with tokens."""
        spans = []
        temp = [0, 0]
        first = True
        for i in range(len(s)):
            if not first:
                new_para = re.search(r"^\.*§", s[i:])
                if new_para:
                    spans.append((temp[0], i))
                    temp[0] = i
                    first = True
            else:
                first = False
            temp[1] = i

        temp[1] = len(s)
        spans.append(tuple(temp))

        return spans


######################################################################

SEGMENTERS = dict(whitespace=nltk.WhitespaceTokenizer,
                  linebreaks=LinebreakTokenizer,
                  blanklines=nltk.BlanklineTokenizer,
                  punkt_sentence=nltk.PunktSentenceTokenizer,
                  punctuation=PunctuationTokenizer,
                  better_word=BetterWordTokenizer,
                  crf_tokenizer=CRFTokenizer,
                  simple_word_punkt=nltk.WordPunctTokenizer,
                  fsv_paragraph=FSVParagraphSplitter
                  )

if not do_segmentation.__doc__:
    do_segmentation.__doc__ = ""
do_segmentation.__doc__ += "The following segmenters are available: %s" % ", ".join(sorted(SEGMENTERS))
