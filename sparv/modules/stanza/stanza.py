"""POS tagging, lemmatisation and dependency parsing with Stanza."""

from typing import Optional

from sparv.api import Annotation, Config, Language, Model, Output, Text, annotator, get_logger, util
from sparv.core.language_registry import LanguageRegistry
from . import stanza_utils

logger = get_logger(__name__)


@annotator("POS, lemma and dependency relations from Stanza", language=["eng"])
def annotate(corpus_text: Text = Text(),
             lang: Language = Language(),
             sentence_chunk: Optional[Annotation] = Annotation("[stanza.sentence_chunk]"),
             sentence_annotation: Optional[Annotation] = Annotation("[stanza.sentence_annotation]"),
             token_annotation: Optional[Annotation] = Annotation("[stanza.token_annotation]"),
             out_sentence: Optional[Output] = Output("stanza.sentence", cls="sentence",
                                                     description="Sentence segments"),
             out_token: Output = Output("stanza.token", cls="token", description="Token segments"),
             out_upos: Output = Output("<token>:stanza.upos", cls="token:upos", description="Part-of-speeches in UD"),
             out_pos: Output = Output("<token>:stanza.pos", cls="token:pos",
                                      description="Part-of-speeches from Stanza"),
             out_baseform: Output = Output("<token>:stanza.baseform", cls="token:baseform",
                                           description="Baseform from Stanza"),
             out_feats: Output = Output("<token>:stanza.ufeats", cls="token:ufeats",
                                        description="Universal morphological features"),
             out_deprel: Output = Output("<token>:stanza.deprel", cls="token:deprel",
                                         description="Dependency relations to the head"),
             out_dephead_ref: Output = Output("<token>:stanza.dephead_ref", cls="token:dephead_ref",
                                              description="Sentence-relative positions of the dependency heads"),
             out_dephead: Output = Output("<token>:stanza.dephead", cls="token:dephead",
                                          description="Positions of the dependency heads"),
             out_ne: Output = Output("stanza.ne", cls="named_entity", description="Named entity segments from Stanza"),
             out_ne_type: Output = Output("stanza.ne:stanza.ne_type", cls="token:named_entity_type",
                                          description="Named entitiy types from Stanza"),
             resources_file: Model = Model("[stanza.resources_file]"),
             use_gpu: bool = Config("stanza.use_gpu"),
             batch_size: int = Config("stanza.batch_size"),
             max_sentence_length: int = Config("stanza.max_sentence_length"),
             cpu_fallback: bool = Config("stanza.cpu_fallback")):
    """Do dependency parsing using Stanza."""
    from stanza.pipeline.core import DownloadMethod

    # cpu_fallback only makes sense if use_gpu is True
    cpu_fallback = cpu_fallback and use_gpu

    # Read corpus_text and text_spans
    text_data = corpus_text.read()

    # Define some values needed for Stanza Pipeline
    nlp_args = {
        "lang": LanguageRegistry.get_language_part1_by_part3(lang),
        "processors": "tokenize,mwt,pos,lemma,depparse,ner",  # Comma-separated list of processors to use
        "dir": str(resources_file.path.parent),
        "depparse_max_sentence_size": 200,  # Create new batch when encountering sentences larger than this
        "depparse_batch_size": batch_size,
        "pos_batch_size": batch_size,
        "lemma_batch_size": batch_size,
        "use_gpu": use_gpu,
        "verbose": False,
        "download_method": DownloadMethod.NONE
    }
    stanza_args = {
        "use_gpu": use_gpu,
        "batch_size": batch_size,
        "max_sentence_length": max_sentence_length,
    }

    write_tokens = True

    if token_annotation:
        write_tokens = False
        sentences, _orphans = sentence_annotation.get_children(token_annotation)
        # sentences.append(orphans)
        token_spans = list(token_annotation.read())
        sentence_segments, all_tokens, ne_segments, ne_types = process_tokens(sentences, token_spans, text_data,
                                                                              nlp_args, stanza_args)
    elif sentence_annotation:
        sentence_spans = list(sentence_annotation.read_spans())
        sentence_segments, all_tokens, ne_segments, ne_types = process_sentences(sentence_spans, text_data, nlp_args,
                                                                                 stanza_args)
    else:
        text_spans = sentence_chunk.read_spans()
        sentence_segments, all_tokens, ne_segments, ne_types = process_text(text_spans, text_data, nlp_args,
                                                                            stanza_args)

    # Write annotations
    if all_tokens:
        if write_tokens:
            out_token.write([(t.start, t.end) for t in all_tokens])
        else:
            out_token.write([])
        out_upos.write([t.upos for t in all_tokens])
        out_pos.write([t.pos for t in all_tokens])
        out_baseform.write([t.baseform for t in all_tokens])
        out_feats.write([t.feats for t in all_tokens])
        out_deprel.write([t.deprel for t in all_tokens])
        out_dephead_ref.write([t.dephead_ref for t in all_tokens])
        out_dephead.write([t.dephead for t in all_tokens])
    # TODO: Sparv does not support optional outputs yet, so always write these, even if they're empty
    out_sentence.write(sentence_segments)
    out_ne.write(ne_segments)
    out_ne_type.write(ne_types)


