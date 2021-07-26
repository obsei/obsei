from obsei.payload import TextPayload

GOOD_TEXT = """मुझे सब चीजे बहुत अच्छी लगी ।"""

BAD_TEXT = """यह जीवन का सबसे बुरा अनुभव था । खराब कारें, नकद में भुगतान करने के लिए कह रहे हैं, पर्याप्त ईंधन नहीं है,
एसी न खोलें, मेरे स्थान से बहुत दूर तक प्रतीक्षा करें जब तक कि यात्रा रद्द न हो जाए, कॉल करें और गंतव्य के बारे में पूछें, फिर रद्द करें, और बहुत कुछ।सबसे खराब सेवा। """
MIXED_TEXT = """ठीक ठाक सेवा थी । बहुत कुछ खास नहीं ।"""
EMOTICONS_TEXT = """Sab kuch theek hai ✌✌✌✌✌☝☝☝☝☝👌👌👌👌👌👌👍👍👍👍👍📿📿📿🛍🛍🕶🕳🕳👁🗨🗯👁‍🗨🖖👉✋💟👍😊"""
HINGLISH_TEXT = """mera naam joker, tera naam kya ?"""

TEXTS = [GOOD_TEXT, BAD_TEXT, MIXED_TEXT, EMOTICONS_TEXT, HINGLISH_TEXT]

# for running in offline mode - https://huggingface.co/transformers/installation.html#offline-mode


def test_translate_analyzer(translate_analyzer):
    source_responses = [
        TextPayload(processed_text=text, source_name="sample") for text in TEXTS
    ]
    analyzer_responses = translate_analyzer.analyze_input(
        source_response_list=source_responses,
    )
    assert len(analyzer_responses) == len(TEXTS)

    for text, analyzer_response in zip(TEXTS, analyzer_responses):
        assert analyzer_response.segmented_data is not None
        assert analyzer_response.segmented_data["translation_data"] is not None
        assert text == analyzer_response.segmented_data["translation_data"]["original_text"]
        assert text != analyzer_response.processed_text
