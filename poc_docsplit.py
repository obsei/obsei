class TextPhrase(object):
    def __init__(self, text, split_id, split_length, overlap_length = 0, ):
        self.metadata = {
            "text" : text,
            "paragraph_id" : split_id,
            "split_length" : split_length,
            "overlap_length" : overlap_length
        }
        self.text  = text
        self.paragraph_id = split_id

    def __repr__(self):
        return 'TextPhrase(text="' + str(self.text) + '" , paragraph_id=' + str(self.paragraph_id) + ')'

class TextSplitter():
    def __init__(self, text, max_length, split_stride = 0):
        self.document = text
        self.max_length = max_length
        self.stride = split_stride
        self.splits : list = []
        self.token_starts = []
        self.split_document()

    def __repr__(self):
        return  'Document(splits=' + str(self.splits) + ')'

    def split_document(self):
        start_idx = 0
        split_id = 0

        while(start_idx < len(self.document)):
            if self.stride:
                start_idx = self._valid_index(start_idx- self.stride)
            end_idx = self._valid_index(min(start_idx + self.max_length, len(self.document)))
            phrase = self.document[start_idx : end_idx]
            start_idx= end_idx + 1
            self.splits.append(TextPhrase(phrase, split_id, len(phrase), self.stride))
            split_id +=1

    def _valid_index(self, end_id):
        if end_id<=0 or end_id == len(self.document):
            return end_id

        idx = end_id
        while(idx>0):
            if self.document[idx] in [' ', '\n','\t']:
                break
            idx-=1
        return idx

    def text_to_id(self):
        return

    def id_to_text(self):
        return


if __name__ == '__main__':
    document = "I am a gooood boy"
    document2 = '''Beyoncé Giselle Knowles-Carter (/biːˈjɒnseɪ/ bee-YON-say; born September 4, 1981)[6] is an American singer, songwriter, record producer, and actress. Born and raised in Houston, Texas, Beyoncé performed in various singing and dancing competitions as a child. She rose to fame in the late 1990s as the lead singer of Destiny's Child, one of the best-selling girl groups of all time. Their hiatus saw the release of her first solo album, Dangerously in Love (2003), which featured the US Billboard Hot 100 number-one singles "Crazy in Love" and "Baby Boy". Following the 2006 disbandment of Destiny's Child, she released her second solo album, B'Day, which contained hit singles "Irreplaceable" and "Beautiful Liar". Beyoncé also starred in multiple films such as The Pink Panther (2006), Dreamgirls (2006), Obsessed (2009), and The Lion King (2019). Her marriage to Jay-Z and her portrayal of Etta James in Cadillac Records (2008) influenced her third album, I Am... Sasha Fierce (2008), which earned a record-setting six Grammy Awards in 2010. It spawned the successful singles "If I Were a Boy", "Single Ladies (Put a Ring on It)", and "Halo". After splitting from her manager and father Mathew Knowles in 2010, Beyoncé released her musically diverse fourth album 4 in 2011. She later achieved universal acclaim for her sonically experimental visual albums, Beyoncé (2013) and Lemonade (2016), the latter of which was the world's best-selling album of 2016 and the most acclaimed album of her career, exploring themes of infidelity and womanism. In 2018, she released Everything Is Love, a collaborative album with her husband, Jay-Z, as the Carters. As a featured artist, Beyoncé topped the Billboard Hot 100 with the remixes of "Perfect" by Ed Sheeran in 2017 and "Savage" by Megan Thee Stallion in 2020. The same year, she released the musical film and visual album Black Is King to widespread acclaim.'''
    x = TextSplitter(document, 512)
    z = TextSplitter(document2, 512)
    y = 1




