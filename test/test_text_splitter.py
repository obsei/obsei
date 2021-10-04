import pytest

from obsei.preprocessor.text_splitter import TextSplitterConfig
from obsei.payload import TextPayload

DOCUMENT_1 = """I love playing console games."""
DOCUMENT_2 = """Beyoncé Giselle Knowles-Carter (/biːˈjɒnseɪ/ bee-YON-say; born September 4, 1981)[6] is an American singer, songwriter, record producer, and actress. Born and raised in Houston, Texas, Beyoncé performed in various singing and dancing competitions as a child. She rose to fame in the late 1990s as the lead singer of Destiny's Child, one of the best-selling girl groups of all time. Their hiatus saw the release of her first solo album, Dangerously in Love (2003), which featured the US Billboard Hot 100 number-one singles "Crazy in Love" and "Baby Boy". Following the 2006 disbandment of Destiny's Child, she released her second solo album, B'Day, which contained hit singles "Irreplaceable" and "Beautiful Liar". Beyoncé also starred in multiple films such as The Pink Panther (2006), Dreamgirls (2006), Obsessed (2009), and The Lion King (2019). Her marriage to Jay-Z and her portrayal of Etta James in Cadillac Records (2008) influenced her third album, I Am... Sasha Fierce (2008), which earned a record-setting six Grammy Awards in 2010. It spawned the successful singles "If I Were a Boy", "Single Ladies (Put a Ring on It)", and "Halo". After splitting from her manager and father Mathew Knowles in 2010, Beyoncé released her musically diverse fourth album 4 in 2011. She later achieved universal acclaim for her sonically experimental visual albums, Beyoncé (2013) and Lemonade (2016), the latter of which was the world's best-selling album of 2016 and the most acclaimed album of her career, exploring themes of infidelity and womanism. In 2018, she released Everything Is Love, a collaborative album with her husband, Jay-Z, as the Carters. As a featured artist, Beyoncé topped the Billboard Hot 100 with the remixes of "Perfect" by Ed Sheeran in 2017 and "Savage" by Megan Thee Stallion in 2020. The same year, she released the musical film and visual album Black Is King to widespread acclaim."""
DOCUMENT_3 = ''' Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to the natural intelligence displayed by humans or animals. Leading AI textbooks define the field as the study of "intelligent agents": any system that perceives its environment and takes actions that maximize its chance of achieving its goals.[a] Some popular accounts use the term "artificial intelligence" to describe machines that mimic "cognitive" functions that humans associate with the human mind, such as "learning" and "problem solving", however this definition is rejected by major AI researchers.

AI applications include advanced web search engines (i.e. Google), recommendation systems (used by YouTube, Amazon and Netflix), understanding human speech (such as Siri or Alexa), self-driving cars (e.g. Tesla), and competing at the highest level in strategic game systems (such as chess and Go). As machines become increasingly capable, tasks considered to require "intelligence" are often removed from the definition of AI, a phenomenon known as the AI effect. For instance, optical character recognition is frequently excluded from things considered to be AI, having become a routine technology.

Artificial intelligence was founded as an academic discipline in 1956, and in the years since has experienced several waves of optimism, followed by disappointment and the loss of funding (known as an "AI winter"), followed by new approaches, success and renewed funding. AI research has tried and discarded many different approaches during its lifetime, including simulating the brain, modeling human problem solving, formal logic, large databases of knowledge and imitating animal behavior. In the first decades of the 21st century, highly mathematical statistical machine learning has dominated the field, and this technique has proved highly successful, helping to solve many challenging problems throughout industry and academia. 
'''
DOC1_VAL = [29]


@pytest.mark.parametrize(
    "doc, expected_lengths, stride",
    [
        (DOCUMENT_1, DOC1_VAL, 0),
        (DOCUMENT_1, DOC1_VAL, 128),
        (DOCUMENT_2, [503, 512, 504, 384], 0),
        (DOCUMENT_2, [503, 512, 507, 505, 394], 128),
        (DOCUMENT_3, [511, 509, 512, 395], 0),
        (DOCUMENT_3, [511, 512, 512, 512, 402], 128)
    ]
)
def test_char_splits_without_paragraph_honor(doc, expected_lengths, stride, text_splitter):
    doc_splits = text_splitter.preprocess_input(
        input_list=[TextPayload(processed_text=doc)],
        config=TextSplitterConfig(
            max_split_length=512,
            split_stride=stride
        ),
    )

    assert len(expected_lengths) == len(doc_splits)
    for text_payload, expected_length in zip(doc_splits, expected_lengths):
        assert "splitter" in text_payload.meta
        splitter_payload = text_payload.meta["splitter"]
        assert splitter_payload.chunk_length == expected_length


@pytest.mark.parametrize(
    "doc, expected_lengths, stride",
    [
        (DOCUMENT_1, DOC1_VAL, 0),
        (DOCUMENT_1, DOC1_VAL, 10),
        (DOCUMENT_2, [126, 124, 123, 127, 125, 128, 119, 122, 124, 124, 125, 123, 126, 128, 128, 19], 0),
        (DOCUMENT_2, [126, 125, 121, 122, 128, 121, 121, 125, 122, 125, 128, 122, 126, 124, 128, 127, 116], 10),
        (DOCUMENT_3, [123, 124, 128, 118, 94, 128, 121, 115, 128, 103, 126, 127, 124, 125, 125, 104], 0),
        (DOCUMENT_3, [123, 123, 120, 126, 123, 33, 128, 128, 124, 122, 123, 28, 126, 124, 123, 120, 122, 124, 67], 10)
    ]
)
def test_char_splits_with_paragraph_honor(doc, expected_lengths, stride, text_splitter):
    doc_splits = text_splitter.preprocess_input(
        input_list=[TextPayload(processed_text=doc)],
        config=TextSplitterConfig(
            max_split_length=128,
            split_stride=stride,
            honor_paragraph_boundary=True,
        ),
    )

    assert len(expected_lengths) == len(doc_splits)
    for text_payload, expected_length in zip(doc_splits, expected_lengths):
        assert "splitter" in text_payload.meta
        splitter_payload = text_payload.meta["splitter"]
        assert splitter_payload.chunk_length == expected_length


@pytest.mark.parametrize(
    "doc, expected_lengths, stride",
    [
        (DOCUMENT_1, DOC1_VAL, 0),
        (DOCUMENT_1, DOC1_VAL, 10),
        (DOCUMENT_2, [149, 108, 122, 172, 159, 133, 194, 100, 130, 270, 104, 155, 98], 0),
        (DOCUMENT_2, [149, 108, 122, 172, 159, 133, 194, 100, 130, 270, 104, 155, 98], 10),
        (DOCUMENT_3, [142, 184, 264, 57, 146, 92, 165, 135, 271, 220, 241], 0),
        (DOCUMENT_3, [142, 184, 264, 57, 146, 92, 165, 135, 271, 220, 241], 10)
    ]
)
def test_sentence_splits(doc, expected_lengths, stride, text_splitter):
    doc_splits = text_splitter.preprocess_input(
        input_list=[TextPayload(processed_text=doc)],
        config=TextSplitterConfig(
            max_split_length=512,
            split_stride=stride,
            enable_sentence_split=True,
        ),
    )

    assert len(expected_lengths) == len(doc_splits)
    for text_payload, expected_length in zip(doc_splits, expected_lengths):
        assert "splitter" in text_payload.meta
        splitter_payload = text_payload.meta["splitter"]
        assert splitter_payload.chunk_length == expected_length
