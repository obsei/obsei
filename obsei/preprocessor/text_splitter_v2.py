import logging
from typing import Any, List, Optional
import uuid

from obsei.payload import TextPayload
from obsei.preprocessor.base_preprocessor import (
    BaseTextPreprocessor,
    BaseTextProcessorConfig,
)

from tokenizers.pre_tokenizers import BertPreTokenizer
from tokenizers.models import WordPiece

logger = logging.getLogger(__name__)


class TextSplitterConfig(BaseTextProcessorConfig):
    max_split_length: int = 512
    split_stride: Optional[int] = 0  # overlap length
    generate_document_id: Optional[bool] = True

    def __init__(self, **data):
        super().__init__(**data)


class TextSplitter(BaseTextPreprocessor):
    def preprocess_input(
        self, input_list: List[TextPayload], config: TextSplitterConfig, **kwargs
    ) -> List[TextPayload]:
        splits = []
        document_id = 0
        pre_tokenizer = BertPreTokenizer()
        max_token_threshold = 0.7
        max_ = int(config.max_split_length * max_token_threshold)
        for input_data in input_list:
            pretokenized = list(
                pre_tokenizer.pre_tokenize_str(input_data.processed_text)
            )
            if config.generate_document_id:
                document_id = uuid.uuid4().int
            start_idx = 0
            split_id = 0
            start_idx_pre = 0
            document_length = len(pretokenized)
            while start_idx_pre < document_length:
                end_idx_pre = min(document_length, start_idx_pre + max_) - 1
                end_idx = pretokenized[end_idx_pre][1][1]
                phrase = input_data.processed_text[start_idx:end_idx]
                splits.append(
                    self._build_payload(phrase, start_idx, split_id, document_id)
                )
                start_idx = end_idx + 1
                start_idx_pre = end_idx_pre + 1
                split_id += 1

        return splits

    def _build_payload(self, phrase, start_idx, split_id, document_id=0):
        text_payload = TextPayload(processed_text=phrase)
        text_payload.segmented_data = phrase
        text_payload.meta = {
            "text": phrase,
            "paragraph_id": split_id,
            "text_length": len(phrase),
            "start_index": start_idx,  # start position of split in document
            "document_id": document_id,
        }

        return text_payload


if __name__ == '__main__':
    text_splitter = TextSplitter()
    DOCUMENT_1 = """I love playing console games."""
    DOCUMENT_2 = """Beyoncé Giselle Knowles-Carter (/biːˈjɒnseɪ/ bee-YON-say; born September 4, 1981)[6] is an American singer, songwriter, record producer, and actress. Born and raised in Houston, Texas, Beyoncé performed in various singing and dancing competitions as a child. She rose to fame in the late 1990s as the lead singer of Destiny's Child, one of the best-selling girl groups of all time. Their hiatus saw the release of her first solo album, Dangerously in Love (2003), which featured the US Billboard Hot 100 number-one singles "Crazy in Love" and "Baby Boy". Following the 2006 disbandment of Destiny's Child, she released her second solo album, B'Day, which contained hit singles "Irreplaceable" and "Beautiful Liar". Beyoncé also starred in multiple films such as The Pink Panther (2006), Dreamgirls (2006), Obsessed (2009), and The Lion King (2019). Her marriage to Jay-Z and her portrayal of Etta James in Cadillac Records (2008) influenced her third album, I Am... Sasha Fierce (2008), which earned a record-setting six Grammy Awards in 2010. It spawned the successful singles "If I Were a Boy", "Single Ladies (Put a Ring on It)", and "Halo". After splitting from her manager and father Mathew Knowles in 2010, Beyoncé released her musically diverse fourth album 4 in 2011. She later achieved universal acclaim for her sonically experimental visual albums, Beyoncé (2013) and Lemonade (2016), the latter of which was the world's best-selling album of 2016 and the most acclaimed album of her career, exploring themes of infidelity and womanism. In 2018, she released Everything Is Love, a collaborative album with her husband, Jay-Z, as the Carters. As a featured artist, Beyoncé topped the Billboard Hot 100 with the remixes of "Perfect" by Ed Sheeran in 2017 and "Savage" by Megan Thee Stallion in 2020. The same year, she released the musical film and visual album Black Is King to widespread acclaim."""
    doc1_splits = text_splitter.preprocess_input(
        input_list=[TextPayload(processed_text=DOCUMENT_2)],
        config=TextSplitterConfig(max_split_length=512),
    )
    x = 1
