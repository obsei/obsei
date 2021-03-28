import logging, sys
from obsei.analyzer.base_analyzer import AnalyzerRequest
from obsei.analyzer.translation_analyzer import TranslationAnalyzerConfig

GOOD_TEXT = '''मुझे सब चीजे बहुत अच्छि लगी ।'''

BAD_TEXT = '''यह जीवन का सबसे बुरा अनुभव था । खराब कारें, नकद में भुगतान करने के लिए कह रहे हैं, पर्याप्त ईंधन नहीं है,
एसी न खोलें, मेरे स्थान से बहुत दूर तक प्रतीक्षा करें जब तक कि यात्रा रद्द न हो जाए, कॉल करें और गंतव्य के बारे में पूछें, फिर रद्द करें, और बहुत कुछ।सबसे खराब सेवा। '''
MIXED_TEXT = '''ठीक ठाक सेवा थी । बहुत कुछ खास नहीं ।'''
EMOTICONS_TEXT = '''Sab kuch theek hai ✌✌✌✌✌☝☝☝☝☝👌👌👌👌👌👌👍👍👍👍👍📿📿📿🛍🛍🕶🕳🕳👁🗨🗯👁‍🗨🖖👉✋💟👍😊'''
HINGLISH_TEXT = '''mera naam joker, tera naam kya ?'''

TEXTS = [GOOD_TEXT, BAD_TEXT, MIXED_TEXT, EMOTICONS_TEXT, HINGLISH_TEXT]

# logging.StreamHandler.terminator = ''
# logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def test_translate_analyzer(translate_analyzer):
    source_responses = [AnalyzerRequest(processed_text=text, source_name="sample") for text in TEXTS]
    analyzer_responses = translate_analyzer.analyze_input(
        source_response_list=source_responses,
        analyzer_config=TranslationAnalyzerConfig()
    )
    assert len(analyzer_responses) == len(TEXTS)

    logger.info("Result:")
    for analyzer_response in analyzer_responses:
        # print(analyzer_response)
        logger.info(analyzer_response)
