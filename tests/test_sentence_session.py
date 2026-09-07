import unittest

from dolls_orchestrator.sentence import SentenceSplitter
from dolls_orchestrator.session import ConversationStore


class SentenceSplitterTests(unittest.TestCase):
    def test_streamed_chinese_sentences_keep_order(self):
        splitter = SentenceSplitter(max_chars=20)
        self.assertEqual([], splitter.feed("你好呀"))
        self.assertEqual(["你好呀！"], splitter.feed("！今天"))
        self.assertEqual(["今天好吗？"], splitter.feed("好吗？还有"))
        self.assertEqual(["还有"], splitter.finish())

    def test_long_unpunctuated_text_uses_fallback(self):
        splitter = SentenceSplitter(max_chars=6)
        self.assertEqual(["一二三四五六"], splitter.feed("一二三四五六七"))
        self.assertEqual(["七"], splitter.finish())


class ConversationStoreTests(unittest.TestCase):
    def test_context_keeps_complete_bounded_turns(self):
        store = ConversationStore(max_turns=2)
        store.commit("s", "u1", "a1")
        store.commit("s", "u2", "a2")
        store.commit("s", "u3", "a3")
        self.assertEqual(2, store.turn_count("s"))
        self.assertEqual(
            [
                {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"},
                {"role": "user", "content": "u3"},
                {"role": "assistant", "content": "a3"},
            ],
            store.messages("s"),
        )


if __name__ == "__main__":
    unittest.main()

