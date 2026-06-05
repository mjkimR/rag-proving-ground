# from llama_index.core import SummaryIndex, Document
#
#
# class LlamaIndexSummarizer:
#     def __init__(self, llm):
#         self.llm = llm
#
#     def summarize(self, full_text: str) -> str:
#         doc = Document(text=full_text)
#         index = SummaryIndex.from_documents([doc])
#         query_engine = index.as_query_engine(
#             llm=self.llm,
#             response_mode="tree_summarize",
#             use_async=True
#         )
#         response = query_engine.query("Summarize ...")
#         return str(response)
