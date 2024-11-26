import os
from typing import Any, List

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.embeddings import BaseEmbedding

from transformers import AutoTokenizer 
from optimum.rbln import RBLNXLMRobertaModel


class RBLNBGEM3Embeddings(BaseEmbedding):
    _model: RBLNXLMRobertaModel = PrivateAttr()

    def __init__(
        self,
        rbln_compiled_model_name: str = "bge-m3",
        **kwargs: Any,
        ) -> None:
        super().__init__(**kwargs)
        # TODO: implement batch size > 1
        self.embed_batch_size = 1
        
        self._model = RBLNXLMRobertaModel.from_pretrained(
            model_id=os.path.join("models", os.path.basename(rbln_compiled_model_name)),
            export=False,
        )
        self._tokenizer = AutoTokenizer.from_pretrained(rbln_compiled_model_name)

    @classmethod
    def class_name(cls) -> str:
        return "rbln_bge_m3"

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)

    def _get_query_embedding(self, query: str) -> List[float]:
        input = self._tokenizer(query, padding="max_length", return_tensors="pt", max_length=8192)
        result = self._model(input.input_ids, input.attention_mask)[0][:,0]
        return result.tolist()[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        input = self._tokenizer(text, padding="max_length", return_tensors="pt", max_length=8192)
        result = self._model(input.input_ids, input.attention_mask)[0][:,0]
        return result.tolist()[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        # TODO: Hard coded to assume that batch size is 1!
        # This has to be fixed at some point...
        input = self._tokenizer(texts[0], padding="max_length", return_tensors="pt", max_length=8192)
        result = self._model(input.input_ids, input.attention_mask)[0][:,0]
        return result.tolist()