def process_tokens(sentences, token_spans, text_data, nlp_args, stanza_args):
    """Process pre-tokenized text with Stanza."""
    import stanza

    # Init Stanza pipeline
    nlp_args["tokenize_pretokenized"] = True
    nlp = stanza.Pipeline(**nlp_args)

    # Format document for stanza: list of lists of string
    document = [[text_data[token_spans[i][0][0]:token_spans[i][1][0]] for i in s] for s in sentences]

    # Run Stanza and process output
    doc = stanza_utils.run_stanza(nlp, document, stanza_args["batch_size"], stanza_args["max_sentence_length"])
    all_tokens = []
    ne_segments = []
    ne_types = []
    token_dephead_count = 0
    token_positions = []

    stanza_utils.check_sentence_respect(len(list(s for s in sentences if s)), len(doc.sentences))
    for sent_span, tagged_sent in zip(sentences, doc.sentences):
        current_sentence_len = 0
        for w_index, tagged_w in zip(sent_span, tagged_sent.words):
            token = Token(tagged_w, offset=0, token_dephead_count=token_dephead_count)
            all_tokens.append(token)
            current_sentence_len += 1
            token_positions.append((token.start, token.end, token_spans[w_index][0][0], token_spans[w_index][1][0]))
        token_dephead_count += current_sentence_len
        stanza_utils.check_token_respect(len(sent_span), len(tagged_sent.words))

    # Get named entities
    token_positions = iter(token_positions)
    stanza_end = -1
    for entity in doc.entities:
        # Get positions for NE spans
        if entity.start_char > stanza_end:
            for stanza_start, stanza_end, start, end in token_positions:
                if stanza_start <= entity.start_char < stanza_end:
                    sparv_start = start
                if stanza_start < entity.end_char <= stanza_end:
                    sparv_end = end
                    break
        ne_segments.append((sparv_start, sparv_end))
        ne_types.append(entity.type)

    return [], all_tokens, ne_segments, ne_types


def process_sentences(sentence_spans, text_data, nlp_args, stanza_args):
    """Process pre-sentence segmented text with Stanza."""
    import stanza

    # Init Stanza pipeline
    nlp_args["tokenize_no_ssplit"] = True
    nlp = stanza.Pipeline(**nlp_args)

    # Format document for stanza: separate sentences by double new lines
    document = "\n\n".join([text_data[sent_span[0]:sent_span[1]].replace("\n", " ") for sent_span in sentence_spans])

    # Run Stanza and process output
    doc = stanza_utils.run_stanza(nlp, document, stanza_args["batch_size"], stanza_args["max_sentence_length"])
    all_tokens = []
    ne_segments = []
    ne_types = []
    token_dephead_count = 0
    offset = 0
    sentence_offsets = []
    previous_sentence_end_position = -2

    stanza_utils.check_sentence_respect(len(sentence_spans), len(doc.sentences))
    for sent_span, tagged_sent in zip(sentence_spans, doc.sentences):
        # Calculate the difference between the positions in the document and the ones from Stanza.
        # -2 is to compensate for two line breaks between sentences in the Stanza input
        offset += sent_span[0] - previous_sentence_end_position - 2
        current_sentence_len = 0
        for w in tagged_sent.words:
            token = Token(w, offset=offset, token_dephead_count=token_dephead_count)
            current_sentence_len += 1
            all_tokens.append(token)
        sentence_offsets.append((previous_sentence_end_position, token.end - offset, offset))
        previous_sentence_end_position = token.end
        token_dephead_count += current_sentence_len

    # Get named entities
    sentence_offsets = iter(sentence_offsets)
    end = -1
    for entity in doc.entities:
        # Calculate positions for NE spans
        if entity.start_char > end:
            for start, end, offs in sentence_offsets:
                if start <= entity.start_char < end:
                    break
        ne_segments.append((entity.start_char + offs, entity.end_char + offs))
        ne_types.append(entity.type)

    return [], all_tokens, ne_segments, ne_types


def process_text(text_spans, text_data, nlp_args, stanza_args):
    """Process text with Stanza (including sentence segmentation)."""
    import stanza

    # Init Stanza pipeline
    nlp = stanza.Pipeline(**nlp_args)

    sentence_segments = []
    all_tokens = []
    token_dephead_count = 0
    ne_segments = []
    ne_types = []

    # Run Stanza once for every input document
    for text_span in text_spans:
        inputtext = text_data[text_span[0]:text_span[1]]
        offset = text_span[0]
        doc = stanza_utils.run_stanza(nlp, inputtext, stanza_args["batch_size"], stanza_args["max_sentence_length"])
        for sent in doc.sentences:
            current_sentence = []
            for w in sent.words:
                token = Token(w, offset=offset, token_dephead_count=token_dephead_count)
                current_sentence.append(token)
                all_tokens.append(token)
            token_dephead_count += len(current_sentence)
            sentence_segments.append((current_sentence[0].start, current_sentence[-1].end))
        # Get named entities
        for entity in doc.entities:
            ne_segments.append((entity.start_char + offset, entity.end_char + offset))
            ne_types.append(entity.type)

    return sentence_segments, all_tokens, ne_segments, ne_types


class Token:
    """Object to store annotation information for a token."""

    def __init__(self, stanza_w, offset=0, token_dephead_count=0):
        """Set attributes."""
        self.word = stanza_w.text  # Mostly used for debugging
        self.start = int(stanza_w.misc.split("|")[0].strip("start_char=")) + offset
        self.end = int(stanza_w.misc.split("|")[1].strip("end_char=")) + offset
        self.upos = stanza_w.upos
        self.pos = stanza_w.xpos
        self.baseform = stanza_w.lemma
        # Format feats
        feats_list = util.misc.set_to_list(stanza_w.feats or "")
        if not feats_list:
            feats_str = "_"
        else:
            feats_str = "|".join(feats_list)
        self.feats = feats_str
        self.dephead_ref = str(stanza_w.head) if stanza_w.head > 0 else ""
        self.deprel = stanza_w.deprel
        self.dephead = str(stanza_w.head - 1 + token_dephead_count) if stanza_w.head > 0 else "-"

    def __repr__(self):
        return f"{self.word} <{self.baseform} {self.upos} {self.deprel}> ({self.start}-{self.end})"
