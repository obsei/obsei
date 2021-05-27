import logging
from typing import Any, Dict, List, Optional
import string
import re
from unicodedata import normalize as unicode_decode

import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize

from pydantic import PrivateAttr

from obsei.analyzer.base_analyzer import AnalyzerRequest
from obsei.preprocessor.base_text_cleaner import (
    BaseTextCleaner,
    BaseTextCleanerConfig,
)

logger = logging.getLogger(__name__)
nltk.download('punkt')


class TextCleaner(BaseTextCleaner):

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.stop_words: List = stopwords.words('english')
        self.stemmer = PorterStemmer()
        

    def clean_input(
        self,
        input_list: List[AnalyzerRequest],
        config: BaseTextCleanerConfig,
        **kwargs
    ) -> List[AnalyzerRequest]:
        text_cleaning_functions: List = config.text_cleaning_functions or self.get_text_cleaning_functions()
        for index, input in enumerate(input_list):
            tokens: List[str] = self.tokenize_text(input.processed_text)
            for text_cleaning_function in text_cleaning_functions:
                print(tokens)
                tokens = text_cleaning_function(tokens)
            input_list[index] = " ".join(tokens)
        
        return input_list
    
    def tokenize_text(self, text: str) -> List[str]:
        """
        Transforms text string to words using NLTK's tokenizer
        """
        return word_tokenize(text)

    def to_lower_case(self, tokens: List[str]) -> List[str]:
        """
        Transforms string tokens to lower case
        """
        return [token.lower() for token in tokens]
    
    def remove_stop_words(self, tokens: List[str]) -> List[str]:
        """
        Removes words that don't add any meaning to the sequence
        """
        return [token for token in tokens if token not in self.stop_words] 
    
    def remove_punctuation(self, tokens: List[str]) -> List[str]:
        """
        Removes punctuations from each token
        """
        return [token.translate(token.maketrans('', '', string.punctuation)) for token in tokens if len(token.translate(token.maketrans('', '', string.punctuation)))] 

    def stem_text(self, tokens: List[str]) -> List[str]:
        """
        Transforms tokens to standardized form
        """
        return [self.stemmer.stem(token) for token in tokens]  
    
    def remove_white_space(self, tokens: List[str]) -> List[str]:
        """
        Transforms string tokens to lower case
        """
        return [token.strip() for token in tokens if len(token.strip())]   
    
    def remove_special_characters(self, tokens: List[str]) -> List[str]:
        """
        Removes special characters by eliminating all characters from each token
        and only retains alphabetic, numeric or alphanumeric tokens by stripping 
        special characters from them
        """
        return [re.sub('[^A-Za-z0-9]+', '', token) for token in tokens]

    def decode_unicode(self, tokens: List[str]) -> List[str]:
        """
        Converts unicodes to ASCII characters
        """
        return [unicode_decode('NFKD', token).encode('ascii', 'ignore').decode("utf-8")   for token in tokens]
    
    def get_text_cleaning_functions(self):
        text_cleaning_functions= [ 
        self.to_lower_case,
        self.remove_white_space,
        self.remove_punctuation,
        self.remove_special_characters,
        self.decode_unicode,
        self.stem_text, 
        self.remove_stop_words
    ]
        return text_cleaning_functions
